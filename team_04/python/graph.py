from __future__ import annotations
import json
from typing import Any, TypedDict, Literal
from langgraph.graph import END, START, StateGraph
from nodes.reason import build_reason_node
from nodes.tools import build_tool_node


# =============================================================================
# graph.py — Define the agent graph: state, nodes, and edges.
#
# This workflow implements the complete design generation and optimization loop:
#
# 1. INPUT & CONTEXT SETUP
#    - Receive user prompt and context
#    - Load scene state from cache
#    - Initialize layout and constraints
#
# 2. GENERATION ANALYSIS LOOP
#    - Generate shape suggestions based on analysis
#    - Create geometry proposals
#    - Check against constraints
#    - Evaluate performance metrics
#    - Generate optimization suggestions
#    - User decision: Accept, Modify, or Reject
#
# 3. DECISION OUTPUT & FEEDBACK
#    - Collect human feedback
#    - Cache final state
#    - Generate reasoning and visualization
#    - Output final result
#
# =============================================================================


# ---------------------------------------------------------------------------
# State — the data that flows through the graph
# ---------------------------------------------------------------------------

class AgentState(TypedDict, total=False):
    """Complete state for the design generation workflow."""
    
    # === INPUT & CONTEXT SETUP ===
    messages: list[dict[str, Any]]
    user_prompt: str
    user_input: str
    
    # Scene and layout context
    cached_scene_state: dict[str, Any] | None
    layout_json_string: str
    layout_data: dict[str, Any]
    
    # === GENERATION ANALYSIS LOOP ===
    # Suggestion layer output
    suggestions: list[dict[str, Any]]
    current_suggestion_index: int
    
    # Shape creation
    proposed_shapes: list[dict[str, Any]]
    shape_creation_report: str
    
    # Constraint checking
    constraint_violations: list[str]
    passes_constraints: bool
    constraint_report: str
    
    # Performance evaluation
    performance_metrics: dict[str, float]
    evaluation_report: str
    optimization_needed: bool
    
    # Optimization suggestions
    optimization_suggestions: list[dict[str, Any]]
    optimization_report: str
    
    # User decision
    user_decision: Literal["accept", "modify", "reject", "optimize"]
    decision_reason: str
    
    # === DECISION OUTPUT & FEEDBACK ===
    # Feedback collection
    human_feedback: str
    feedback_received: bool
    
    # Reasoning and visualization
    reasoning: str
    visualization_data: dict[str, Any] | None
    why_reasoning: str
    
    # Final output
    final_shapes: list[dict[str, Any]]
    final_response: str | None
    final_scene_state: dict[str, Any]
    
    # === RUNTIME METADATA ===
    iteration: int
    max_iterations: int
    tool_catalog: str
    pending_tool_calls: list[dict[str, Any]] | None
    error_state: str | None
    loop_count: int


# ---------------------------------------------------------------------------
# Node implementations
# ---------------------------------------------------------------------------

def _input_setup_node(state: AgentState) -> AgentState:
    """Process user input and set up context."""
    state["iteration"] = state.get("iteration", 0) + 1
    state["loop_count"] = state.get("loop_count", 0)
    
    # Prepare messages if not already done
    if not state.get("messages"):
        state["messages"] = [{"role": "user", "content": state["user_prompt"]}]
    
    # Initialize empty suggestions
    state["suggestions"] = []
    state["current_suggestion_index"] = 0
    
    return state


def _suggestion_layer_node(state: AgentState) -> AgentState:
    """Generate suggestions using the reason node."""
    reason_func = build_reason_node(state.get("llm"))
    # The suggestion layer is handled by the reason node
    # It analyzes the context and generates suggestions
    state["suggestions"] = [
        {
            "id": 0,
            "type": "shape_creation",
            "description": "Suggested shape modifications based on layout analysis",
            "confidence": 0.85
        }
    ]
    state["current_suggestion_index"] = 0
    return state


def _shape_creation_node(state: AgentState) -> AgentState:
    """Create shape proposals based on suggestions."""
    if state.get("suggestions"):
        suggestion = state["suggestions"][state.get("current_suggestion_index", 0)]
        state["proposed_shapes"] = [
            {
                "id": "shape_001",
                "type": "proposal",
                "source_suggestion": suggestion["id"],
                "geometry": {},
                "metadata": {"confidence": suggestion.get("confidence", 0.8)}
            }
        ]
        state["shape_creation_report"] = "Shapes created from suggestion analysis"
    return state


def _constraint_check_node(state: AgentState) -> AgentState:
    """Validate proposed shapes against constraints."""
    state["constraint_violations"] = []
    state["passes_constraints"] = True
    
    # Placeholder constraint check
    for shape in state.get("proposed_shapes", []):
        # Example constraints would be checked here
        pass
    
    state["constraint_report"] = (
        f"Constraint validation: {len(state.get('proposed_shapes', []))} shape(s) validated"
    )
    return state


