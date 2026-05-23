"""
PERSONA_COMPILER node — end of onboarding.

Runs once, immediately after INSPIRE completes.
Synthesises all quiz answers + inspire summary into a structured persona
profile JSON, saves it to disk, and unlocks layout mode.

State consumed:   quiz_answers (dict), inspire_summary (str)
State produced:   persona_profile (dict), user_type (str),
                  onboarding_complete (True), final_response (str)

Output file:  team_02/personas/persona.json
              (resolved as ctx.layout_input_dir.parent / "personas" / "persona.json")

Robustness layers (in order of application):
  1. LLM call → JSON profile (happy path)
  2. Brace-counting JSON extractor — handles prose before/after the JSON block
  3. Minimal-profile fallback if all parsing fails
  4. Deterministic q3 sensory patch — always applied last, ensures weights/priorities
     reflect what the user explicitly said even if the LLM under-delivered
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
  - IMPORTANT: q3 contains the user's explicit sensory bothers. Any sense named
    there must receive a weight of at least 0.75. Do not default these to 0.5.

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

_ALL_SENSES = ["thermal", "visual", "acoustic", "spatial", "olfactory", "tactile"]

_MINIMAL_PROFILE: dict = {
    "name": "User",
    "role": "client",
    "description": "User with unspecified comfort preferences",
    "age_group": None,
    "household_type": None,
    "sensory_priorities": _ALL_SENSES[:],
    "sensory_sensitivities": [],
    "comfort_weights": {s: 0.5 for s in _ALL_SENSES},
    "aesthetic_preferences": "",
    "lifestyle": "",
    "key_requirements": [],
    "preference_vs_baseline": {},
    "notes": "",
}

# Keywords used by the q3 direct-extraction fallback.
# The UI sends: "The senses that pull me out of comfort: thermal, acoustic, visual."
# so sense names appear verbatim — keyword scan is a reliable match.
_SENSE_KEYWORDS: dict[str, list[str]] = {
    "thermal":   ["thermal", "temperature", "hot", "cold", "heat", "warm"],
    "visual":    ["visual", "light", "glare", "bright", "lighting", "sunlight", "daylight"],
    "acoustic":  ["acoustic", "noise", "sound", "loud", "quiet"],
    "spatial":   ["spatial", "cramped", "crowded", "small", "tight"],
    "olfactory": ["olfactory", "smell", "odor", "odour", "air quality", "ventilation"],
    "tactile":   ["tactile", "texture", "material", "surface"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_json_object(text: str) -> str | None:
    """
    Find the first balanced {…} block that parses as valid JSON.
    Iterates over every top-level {…} block (handles prose like
    "Here's the profile {name}: {...}" where a non-JSON brace appears first).
    Returns the first candidate that json.loads() accepts, or None.
    """
    import json as _json
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start:i + 1]
                try:
                    _json.loads(candidate)
                    return candidate          # first valid JSON object wins
                except _json.JSONDecodeError:
                    start = -1              # not valid — keep scanning
    return None


def _senses_from_q3(q3_text: str) -> list[str]:
    """Return the sense names explicitly mentioned in the q3 answer."""
    t = q3_text.lower()
    return [s for s, kws in _SENSE_KEYWORDS.items() if any(kw in t for kw in kws)]


def _apply_q3_sensory_patch(persona_profile: dict, quiz_answers: dict) -> dict:
    """
    Safety net: if all comfort_weights are still at 0.5 (default / LLM failure),
    parse q3 directly and boost the weights for any senses the user named.
    Also updates sensory_priorities and sensory_sensitivities to reflect them.

    This runs even after a successful LLM call — if the LLM ignored q3 and
    left everything at 0.5, this corrects it deterministically.
    """
    weights = persona_profile.get("comfort_weights", {})
    all_default = all(abs(weights.get(s, 0.5) - 0.5) < 0.02 for s in _ALL_SENSES)

    if not all_default:
        # LLM already differentiated weights — trust it.
        return persona_profile

    q3 = quiz_answers.get("q3", "")
    if not q3:
        return persona_profile

    bothered_senses = _senses_from_q3(q3)
    if not bothered_senses:
        return persona_profile

    print(f"[persona_compiler] q3 patch — boosting weights for: {bothered_senses}")

    for sense in bothered_senses:
        weights[sense] = 0.80

    # Reorder priorities: bothered senses first, rest after
    other = [s for s in _ALL_SENSES if s not in bothered_senses]
    persona_profile["comfort_weights"]       = weights
    persona_profile["sensory_priorities"]    = bothered_senses + other
    persona_profile["sensory_sensitivities"] = bothered_senses

    return persona_profile


# ---------------------------------------------------------------------------
# Node factory
# ---------------------------------------------------------------------------

def build_persona_compiler_node(llm, persona_output_path: str):
    """
    Return the persona_compiler node function.

    Args:
        llm               : plain LLM instance (llm_simple from Context)
        persona_output_path: absolute path where persona.json will be saved
    """

    def persona_compiler_node(state: dict) -> dict:
        quiz_answers: dict    = state.get("quiz_answers") or {}
        inspire_summary: str  = state.get("inspire_summary", "")
        user_name: str        = state.get("user_name", "") or ""
        preliminary_role: str = state.get("preliminary_role", "client") or "client"

        print("[persona_compiler] Compiling full persona profile...")
        print(f"[persona_compiler] quiz_answers keys: {list(quiz_answers.keys())}")
        print(f"[persona_compiler] q3 (sensory bothers): {quiz_answers.get('q3', '(none)')[:120]}")
        print(f"[persona_compiler] inspire_summary ({len(inspire_summary)} chars): "
              f"{inspire_summary[:80].strip() or '(empty)'}...")
        print(f"[persona_compiler] user_name={user_name!r}  role={preliminary_role!r}")

        if not quiz_answers:
            print("[persona_compiler] WARNING: quiz_answers is empty — sensory data will be minimal")

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
            print(f"[persona_compiler] LLM response: {len(raw)} chars")

            clean = raw.strip()
            # Strip markdown fences if the model wrapped the JSON
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1]).strip()

            # Attempt 1: direct parse
            try:
                persona_profile = json.loads(clean)
            except json.JSONDecodeError:
                # Attempt 2: brace-counting extractor (handles prose around JSON)
                extracted = _extract_json_object(clean)
                if extracted:
                    persona_profile = json.loads(extracted)
                    print("[persona_compiler] JSON extracted via brace-counting fallback")
                else:
                    raise ValueError("No JSON object found in LLM response")

            print(f"[persona_compiler] Profile compiled for: {persona_profile.get('name', '?')}")

        except Exception as exc:
            print(f"[persona_compiler] LLM/parse error ({exc}) — using minimal profile")
            persona_profile = dict(_MINIMAL_PROFILE)
            persona_profile["notes"] = f"LLM fallback. quiz_answers: {str(quiz_answers)[:300]}"

        # ── Ensure all required keys exist ────────────────────────────────
        for key, default in _MINIMAL_PROFILE.items():
            if key not in persona_profile:
                persona_profile[key] = default

        # Ensure all six comfort_weights are present
        weights = persona_profile.get("comfort_weights", {})
        for sense in _ALL_SENSES:
            if sense not in weights:
                weights[sense] = 0.5
        persona_profile["comfort_weights"] = weights

        # ── Q3 sensory patch — deterministic safety net ───────────────────
        # Applied whether the LLM succeeded or not. If the LLM already
        # differentiated the weights, this is a no-op. If it returned all
        # 0.5s (either from fallback or LLM laziness), this fills in the
        # sensory data from the user's explicit q3 answer.
        persona_profile = _apply_q3_sensory_patch(persona_profile, quiz_answers)

        # ── Recompute preference_vs_baseline ─────────────────────────────
        pvb = persona_profile.get("preference_vs_baseline") or {}
        if not pvb:
            weights = persona_profile.get("comfort_weights", {})
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

        # ── Patch name / role from session if LLM missed them ─────────────
        stored_name = persona_profile.get("name", "")
        if not stored_name or stored_name.lower() in ("user", "there", ""):
            if user_name and user_name.lower() not in ("there", ""):
                persona_profile["name"] = user_name.strip().capitalize()
                print(f"[persona_compiler] Name patched from session: {persona_profile['name']}")

        stored_role = persona_profile.get("role", "client")
        if stored_role == "client" and preliminary_role not in ("client", "", None):
            persona_profile["role"] = preliminary_role
            print(f"[persona_compiler] Role patched from session: {preliminary_role}")

        # ── Save to disk ──────────────────────────────────────────────────
        save_ok = False
        try:
            os.makedirs(os.path.dirname(persona_output_path), exist_ok=True)
            with open(persona_output_path, "w", encoding="utf-8") as f:
                json.dump(persona_profile, f, indent=2, ensure_ascii=False)
            save_ok = True
            print(f"[persona_compiler] Persona saved -> {persona_output_path}")
            weights_summary = {s: round(persona_profile["comfort_weights"].get(s, 0.5), 2) for s in _ALL_SENSES}
            print(f"[persona_compiler] Weights: {weights_summary}")
        except Exception as exc:
            print(f"[persona_compiler] WARNING: could not save persona file: {exc}")

        if not save_ok:
            print(f"[persona_compiler] Save path was: {persona_output_path!r}")

        # ── Build final response ──────────────────────────────────────────
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
            "persona_profile":     persona_profile,
            "user_type":           role,
            "onboarding_complete": True,
            "final_response":      response,
        }

    return persona_compiler_node
