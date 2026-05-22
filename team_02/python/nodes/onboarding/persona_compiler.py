"""
PERSONA_COMPILER node — end of onboarding.

Runs once, immediately after INSPIRE completes.
Synthesises all quiz answers + inspire summary into a structured persona
profile JSON, saves it to disk, and unlocks layout mode.

State consumed:   quiz_answers (dict), inspire_summary (str)
State produced:   persona_profile (dict), user_type (str),
                  onboarding_complete (True), final_response (str)

Output file:  team_02/persona.json
              (resolved as ctx.layout_input_dir.parent / "persona.json")
"""

from __future__ import annotations
import json
import os
from _runtime.llm import call_llm_simple


_SYSTEM_PROMPT = """\
You are Sensi's persona compiler.

Synthesise the quiz answers and aesthetic summary below into a single,
structured comfort persona profile. This profile will drive all comfort
analysis and response personalisation for this user.

INPUT you will receive:
  QUIZ ANSWERS — keys q0 (intro / who are you?) through q5 (ideal space)
  INSPIRE SUMMARY — a paragraph describing aesthetic and sensory preferences

OUTPUT — return ONLY this JSON schema, no explanation, no markdown fences:

{
  "name": "<first name if given, else User>",
  "role": "architect" | "client" | "student",
  "description": "<one sentence: who they are and their comfort situation>",
  "age_group": "child" | "young_adult" | "adult" | "elderly" | null,
  "household_type": "single" | "dual" | "family" | null,
  "sensory_priorities": [
    "<ranked list — most important first — from: thermal, visual, acoustic, spatial, olfactory, tactile>"
  ],
  "sensory_sensitivities": [
    "<specific sensitivities or intolerances mentioned by the user>"
  ],
  "comfort_weights": {
    "thermal":   <0.0-1.0>,
    "visual":    <0.0-1.0>,
    "acoustic":  <0.0-1.0>,
    "spatial":   <0.0-1.0>,
    "olfactory": <0.0-1.0>,
    "tactile":   <0.0-1.0>
  },
  "aesthetic_preferences": "<concise distillation of their sensory aesthetic world>",
  "lifestyle": "<how they mainly use their home>",
  "key_requirements": ["<up to 3 non-negotiables the user explicitly stated>"],
  "notes": "<anything else relevant that does not fit above>"
}

comfort_weights rules:
  - Derive from sensory priorities and explicit sensitivities.
  - High sensitivity to a sense -> weight closer to 1.0 (flags issues more aggressively).
  - Sense explicitly stated as non-priority -> weight 0.3.
  - Sense not mentioned -> default 0.5.
  - All six senses must appear.

STATED PREFERENCES vs RESEARCH BASELINES:
After deriving comfort_weights from the user's stated preferences, compare each
weight against these evidence-based research baselines. Where the user's stated
weight deviates by more than 0.25, note it in preference_vs_baseline.

Research baselines (evidence-based minimum comfort thresholds):
  thermal:   0.70  -- thermal discomfort is the #1 cause of occupant complaints
  visual:    0.60  -- adequate daylighting is linked to productivity and sleep
  acoustic:  0.65  -- chronic noise exposure causes measurable stress responses
  spatial:   0.50  -- spatial adequacy affects psychological restoration
  olfactory: 0.40  -- air quality threshold; lower risk unless sensitivity stated
  tactile:   0.35  -- lowest baseline; only flagged for explicit sensitivities

Add this field to the JSON output:
  "preference_vs_baseline": {
    "<sense>": "<brief note if user's weight differs from baseline by >0.25>"
    // omit senses where user and baseline are aligned
  }

Return ONLY the JSON object. Nothing else.
"""

_COMFORT_BASELINES: dict = {
    "thermal":   0.70,
    "visual":    0.60,
    "acoustic":  0.65,
    "spatial":   0.50,
    "olfactory": 0.40,
    "tactile":   0.35,
}

_MINIMAL_PROFILE: dict = {
    "name": "User",
    "role": "client",
    "description": "User with unspecified comfort preferences",
    "age_group": None,
    "household_type": None,
    "sensory_priorities": ["thermal", "visual", "acoustic", "spatial", "olfactory", "tactile"],
    "sensory_sensitivities": [],
    "comfort_weights": {s: 0.5 for s in ["thermal", "visual", "acoustic", "spatial", "olfactory", "tactile"]},
    "aesthetic_preferences": "",
    "lifestyle": "",
    "key_requirements": [],
    "preference_vs_baseline": {},
    "notes": "",
}


