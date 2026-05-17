"""
graph.py -- Comfort Copilot state graph  (v2 — Phase 2 redesign)

===========================================================================
WHAT CHANGED FROM v1
===========================================================================

Phase 1 graph (retired):
  preprocess [PY keyword] → load_layout → ask_persona [PY rigid picker]
  → route_intent [LLM, analyze/detect/full only] → analyze → detect → suggest
  → respond → END

Phase 2 graph (this file):
  ┌─ ENTRY (first turn only) ────────────────────────────────────────────┐
  │  greet [LLM]  →  (next turn)  user_profiler [LLM]                   │
  └──────────────────────────────────────────────────────────────────────┘
  ┌─ ROUTING ────────────────────────────────────────────────────────────┐
  │  intent_classifier [LLM]  replaces keyword preprocess                │
  └──────────────────────────────────────────────────────────────────────┘
  ┌─ PERSONA CHAIN ──────────────────────────────────────────────────────┐
  │  persona_builder [LLM]  →  persona_validator [LLM]                   │
  │    → advisor [LLM]  (when user is unsure)                            │
  └──────────────────────────────────────────────────────────────────────┘
  ┌─ ANALYSIS CHAIN ─────────────────────────────────────────────────────┐
  │  route_intent → analyze [MCP] → score_interpreter [LLM]             │
  │  → detect [MCP] → conflict_reasoner [LLM]                           │
  │  → suggest [MCP] → suggestion_critic [LLM] → respond [LLM]          │
  └──────────────────────────────────────────────────────────────────────┘
  ┌─ TOOL PATHS (placeholders) ──────────────────────────────────────────┐
  │  what-if:   change_material / modify_glazing / add_furniture         │
  │             → analyze (re-score) → compare_versions → score_interp  │
  │  topologic: topologic_analysis → conflict_reasoner                   │
  │  compare:   persona_comparison → score_interpreter                   │
  │  biophilic: biophilic_audit → (opt) add_furniture → score_interp    │
  └──────────────────────────────────────────────────────────────────────┘
  ┌─ QUALITY LOOP ───────────────────────────────────────────────────────┐
  │  respond → evaluator [LLM] ←→ respond  (max 3)                      │
  │  evaluator → fact_checker [LLM] ←→ respond  (max 3)                 │
  └──────────────────────────────────────────────────────────────────────┘
  ┌─ FEEDBACK LOOP ──────────────────────────────────────────────────────┐
  │  fact_checker → what_next [LLM] → END                               │
  │  (user's next message re-enters via intent_classifier)               │
  └──────────────────────────────────────────────────────────────────────┘

===========================================================================
NODE SUMMARY
===========================================================================
  greet              [LLM]     opening move — "who are you?"
  user_profiler      [LLM]     classifies architect / client / learner
  intent_classifier  [LLM]     replaces preprocess keyword matching
  load_layout        [PYTHON]  file I/O, skips if same layout already loaded
  overview_respond   [PYTHON]  room list, no analysis
  persona_builder    [LLM]     fluid multi-turn persona building
  persona_validator  [LLM]     completeness check, loop max 3
  advisor            [LLM]     recommends starting path when user is unsure
  route_intent       [LLM]     analyze/detect/full + what-if/compare/biophilic/topologic
  analyze            [MCP]     compute_comfort_scores
  score_interpreter  [LLM]     what scores mean for this persona
  detect             [MCP]     detect_sensorial_conflicts
  conflict_reasoner  [LLM]     why did it fail? root cause analysis
  suggest            [MCP]     generate_suggestions
  suggestion_critic  [LLM]     feasibility, priority, cross-sense consequences
  respond            [LLM]     final natural-language response
  evaluator          [LLM]     quality gate: coherent, complete, right tone?
  fact_checker       [LLM]     data integrity: no invented scores or rooms
  what_next          [LLM]     feedback loop offer
  chitchat           [LLM]     conversational node, user-type aware
  inspire            [PYTHON]  Phase 3 placeholder
  change_material    [PH·MCP]  P1: modify material → re-score
  topologic_analysis [PH·MCP]  P1: room adjacency via TopologicPy
  compare_versions   [PH·MCP]  P2: before/after score delta
  persona_comparison [PH·LLM]  P2: same layout, two personas
  modify_glazing     [PH·MCP]  P3: glazing ratio/type → re-score
  add_furniture      [PH·MCP]  P3: add furniture/plants → re-score
  biophilic_audit    [PH·LLM]  P3: "Talk Green To Me" mode
  output_writer      [PYTHON]  post-graph, writes resulting_layout/
"""

