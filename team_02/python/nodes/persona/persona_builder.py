"""
PERSONA_BUILDER node — multi-turn fluid persona building via LLM.
Extracts and merges persona info from each message into persona_profile dict.
Handles single and dual occupancy. Asks ONE follow-up question if profile is
incomplete; passes through silently when completion_status is "complete".
"""

from __future__ import annotations
import json
from _runtime.llm import call_llm_simple


_EXTRACT_SYSTEM_PROMPT = """\
You are a persona extraction assistant for an architectural comfort analysis tool.

Your job: read the user's message and the existing partial persona profile,
then return an UPDATED persona_profile JSON.

The persona_profile schema:
{{
  "primary_user": {{
    "description": "<free text, e.g. 'single mother, 38, works from home'>",
    "age_group": "child" | "young_adult" | "adult" | "elderly" | null,
    "sensory_priorities": ["thermal", "acoustic", "visual", "spatial", "olfactory", "tactile"],
    "sensory_sensitivities": ["<e.g. sensitive to noise>", "<e.g. glare intolerant>"],
    "mobility": "full" | "limited" | "wheelchair" | null,
    "use_patterns": {{"<room_type>": "<how they use it>"}},
    "notes": "<any other relevant context>"
  }},
  "secondary_user": null,
  "household_type": "single" | "dual" | "family" | null,
  "completion_status": "complete" | "partial" | "minimal"
}}

completion_status rules:
  complete — age_group AND at least one sensory_priority are known for ALL users
  partial  — age_group OR sensory_priorities known, but not both
  minimal  — almost nothing known yet

Instructions:
  - Merge new info from the message into the existing profile. Never erase existing data.
  - If the user mentions a second person ("grandma", "child", "partner"), populate secondary_user.
  - Set household_type: "single" for one person, "dual" for two adults, "family" for children present.
  - Set completion_status honestly.
  - Return ONLY the updated JSON. No explanation. No markdown.

EXISTING PROFILE (may be empty {{}}):
{existing_profile}

USER MESSAGE:
{raw_prompt}
"""

_QUESTION_SYSTEM_PROMPT = """\
You are Sensi, building a comfort profile for an architectural analysis.

You have a partial persona profile. Ask the user for the SINGLE most important
missing piece of information.

Priority order for missing info:
  1. Age or life stage (if unknown) — "How old is the person you're designing for?"
  2. Main sensory sensitivities — "Is she more sensitive to noise, light, temperature, or something else?"
  3. How they use the key rooms — "Does she spend most of her time in the bedroom or the living room?"

Rules:
  - Ask ONLY ONE question. Never ask two things at once.
  - Be warm and conversational, not clinical or robotic.
  - Keep it short: one sentence question maximum.
  - Reference what you already know to show you were listening.

WHAT YOU KNOW SO FAR:
{known_so_far}
"""


def build_persona_builder_node(llm):
    """Return the persona_builder node function, capturing the LLM instance."""

    def persona_builder_node(state: dict) -> dict:
        raw_prompt: str = state.get("raw_prompt", "")
        existing_profile: dict = state.get("persona_profile") or {}
        user_type: str = state.get("user_type", "learner")

        print("[persona_builder] Building persona profile...")

        # ── Step 1: Extract any new info from current message ─────────────
        extract_prompt = _EXTRACT_SYSTEM_PROMPT.format(
            existing_profile=json.dumps(existing_profile, indent=2),
            raw_prompt=raw_prompt,
        )
        updated_profile = existing_profile.copy()
        try:
            raw_extract = call_llm_simple(llm, extract_prompt, raw_prompt)
            clean = raw_extract.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1]).strip()
            updated_profile = json.loads(clean)
            print(f"[persona_builder] completion_status={updated_profile.get('completion_status', '?')}")
        except Exception as exc:
            print(f"[persona_builder] Extraction error ({exc}) — keeping existing profile")

        result = {**state, "persona_profile": updated_profile}

        # ── Step 2: If profile complete, no question needed ───────────────
        if updated_profile.get("completion_status") == "complete":
            print("[persona_builder] Profile complete — no question needed")
            return result

        # ── Step 3: Profile incomplete — generate ONE follow-up question ──
        primary = updated_profile.get("primary_user", {})
        secondary = updated_profile.get("secondary_user")
        known_parts = []
        if primary.get("description"):
            known_parts.append(primary["description"])
        if primary.get("age_group"):
            known_parts.append(f"age group: {primary['age_group']}")
        if primary.get("sensory_priorities"):
            known_parts.append(f"sensory priorities: {', '.join(primary['sensory_priorities'])}")
        if secondary:
            known_parts.append("dual occupancy household")
        known_so_far = "; ".join(known_parts) if known_parts else "nothing yet"

        question_prompt = _QUESTION_SYSTEM_PROMPT.format(known_so_far=known_so_far)
        try:
            question = call_llm_simple(llm, question_prompt, "")
            print(f"[persona_builder] Asking follow-up: {question[:80]}...")
            result["final_response"] = question
        except Exception as exc:
            print(f"[persona_builder] Question error ({exc})")
            result["final_response"] = (
                "Could you tell me a bit more about the person you're designing for? "
                "Their age and main sensory sensitivities would really help."
            )

        return result

    return persona_builder_node
