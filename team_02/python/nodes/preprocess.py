"""
nodes/preprocess.py — PREPROCESS node for the Comfort Copilot state graph.

Pure Python — no LLM, no MCP calls. Runs first on every user message.

Responsibilities:
  1. Detect the top-level path (coarse routing only):
       "comfort"  → a layout ID (201 / 202 / 203) was mentioned
       "inspire"  → an image was attached
       "chitchat" → everything else
  2. Detect which persona the user mentioned, if any.
  3. Flag if a persona is still missing (so ask_persona node knows to run).

Depth within the comfort path (analyze / detect / full) is decided later
by route_intent.py, which uses the LLM.
"""

from __future__ import annotations
import re
from personas import detect_persona_in_text


# Layout IDs that are valid for this project
_LAYOUT_IDS: tuple[str, ...] = ("201", "202", "203")

# Words that strongly indicate an inspire / atmosphere request
_INSPIRE_KEYWORDS: tuple[str, ...] = (
    "inspire", "inspiration", "atmosphere", "mood", "aesthetic",
    "vibe", "feel like", "generate image", "create image", "imagine",
)


# ---------------------------------------------------------------------------
# Coarse intent detection
# ---------------------------------------------------------------------------

def detect_coarse_intent(prompt: str, has_image: bool = False) -> str:
    """
    Classify the prompt into one of three top-level paths.

    Returns one of: "comfort", "inspire", "chitchat"
    """
    if has_image:
        return "inspire"

    lower = prompt.lower()

    # Layout ID anywhere in the prompt → comfort analysis path
    if any(lid in lower for lid in _LAYOUT_IDS):
        return "comfort"

    if any(kw in lower for kw in _INSPIRE_KEYWORDS):
        return "inspire"

    return "chitchat"


# ---------------------------------------------------------------------------
# Preprocess node — wired into StateGraph in graph.py
# ---------------------------------------------------------------------------

def preprocess_node(state: dict) -> dict:
    """
    Read the raw user prompt, run coarse routing, detect persona.

    Writes to state:
      intent            (str)        — "comfort" | "inspire" | "chitchat"
      layout_id         (str | None) — e.g. "201" if found in prompt
      persona_detected  (str | None) — persona name, or None
      needs_persona_ask (bool)       — True when comfort but no persona found
    """
    raw_prompt: str = state.get("raw_prompt", "")
    has_image: bool = state.get("has_image", False)

    print(f"\n[preprocess] Prompt : {raw_prompt[:120]}")

    # ── 1. Coarse intent ─────────────────────────────────────────────────
    intent = detect_coarse_intent(raw_prompt, has_image)
    print(f"[preprocess] Intent : {intent}")

    # ── 2. Extract layout ID (if present) ────────────────────────────────
    layout_id: str | None = None
    if intent == "comfort":
        lower = raw_prompt.lower()
        for lid in _LAYOUT_IDS:
            if lid in lower:
                layout_id = lid
                break
    print(f"[preprocess] Layout : {layout_id or 'none'}")

    # ── 3. Detect persona — only relevant on the comfort path ────────────
    # On chitchat / inspire, keyword overlap (e.g. "sensory" in a general
    # question) would incorrectly lock a persona into the session.
    if intent == "comfort":
        # Respect a persona already carried over from a previous turn.
        persona: str | None = state.get("persona_detected") or detect_persona_in_text(raw_prompt)
    else:
        persona = None
    print(f"[preprocess] Persona: {persona or 'not found'}")

    # ── 4. Flag missing persona for comfort requests ──────────────────────
    needs_persona_ask = (intent == "comfort") and (persona is None)

    return {
        **state,
        "intent":            intent,
        "layout_id":         layout_id,
        "persona_detected":  persona,
        "needs_persona_ask": needs_persona_ask,
    }