from __future__ import annotations
from typing import Any, TypedDict
from langgraph.graph import END, START, StateGraph

# Existing nodes
from nodes.persona.load_layout     import build_load_layout_node
from nodes.analysis.analyze         import build_analyze_node
from nodes.analysis.detect          import build_detect_node
from nodes.analysis.suggest         import build_suggest_node
from nodes.conversation.inspire     import inspire_node
from nodes.conversation.overview    import overview_respond_node
from nodes._shared.output_writer    import write_analysis_to_layout

# New conversation nodes
from nodes.session.greet            import build_greet_node
from nodes.session.user_profiler    import build_user_profiler_node
from nodes.session.intent_classifier import build_intent_classifier_node
from nodes.conversation.chitchat    import build_chitchat_node
from nodes.persona.persona_builder  import build_persona_builder_node
from nodes.persona.persona_validator import build_persona_validator_node
from nodes.persona.advisor          import build_advisor_node
from nodes.analysis.route_intent    import build_route_intent_node
from nodes.conversation.what_next   import build_what_next_node

# New specialist nodes
from nodes.analysis.score_interpreter  import build_score_interpreter_node
from nodes.analysis.conflict_reasoner  import build_conflict_reasoner_node
from nodes.analysis.suggestion_critic  import build_suggestion_critic_node
from nodes.quality.evaluator          import build_evaluator_node
from nodes.quality.fact_checker       import build_fact_checker_node
from nodes.quality.respond            import build_respond_node

# Placeholder tool nodes
from nodes.tools.change_material      import build_change_material_node
from nodes.tools.topologic_analysis   import build_topologic_analysis_node
from nodes.tools.compare_versions     import build_compare_versions_node
from nodes.tools.persona_comparison   import build_persona_comparison_node
from nodes.tools.modify_glazing       import build_modify_glazing_node
from nodes.tools.add_furniture        import build_add_furniture_node
from nodes.tools.biophilic_audit      import build_biophilic_audit_node


# ---------------------------------------------------------------------------
# AgentState  --  everything the graph needs, passed between every node
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):

    # ── Input (set at the start of each turn) ───────────────────────────────
    raw_prompt:            str
    has_image:             bool

    # ── User identity (persisted across turns via session) ──────────────────
    user_type:             str        # "architect" | "client" | "learner"
    initial_context:       str        # layout/persona hints from first intro
    greeted:               bool       # True once GREET has run

    # ── Top-level routing ────────────────────────────────────────────────────
    intent:                str        # "comfort"|"overview"|"inspire"|"chitchat"|"tools"

    # ── Layout ───────────────────────────────────────────────────────────────
    layout_id:             str | None
    layout_json_string:    str        # full JSON of the loaded layout
    target_room_id:        str | None

    # ── Persona (replaces persona_detected + needs_persona_ask) ─────────────
    persona_profile:         dict     # rich object built by PERSONA_BUILDER
    persona_validator_loops: int      # counter for loop guard (max 3)
    persona_validator_decision: str   # "ready" | "incomplete" | "unsure"
    advisor_recommendation:  str      # from ADVISOR

    # ── Analysis routing ─────────────────────────────────────────────────────
    route_intent_decision: str        # "analyze"|"detect"|"full"|"what-if"|etc.
    comfort_depth:         str        # "analyze" | "detect" | "full"
    pending_comparison:    bool       # True when a MOD tool just ran

    # ── MCP tool results ─────────────────────────────────────────────────────
    last_scores_json:      str
    last_conflicts_json:   str
    last_suggestions_json: str
    original_scores_json:  str        # snapshot before modification

    # ── Intermediate specialist outputs ──────────────────────────────────────
    score_interpretation:      str    # from SCORE_INTERPRETER
    conflict_reasoning:        str    # from CONFLICT_REASONER
    suggestion_critique:       str    # from SUGGESTION_CRITIC
    adjacency_graph:           dict   # from TOPOLOGIC_ANALYSIS
    compare_versions_summary:  str    # from COMPARE_VERSIONS
    biophilic_summary:         str    # from BIOPHILIC_AUDIT
    biophilic_plants_needed:   bool   # flag from BIOPHILIC_AUDIT
    persona_comparison_summary: str   # from PERSONA_COMPARISON

    # ── Quality loop ─────────────────────────────────────────────────────────
    evaluator_decision:    str        # "APPROVED" | "REVISE"
    evaluator_feedback:    str        # revision instructions
    evaluator_loops:       int        # counter (max 3)
    fact_check_decision:   str        # "VERIFIED" | "DISCREPANCY"
    fact_check_feedback:   str        # discrepancy details
    fact_check_loops:      int        # counter (max 3)

    # ── Output ───────────────────────────────────────────────────────────────
    final_response:        str | None


