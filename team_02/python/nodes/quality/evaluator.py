"""
EVALUATOR node — quality gate before the response reaches the user.
Checks coherence, completeness, and tone (per user_type).
Returns APPROVED or REVISE with a one-sentence instruction. Max 1 loop.
"""

from __future__ import annotations
import json
from _runtime.llm import call_llm_simple


_SYSTEM_PROMPT = """\
You are a quality reviewer for an architectural comfort analysis tool.

Review the response draft below and decide: APPROVED or REVISE.

Evaluation criteria:
  Coherence  — Does it flow logically? No contradictions? No abrupt jumps?
  Completeness — Does it cover what was asked at the right depth?
               analyze → scores and their meaning
               detect  → conflicts and what is failing
               full    → suggestions, ranked, with reasoning
  Tone       — Is it appropriate for this user?
               architect → professional, concise, technically confident
               client    → warm, plain language, no jargon, human-centred
               learner   → educational, curious, explains concepts briefly

Return ONLY:
  APPROVED
  — or —
  REVISE: [specific instruction in one sentence, e.g. "Add a closing summary sentence" or
           "The tone is too technical for a client — simplify the language in the bedroom section"]

Nothing else. No explanation beyond the instruction.

USER TYPE: {user_type}
ANALYSIS DEPTH: {comfort_depth}
PERSONA: {persona_summary}

RESPONSE DRAFT:
{response_draft}
"""


def build_evaluator_node(llm):
    """Return the evaluator node function, capturing the LLM instance."""

    def evaluator_node(state: dict) -> dict:
        final_response: str = state.get("final_response") or ""
        user_type: str = state.get("user_type", "architect")
        comfort_depth: str = state.get("comfort_depth", "analyze")
        persona_profile: dict = state.get("persona_profile") or {}
        loops: int = state.get("evaluator_loops", 0)

        new_loops = loops + 1
        print(f"[evaluator] Evaluating response (loop {new_loops}/1)...")

        # Build persona summary
        primary = persona_profile.get("primary_user", {})
        persona_summary = primary.get("description", "no specific persona")

        system = _SYSTEM_PROMPT.format(
            user_type=user_type,
            comfort_depth=comfort_depth,
            persona_summary=persona_summary,
            response_draft=final_response,
        )

        decision = "APPROVED"
        feedback = ""

        try:
            raw = call_llm_simple(llm, system, "Evaluate this response.")
            raw = raw.strip()
            if raw.upper().startswith("APPROVED"):
                decision = "APPROVED"
                print("[evaluator] APPROVED")
            elif raw.upper().startswith("REVISE"):
                decision = "REVISE"
                # Extract the instruction after "REVISE:"
                if ":" in raw:
                    feedback = raw.split(":", 1)[1].strip()
                else:
                    feedback = raw[6:].strip()
                print(f"[evaluator] REVISE — {feedback[:80]}")
            else:
                # Unclear response — default to APPROVED to avoid infinite loop
                decision = "APPROVED"
                print(f"[evaluator] Unclear response '{raw[:40]}' — defaulting to APPROVED")
        except Exception as exc:
            decision = "APPROVED"
            print(f"[evaluator] LLM error ({exc}) — defaulting to APPROVED")

        return {
            **state,
            "evaluator_decision": decision,
            "evaluator_feedback": feedback,
            "evaluator_loops": new_loops,
        }

    return evaluator_node
