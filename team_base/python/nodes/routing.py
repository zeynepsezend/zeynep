from typing import Any, Callable, TypedDict


class WorkflowState(TypedDict):
    '''
    The outer workflow state decides which domain-specific sub-agent should run.

    Think of this as the "project manager" state. It does not store the inner
    tool-calling conversation history. Instead, it stores the user's prompt,
    the chosen route, and the finished result from each domain sub-agent.
    '''

    user_prompt: str
    route: str | None
    volume_response: str | None
    area_response: str | None
    final_response: str | None


def create_route_after_reason(dbg: Callable[[str], None]) -> Callable[[dict[str, Any]], str]:
    '''
    Decide whether to finish the workflow or run the tool node next.
    '''

    def route_after_reason(state: dict[str, Any]) -> str:
        if state["final_response"] is not None:
            dbg("[graph][route] reason -> finish")
            return "finish"
        dbg("[graph][route] reason -> run_tool")
        return "run_tool"

    return route_after_reason


def create_route_after_classifier(dbg: Callable[[str], None]) -> Callable[[WorkflowState], str]:
    '''
    Decide which domain branch should run first.

    For the "both" route we deliberately start with volume and then continue to
    area. Doing the two branches sequentially keeps the workflow simple for a
    novice reader while still separating the two domains cleanly.
    '''

    def route_after_classifier(state: WorkflowState) -> str:
        route = state["route"]
        if route == "volume":
            dbg("[graph][route] classify -> run_volume")
            return "run_volume"
        if route == "area":
            dbg("[graph][route] classify -> run_area")
            return "run_area"
        if route == "both":
            dbg("[graph][route] classify -> run_volume -> run_area")
            return "run_volume"
        raise RuntimeError("Workflow classifier did not choose a valid route")

    return route_after_classifier


def create_route_after_volume(dbg: Callable[[str], None]) -> Callable[[WorkflowState], str]:
    '''
    After the volume branch finishes, either continue to the area branch or go
    straight to the final combine step.
    '''

    def route_after_volume(state: WorkflowState) -> str:
        if state["route"] == "both":
            dbg("[graph][route] run_volume -> run_area")
            return "run_area"

        dbg("[graph][route] run_volume -> combine")
        return "combine"

    return route_after_volume


