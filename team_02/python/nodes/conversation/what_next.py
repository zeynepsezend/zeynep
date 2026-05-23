"""
WHAT_NEXT node — offers 2-3 contextual next steps after every complete turn.
Adapts suggestions to what just ran (analyze/detect/full/overview/chitchat)
and to user_type. Appends to chitchat responses rather than replacing them.
"""

from __future__ import annotations
from _runtime.llm import call_llm_simple


_SYSTEM_PROMPT = """\
You are Sensi. You just completed an analysis and the user has seen
the results. Your job now is to offer natural next steps.

Adapt to what just happened:
  analyze  → offer to "go deeper" (detect conflicts), run a what-if, or stop
  detect   → offer to get suggestions (full), run a what-if, or stop
  full     → offer to modify something (what-if), compare personas, try biophilic, or stop
  overview → offer to run a comfort analysis, or stop
  chitchat → offer to start an analysis, or stop

Adapt to the user type:
  architect — professional framing: "Want me to run a conflict check? Or try a what-if?"
  client    — friendly framing: "Want to see what could be improved? Or try changing something?"
  learner   — educational framing: "Want to go deeper? You could try the conflict check next."

Rules:
  - Offer 2–3 options MAXIMUM. Too many choices is paralysing.
  - Be brief: 2 sentences maximum.
  - Do NOT summarise what just happened. The user just read it.
  - Use plain language. No markdown. No lists.
  - If nothing was analysed (chitchat/overview path), mention that analysis is available.
  - Always include "or type 'done' to finish" as one option.

CONTEXT:
  user_type: {user_type}
  last_path: {last_path}
  layout_id: {layout_id}
  persona: {persona_summary}
"""


def build_what_next_node(llm):
    """Return the what_next node function, capturing the LLM instance."""

    def what_next_node(state: dict) -> dict:
        user_type: str = state.get("user_type", "architect")
        comfort_depth: str = state.get("comfort_depth", "analyze")
        intent: str = state.get("intent", "comfort")
        layout_id: str = state.get("layout_id") or "?"
        persona_profile: dict = state.get("persona_profile") or {}

        # Determine what just happened
        if intent == "overview":
            last_path = "overview (room list, no analysis)"
        elif intent in ("comfort", "tools"):
            last_path = f"comfort analysis — depth: {comfort_depth}"
        elif intent == "chitchat":
            last_path = "chitchat conversation"
        elif intent == "inspire":
            last_path = "inspire (atmosphere)"
        else:
            last_path = intent

        primary = persona_profile.get("primary_user", {})
        persona_summary = primary.get("description", "no specific persona")

        print("[what_next] Generating next step offer...")

        system = _SYSTEM_PROMPT.format(
            user_type=user_type,
            last_path=last_path,
            layout_id=layout_id,
            persona_summary=persona_summary,
        )

        offer = call_llm_simple(llm, system, "Offer next steps.")

        # Always append the next-step nudge to the existing response.
        # For comfort/tools paths the respond node already wrote the full
        # analysis into final_response — we must not overwrite it.
        existing = state.get("final_response", "")
        if existing:
            combined = existing + "\n\n" + offer
        else:
            combined = offer

        return {
            **state,
            "final_response": combined,
        }

    return what_next_node
