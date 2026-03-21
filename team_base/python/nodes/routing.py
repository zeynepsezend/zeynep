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
    Decide which top-level branch should run next.

    - volume -> run only the volume branch
    - area -> run only the area branch
    - both -> go to a fan-out node that launches volume and area in parallel
    '''

    def route_after_classifier(state: WorkflowState) -> str:
        route = state["route"]
        if route == "volume":
            dbg("[graph][route] classify -> run_volume_only")
            return "run_volume_only"
        if route == "area":
            dbg("[graph][route] classify -> run_area_only")
            return "run_area_only"
        if route == "both":
            dbg("[graph][route] classify -> fan_out_both")
            return "fan_out_both"
        raise RuntimeError("Workflow classifier did not choose a valid route")

    return route_after_classifier


