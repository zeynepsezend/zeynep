"""
graph.py — Phase 3 agent graph: state, nodes, edges, and routing.

This is the main file to edit when changing how the agent works.
- AgentState        : all data flowing between nodes
- build_graph       : wires every node and edge together
- run_agent         : called from main.py; builds and runs the graph once
"""

from __future__ import annotations
import json
from typing import Annotated, Any, TypedDict
from langgraph.graph.message import add_messages

from langgraph.graph import END, START, StateGraph

from nodes.reason import build_reason_node
from nodes.tools import build_tool_node
from nodes.add_objects import build_add_objects_node
from nodes.visibility import build_visibility_node
from nodes.path_analysis import build_path_node
from nodes.reachability import build_reachability_node
from nodes.orientation import build_orientation_node
from nodes.collision import build_collision_node
from nodes.scoring import build_scoring_node
from nodes.profile_agent import build_profile_agent_node
from nodes.space_type_agent import build_space_type_agent_node
from nodes.query_agent import build_query_agent_node
from nodes.checkpoint import build_user_checkpoint_node
from nodes.explain import explain_node
from nodes.output import output_node
from nodes.fan_out import analysis_fan_out_node, group1_join_node
from _runtime.utils import _slim_layout, _format_tool_catalog


# ---------------------------------------------------------------------------
# Reducer for parallel node writes.
# When Group 1 nodes (collision, visibility, orientation) run in parallel they
# all return state updates simultaneously. LangGraph requires a reducer for any
# field that more than one parallel branch writes; without one it raises
# InvalidUpdateError. _keep_last takes the last non-None value so a node that
# doesn't touch a field (returns None) never clobbers a sibling's result.
# ---------------------------------------------------------------------------

def _keep_last(a, b):
    return b if b is not None else a


# ---------------------------------------------------------------------------
# State — the data every node can read and write.
# Keys are grouped by concern so it is easy to trace which nodes own each field.
# Fields written by parallel branches are Annotated with _keep_last.
# Fields written only by a single node stay as plain TypedDict fields.
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    # Core conversation — add_messages merges appended entries rather than
    # replacing the whole list; required because parallel nodes all append.
    messages:            Annotated[list[dict[str, Any]], add_messages]

    # Every node increments iteration and may write pending_tool_calls or
    # final_response — _keep_last prevents InvalidUpdateError from parallel writes.
    pending_tool_calls:  Annotated[list[dict[str, Any]] | None, _keep_last]
    iteration:           Annotated[int,                         _keep_last]
    final_response:      Annotated[str | None,                  _keep_last]

    # Plain fields — written only once at startup, never by parallel branches.
    max_iterations:      int
    tool_catalog:        str

    # Layout and session paths — layout_json_string is updated by add_objects
    # and tools nodes after placements; needs _keep_last so updates propagate.
    layout_json_string:  Annotated[str, _keep_last]
    workspace_path:      str
    layout_name:         str
    _llm:                Any

    # Pre-agent outputs — written by sequential pre-agents; _keep_last guards
    # against the unlikely case a retry or graph change writes them in parallel.
    space_config:        Annotated[dict[str, Any] | None, _keep_last]
    profile_config:      Annotated[dict[str, Any] | None, _keep_last]

    # Object placement — reason sets these, add_objects clears them.
    object_to_place:       Annotated[dict[str, Any] | None, _keep_last]
    object_queue:          Annotated[list[dict] | None,     _keep_last]
    last_placement_result: Annotated[dict[str, Any] | None, _keep_last]

    # Analysis results — collision/visibility/orientation run in parallel;
    # path/reachability are sequential but annotated for future-safety.
    collision_results:    Annotated[dict[str, Any] | None, _keep_last]
    visibility_results:   Annotated[list | None,           _keep_last]
    orientation_results:  Annotated[dict[str, Any] | None, _keep_last]
    path_results:         Annotated[dict[str, Any] | None, _keep_last]
    reachability_results: Annotated[dict[str, Any] | None, _keep_last]

    # Scoring and control — each written by a single node but annotated
    # defensively so any future parallelisation doesn't silently corrupt state.
    scoring_results:     Annotated[dict[str, Any] | None, _keep_last]
    evaluation_passed:   Annotated[bool | None,           _keep_last]
    user_approved:       Annotated[bool | None,           _keep_last]

    # Adjustment loop counter — prevents infinite loops when collision/reachability
    # violations persist despite object placement attempts. After max adjustments
    # the graph continues to scoring regardless.
    adjustment_count:    Annotated[int, _keep_last]

    # Placement history — list of dicts describing each furniture move.
    # Populated by add_objects, displayed by user_checkpoint before approval.
    placement_history:   Annotated[list[dict] | None, _keep_last]

    # Previous scoring — snapshot of scoring_results from the last checkpoint
    # visit, used to show before/after score comparison with deltas.
    previous_scoring:    Annotated[dict[str, Any] | None, _keep_last]

    # Original layout snapshot — used to detect if doors/windows/structure
    # were modified or lost during the pipeline.
    original_layout:     dict | None

    # Query mode flag — set by reason node when user asks to analyze without placing.
    # Routes to query_agent instead of analysis_fan_out.
    _query_mode:         Annotated[bool | None, _keep_last]


