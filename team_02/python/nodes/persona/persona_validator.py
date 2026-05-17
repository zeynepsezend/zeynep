"""
PERSONA_VALIDATOR node — checks if persona_profile has enough info to run analysis.
Returns: ready / incomplete / unsure (unsure routes to ADVISOR).
Loop guard: after 3 loops, forces "ready" to avoid asking indefinitely.
"""

from __future__ import annotations
import json
from _runtime.llm import call_llm_simple


_SYSTEM_PROMPT = """\
You are a validation assistant for an architectural comfort analysis tool.

You receive a persona_profile JSON and the user's latest message.
Your ONLY job is to decide if the profile is ready for comfort analysis.

Return exactly ONE word:
  ready      — the profile has age_group AND at least one sensory_priority for
               every user in the household. Analysis can proceed.
  incomplete — critical information is still missing. Do NOT list what is missing —
               PERSONA_BUILDER will ask for it. Just return "incomplete".
  unsure     — the user's message contains phrases like "I don't know", "I'm not sure
               where to start", "advise me", "what do you think", or similar signals
               that they want guidance rather than analysis. Send them to the advisor.

Return ONLY one of: ready, incomplete, unsure
No explanation. No punctuation.

PERSONA PROFILE:
{persona_profile}

USER MESSAGE:
{raw_prompt}
"""


def build_persona_validator_node(llm):
    """Return the persona_validator node function, capturing the LLM instance."""

    def persona_validator_node(state: dict) -> dict:
        persona_profile: dict = state.get("persona_profile") or {}
        raw_prompt: str = state.get("raw_prompt", "")
        loops: int = state.get("persona_validator_loops", 0)

        # Increment loop counter
        new_loops = loops + 1

        print(f"[persona_validator] Validating profile (loop {new_loops}/3)...")

        decision = "incomplete"  # safe default

        # Fast-path: if completion_status is already "complete" in the profile
        if persona_profile.get("completion_status") == "complete":
            decision = "ready"
            print("[persona_validator] Fast-path: profile already complete")
        else:
            try:
                user_message = (
                    f"PERSONA PROFILE:\n{json.dumps(persona_profile, indent=2)}"
                    f"\n\nUSER MESSAGE:\n{raw_prompt}"
                )
                raw = call_llm_simple(llm, _SYSTEM_PROMPT.format(
                    persona_profile=json.dumps(persona_profile, indent=2),
                    raw_prompt=raw_prompt,
                ), "validate")
                candidate = raw.strip().lower().split()[0].rstrip(".,;:")
                if candidate in ("ready", "incomplete", "unsure"):
                    decision = candidate
                    print(f"[persona_validator] decision={decision}")
                else:
                    print(f"[persona_validator] Unexpected response '{candidate}' — defaulting to incomplete")
            except Exception as exc:
                print(f"[persona_validator] LLM error ({exc}) — defaulting to incomplete")

        # Loop guard: after 3 attempts, force proceed with whatever we have
        if decision == "incomplete" and new_loops >= 3:
            print("[persona_validator] Max loops reached — proceeding with partial profile")
            decision = "ready"

        return {
            **state,
            "persona_validator_decision": decision,
            "persona_validator_loops": new_loops,
        }

    return persona_validator_node
