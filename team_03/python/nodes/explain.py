from __future__ import annotations
from typing import TYPE_CHECKING, Any
from _runtime.llm import call_llm, call_llm_simple

if TYPE_CHECKING:
    from graph import AgentState


def explain_node(state: AgentState) -> dict:
    # Called only once, immediately after the user approves at the checkpoint.
    # The LLM receives a compact summary of every tool's results so it can
    # give grounded feedback without re-reading the full layout JSON.

    scoring    = state.get("scoring_results") or {}
    collision  = state.get("collision_results") or {}
    path       = state.get("path_results") or {}

    score     = scoring.get("total_score", 0)
    grade     = scoring.get("grade", "?")
    breakdown = scoring.get("breakdown", {})

    # Build a concise text summary the LLM can reason over quickly.
    analysis_summary = (
        f"Layout score: {score:.1f}/100  Grade: {grade}\n\n"
        f"Tool breakdown:\n"
        f"- Collision:    {breakdown.get('collision',    {}).get('score', 0):.0f}/100\n"
        f"- Visibility:   {breakdown.get('visibility',   {}).get('score', 0):.0f}/100\n"
        f"- Path:         {breakdown.get('path',         {}).get('score', 0):.0f}/100\n"
        f"- Reachability: {breakdown.get('reachability', {}).get('score', 0):.0f}/100\n"
        f"- Orientation:  {breakdown.get('orientation',  {}).get('score', 0):.0f}/100\n\n"
    )

    # Include the top collision violations so the LLM can name specific issues.
    violations = collision.get("violations", [])
    if violations:
        analysis_summary += "Collision issues:\n"
        for v in violations[:3]:
            analysis_summary += f"  - {v}\n"

    # Worst-case path distance gives the LLM a concrete distance to cite.
    wc = path.get("worst_case", {})
    if wc.get("from"):
        analysis_summary += (
            f"\nLongest path: {wc['from']} -> {wc['to']} ({wc['distance']}m)\n"
        )

    # Build the prompt by concatenation — avoids .format() choking on any
    # literal braces that appear in the analysis summary or layout JSON.
    prompt = (
        "You are a spatial design expert.\n"
        "The user has approved a layout.\n\n"
        "Analysis results:\n" + analysis_summary +
        "\nLayout JSON (first 2000 chars):\n" +
        state["layout_json_string"][:2000] +
        "\n\nWrite a clear 3-5 sentence explanation covering: "
        "overall assessment, main strengths, key weaknesses, "
        "one specific recommendation. "
        "Reference actual object names and distances.\n\n"
        "Respond with action final and put your explanation in final_response."
    )

    try:
        result = call_llm(
            state.get("_llm"),
            prompt,
            state["messages"],
            state["tool_catalog"],
        )
        explanation = result.get("final_response", "Layout approved and saved.")
    except Exception:
        # LLM may return markdown/text instead of JSON — use call_llm_simple
        # as a fallback to get the raw text response.
        try:
            raw = call_llm_simple(state.get("_llm"), prompt, "Generate the explanation.")
            if raw and isinstance(raw, dict):
                explanation = raw.get("final_response", str(raw))
            else:
                explanation = "Layout approved and saved."
        except Exception as exc2:
            print(f"[explain] Fallback also failed: {exc2}")
            explanation = "Layout approved and saved."
    print(f"\nLayout Explanation:\n{explanation}")
    return {"final_response": explanation}
