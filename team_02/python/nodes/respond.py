"""
nodes/respond.py — RESPOND node for the Comfort Copilot state graph.

LLM node. Runs last on the comfort path, after all tool nodes have finished.
Reads the raw JSON results from state and produces a natural language report
for the user — no JSON, no markdown tables, just clear prose.

Reads from state:
  raw_prompt             (str)       — original user request
  persona_detected       (str)       — e.g. "Elderly 65+"
  layout_id              (str)       — e.g. "201"
  comfort_depth          (str)       — "analyze" | "detect" | "full"
  last_scores_json       (str)       — output of compute_comfort_scores
  last_conflicts_json    (str | "")  — output of detect_sensorial_conflicts
  last_suggestions_json  (str | "")  — output of generate_suggestions

Writes to state:
  final_response  (str)  — the formatted natural language report
"""

from __future__ import annotations
from _runtime.llm import call_llm_simple


_SYSTEM_PROMPT = """\
You are Comfort Copilot, an architectural comfort analyst specialising in
multi-sensory wellbeing across six dimensions: thermal, visual, acoustic,
spatial, olfactory, and tactile.

You have just run an analysis of an apartment layout. Below you will find the
raw JSON results. Your job is to translate them into a clear, readable report
that combines the actual scores with plain-language interpretation.

Guidelines:
- Address the persona by name (e.g. "For an Elderly 65+ user...").
- Go room by room. For each room, list every comfort dimension with its score
  in parentheses (e.g. "Thermal (0.74) - good temperature stability") and a
  one-line plain-language note. Scores range from 0.0 (very poor) to 1.0
  (excellent).
- After the scores, add a short 1-2 sentence summary of that room's overall
  comfort situation and what stands out for this persona.
- If conflict data is provided, list each flagged conflict clearly under a
  "Conflicts" heading. Name the room, the sense, and why it matters.
- If suggestion data is provided, list improvements under a "Suggestions"
  heading, grouped by room, using action language ("Add acoustic panels").
- Keep tone warm and professional.
- End with one sentence summarising the overall comfort level of the layout.
- Do not mention JSON, schemas, thresholds, or internal tool names.
"""


def build_respond_node(llm):
    """Return the respond node function, capturing the LLM instance."""

    def respond_node(state: dict) -> dict:
        persona       = state.get("persona_detected", "Neutral")
        layout_id     = state.get("layout_id", "?")
        depth         = state.get("comfort_depth", "analyze")
        scores        = state.get("last_scores_json", "")
        conflicts     = state.get("last_conflicts_json", "")
        suggestions   = state.get("last_suggestions_json", "")
        raw_prompt    = state.get("raw_prompt", "")

        # Build the user message — include only the data that was actually computed
        sections: list[str] = [
            f"User request: {raw_prompt}",
            f"Persona: {persona}",
            f"Layout ID: {layout_id}",
            f"Analysis depth: {depth}",
            "",
            "--- COMFORT SCORES ---",
            scores or "(not computed)",
        ]

        if conflicts:
            sections += ["", "--- CONFLICTS ---", conflicts]

        if suggestions:
            sections += ["", "--- SUGGESTIONS ---", suggestions]

        user_message = "\n".join(sections)

        print(f"[respond] Generating natural language report...")
        response = call_llm_simple(llm, _SYSTEM_PROMPT, user_message)

        return {
            **state,
            "final_response": response,
        }

    return respond_node
