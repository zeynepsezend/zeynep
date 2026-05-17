"""
INTENT_CLASSIFIER node — reads meaning of the user message and routes to:
comfort, overview, inspire, chitchat, or tools.
Also extracts layout_id (201/202/203) if mentioned.
Falls back to keyword matching if the LLM fails.
"""

from __future__ import annotations
import json
from _runtime.llm import call_llm_simple


# ── Keyword fallback ──────────────────────────────────────────────────────────

_COMFORT_KEYWORDS = (
    "comfort", "analyse", "analyze", "score", "assess", "check", "detect",
    "conflict", "suggest", "fix", "improve", "thermal", "acoustic", "visual",
    "spatial", "olfactory", "tactile", "layout", "201", "202", "203",
    "what-if", "compare", "biophilic", "topologic",
)
_INSPIRE_KEYWORDS = ("image", "visualise", "visualize", "atmosphere", "mood",
                     "generate", "inspire", "picture", "render", "vibe")
_OVERVIEW_KEYWORDS = ("overview", "list rooms", "show rooms", "what rooms",
                      "room list", "summary of the layout")


def _keyword_fallback(prompt: str) -> str:
    lower = prompt.lower()
    if any(kw in lower for kw in _INSPIRE_KEYWORDS):
        return "inspire"
    if any(kw in lower for kw in _OVERVIEW_KEYWORDS):
        return "overview"
    if any(kw in lower for kw in _COMFORT_KEYWORDS):
        return "comfort"
    return "chitchat"


def _extract_layout_id(prompt: str) -> str | None:
    for lid in ("201", "202", "203"):
        if lid in prompt:
            return lid
    return None


# ── System prompt ─────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a routing assistant for an architectural comfort analysis tool.

Read the user's message and return a JSON object:

{
  "intent": "comfort" | "overview" | "inspire" | "chitchat" | "tools",
  "layout_id": "201" | "202" | "203" | null
}

Intent definitions:
  comfort   — any request to analyse, score, detect, fix, improve, or check
              comfort dimensions of a layout (thermal, acoustic, visual, etc.)
              Also use for what-if, compare personas, biophilic, topologic.
  overview  — user wants to see the room list or a layout summary, no scores
  inspire   — user wants image generation, atmosphere, or mood visualisation
  chitchat  — greeting, general question, learning, "what can you do?"
  tools     — ONLY use this if the user explicitly names a specific tool like
              "change material", "biophilic audit", "topologic analysis"

When in doubt between comfort and chitchat: if any layout or sense is mentioned,
use comfort.

layout_id: extract "201", "202", or "203" if mentioned. Otherwise null.

Return ONLY the JSON. No explanation. No markdown fences.
"""


# ── Node factory ──────────────────────────────────────────────────────────────

def build_intent_classifier_node(llm):
    """Return the intent_classifier node function, capturing the LLM instance."""

    def intent_classifier_node(state: dict) -> dict:
        raw_prompt: str = state.get("raw_prompt", "")

        print("[intent_classifier] Classifying intent...")

        intent = "chitchat"
        layout_id = state.get("layout_id")  # keep existing if not mentioned

        try:
            raw = call_llm_simple(llm, _SYSTEM_PROMPT, raw_prompt)
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1]).strip()
            parsed = json.loads(clean)

            candidate_intent = parsed.get("intent", "chitchat").lower().strip()
            if candidate_intent in ("comfort", "overview", "inspire", "chitchat", "tools"):
                intent = candidate_intent
            else:
                intent = _keyword_fallback(raw_prompt)
                print(f"[intent_classifier] Unknown intent '{candidate_intent}' — fallback: {intent}")

            extracted_id = parsed.get("layout_id")
            if extracted_id in ("201", "202", "203"):
                layout_id = extracted_id

            print(f"[intent_classifier] intent={intent} | layout_id={layout_id}")

        except Exception as exc:
            intent = _keyword_fallback(raw_prompt)
            if layout_id is None:
                layout_id = _extract_layout_id(raw_prompt)
            print(f"[intent_classifier] LLM error ({exc}) — fallback: {intent}")

        return {
            **state,
            "intent": intent,
            "layout_id": layout_id,
        }

    return intent_classifier_node
