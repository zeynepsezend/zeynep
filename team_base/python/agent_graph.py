# =============================================================================
# agent_graph.py — The "brain" of the AI agent
# =============================================================================
#
# WHAT THIS FILE DOES:
#   This file defines how the AI agent thinks and acts. The agent follows a
#   simple loop:
#
#     1. REASON  — The AI reads your question and the list of available tools,
#                  then decides what to do next: either call a tool or give a
#                  final answer.
#
#     2. TOOL    — If the AI decided to call a tool, this step runs that tool
#                  (e.g. a Grasshopper calculation) and hands the result back
#                  to the AI so it can keep going.
#
#     3. REPEAT  — Steps 1–2 repeat until the AI has everything it needs to
#                  give a complete final answer.
#
#   The structure of this loop is called a "graph" (hence the filename). The
#   graph is built with a library called LangGraph.
#
# KEY PIECES YOU MIGHT WANT TO CHANGE:
#
#   SYSTEM_PROMPT (in nodes/reason_node.py)
#     This is the instruction sheet the AI reads before every conversation.
#     Change this text to give the AI a different personality, more specific
#     rules, or a different output format. For example:
#       - "Always respond in bullet points."
#       - "You are an expert structural engineer assistant."
#       - "Return results as a JSON object."
#
#   max_iterations (passed in from main.py)
#     This is the maximum number of tool calls the agent is allowed to make
#     before it is forced to stop. Raise it if your task needs many tool calls;
#     lower it to keep things fast and cheap.
#
#   route_after_reason (in nodes/route_after_reason.py)
#     This is the decision function that chooses which step comes next in the
#     graph. If you wanted the agent to do something different after calling a
#     tool — for example, a validation step before looping back — you would
#     add a new node and wire it in here.
#
#   Adding a new node
#     To add a new step to the agent loop (e.g. a "summarize" step after the
#     final answer), you would:
#       1. Write a new function like `def summarize_node(state): ...`
#       2. Register it:  graph.add_node("summarize", summarize_node)
#       3. Wire it in:   graph.add_edge("reason", "summarize")
#                        graph.add_edge("summarize", END)
#
# =============================================================================

from __future__ import annotations

import json
from typing import Any, Callable, TypedDict

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from execution_graph_ascii import print_execution_graph_ascii
from mcp_client import McpClient
from nodes.classifier_node import CLASSIFIER_RESPONSE_FORMAT, create_classifier_node
from nodes.reason_node import create_reason_node
from nodes.routing import WorkflowState, create_route_after_reason, create_route_after_classifier, create_route_after_volume
from nodes.tool_node import create_tool_node, get_llm_response_format


class AgentState(TypedDict):
    '''
    Represents the state of the AI agent during its reasoning and tool-calling loop.
    This includes the conversation history, any pending tool calls, the final response 
    if available, the current iteration count, the maximum allowed iterations, and a 
    formatted catalog of available tools.
    '''

    messages: list[dict[str, str]]
    pending_tool_calls: list[dict[str, Any]] | None
    final_response: str | None
    iteration: int
    max_iterations: int
    tool_catalog: str


def _format_tools(tools: list[dict[str, Any]]) -> str:
    '''
    Formats the list of available tools into a human-readable string.
    Each tool is represented with its name, description, and input schema.
    This reflects the definitions in the Swiftlet definition for each tool.
    '''

    lines: list[str] = []
    for tool in tools:
        name = str(tool.get("name", "<unknown>"))
        description = str(tool.get("description", ""))
        input_schema = json.dumps(tool.get("inputSchema", {}))
        lines.append(f"- {name}: {description} | inputSchema={input_schema}")
    return "\n".join(lines)


def build_initial_state(user_prompt: str, tools: list[dict[str, Any]], max_iterations: int) -> AgentState:
    '''
    Builds the initial state for the AI agent, including the user prompt,
    the formatted tool catalog, and the maximum number of iterations allowed.
    '''

    return {
        "messages": [{"role": "user", "content": user_prompt}],
        "pending_tool_calls": None,
        "final_response": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "tool_catalog": _format_tools(tools),
    }


def _build_workflow_initial_state(user_prompt: str) -> WorkflowState:
    '''
    The parent graph starts with just the user prompt. The classifier fills in
    the route, and the runner nodes fill in the domain-specific answers.
    '''

    return {
        "user_prompt": user_prompt,
        "route": None,
        "volume_response": None,
        "area_response": None,
        "final_response": None,
    }


def _create_chat_llm(
    api_key: str,
    base_url: str,
    llm_model: str,
    timeout_seconds: float,
    model_kwargs: dict[str, Any] | None = None,
) -> ChatOpenAI:
    '''
    Both the classifier and the domain sub-agents use the same model settings.
    This helper keeps that setup in one place so the code stays easy to read.
    '''

    return ChatOpenAI(
        api_key=api_key,
        base_url=base_url,
        model=llm_model,
        timeout=timeout_seconds,
        temperature=0,
        model_kwargs=model_kwargs or {},
    )


