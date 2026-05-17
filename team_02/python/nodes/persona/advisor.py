"""
ADVISOR node — triggered when user is unsure where to start.
Recommends ONE clear starting path based on the loaded layout and persona profile.
Sets comfort_depth to "full" so the full analysis chain runs after.
"""

from __future__ import annotations
import json
from _runtime.llm import call_llm_simple


_SYSTEM_PROMPT = """\
You are Sensi, an expert in multi-sensory architectural comfort.

The user has asked for guidance on where to start. You have access to their layout
and persona profile. Your job is to recommend ONE clear starting point.

Guidelines:
  - Be direct: "I'd suggest starting with..."
  - Reference SPECIFIC rooms and senses from the layout and persona profile
  - Explain WHY in one sentence (which sense is most at risk for this persona, and why)
  - Recommend a depth: "a full analysis" (if they need suggestions) or
    "a conflict check" (if they just want to know what's failing)
  - Do NOT list all options. Decide for them. They asked you to advise.
  - Keep it to 2–3 sentences maximum.
  - End by asking: "Shall I go ahead with that?" or a natural variation.

Adapt your register to the user type:
  architect — professional language, reference design implications
  client    — plain language, focus on daily comfort and lived experience
  learner   — educational tone, explain why this is a good starting point

LAYOUT (room names and types):
{layout_summary}

PERSONA PROFILE:
{persona_profile}
"""


def _summarise_layout(layout_json_string: str) -> str:
    """Extract a brief room summary from the layout JSON."""
    if not layout_json_string:
        return "(no layout loaded)"
    try:
        layout = json.loads(layout_json_string)
        rooms = layout.get("rooms", [])
        lines = []
        for r in rooms:
            name = r.get("name", "unknown")
            rtype = r.get("roomType", "")
            orientation = r.get("orientation", "")
            lines.append(f"  - {name} ({rtype}, {orientation})")
        return "\n".join(lines) if lines else "(no rooms found)"
    except Exception:
        return "(layout parse error)"


def build_advisor_node(llm):
    """Return the advisor node function, capturing the LLM instance."""

    def advisor_node(state: dict) -> dict:
        layout_json_string: str = state.get("layout_json_string", "")
        persona_profile: dict = state.get("persona_profile") or {}
        user_type: str = state.get("user_type", "architect")

        print("[advisor] Generating advisory recommendation...")

        layout_summary = _summarise_layout(layout_json_string)
        system = _SYSTEM_PROMPT.format(
            layout_summary=layout_summary,
            persona_profile=json.dumps(persona_profile, indent=2),
        )

        user_message = (
            f"I'm a {user_type}. I'm not sure where to start. "
            f"Please advise me on the best starting point for this layout and persona."
        )

        recommendation = call_llm_simple(llm, system, user_message)
        print(f"[advisor] Recommendation: {recommendation[:80]}...")

        return {
            **state,
            "advisor_recommendation": recommendation,
            "route_intent_decision": "full",   # advisee gets full analysis
            "comfort_depth": "full",
            "final_response": recommendation,  # shown to user before analysis runs
        }

    return advisor_node