# ---------------------------------------------------------------------------
# Routing functions — pure state reads, no side effects.
# Each returns a string that matches a key in the conditional_edges map.
# ---------------------------------------------------------------------------

def _route_after_reason(state: AgentState) -> str:
    # Reason node sets exactly one of these fields to signal what should happen next.
    # object_to_place takes priority: place the object before running any analysis.
    if state.get("object_to_place"):
        return "add_objects"
    if state.get("_query_mode"):
        return "query_agent"
    # final_response means the LLM is done reasoning — move to analysis pipeline.
    # Empty string "" is treated as "cleared" (not finished); only a real
    # non-empty string triggers the finish route.
    fr = state.get("final_response")
    if fr is not None and fr != "":
        return "finish"
    # Default: a tool call was queued; execute it then return to reason.
    return "run_tool"


MAX_ADJUSTMENTS = 3  # Max times the graph loops back to reason for collision/reachability fixes


def _route_after_group1(state: AgentState) -> str:
    # Group 1 = collision + visibility + orientation.
    # Hard violations mean the layout is physically impassable — route back
    # to reason immediately rather than wasting time on path checks.
    # BUT: only loop back if (a) the agent placed objects, and (b) we haven't
    # exceeded the max adjustment attempts. Otherwise continue to scoring.
    adj = state.get("adjustment_count", 0)
    collision = state.get("collision_results")
    if collision and not collision.get("pass", True):
        hard = collision.get("summary", {}).get("hard_violations", 0)
        if hard > 0 and state.get("last_placement_result") is not None and adj < MAX_ADJUSTMENTS:
            print(f"[router] Hard collision violations — adjustment {adj + 1}/{MAX_ADJUSTMENTS}")
            return "adjust"
    return "continue"


def _route_after_group2(state: AgentState) -> str:
    # Group 2 = path + reachability.
    # Same logic with max adjustment limit.
    has_placed = state.get("last_placement_result") is not None
    adj = state.get("adjustment_count", 0)

    if has_placed and adj < MAX_ADJUSTMENTS:
        path = state.get("path_results")
        if path:
            pairs = path.get("pairs", [])
            unreachable = [p for p in pairs if p.get("status") == "unreachable"]
            if pairs and len(unreachable) > len(pairs) * 0.3:
                print(f"[router] Path violations — adjustment {adj + 1}/{MAX_ADJUSTMENTS}")
                return "adjust"

        reach = state.get("reachability_results")
        if reach:
            summary = reach.get("summary", {})
            total    = summary.get("total", 0)
            reachable = summary.get("reachable", 0)
            if total > 0 and reachable / total < 0.7:
                print(f"[router] Reachability violations — adjustment {adj + 1}/{MAX_ADJUSTMENTS}")
                return "adjust"

    return "continue"


