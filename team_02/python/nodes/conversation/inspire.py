"""
INSPIRE node — Phase 3 placeholder for atmosphere / image generation.
Returns a holding message until the feature is implemented.
"""

from __future__ import annotations


_PLACEHOLDER = (
    "The Inspire mode — atmosphere generation from layout and image — "
    "is coming in Phase 3. For now, try asking me to analyse a layout "
    "by mentioning its number (201, 202, or 203) in your message."
)


def inspire_node(state: dict) -> dict:
    print("[inspire] Inspire path triggered — returning placeholder.")
    return {
        **state,
        "final_response": _PLACEHOLDER,
    }