# ---------------------------------------------------------------------------
# Routing functions
# ---------------------------------------------------------------------------

def _route_start(state: AgentState) -> str:
    """Entry routing: GREET → USER_PROFILER → INTENT_CLASSIFIER across turns."""
    if state.get("user_type"):
        return "intent_classifier"
    elif state.get("greeted"):
        return "user_profiler"
    else:
        return "greet"


def _route_after_user_profiler(state: AgentState) -> str:
    user_type = state.get("user_type", "learner")
    if user_type == "learner":
        return "chitchat"
    return "intent_classifier"


def _route_after_intent_classifier(state: AgentState) -> str:
    intent = state.get("intent", "chitchat")
    if intent == "inspire":
        return "inspire"
    if intent in ("overview", "comfort", "tools"):
        return "load_layout"
    return "chitchat"


def _route_after_chitchat(state: AgentState) -> str:
    """Chitchat can detect analysis intent and redirect."""
    if state.get("intent") == "comfort":
        return "intent_classifier"
    return "what_next"


def _route_after_load_layout(state: AgentState) -> str:
    intent = state.get("intent", "comfort")
    if intent == "overview":
        return "overview_respond"
    return "persona_builder"


def _route_after_persona_validator(state: AgentState) -> str:
    decision = state.get("persona_validator_decision", "incomplete")
    loops = state.get("persona_validator_loops", 0)
    if decision == "ready":
        return "route_intent"
    if decision == "unsure":
        return "advisor"
    if loops >= 3:
        return "route_intent"  # give up, proceed with partial profile
    # PERSONA_BUILDER already wrote the question to final_response → end turn
    return END


def _route_after_route_intent(state: AgentState) -> str:
    decision = state.get("route_intent_decision", "analyze")
    if decision in ("analyze", "detect", "full"):
        return "analyze"
    if decision in ("what-if", "what-if-material", "modify-material"):
        return "change_material"
    if decision in ("what-if-glazing", "modify-glazing"):
        return "modify_glazing"
    if decision == "compare":
        return "persona_comparison"
    if decision == "biophilic":
        return "biophilic_audit"
    if decision == "topologic":
        return "topologic_analysis"
    return "analyze"  # safe fallback


def _route_after_analyze(state: AgentState) -> str:
    if state.get("pending_comparison"):
        return "compare_versions"
    return "score_interpreter"


def _route_after_score_interpreter(state: AgentState) -> str:
    depth = state.get("comfort_depth", "analyze")
    if depth in ("detect", "full"):
        return "detect"
    return "respond"


def _route_after_detect(state: AgentState) -> str:
    """Detect always goes to conflict_reasoner, which then routes."""
    return "conflict_reasoner"


def _route_after_conflict_reasoner(state: AgentState) -> str:
    depth = state.get("comfort_depth", "detect")
    if depth == "full":
        return "suggest"
    return "respond"


def _route_after_biophilic_audit(state: AgentState) -> str:
    if state.get("biophilic_plants_needed"):
        return "add_furniture"
    return "score_interpreter"


