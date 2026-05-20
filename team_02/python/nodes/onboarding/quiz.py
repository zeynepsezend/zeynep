"""
QUIZ node — structured multi-turn onboarding profiler.

Replaces user_profiler, persona_builder, persona_validator, and advisor.
Runs in the second phase of onboarding (after GREET, before INSPIRE).

Flow (one question per turn):
  Step 0 (turn 2): User's response to GREET's "who are you?" → stored, Q1 asked
  Step 1 (turn 3): Q1 answer stored, Q2 asked
  Step 2 (turn 4): Q2 answer stored, Q3 asked
  Step 3 (turn 5): Q3 answer stored, Q4 asked
  Step 4 (turn 6): Q4 answer stored, Q5 asked
  Step 5 (turn 7): Q5 answer stored → quiz_complete = True → routes to INSPIRE

State consumed:  quiz_step (int), quiz_answers (dict), raw_prompt (str)
State produced:  quiz_step (incremented), quiz_answers (updated),
                 quiz_complete (bool), final_response (str)
"""

from __future__ import annotations
from _runtime.llm import call_llm_simple


# ── Questions ─────────────────────────────────────────────────────────────────
# Index = the step AFTER which this question is asked.
# Step 0 answer = response to GREET's "who are you?" — we store it and ask Q1.

_QUESTIONS: dict[int, str] = {
    1: (
        "Tell me about a space where you've felt truly comfortable — "
        "could be anywhere. What made it feel right?"
    ),
    2: (
        "What usually bothers you most in a space? "
        "Think about temperature, noise, light, air quality, "
        "or feeling cramped — whatever comes to mind first."
    ),
    3: (
        "How do you mainly use your home — "
        "working from home, hosting people, relaxing, or a mix?"
    ),
    4: (
        "Do you have any specific needs or sensitivities I should keep in mind? "
        "For example: trouble sleeping with noise, a preference for natural light, "
        "sensitivity to temperature swings, or a need for fresh air..."
    ),
    5: (
        "Last one — if your ideal space had one non-negotiable quality, "
        "what would it be?"
    ),
}

_TOTAL_STEPS = 5  # Steps 0–5 inclusive (6 answers total, 5 follow-up questions)

_ACK_SYSTEM_PROMPT = """\
You are Sensi, a warm and attentive comfort companion.
The user just answered a question during their onboarding quiz.

Give them a brief, natural acknowledgment — one short sentence, max 10 words.
Then ask them the next question below on a new line.

Next question to ask: {next_question}

Rules:
- Vary your acknowledgments. Do NOT start with "Great!", "Awesome!", or "Fantastic!" every time.
- Do NOT repeat what the user said back to them verbatim.
- Keep the whole response short and conversational — one ack line + the question.
- Output ONLY the acknowledgment + question. Nothing else.
"""


def build_quiz_node(llm):
    """Return the quiz node function, capturing the LLM instance."""

    def quiz_node(state: dict) -> dict:
        raw_prompt: str = state.get("raw_prompt", "")
        quiz_step: int = state.get("quiz_step", 0)
        quiz_answers: dict = dict(state.get("quiz_answers") or {})

        print(f"[quiz] Step {quiz_step} — storing answer, preparing next question")

        # ── Store the current answer ──────────────────────────────────────
        step_key = f"q{quiz_step}"
        quiz_answers[step_key] = raw_prompt

        # ── Last step answered: quiz is done ─────────────────────────────
        if quiz_step >= _TOTAL_STEPS:
            print("[quiz] All answers collected — quiz complete, routing to inspire")
            return {
                **state,
                "quiz_step": quiz_step + 1,
                "quiz_answers": quiz_answers,
                "quiz_complete": True,
                "final_response": (
                    "Thank you — that gives me a really clear picture of you. "
                    "Now let's talk about atmosphere and aesthetic. "
                    "This next part helps me understand your sensory world beyond just data."
                ),
            }

        # ── Ask the next question ─────────────────────────────────────────
        next_step = quiz_step + 1
        next_question = _QUESTIONS[next_step]

        if quiz_step == 0:
            # First answer ever — simple warm response, no LLM overhead
            response = f"Nice to meet you! {next_question}"
        else:
            try:
                prompt = _ACK_SYSTEM_PROMPT.format(next_question=next_question)
                response = call_llm_simple(llm, prompt, raw_prompt)
            except Exception as exc:
                print(f"[quiz] LLM acknowledgment failed ({exc}) — using fallback")
                response = next_question

        return {
            **state,
            "quiz_step": next_step,
            "quiz_answers": quiz_answers,
            "quiz_complete": False,
            "final_response": response,
        }

    return quiz_node
