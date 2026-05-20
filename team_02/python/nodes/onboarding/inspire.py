"""
INSPIRE node — two modes:

  ONBOARDING MODE  (onboarding_complete = False):
    A two-sub-step aesthetic profiler, mandatory in the onboarding flow.
    The node runs twice across two turns:

      Turn A  — asks the user to describe their aesthetic world freely.
                Sets inspire_prompted = True. Returns to END (waits for answer).
      Turn B  — captures the answer, synthesises it into inspire_summary.
                Sets inspire_complete = True. Routes to PERSONA_COMPILER.

    Designed so the GUI phase can replace the text description with a live
    visual moodboard (Unsplash queries, image picking) without changing the
    node's contract — only the internal rendering changes.

  LAYOUT MODE  (onboarding_complete = True):
    Phase 3 placeholder. Returns a holding message for visual moodboard
    generation (coming with the GUI).

State consumed:   onboarding_complete, inspire_prompted, inspire_complete,
                  raw_prompt
State produced:   inspire_prompted (bool), inspire_summary (str),
                  inspire_complete (bool), final_response (str)
"""

from __future__ import annotations
from _runtime.llm import call_llm_simple


# ── Onboarding prompts ────────────────────────────────────────────────────────

_AESTHETIC_QUESTION = (
    "Now for the part I love most — let's talk about atmosphere. "
    "\n\n"
    "Think of spaces that have genuinely moved you: a room, a hotel, a landscape, "
    "a restaurant, a scene from a film. What did they feel like? "
    "What colors, textures, quality of light, or mood comes to mind? "
    "\n\n"
    "Describe your ideal sensory world as freely as you like — "
    "there are no wrong answers here."
)

_SYNTHESIS_SYSTEM_PROMPT = """\
You are Sensi, synthesising a user's aesthetic and sensory world into an
inspire_summary that will feed directly into the comfort persona compiler.

You will receive one of two input formats:
  A) A combined block containing a visual analysis (from reference images the
     user uploaded) PLUS their written description. Synthesise both sources.
  B) A plain free-form description only.

Capture:
  - Key colors, materials, or finishes mentioned or implied
  - Quality of light  (bright, diffuse, warm, cool, dramatic, soft, natural...)
  - Mood and atmosphere words
  - Spatial qualities  (open, intimate, layered, high-ceiling, cosy, grand...)
  - The emotional or sensory feeling they are seeking

Format: a short paragraph of 4–6 sentences, written in second person.
Start with: "You gravitate toward..."

Make it specific and grounded — avoid vague compliments or filler.
Return ONLY the paragraph. No headers. No markdown.
"""

_ONBOARDING_TRANSITION = (
    "That's a vivid picture — I can feel the atmosphere you're describing. "
    "Let me now bring all of this together into your full comfort profile."
)

# ── Layout-mode placeholder ───────────────────────────────────────────────────

_LAYOUT_PLACEHOLDER = (
    "The visual Inspire mode — real-time moodboard generation with image references — "
    "is coming with the GUI. For now, continue using the comfort analysis tools to "
    "explore and refine your layout."
)


# ── Node factory ──────────────────────────────────────────────────────────────

def build_inspire_node(llm):
    """Return the inspire node function, capturing the LLM instance."""

    def inspire_node(state: dict) -> dict:
        onboarding_complete: bool = state.get("onboarding_complete", False)

        # ── LAYOUT MODE ───────────────────────────────────────────────────
        if onboarding_complete:
            print("[inspire] Layout mode — returning placeholder")
            return {
                **state,
                "final_response": _LAYOUT_PLACEHOLDER,
            }

        # ── ONBOARDING MODE ───────────────────────────────────────────────
        inspire_prompted: bool = state.get("inspire_prompted", False)

        # Sub-step A: ask the aesthetic question
        if not inspire_prompted:
            print("[inspire] Onboarding A — asking aesthetic question")
            return {
                **state,
                "inspire_prompted": True,
                "final_response": _AESTHETIC_QUESTION,
            }

        # Sub-step B: capture and synthesise the answer
        raw_prompt: str           = state.get("raw_prompt", "")
        image_analysis: str       = state.get("inspire_image_analysis", "")
        print("[inspire] Onboarding B — synthesising inspire summary")

        # Build synthesis input: merge VLM image analysis with text description if present
        if image_analysis:
            synthesis_input = (
                f"=== Visual aesthetic analysis from reference images ===\n"
                f"{image_analysis}\n\n"
                f"=== User's written description and moodboard context ===\n"
                f"{raw_prompt}"
            )
            print("[inspire] Including VLM image analysis in synthesis")
        else:
            synthesis_input = raw_prompt

        inspire_summary: str = raw_prompt  # safe fallback
        try:
            inspire_summary = call_llm_simple(llm, _SYNTHESIS_SYSTEM_PROMPT, synthesis_input)
            print(f"[inspire] Summary: {inspire_summary[:80]}...")
        except Exception as exc:
            print(f"[inspire] LLM synthesis failed ({exc}) — storing raw answer")

        return {
            **state,
            "inspire_summary": inspire_summary,
            "inspire_complete": True,
            "final_response": _ONBOARDING_TRANSITION,
        }

    return inspire_node