def _route_after_evaluator(state: AgentState) -> str:
    decision = state.get("evaluator_decision", "APPROVED")
    loops = state.get("evaluator_loops", 0)
    if decision == "REVISE" and loops < 3:
        return "respond"
    return "fact_checker"


def _route_after_fact_checker(state: AgentState) -> str:
    decision = state.get("fact_check_decision", "VERIFIED")
    loops = state.get("fact_check_loops", 0)
    if decision == "DISCREPANCY" and loops < 3:
        return "respond"
    return "what_next"


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_graph(ctx: Any) -> Any:
    """
    Instantiate all nodes, wire up edges, and compile the StateGraph.

    Nodes that need external resources (LLM, MCP) are built via factory
    functions so the resource is captured in a closure — the graph itself
    stays stateless.
    """

    # Build all nodes
    greet              = build_greet_node(ctx.llm_simple)
    user_profiler      = build_user_profiler_node(ctx.llm_simple)
    intent_classifier  = build_intent_classifier_node(ctx.llm_simple)
    chitchat           = build_chitchat_node(ctx.llm_simple)
    load_layout        = build_load_layout_node(ctx.layout_input_dir)
    persona_builder    = build_persona_builder_node(ctx.llm_simple)
    persona_validator  = build_persona_validator_node(ctx.llm_simple)
    advisor            = build_advisor_node(ctx.llm_simple)
    route_intent       = build_route_intent_node(ctx.llm_simple)
    analyze            = build_analyze_node(ctx.mcp_client)
    score_interpreter  = build_score_interpreter_node(ctx.llm_simple)
    detect             = build_detect_node(ctx.mcp_client)
    conflict_reasoner  = build_conflict_reasoner_node(ctx.llm_simple)
    suggest            = build_suggest_node(ctx.mcp_client)
    suggestion_critic  = build_suggestion_critic_node(ctx.llm_simple)
    respond            = build_respond_node(ctx.llm_simple)
    evaluator          = build_evaluator_node(ctx.llm_simple)
    fact_checker       = build_fact_checker_node(ctx.llm_simple)
    what_next          = build_what_next_node(ctx.llm_simple)

    # Placeholder tool nodes (no LLM or MCP needed yet)
    change_material    = build_change_material_node()
    topologic_analysis = build_topologic_analysis_node()
    compare_versions   = build_compare_versions_node()
    persona_comparison = build_persona_comparison_node()
    modify_glazing     = build_modify_glazing_node()
    add_furniture      = build_add_furniture_node()
    biophilic_audit    = build_biophilic_audit_node()

    g = StateGraph(AgentState)

    # ── Register all nodes ─────────────────────────────────────────────────
    # Entry
    g.add_node("greet",             greet)
    g.add_node("user_profiler",     user_profiler)
    g.add_node("intent_classifier", intent_classifier)
    g.add_node("chitchat",          chitchat)

    # Layout
    g.add_node("load_layout",       load_layout)
    g.add_node("overview_respond",  overview_respond_node)
    g.add_node("inspire",           inspire_node)

    # Persona chain
    g.add_node("persona_builder",   persona_builder)
    g.add_node("persona_validator", persona_validator)
    g.add_node("advisor",           advisor)

    # Analysis chain
    g.add_node("route_intent",      route_intent)
    g.add_node("analyze",           analyze)
    g.add_node("score_interpreter", score_interpreter)
    g.add_node("detect",            detect)
    g.add_node("conflict_reasoner", conflict_reasoner)
    g.add_node("suggest",           suggest)
    g.add_node("suggestion_critic", suggestion_critic)
    g.add_node("respond",           respond)

    # Quality loop
    g.add_node("evaluator",         evaluator)
    g.add_node("fact_checker",      fact_checker)

    # Feedback
    g.add_node("what_next",         what_next)

    # Placeholder tools
    g.add_node("change_material",    change_material)
    g.add_node("modify_glazing",     modify_glazing)
    g.add_node("add_furniture",      add_furniture)
    g.add_node("compare_versions",   compare_versions)
    g.add_node("topologic_analysis", topologic_analysis)
    g.add_node("persona_comparison", persona_comparison)
    g.add_node("biophilic_audit",    biophilic_audit)

    # ── Wire edges ─────────────────────────────────────────────────────────

    # START: route based on session state
    g.add_conditional_edges(
        START,
        _route_start,
        {"greet": "greet", "user_profiler": "user_profiler", "intent_classifier": "intent_classifier"},
    )

    # GREET ends the first turn
    g.add_edge("greet", END)

    # USER_PROFILER → chitchat (learner) or intent_classifier (architect/client)
    g.add_conditional_edges(
        "user_profiler",
        _route_after_user_profiler,
        {"chitchat": "chitchat", "intent_classifier": "intent_classifier"},
    )

    # INTENT_CLASSIFIER branches
    g.add_conditional_edges(
        "intent_classifier",
        _route_after_intent_classifier,
        {"inspire": "inspire", "load_layout": "load_layout", "chitchat": "chitchat"},
    )

    # CHITCHAT: either done (→ what_next) or analysis intent detected (→ intent_classifier)
    g.add_conditional_edges(
        "chitchat",
        _route_after_chitchat,
        {"intent_classifier": "intent_classifier", "what_next": "what_next"},
    )

    # INSPIRE and OVERVIEW both go to WHAT_NEXT (not END)
    g.add_edge("inspire",          "what_next")
    g.add_edge("overview_respond", "what_next")

    # LOAD_LAYOUT → overview_respond or persona_builder
    g.add_conditional_edges(
        "load_layout",
        _route_after_load_layout,
        {"overview_respond": "overview_respond", "persona_builder": "persona_builder"},
    )

    # PERSONA chain loop
    g.add_edge("persona_builder", "persona_validator")
    g.add_conditional_edges(
        "persona_validator",
        _route_after_persona_validator,
        {"route_intent": "route_intent", "advisor": "advisor", END: END},
    )
    g.add_edge("advisor", "route_intent")

    # ROUTE_INTENT branches to all analysis/tool paths
    g.add_conditional_edges(
        "route_intent",
        _route_after_route_intent,
        {
            "analyze":           "analyze",
            "change_material":   "change_material",
            "modify_glazing":    "modify_glazing",
            "persona_comparison":"persona_comparison",
            "biophilic_audit":   "biophilic_audit",
            "topologic_analysis":"topologic_analysis",
        },
    )

    # MODIFICATION TOOLS → re-score via ANALYZE
    g.add_edge("change_material",  "analyze")
    g.add_edge("modify_glazing",   "analyze")
    g.add_edge("add_furniture",    "analyze")

    # ANALYZE → compare_versions (after modification) or score_interpreter (direct)
    g.add_conditional_edges(
        "analyze",
        _route_after_analyze,
        {"compare_versions": "compare_versions", "score_interpreter": "score_interpreter"},
    )
    g.add_edge("compare_versions", "score_interpreter")

    # SCORE_INTERPRETER → detect (detect/full) or respond (analyze only)
    g.add_conditional_edges(
        "score_interpreter",
        _route_after_score_interpreter,
        {"detect": "detect", "respond": "respond"},
    )

    # DETECT always goes to CONFLICT_REASONER
    g.add_edge("detect", "conflict_reasoner")

    # CONFLICT_REASONER → suggest (full) or respond (detect)
    g.add_conditional_edges(
        "conflict_reasoner",
        _route_after_conflict_reasoner,
        {"suggest": "suggest", "respond": "respond"},
    )

    # TOPOLOGIC_ANALYSIS feeds CONFLICT_REASONER
    g.add_edge("topologic_analysis", "conflict_reasoner")

    # PERSONA_COMPARISON feeds SCORE_INTERPRETER
    g.add_edge("persona_comparison", "score_interpreter")

    # BIOPHILIC_AUDIT → add_furniture (opt) or score_interpreter (direct)
    g.add_conditional_edges(
        "biophilic_audit",
        _route_after_biophilic_audit,
        {"add_furniture": "add_furniture", "score_interpreter": "score_interpreter"},
    )

    # SUGGEST → SUGGESTION_CRITIC → RESPOND
    g.add_edge("suggest",           "suggestion_critic")
    g.add_edge("suggestion_critic", "respond")

    # QUALITY LOOP: respond ↔ evaluator ↔ fact_checker
    g.add_edge("respond", "evaluator")
    g.add_conditional_edges(
        "evaluator",
        _route_after_evaluator,
        {"respond": "respond", "fact_checker": "fact_checker"},
    )
    g.add_conditional_edges(
        "fact_checker",
        _route_after_fact_checker,
        {"respond": "respond", "what_next": "what_next"},
    )

    # WHAT_NEXT ends the turn
    g.add_edge("what_next", END)

    return g.compile()