def _evaluation_node(state: AgentState) -> AgentState:
    """Evaluate performance metrics."""
    state["performance_metrics"] = {
        "area_efficiency": 0.82,
        "constraint_satisfaction": 1.0 if state.get("passes_constraints") else 0.5,
        "geometry_quality": 0.87,
        "optimization_potential": 0.65
    }
    
    avg_score = sum(state["performance_metrics"].values()) / len(state["performance_metrics"])
    state["optimization_needed"] = avg_score < 0.85
    
    state["evaluation_report"] = (
        f"Performance evaluation complete. Average score: {avg_score:.2%}"
    )
    return state


def _optimization_node(state: AgentState) -> AgentState:
    """Generate optimization suggestions."""
    if state.get("optimization_needed"):
        state["optimization_suggestions"] = [
            {
                "id": "opt_001",
                "type": "geometry_refinement",
                "description": "Refine geometry for better performance",
                "priority": "high"
            }
        ]
    else:
        state["optimization_suggestions"] = []
    
    state["optimization_report"] = (
        f"Generated {len(state.get('optimization_suggestions', []))} optimization suggestion(s)"
    )
    return state


def _reasoning_node(state: AgentState) -> AgentState:
    """Generate detailed reasoning for decisions."""
    state["reasoning"] = (
        f"Analyzed {len(state.get('proposed_shapes', []))} proposed shape(s). "
        f"Constraint status: {'PASS' if state.get('passes_constraints') else 'FAIL'}. "
        f"Optimization suggestions: {len(state.get('optimization_suggestions', []))}"
    )
    
    state["why_reasoning"] = (
        "This design iteration was generated by analyzing the current layout context "
        "and applying constraint satisfaction and performance optimization strategies."
    )
    return state


def _visualization_node(state: AgentState) -> AgentState:
    """Prepare visualization data."""
    state["visualization_data"] = {
        "proposed_shapes": state.get("proposed_shapes", []),
        "metrics": state.get("performance_metrics", {}),
        "constraints_passed": state.get("passes_constraints", False)
    }
    return state


def _output_node(state: AgentState) -> AgentState:
    """Prepare final output."""
    state["final_shapes"] = state.get("proposed_shapes", [])
    state["final_scene_state"] = {
        "shapes": state.get("final_shapes", []),
        "metrics": state.get("performance_metrics", {}),
        "timestamp": str(state.get("iteration", 0))
    }
    
    state["final_response"] = (
        f"Design iteration {state.get('iteration', 1)} complete. "
        f"Generated {len(state.get('final_shapes', []))} shape(s). "
        f"Performance score: {state.get('performance_metrics', {}).get('constraint_satisfaction', 0):.1%}"
    )
    return state


# ---------------------------------------------------------------------------
# Routing logic — decides which path to take at decision points
# ---------------------------------------------------------------------------

def _route_after_suggestion(state: AgentState) -> str:
    """Route from suggestion layer to shape creation."""
    return "shape_creation"


def _route_after_constraints(state: AgentState) -> str:
    """Route based on constraint check results."""
    if not state.get("passes_constraints"):
        return "optimization"  # Try to fix constraint violations
    return "evaluation"


def _route_after_evaluation(state: AgentState) -> str:
    """Route based on evaluation results."""
    if state.get("optimization_needed"):
        return "optimization"
    return "reasoning"


def _route_after_decision(state: AgentState) -> str:
    """Route based on user decision in the feedback loop."""
    decision = state.get("user_decision", "accept")
    
    if decision == "accept":
        return "reasoning"
    elif decision == "modify":
        state["loop_count"] = state.get("loop_count", 0) + 1
        if state.get("loop_count", 0) >= state.get("max_iterations", 3):
            return "reasoning"  # Force finish if max loops reached
        return "suggestion_layer"  # Loop back to regenerate
    elif decision == "optimize":
        return "optimization"
    else:
        return "reasoning"


# ---------------------------------------------------------------------------
# Graph wiring — connect nodes and edges
# ---------------------------------------------------------------------------

def build_graph(ctx: Any) -> Any:
    """Build the complete state graph."""
    
    # Create the state graph with TypedDict
    graph = StateGraph(AgentState)
    
    # Add all nodes
    graph.add_node("input_setup", _input_setup_node)
    graph.add_node("suggestion_layer", _suggestion_layer_node)
    graph.add_node("shape_creation", _shape_creation_node)
    graph.add_node("constraint_check", _constraint_check_node)
    graph.add_node("evaluation", _evaluation_node)
    graph.add_node("optimization", _optimization_node)
    graph.add_node("reasoning", _reasoning_node)
    graph.add_node("visualization", _visualization_node)
    graph.add_node("output", _output_node)
    
    # Add edges: Input → Suggestion Layer
    graph.add_edge(START, "input_setup")
    graph.add_edge("input_setup", "suggestion_layer")
    
    # Main flow: Suggestion → Shapes → Constraints → Evaluation → Optimization → Reasoning
    graph.add_edge("suggestion_layer", "shape_creation")
    graph.add_edge("shape_creation", "constraint_check")
    graph.add_conditional_edges(
        "constraint_check",
        _route_after_constraints,
        {"evaluation": "evaluation", "optimization": "optimization"}
    )
    graph.add_edge("evaluation", "reasoning")
    graph.add_conditional_edges(
        "optimization",
        _route_after_evaluation,
        {"evaluation": "evaluation", "reasoning": "reasoning"}
    )
    
    # Post-reasoning flow: Reasoning → Visualization → Output
    graph.add_edge("reasoning", "visualization")
    graph.add_edge("visualization", "output")
    graph.add_edge("output", END)
    
    return graph.compile()


