from __future__ import annotations
import logging
import json
from typing import Any, TypedDict
from langgraph.graph import END, START, StateGraph
from nodes.preprocess import build_preprocess_node
from nodes.reason import build_reason_node
from nodes.search import build_search_node
from nodes.select import build_select_node
from nodes.adapt import build_adapt_node
from nodes.evaluate import build_evaluate_node
from nodes.feedback import build_feedback_node
from nodes.modify import build_modify_node


# =============================================================================
# graph.py — Define the agent graph: state, nodes, and edges.
#
# This is the main file you edit to change how the agent works.
# - AgentState  : the data that flows through the graph
# - build_graph : wires nodes and edges together
# - run_agent   : called from main.py; builds and runs the graph once
# =============================================================================

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# State — the data that every node can read and write.
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    user_prompt: str                               # NEW - the raw use message prompt
    iteration: int                                 # current tool-call count
    max_iterations: int                            # safety cap to stop the process (set from .env)
    final_response: str | None                     # set when the agent is done
    #-----------jsons for tools-----------
    layout_json_string: str                        # current layout as a JSON string, injected into tool calls 
    input_layout_json_string: str | None           # NEW - input layout, defining outline, as a JSON string, injected into tool calls 
    topology_graph_json_string: str | None         # NEW - topology graph for search, as a JSON string
    evaluation_json_string: str | None             # NEW - evaluation results
    search_results_json_string: str | None         # NEW - {id, score, description} only
    tried_layout_ids: list[str]                    # NEW - keep track of which layout IDs we've tried adapting
    #-----------results from nodes (for routing)-----------
    preprocess_result: str                         # NEW - which node to go to after preprocess: "search" | "select" | "modify" | "evaluate" | "reason" | "end"
    search_result: str                             # NEW - which node to go to after search: "success" | "failed"
    select_result: str                             # NEW - which node to go to after select: "success" | "failed"
    adapt_result: str | None                       # NEW - result from adapt node: "success" | "failed"
    
    # REMOVED: messages, pending_tool_calls, tool_catalog
        
# ---------------------------------------------------------------------------
# Routing — decides which node runs next.
# ---------------------------------------------------------------------------
def _route_after_preprocessing(state: AgentState) -> str:
    result = state.get("preprocess_result")
    return {
        "search": "search",
        "select": "select",
        "modify": "modify",
        "evaluate": "evaluate",
        "reason": "reason",
        "end": "end",
    }.get(result, "end")

def _route_after_search(state: AgentState) -> str:
    result = state.get("search_result")
    return {
        "success": "select",     # Found a candidate, go to select
        "failed": "feedback"     # No candidates found, ask the user
    }.get(result, "feedback")
    
def _route_after_select(state: AgentState) -> str:
    result = state.get("select_result")
    return {
        "success": "adapt",      # Candidate selected, go to adapt
        "failed": "feedback"     # Id does not exist / No more candidates, ask the user
    }.get(result, "feedback")
    
def _route_after_adapt(state: AgentState) -> str:
    result = state.get("adapt_result")
    return {
        "success": "evaluate",
        "failed": "select",      # Adapt failed, try next candidate
    }.get(result, "select")

# ---------------------------------------------------------------------------
# Graph wiring — add nodes and edges here.
# ---------------------------------------------------------------------------

def build_graph(ctx: Any) -> Any:
    """Build the layout agent graph."""
    reason = build_reason_node(ctx.llm)
    preprocess = build_preprocess_node()
    search = build_search_node()
    select = build_select_node(ctx.llm)
    adapt = build_adapt_node(ctx.mcp_client)
    evaluate = build_evaluate_node(ctx.mcp_client)
    feedback = build_feedback_node(ctx.llm)
    modify = build_modify_node(ctx.mcp_client)
    
    # Wrap nodes to log entry/exit
    def make_logged_node(node_fn, node_name):
        def logged_wrapper(state):
            logger.info(f"▶️  Entering node: {node_name}")
            try:
                result = node_fn(state)
                logger.info(f"✅ {node_name} completed")
                return result
            except Exception as e:
                logger.error(f"❌ {node_name} failed: {str(e)}", exc_info=True)
                raise
        return logged_wrapper
    
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("reason", make_logged_node(reason, "reason"))
    workflow.add_node("preprocess", make_logged_node(preprocess, "preprocess"))
    workflow.add_node("search", make_logged_node(search, "search"))
    workflow.add_node("select", make_logged_node(select, "select"))
    workflow.add_node("adapt", make_logged_node(adapt, "adapt"))
    workflow.add_node("evaluate", make_logged_node(evaluate, "evaluate"))
    workflow.add_node("feedback", make_logged_node(feedback, "feedback"))
    workflow.add_node("modify", make_logged_node(modify, "modify"))
    
    workflow.add_edge(START, "preprocess")
    
    # Add edges
    workflow.add_conditional_edges("preprocess", _route_after_preprocessing, {
        "reason": "reason",
        "select": "select",
        "evaluate": "evaluate",
        "search": "search",
        "modify": "modify",
        "end": END
    })
    workflow.add_edge("reason", "preprocess")
    workflow.add_conditional_edges("search", _route_after_search, {
        "select": "select",
        "feedback": "feedback"
    })
    workflow.add_conditional_edges("select", _route_after_select, {
        "adapt": "adapt",
         "feedback": "feedback"
    })
    workflow.add_conditional_edges("adapt", _route_after_adapt, {
        "evaluate": "evaluate",
         "feedback": "feedback"
    })
    workflow.add_edge("evaluate", "feedback")
    workflow.add_edge("feedback", "preprocess")
    workflow.add_edge("modify", "adapt")
    
    return workflow.compile()


