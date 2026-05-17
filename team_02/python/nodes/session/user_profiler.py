"""
USER_PROFILER node — classifies user as architect / client / learner.
Extracts any layout IDs, persona hints, or goals from the self-introduction.
Defaults to learner on parse error or ambiguous input.
"""

from __future__ import annotations
import json
from _runtime.llm import call_llm_simple


_SYSTEM_PROMPT = """\
You are a user profiler for an architectural comfort analysis tool.

Read the user's message and return a JSON object with exactly these fields:

{
  "user_type": "architect" | "client" | "learner",
  "initial_context": "<one sentence summarising any layout IDs, user profile info, or goals already mentioned>"
}

Classification guide:
  architect — uses technical language, mentions a client or brief, has a design goal,
              refers to layout numbers or rooms professionally
  client    — speaks from personal experience, mentions family members or daily life,
              describes a real living situation ("I live with my grandmother", "our apartment")
  learner   — explicitly says they are learning, a student, or curious; no clear design goal;
              asks "what can you do?" or "how does this work?"

When in doubt, classify as learner.

If the user has not mentioned any layout, persona, or goal yet, set initial_context to "none".

Return ONLY the JSON object. No explanation. No markdown.
"""


def build_user_profiler_node(llm):
    """Return the user_profiler node function, capturing the LLM instance."""

    def user_profiler_node(state: dict) -> dict:
        raw_prompt: str = state.get("raw_prompt", "")

        print("[user_profiler] Classifying user type...")

        raw = call_llm_simple(llm, _SYSTEM_PROMPT, raw_prompt)

        # Parse JSON response safely
        user_type = "learner"
        initial_context = "none"
        try:
            # Strip markdown fences if present
            clean = raw.strip()
            if clean.startswith("```"):
                lines = clean.splitlines()
                clean = "\n".join(lines[1:-1]).strip()
            parsed = json.loads(clean)
            candidate = parsed.get("user_type", "learner").lower().strip()
            if candidate in ("architect", "client", "learner"):
                user_type = candidate
            initial_context = parsed.get("initial_context", "none")
            print(f"[user_profiler] user_type={user_type} | context={initial_context}")
        except Exception as exc:
            print(f"[user_profiler] JSON parse error ({exc}) — defaulting to learner")

        return {
            **state,
            "user_type": user_type,
            "initial_context": initial_context,
        }

    return user_profiler_node