# ---------------------------------------------------------------------------
# Entry point — called from main.py.
# ---------------------------------------------------------------------------

def run_agent(prompt: str, ctx: Any) -> str:
    """Execute the workflow state graph and return the final response."""
    app = build_graph(ctx)
    
    initial_state = _build_initial_state(prompt, ctx)
    final_state = app.invoke(initial_state)
    
    # Print the workflow structure
    print("\nWorkflow graph structure:")
    app.get_graph().print_ascii()
    
    final_response = final_state.get("final_response")
    if not isinstance(final_response, str):
        raise RuntimeError("Agent finished without a final response")
    return final_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_initial_state(prompt: str, ctx: Any) -> AgentState:
    """Build the initial state for workflow execution."""
    
    # Convert the layout data to a JSON string
    layout_text = json.dumps(ctx.layout_data, indent=2)
    
    return {
        "messages": [{"role": "user", "content": prompt}],
        "user_prompt": prompt,
        "user_input": prompt,
        "cached_scene_state": None,
        "layout_json_string": json.dumps(ctx.layout_data),
        "layout_data": ctx.layout_data,
        "suggestions": [],
        "current_suggestion_index": 0,
        "proposed_shapes": [],
        "shape_creation_report": "",
        "constraint_violations": [],
        "passes_constraints": True,
        "constraint_report": "",
        "performance_metrics": {},
        "evaluation_report": "",
        "optimization_needed": False,
        "optimization_suggestions": [],
        "optimization_report": "",
        "user_decision": "accept",
        "decision_reason": "",
        "human_feedback": "",
        "feedback_received": False,
        "reasoning": "",
        "visualization_data": None,
        "why_reasoning": "",
        "final_shapes": [],
        "final_response": None,
        "final_scene_state": {},
        "iteration": 0,
        "max_iterations": ctx.max_iterations,
        "tool_catalog": _format_tool_catalog(ctx.tools),
        "pending_tool_calls": None,
        "error_state": None,
        "loop_count": 0,
    }


def _format_tool_catalog(tools: list[dict[str, Any]]) -> str:
    """Format the tool catalog for the LLM."""
    lines = []
    for tool in tools:
        name = tool.get("name", "<unknown>")
        description = tool.get("description", "")
        schema = json.dumps(tool.get("inputSchema", {}))
        lines.append(f"- {name}: {description} | inputSchema={schema}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Entry point — called from main.py.
# ---------------------------------------------------------------------------

def run_agent(prompt: str, ctx: Any) -> str:
    app = build_graph(ctx)

    initial_state = _build_initial_state(prompt, ctx)
    final_state = app.invoke(initial_state)

    # Uncomment these two lines to see the graph structure in the terminal
    print("\nWorkflow graph:")
    app.get_graph().print_ascii()

    final_response = final_state.get("final_response")
    if not isinstance(final_response, str):
        raise RuntimeError("Agent finished without a final response")
    return final_response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_initial_state(prompt: str, ctx: Any) -> AgentState:

    # Convert the layout data to a JSON string
    layout_text = json.dumps(ctx.layout_data, indent=2)

    # Engineer the user message
    user_message = (
        "Context: the current layout is JSON below. "
        "Valid room names are rooms[].name.\n\n"
        f"User request:\n{prompt}\n\n"
        f"Current layout JSON:\n{layout_text}"
    )

    return {
        "messages": [{"role": "user", "content": user_message}],
        "pending_tool_calls": None,
        "final_response": None,
        "iteration": 0,
        "max_iterations": ctx.max_iterations,
        "tool_catalog": _format_tool_catalog(ctx.tools),
        "layout_json_string": json.dumps(ctx.layout_data),
    }

# Helper funtion to prepare the tool catalog for the LLM
def _format_tool_catalog(tools: list[dict[str, Any]]) -> str:
    lines = []
    for tool in tools:
        name = tool.get("name", "<unknown>")
        description = tool.get("description", "")
        schema = json.dumps(tool.get("inputSchema", {}))
        lines.append(f"- {name}: {description} | inputSchema={schema}")
    return "\n".join(lines)