def _route_after_checkpoint(state: AgentState) -> str:
    # User either approves the layout (write output and end) or requests more
    # changes (loop back to reason with their new instructions).
    if state.get("user_approved"):
        return "approved"
    if state.get("_query_mode") is False and not state.get("placement_history"):
        return "query_done"
    return "continue"


# ---------------------------------------------------------------------------
# analysis_fan_out_node, group1_join_node → nodes/fan_out.py
# build_user_checkpoint_node             → nodes/checkpoint.py
# explain_node                           → nodes/explain.py
# output_node                            → nodes/output.py
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Graph wiring — build all nodes, then wire edges and conditional routes.
# ---------------------------------------------------------------------------

def build_graph(ctx: Any) -> Any:
    # Build every node from its factory function.
    # Factories receive the dependencies they need (LLM, MCP client, paths)
    # and return a plain callable that accepts and returns AgentState.
    profile_agent    = build_profile_agent_node(ctx.llm, ctx.knowledge_dir)
    space_type_agent = build_space_type_agent_node(ctx.llm, ctx.knowledge_dir)
    query_agent      = build_query_agent_node(ctx.mcp_client)

    def query_end_node(state):
        print("\n[query_agent] Analysis complete — no changes saved.")
        return {}

    reason           = build_reason_node(ctx.llm)
    tool             = build_tool_node(ctx.mcp_client, ctx.tools, ctx.workspace_path)
    add_objects      = build_add_objects_node(ctx.mcp_client, ctx.workspace_path)
    visibility       = build_visibility_node(ctx.mcp_client)
    path             = build_path_node(ctx.mcp_client)
    reachability     = build_reachability_node(ctx.mcp_client)
    orientation      = build_orientation_node(ctx.mcp_client)
    collision        = build_collision_node(ctx.mcp_client, ctx.workspace_path)
    scoring          = build_scoring_node()
    user_checkpoint  = build_user_checkpoint_node(ctx.mcp_client)

    graph = StateGraph(AgentState)

    # Register every node so it can be referenced by name in edge wiring.
    graph.add_node("profile_agent",    profile_agent)
    graph.add_node("space_type_agent", space_type_agent)
    graph.add_node("query_agent",      query_agent)
    graph.add_node("query_end",        query_end_node)
    graph.add_node("reason",           reason)
    graph.add_node("tool",             tool)
    graph.add_node("add_objects",      add_objects)
    graph.add_node("analysis_fan_out", analysis_fan_out_node)
    graph.add_node("visibility",       visibility)
    graph.add_node("path",             path)
    graph.add_node("reachability",     reachability)
    graph.add_node("orientation",      orientation)
    graph.add_node("collision",        collision)
    graph.add_node("group1_join",      group1_join_node)
    graph.add_node("scoring",          scoring)
    graph.add_node("user_checkpoint",  user_checkpoint)
    graph.add_node("explain",          explain_node)
    graph.add_node("output",           output_node)

    # Pre-agents run sequentially once at startup to classify the layout type
    # and resolve the user accessibility profile before the LLM sees anything.
    graph.add_edge(START, "profile_agent")
    graph.add_edge("profile_agent", "space_type_agent")
    graph.add_edge("space_type_agent", "reason")

    # Reason routes to: place an object, execute a tool, or move to analysis.
    # "finish" goes to analysis_fan_out which triggers all Group 1 nodes in parallel.
    graph.add_conditional_edges(
        "reason", _route_after_reason,
        {
            "add_objects":  "add_objects",
            "query_agent":  "query_agent",
            "run_tool":     "tool",
            "finish":       "analysis_fan_out",
        },
    )

    # Tool result is fed back to reason so the LLM can interpret it.
    graph.add_edge("tool", "reason")

    # Query agent bypasses placement pipeline — goes to a no-save terminal.
    graph.add_edge("query_agent", "user_checkpoint")
    graph.add_edge("query_end",   END)

    # After a placement, go through the same analysis fan-out node
    # so both paths (placement and direct finish) trigger the same parallel group.
    graph.add_edge("add_objects", "analysis_fan_out")

    # analysis_fan_out fans out to all three Group 1 nodes in parallel.
    graph.add_edge("analysis_fan_out", "collision")
    graph.add_edge("analysis_fan_out", "visibility")
    graph.add_edge("analysis_fan_out", "orientation")

    # Group 1 convergence: all three feed into group1_join so LangGraph
    # waits for all of them before evaluating collision results.
    graph.add_edge("collision",   "group1_join")
    graph.add_edge("visibility",  "group1_join")
    graph.add_edge("orientation", "group1_join")

    # group1_join checks collision results — hard violations route back to reason.
    graph.add_conditional_edges(
        "group1_join", _route_after_group1,
        {"adjust": "reason", "continue": "path"},
    )

    # Group 2: path then reachability; poor connectivity sends back to reason.
    graph.add_edge("path", "reachability")
    graph.add_conditional_edges(
        "reachability", _route_after_group2,
        {"adjust": "reason", "continue": "scoring"},
    )

    # Scoring aggregates all results and triggers the human approval step.
    graph.add_edge("scoring", "user_checkpoint")

    # User checkpoint: approve → explain → output; otherwise loop back for changes.
    graph.add_conditional_edges(
        "user_checkpoint", _route_after_checkpoint,
        {"approved": "explain", "continue": "reason", "query_done": "query_end"},
    )

    # Explain runs once after approval; output writes the file and ends the session.
    graph.add_edge("explain", "output")
    graph.add_edge("output", END)

    return graph.compile()


