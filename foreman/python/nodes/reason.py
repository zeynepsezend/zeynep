from __future__ import annotations
from typing import Any
from _runtime.llm import call_llm


# ---------------------------------------------------------------------------
# System prompt — edit this to change how the agent thinks and behaves.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are the reasoning module of an agent with the following description: 
{agent_description}

You may response with one of three actions:
- "final": the agent has completed the task and has a final response. No more interaction is needed.
- "agent": the agent needs to use one of the other agents to complete the task, and will specify which one and with what arguments.
- "further_thought": the agent needs to think more and will specify more information for itself to consider in the next reasoning step.

Return strictly valid JSON with exactly this shape:
{{
  "action": "final" | "agent" | "further_thought",
  "response": "thoughts or final answer for the user, depending on the action",
  "agent_calls": [{{"name": "<agent-name>", "arguments": {{...}}}}, ...]
}}

Output rules:
- Return JSON only, with no prose or explanation.
- Do not use markdown code fences.
- If action is "final", set agent_calls to [] and put the answer in response.
- If action is "agent", set response to "" and put one or more agent calls in agent_calls.
- If action is "further_thought", set response to your current thoughts for yourself, set agent_calls to [].
"""


# ---------------------------------------------------------------------------
# Reason node — the LLM decision step in the graph.
# ---------------------------------------------------------------------------

def build_reason_node(llm):
    """Return a reason node function ready to be added to a LangGraph StateGraph."""

    def reason_node(state):
        print("\nReasoning with LLM...")
        result = call_llm(llm, SYSTEM_PROMPT, state["messages"], state["tool_catalog"])

        # If the LLM decided no more actions are needed (action is final), set the final response in the state and clear pending tool calls
        if result["action"] == "final":
            state["response"] = result["response"]
            state["agent_calls"] = []

        # If the LLM decided the action is to use a tool, set the pending tool calls
        elif result["action"] == "agent":
            state["agent_calls"] = result["agent_calls"]

        else:  # further thought
            state["response"] = result["response"]
            state["agent_calls"] = []

        return state

    return reason_node
