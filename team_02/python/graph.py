"""
graph.py — Comfort Copilot state graph.

Architecture:

  START → PREPROCESS
    ├─[chitchat]─→ CHITCHAT → END
    ├─[inspire]──→ INSPIRE  → END
    └─[comfort]──→ LOAD_LAYOUT → ASK_PERSONA → ROUTE_INTENT → ANALYZE
                                                                  │
                                              ┌───────[analyze]───┘
                                              │   [detect/full]──→ DETECT
                                              │                       │
                                              │       ┌──[detect]────┘
                                              │       │  [full]──→ SUGGEST
                                              │       │               │
                                              └───→ RESPOND ←────────┘
                                                      │
                                                     END

Nodes:
  preprocess    Pure Python. Coarse routing: comfort / inspire / chitchat.
                Extracts layout ID and detects persona from prompt.

  load_layout   Pure Python. Loads layout JSON by ID or interactive picker.
                Skips if layout already in session state.

  ask_persona   Pure Python. Interactive persona picker.
                Pass-through if persona already known.

  route_intent  LLM. Classifies depth: analyze / detect / full.
                Python keyword fallback if LLM fails.

  analyze       Pure Python. Calls compute_comfort_scores via MCP.
  detect        Pure Python. Calls detect_sensorial_conflicts via MCP.
  suggest       Pure Python. Calls generate_suggestions via MCP.

  respond       LLM. Formats all accumulated results into natural language.
  chitchat      LLM. Conversational response for non-comfort prompts.
  inspire       Placeholder. Phase 3 — atmosphere / image generation.
"""

from __future__ import annotations
from typing import Any, TypedDict
from langgraph.graph import END, START, StateGraph

from nodes.preprocess   import preprocess_node
from nodes.load_layout  import build_load_layout_node
from nodes.ask_persona  import ask_persona_node
from nodes.route_intent import build_route_intent_node
from nodes.analyze      import build_analyze_node
from nodes.detect       import build_detect_node
from nodes.suggest      import build_suggest_node
from nodes.respond      import build_respond_node
from nodes.chitchat     import build_chitchat_node
from nodes.inspire      import inspire_node


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    # Input
    raw_prompt:            str
    has_image:             bool

    # Routing
    intent:                str          # "comfort" | "inspire" | "chitchat"
    layout_id:             str | None   # e.g. "201"
    persona_detected:      str | None   # e.g. "Elderly 65+"
    needs_persona_ask:     bool
    comfort_depth:         str          # "analyze" | "detect" | "full"

    # Session persistence (carried across turns in main.py)
    layout_json_string:    str

    # Tool results (accumulated within one turn)
    last_scores_json:      str
    last_conflicts_json:   str
    last_suggestions_json: str

    # Output
    final_response:        str | None


# ---------------------------------------------------------------------------
# Routing functions (conditional edges)
# ---------------------------------------------------------------------------

def _route_after_preprocess(state: AgentState) -> str:
    intent = state.get("intent", "chitchat")
    if intent == "comfort":
        return "load_layout"
    if intent == "inspire":
        return "inspire"
    return "chitchat"


def _route_after_analyze(state: AgentState) -> str:
    depth = state.get("comfort_depth", "analyze")
    if depth in ("detect", "full"):
        return "detect"
    return "respond"