# ---------------------------------------------------------------------------
# Entry point — called from main.py.
# ---------------------------------------------------------------------------

def run_agent(prompt: str, ctx: Any) -> str:
    app = build_graph(ctx)
    initial_state = _build_initial_state(prompt, ctx)

    # Print the graph topology before running so the wiring is visible
    # in the terminal output before any node executes.
    print("\nWorkflow graph:")
    app.get_graph().print_ascii()
    print()

    final_state = app.invoke(initial_state)

    final_response = final_state.get("final_response")
    if not isinstance(final_response, str):
        raise RuntimeError("Agent finished without final response")
    return final_response


# ---------------------------------------------------------------------------
# Helpers — _slim_layout and _format_tool_catalog live in _runtime/utils.py
# ---------------------------------------------------------------------------

def _build_initial_state(prompt: str, ctx: Any) -> AgentState:
    # The user message embeds a slim version of the layout JSON to keep the
    # LLM context lean. But layout_json_string stores the FULL layout because
    # MCP tools (collision-detector-grid, visualize_visibility) need all fields
    # (outline, structure, mep) that _slim_layout strips.
    slim = _slim_layout(ctx.layout_data)
    layout_text = json.dumps(slim, indent=2)
    user_message = (
        f"Space config will be determined by Space Type Agent.\n"
        f"Profile config will be determined by Profile Agent.\n\n"
        f"User request:\n{prompt}\n\n"
        f"Current layout JSON:\n{layout_text}"
    )
    return {
        "messages":              [{"role": "user", "content": user_message}],
        "pending_tool_calls":    None,
        "final_response":        None,
        "iteration":             0,
        "max_iterations":        ctx.max_iterations,
        "tool_catalog":          _format_tool_catalog(ctx.tools),
        "layout_json_string":    json.dumps(ctx.layout_data),
        "workspace_path":        str(ctx.workspace_path),
        "layout_name":           ctx.layout_name,
        "space_config":          None,
        "profile_config":        None,
        "object_to_place":       None,
        "object_queue":          [],
        "last_placement_result": None,
        "visibility_results":    None,
        "path_results":          None,
        "reachability_results":  None,
        "orientation_results":   None,
        "collision_results":     None,
        "scoring_results":       None,
        "evaluation_passed":     None,
        "user_approved":         None,
        "adjustment_count":      0,
        "placement_history":     None,
        "previous_scoring":      None,
        "original_layout":       ctx.layout_data,
        "_llm":                  ctx.llm,
        "_query_mode":           None,
    }


