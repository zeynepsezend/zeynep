"""
nodes/analyze.py — ANALYZE node for the Comfort Copilot state graph.

Pure Python — no LLM. Directly calls the compute_comfort_scores MCP tool.

Reads from state:
  layout_json_string  (str)  — full layout JSON
  persona_detected    (str)  — persona name (e.g. "Elderly 65+")

Writes to state:
  last_scores_json    (str)  — unwrapped JSON string from compute_comfort_scores
"""

from __future__ import annotations
from nodes.utils import unwrap_mcp_result


def build_analyze_node(mcp_client):
    """Return the analyze node function, capturing the MCP client."""

    def analyze_node(state: dict) -> dict:
        layout_json = state.get("layout_json_string", "")
        persona     = state.get("persona_detected", "Neutral")

        if not layout_json:
            raise RuntimeError("[analyze] No layout loaded — cannot compute comfort scores.")

        print(f"[analyze] Calling compute_comfort_scores (persona={persona})")

        raw_output = mcp_client.call_tool(
            "compute_comfort_scores",
            {
                "layout_json": layout_json,
                "persona":     persona,
            },
        )

        scores_json = unwrap_mcp_result(raw_output)
        print(f"[analyze] Scores received ({len(scores_json)} chars)")

        return {
            **state,
            "last_scores_json": scores_json,
        }

    return analyze_node