def _route_after_detect(state: AgentState) -> str:
    depth = state.get("comfort_depth", "detect")
    if depth == "full":
        return "suggest"
    return "respond"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(ctx: Any) -> Any:
    """Build and compile the Comfort Copilot state graph."""

    # Instantiate all nodes that need context.
    # route_intent, respond, chitchat use llm_simple (no JSON schema constraint).
    # llm (structured) is kept in ctx for any future tool-calling nodes.
    load_layout  = build_load_layout_node(ctx.layout_input_dir)
    route_intent = build_route_intent_node(ctx.llm_simple)
    analyze      = build_analyze_node(ctx.mcp_client)
    detect       = build_detect_node(ctx.mcp_client)
    suggest      = build_suggest_node(ctx.mcp_client)
    respond      = build_respond_node(ctx.llm_simple)
    chitchat     = build_chitchat_node(ctx.llm_simple)

    g = StateGraph(AgentState)

    # ── Add nodes ─────────────────────────────────────────────────────────
    g.add_node("preprocess",   preprocess_node)
    g.add_node("load_layout",  load_layout)
    g.add_node("ask_persona",  ask_persona_node)
    g.add_node("route_intent", route_intent)
    g.add_node("analyze",      analyze)
    g.add_node("detect",       detect)
    g.add_node("suggest",      suggest)
    g.add_node("respond",      respond)
    g.add_node("chitchat",     chitchat)
    g.add_node("inspire",      inspire_node)

    # ── Add edges ─────────────────────────────────────────────────────────
    g.add_edge(START, "preprocess")

    g.add_conditional_edges(
        "preprocess",
        _route_after_preprocess,
        {
            "load_layout": "load_layout",
            "inspire":     "inspire",
            "chitchat":    "chitchat",
        },
    )

    # Comfort path — always sequential up to analyze
    g.add_edge("load_layout",  "ask_persona")
    g.add_edge("ask_persona",  "route_intent")
    g.add_edge("route_intent", "analyze")

    # After analyze: go to detect or straight to respond
    g.add_conditional_edges(
        "analyze",
        _route_after_analyze,
        {
            "detect":  "detect",
            "respond": "respond",
        },
    )

    # After detect: go to suggest or straight to respond
    g.add_conditional_edges(
        "detect",
        _route_after_detect,
        {
            "suggest": "suggest",
            "respond": "respond",
        },
    )

    g.add_edge("suggest",  "respond")
    g.add_edge("respond",  END)
    g.add_edge("chitchat", END)
    g.add_edge("inspire",  END)

    return g.compile()


# ---------------------------------------------------------------------------
# run_agent — called once per user turn from main.py
# ---------------------------------------------------------------------------

def run_agent(prompt: str, ctx: Any, session: dict | None = None) -> tuple[str, dict]:
    """
    Run one turn of the agent.

    Args:
        prompt   : raw user input for this turn
        ctx      : Context object from bootstrap()
        session  : dict carrying persistent state across turns
                   (layout_json_string, persona_detected, layout_id)
                   Pass None or {} for the first turn.

    Returns:
        (final_response, updated_session)
        updated_session can be passed into the next run_agent() call.
    """
    if session is None:
        session = {}

    initial_state: AgentState = {
        # This turn's input
        "raw_prompt":  prompt,
        "has_image":   False,

        # Carry over persistent fields from the previous turn
        "layout_json_string": session.get("layout_json_string", ""),
        "persona_detected":   session.get("persona_detected"),
        "layout_id":          session.get("layout_id"),

        # Reset per-turn fields
        "intent":                "",
        "needs_persona_ask":     False,
        "comfort_depth":         "analyze",
        "last_scores_json":      "",
        "last_conflicts_json":   "",
        "last_suggestions_json": "",
        "final_response":        None,
    }

    app = build_graph(ctx)

    print("\nWorkflow graph:")
    app.get_graph().print_ascii()

    final_state = app.invoke(initial_state)

    final_response = final_state.get("final_response")
    if not isinstance(final_response, str):
        raise RuntimeError("Agent finished without a final response.")

    # Build updated session — persist layout and persona across turns,
    # but only when this was a comfort turn. Chitchat / inspire should
    # never overwrite a previously chosen persona with a keyword false-positive.
    intent = final_state.get("intent", "")
    if intent == "comfort":
        updated_session = {
            "layout_json_string": final_state.get("layout_json_string", ""),
            "persona_detected":   final_state.get("persona_detected"),
            "layout_id":          final_state.get("layout_id"),
        }
    else:
        # Non-comfort turn: carry forward whatever was already in the session
        updated_session = session

    return final_response, updated_session