def build_persona_compiler_node(llm, persona_output_path: str):
    """
    Return the persona_compiler node function.

    Args:
        llm               : plain LLM instance (llm_simple from Context)
        persona_output_path: absolute path where persona.json will be saved
    """

    def persona_compiler_node(state: dict) -> dict:
        quiz_answers: dict = state.get("quiz_answers") or {}
        inspire_summary: str = state.get("inspire_summary", "")

        print("[persona_compiler] Compiling full persona profile...")

        # ── Build the input message for the LLM ──────────────────────────
        quiz_block = "\n".join(
            f"  {k}: {v}" for k, v in sorted(quiz_answers.items())
        ) or "  (no answers recorded)"

        user_message = (
            "QUIZ ANSWERS:\n"
            + quiz_block
            + "\n\nINSPIRE SUMMARY:\n"
            + (inspire_summary.strip() or "(no aesthetic summary provided)")
        )

        # ── Call LLM ──────────────────────────────────────────────────────
        persona_profile: dict = {}
        try:
            raw = call_llm_simple(llm, _SYSTEM_PROMPT, user_message)
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1]).strip()
            persona_profile = json.loads(clean)
            print(f"[persona_compiler] Profile compiled for: {persona_profile.get('name', '?')}")
        except Exception as exc:
            print(f"[persona_compiler] LLM error ({exc}) — falling back to minimal profile")
            persona_profile = dict(_MINIMAL_PROFILE)
            persona_profile["notes"] = str(quiz_answers)

        # ── Ensure all required keys exist ────────────────────────────────
        for key, default in _MINIMAL_PROFILE.items():
            if key not in persona_profile:
                persona_profile[key] = default

        # Ensure all six comfort_weights are present
        weights = persona_profile.get("comfort_weights", {})
        for sense in ["thermal", "visual", "acoustic", "spatial", "olfactory", "tactile"]:
            if sense not in weights:
                weights[sense] = 0.5
        persona_profile["comfort_weights"] = weights

        # Compute preference_vs_baseline if LLM omitted it or left it empty
        pvb = persona_profile.get("preference_vs_baseline") or {}
        if not pvb:
            for sense, baseline in _COMFORT_BASELINES.items():
                user_w = weights.get(sense, 0.5)
                delta  = user_w - baseline
                if abs(delta) > 0.25:
                    direction = "above" if delta > 0 else "below"
                    note = (
                        "User rates this highly -- aligns well with research."
                        if delta > 0 else
                        "User rates this low -- research flags it as a consistent comfort risk."
                    )
                    pvb[sense] = (
                        f"Stated weight {user_w:.2f} is {direction} research "
                        f"baseline {baseline:.2f} (delta {delta:+.2f}). {note}"
                    )
        persona_profile["preference_vs_baseline"] = pvb
        if pvb:
            print(f"[persona_compiler] Preference vs baseline deviations: {list(pvb.keys())}")

        # -- Save to disk -----------------------------------------------------
        try:
            os.makedirs(os.path.dirname(persona_output_path), exist_ok=True)
            with open(persona_output_path, "w", encoding="utf-8") as f:
                json.dump(persona_profile, f, indent=2, ensure_ascii=False)
            print(f"[persona_compiler] Persona saved -> {persona_output_path}")
        except Exception as exc:
            print(f"[persona_compiler] WARNING: could not save persona file: {exc}")

        # -- Build final response ---------------------------------------------
        name = persona_profile.get("name", "you")
        role = persona_profile.get("role", "client")
        priorities = persona_profile.get("sensory_priorities", [])
        top_senses = ", ".join(priorities[:3]) if priorities else "comfort overall"

        response = (
            f"Your profile is ready, {name}! "
            f"I now know you as a {role} who cares most about {top_senses}. "
            "I've saved your comfort profile so you won't need to set this up again. "
            "\n\n"
            "Whenever you're ready, tell me which layout you'd like to explore "
            "(201, 202, or 203) and we'll get started."
        )

        return {
            **state,
            "persona_profile":    persona_profile,
            "user_type":          role,
            "onboarding_complete": True,
            "final_response":     response,
        }

    return persona_compiler_node