def _group_tools_by_domain(tools: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    '''
    Split the MCP tools into the small domain-specific collections used by the
    child agents. Right now the tool names are the simplest source of truth:
    tools containing "volume" go to the volume agent, and tools containing
    "area" go to the area agent.
    '''

    grouped_tools: dict[str, list[dict[str, Any]]] = {
        "volume": [],
        "area": [],
    }

    for tool in tools:
        tool_name = str(tool.get("name", "")).lower()
        if "volume" in tool_name:
            grouped_tools["volume"].append(tool)
        elif "area" in tool_name:
            grouped_tools["area"].append(tool)

    return grouped_tools


def _build_domain_prompt(domain_name: str, user_prompt: str) -> str:
    '''
    When a sub-agent runs, we remind it to solve only its own slice of the job.
    That keeps the volume agent from trying to answer area questions, and vice
    versa, even when the original user prompt asks for both.
    '''

    return (
        f"You are the {domain_name} specialist inside a larger workflow. "
        f"Only solve the parts of the request related to {domain_name}.\n\n"
        f"Original user request:\n{user_prompt}"
    )


def _run_domain_agent(
    domain_name: str,
    user_prompt: str,
    tools: list[dict[str, Any]],
    mcp_client: McpClient,
    api_key: str,
    base_url: str,
    llm_model: str,
    debug_graph: bool,
    timeout_seconds: float,
    max_iterations: int,
) -> str:
    '''
    This is the reusable inner agent. We use the exact same logic for both
    volume and area; the only thing that changes is the tool list and the
    small domain-specific instruction added to the user prompt.
    '''

    def dbg(message: str) -> None:
        if debug_graph:
            print(message)

    if not tools:
        raise RuntimeError(f"No {domain_name} tools were found")

    dbg(f"[graph][{domain_name}] Starting domain agent")

    llm = _create_chat_llm(
        api_key=api_key,
        base_url=base_url,
        llm_model=llm_model,
        timeout_seconds=timeout_seconds,
        model_kwargs=get_llm_response_format(tools),
    ) # This is the LLM used by the domain sub-agent

    reason_node = create_reason_node(llm=llm, dbg=dbg) # This node handles the reasoning step in the domain sub-agent
    tool_node = create_tool_node(mcp_client=mcp_client, allowed_tools=tools, dbg=dbg) # This node handles calling the appropriate tool in the domain sub-agent
    route_after_reason = create_route_after_reason(dbg=dbg) # This function decides the next step after the reasoning node

    graph = StateGraph(AgentState) # This is the state graph for the domain sub-agent
    graph.add_node("reason", reason_node) # Add the reasoning node to the domain sub-agent graph
    graph.add_node("tool", tool_node) # Add the tool node to the domain sub-agent graph
    graph.add_edge(START, "reason") # Connect the start of the graph to the reasoning node
    graph.add_conditional_edges(
        "reason",
        route_after_reason,
        {
            "run_tool": "tool",
            "finish": END,
        },
    ) # Add conditional edges from the reasoning node to either the tool node or the end node based on the route
    graph.add_edge("tool", "reason") # Connect the tool node back to the reasoning node for iterative processing

    app = graph.compile() # Compile the domain sub-agent graph into an executable app
    final_state = app.invoke(
        build_initial_state(
            _build_domain_prompt(domain_name, user_prompt),
            tools,
            max_iterations,
        )
    ) # Invoke the domain sub-agent graph with the initial state

    final_response = final_state.get("final_response")
    if not isinstance(final_response, str):
        raise RuntimeError(f"{domain_name.title()} agent finished without a final response")

    if debug_graph:
        print(f"\n{domain_name.title()} sub-agent graph (ASCII):")
        app.get_graph().print_ascii() # Print the ASCII representation of the domain sub-agent graph
        print_execution_graph_ascii(final_state["messages"], final_response) # Print the execution trace of the domain sub-agent graph

    dbg(f"[graph][{domain_name}] Completed successfully")
    return final_response


def _create_domain_runner_node(
    domain_name: str,
    tools: list[dict[str, Any]],
    mcp_client: McpClient,
    api_key: str,
    base_url: str,
    llm_model: str,
    debug_graph: bool,
    timeout_seconds: float,
    max_iterations: int,
) -> Callable[[WorkflowState], WorkflowState]:
    '''
    Create one parent-graph node that runs a domain sub-agent and stores the
    answer in the outer workflow state.
    '''

    def run_domain(state: WorkflowState) -> WorkflowState:
        response = _run_domain_agent(
            domain_name=domain_name,
            user_prompt=state["user_prompt"],
            tools=tools,
            mcp_client=mcp_client,
            api_key=api_key,
            base_url=base_url,
            llm_model=llm_model,
            debug_graph=debug_graph,
            timeout_seconds=timeout_seconds,
            max_iterations=max_iterations,
        )

        if domain_name == "volume":
            state["volume_response"] = response
        elif domain_name == "area":
            state["area_response"] = response
        else:
            raise RuntimeError(f"Unsupported domain runner: {domain_name}")

        return state

    return run_domain


def _combine_results_node(state: WorkflowState) -> WorkflowState:
    '''
    Turn the branch outputs back into one final answer for the user.
    '''

    route = state["route"]

    if route == "volume":
        final_response = state["volume_response"]
    elif route == "area":
        final_response = state["area_response"]
    elif route == "both":
        volume_response = state["volume_response"]
        area_response = state["area_response"]
        if volume_response is None or area_response is None:
            raise RuntimeError("Both-route workflow finished without both branch results")

        final_response = (
            "Volume result:\n"
            f"{volume_response}\n\n"
            "Area result:\n"
            f"{area_response}"
        )
    else:
        raise RuntimeError("Workflow combine step received an invalid route")

    if not isinstance(final_response, str):
        raise RuntimeError("Workflow combine step did not produce a final response")

    state["final_response"] = final_response
    return state


def run_agent(
    user_prompt: str,
    tools: list[dict[str, Any]],
    mcp_client: McpClient,
    api_key: str,
    base_url: str,
    llm_model: str,
    debug_graph: bool,
    timeout_seconds: float,
    max_iterations: int,
    llm_provider: str,
) -> str:
    '''
    Run a two-level LangGraph workflow.

    Level 1 is a small router graph that decides whether the question is about
    volume, area, or both.

    Level 2 is a reusable domain sub-agent. We run the same inner graph for the
    volume and area branches, but each branch receives only its own tool list.
    That means each tool node has a deliberately small and explicit tool surface.
    '''

    def dbg(message: str) -> None:
        '''
        Prints a debug message if debug_graph is True.
        '''

        if debug_graph:
            print(message)

    dbg("[graph] Initializing agent graph")
    dbg(f"[graph] Model: {llm_model}")
    dbg(f"[graph] Max iterations: {max_iterations}")

    grouped_tools = _group_tools_by_domain(tools)

    classifier_llm = _create_chat_llm(
        api_key=api_key,
        base_url=base_url,
        llm_model=llm_model,
        timeout_seconds=timeout_seconds,
        model_kwargs=CLASSIFIER_RESPONSE_FORMAT,
    )

    classifier_node = create_classifier_node(llm=classifier_llm, dbg=dbg)
    run_volume_node = _create_domain_runner_node(
        domain_name="volume",
        tools=grouped_tools["volume"],
        mcp_client=mcp_client,
        api_key=api_key,
        base_url=base_url,
        llm_model=llm_model,
        debug_graph=debug_graph,
        timeout_seconds=timeout_seconds,
        max_iterations=max_iterations,
    )
    run_area_node = _create_domain_runner_node(
        domain_name="area",
        tools=grouped_tools["area"],
        mcp_client=mcp_client,
        api_key=api_key,
        base_url=base_url,
        llm_model=llm_model,
        debug_graph=debug_graph,
        timeout_seconds=timeout_seconds,
        max_iterations=max_iterations,
    )
    route_after_classifier = create_route_after_classifier(dbg=dbg)
    route_after_volume = create_route_after_volume(dbg=dbg)

    # This outer graph does only orchestration. The actual reasoning and tool
    # calls happen inside the reusable domain sub-agents created above.
    graph = StateGraph(WorkflowState)
    graph.add_node("classify", classifier_node)
    graph.add_node("run_volume", run_volume_node)
    graph.add_node("run_area", run_area_node)
    graph.add_node("combine", _combine_results_node)
    graph.add_edge(START, "classify")
    graph.add_conditional_edges(
        "classify",
        route_after_classifier,
        {
            "run_volume": "run_volume",
            "run_area": "run_area",
        },
    )
    graph.add_conditional_edges(
        "run_volume",
        route_after_volume,
        {
            "run_area": "run_area",
            "combine": "combine",
        },
    )
    graph.add_edge("run_area", "combine")
    graph.add_edge("combine", END)

    app = graph.compile()
    dbg("[graph] Graph compiled")

    final_state = app.invoke(_build_workflow_initial_state(user_prompt))
    dbg(f"[graph] Final state: {final_state}")
    final_response = final_state.get("final_response")
    if not isinstance(final_response, str):
        raise RuntimeError("Agent finished without a final response")

    print("\nWorkflow graph (ASCII):")
    app.get_graph().print_ascii()

    dbg("[graph] Completed successfully")

    return final_response