# ---------------------------------------------------------------------------
# Entry point — called from main.py.
# ---------------------------------------------------------------------------

def run_agent(prompt: str, ctx: Any, session: dict | None = None) -> tuple[str, dict]:
    if session is None:
        session = {}
    
    logger.info(f"🚀 Analyzing your prompt...")
    
    app = build_graph(ctx)
    initial_state = _build_initial_state(prompt, ctx, session)
    final_state = app.invoke(initial_state)
    
    # Optional: log the entire graph at the end for debugging
    #logger.info("\nWorkflow graph (Mermaid):")
    #logger.info(app.get_graph().draw_mermaid())

    final_response = final_state.get("final_response")
    if final_response is None:
        logger.error(f"❌ Agent finished without final_response!")
        raise RuntimeError("Agent finished without setting final_response")
    
    logger.info(f"✅ Done")
    
    # Return response + updated session for next turn
    updated_session = {
        "layout_json_string": final_state.get("layout_json_string"),
        "topology_graph_json_string": final_state.get("topology_graph_json_string"),
        "search_results_json_string": final_state.get("search_results_json_string"),
    }
    
    return final_response, updated_session


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_initial_state(prompt: str, ctx: Any, session: dict | None = None) -> AgentState:
    """Initialize state with priority: session → edited → reference → input layout."""
    if session is None:
        session = {}

    layout_json = session.get("layout_json_string")

    # If not in session, try loading from files
    if not layout_json:
        # Priority 1: edited_layout
        if hasattr(ctx, 'edited_layout_path') and ctx.edited_layout_path:
            try:
                with open(ctx.edited_layout_path, 'r') as f:
                    layout_json = json.dumps(json.load(f))
            except:
                pass

        # Priority 2: reference_layout
        if not layout_json and hasattr(ctx, 'reference_layout_path') and ctx.reference_layout_path:
            try:
                with open(ctx.reference_layout_path, 'r') as f:
                    layout_json = json.dumps(json.load(f))
            except:
                pass

        # Priority 3: input_layout
        if not layout_json and hasattr(ctx, 'input_layout_path') and ctx.input_layout_path:
            try:
                with open(ctx.input_layout_path, 'r') as f:
                    layout_json = json.dumps(json.load(f))
            except:
                pass

        # Fallback
        if not layout_json:
            layout_json = json.dumps(ctx.layout_data, indent=2)

    # Always load input_layout separately
    input_layout_json = None
    if hasattr(ctx, 'input_layout_path') and ctx.input_layout_path:
        try:
            with open(ctx.input_layout_path, 'r') as f:
                input_layout_json = json.dumps(json.load(f))
        except:
            pass

    # --- Add tried_layout_ids initialization here ---
    tried_layout_ids = session.get("tried_layout_ids", [])

    return {
        "user_prompt": prompt,
        "layout_json_string": layout_json,
        "input_layout_json_string": input_layout_json,
        "evaluation_json_string": None,
        "search_results_json_string": session.get("search_results_json_string"),  # Carry over
        "preprocess_result": None,
        "search_result": None,
        "select_result": None,
        "adapt_result": None,
        "topology_graph_json_string": session.get("topology_graph_json_string"),  # Carry over
        "iteration": 0,
        "max_iterations": ctx.max_iterations,
        "final_response": None,
        "tried_layout_ids": tried_layout_ids,  # <-- Ensure this is always present!
    }