# ---------------------------------------------------------------------------
# run_agent  --  called once per user turn from main.py
# ---------------------------------------------------------------------------

def run_agent(prompt: str, ctx: Any, session: dict | None = None) -> tuple[str, dict]:
    """
    Run one turn of the Comfort Copilot agent.

    Args:
        prompt  : raw user input for this turn
        ctx     : Context object from bootstrap() — holds LLM, MCP client, paths
        session : persistent state carried across turns. Pass {} on first turn.

    Returns:
        (final_response, updated_session)
    """
    if session is None:
        session = {}

    initial_state: AgentState = {
        # This turn's input
        "raw_prompt": prompt,
        "has_image":  False,

        # Carry persistent identity fields from previous turn
        "user_type":        session.get("user_type"),
        "initial_context":  session.get("initial_context", ""),
        "greeted":          session.get("greeted", False),

        # Carry persistent layout + persona fields
        "layout_json_string":    session.get("layout_json_string", ""),
        "layout_id":             session.get("layout_id"),
        "persona_profile":       session.get("persona_profile"),
        "persona_validator_loops": session.get("persona_validator_loops", 0),

        # Reset per-turn fields
        "intent":                "",
        "route_intent_decision": "",
        "comfort_depth":         "analyze",
        "target_room_id":        None,
        "pending_comparison":    False,
        "last_scores_json":      "",
        "last_conflicts_json":   "",
        "last_suggestions_json": "",
        "original_scores_json":  "",
        "score_interpretation":  "",
        "conflict_reasoning":    "",
        "suggestion_critique":   "",
        "compare_versions_summary": "",
        "biophilic_summary":     "",
        "biophilic_plants_needed": False,
        "persona_comparison_summary": "",
        "adjacency_graph":       {},
        "evaluator_decision":    "",
        "evaluator_feedback":    "",
        "evaluator_loops":       0,
        "fact_check_decision":   "",
        "fact_check_feedback":   "",
        "fact_check_loops":      0,
        "persona_validator_decision": "",
        "advisor_recommendation": "",
        "final_response":        None,
    }

    app = build_graph(ctx)

    # Run the graph
    final_state = app.invoke(initial_state)

    response = final_state.get("final_response") or ""
    intent   = final_state.get("intent", "")
    depth    = final_state.get("comfort_depth", "")
    scores_ready = bool(final_state.get("last_scores_json"))

    print("[run_agent] intent={} | depth={} | scores_ready={}".format(
        intent, depth, scores_ready
    ))

    # [POST-GRAPH] Write analysis to resulting_layout/
    if intent in ("comfort", "tools") and scores_ready:
        try:
            write_analysis_to_layout(final_state, ctx.layout_output_dir)
        except Exception as exc:
            print("[run_agent] ERROR in output_writer: {}".format(exc))

    # Update session with all persistent fields
    updated_session = {
        # Identity
        "user_type":         final_state.get("user_type") or session.get("user_type"),
        "initial_context":   final_state.get("initial_context") or session.get("initial_context", ""),
        "greeted":           final_state.get("greeted", session.get("greeted", False)),
        # Layout
        "layout_json_string": final_state.get("layout_json_string") or session.get("layout_json_string", ""),
        "layout_id":          final_state.get("layout_id") or session.get("layout_id"),
        # Persona
        "persona_profile":           final_state.get("persona_profile") or session.get("persona_profile"),
        "persona_validator_loops":   final_state.get("persona_validator_loops", session.get("persona_validator_loops", 0)),
    }

    return response, updated_session
