from __future__ import annotations
from typing import Any
from _runtime.llm import call_llm


# ---------------------------------------------------------------------------
# System prompt — edit this to change how the agent thinks and behaves.
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an assistant that helps users work with building layouts.

## Decision Tree (Priority Order)

**Step 0: SEARCH REQUEST?** (highest priority)
- Triggers: "find", "search", "show me", "select layout with", "get", "what layouts", "any layouts"
- Action: Call layout_graph_search (override any current layout context)
- Return candidates as final response (do NOT auto-call filter)

**Step 1: WORKING ON CURRENT LAYOUT?**
- If "Currently Selected Layout" exists and NOT searching: Use MCP tools for modifications
- If "Available Candidates" exist and NOT searching: Return candidates, user chooses next action

**Step 2: USER SPECIFIED LAYOUT ID?**
- Examples: "work on layout-1", "select layout-5"
- Action: Call layout_filter(layout_id=...)

**Step 3: MODIFICATIONS REQUESTED?**
- Examples: "delete the kitchen", "add a window", "change entry"
- Action: Call appropriate MCP tools

## Graph Search Rules

**Count matters!** Include duplicates:
- "2-bedroom" → ["bed", "bed"]
- "3 bathrooms" → ["bath", "bath", "bath"]

**Connection type:**
- "any" (default): rooms exist but not necessarily connected
- "connected": all rooms must be interconnected (keywords: "connected", "accessible", "open floor plan", etc.)

**Room normalization:**
- bed (bedroom, 2-bedroom, sleeping room)
- kitchen (kitchenette)
- living (living room, living space)
- bath (bathroom, washroom)
- dining (dining room, dining area)
- entry (foyer, entrance)

**Example:**
- "find 2-bedroom with open kitchen-living" → layout_graph_search(programs=["bed", "bed", "kitchen", "living"], connection_type="connected")

## Available Tools
{tool_catalog}
Return strictly valid JSON with exactly this shape:
{{
  "action": "final" | "tool",
  "final_response": "...",
  "tool_calls": [{{"name": "<tool-name>", "arguments": {{...}}}}, ...]
}}

Output rules:
- Return JSON only, with no prose or explanation.
- Do not use markdown code fences.
- If action is "final", set tool_calls to [] and put the answer in final_response.
- If action is "tool", set final_response to "" and put one or more tool calls in tool_calls.
"""


# ---------------------------------------------------------------------------
# Reason node — the LLM decision step in the graph.
# ---------------------------------------------------------------------------

def build_reason_node(llm):
    """Return a reason node function ready to be added to a LangGraph StateGraph."""

    def reason_node(state):
        print("\nReasoning with LLM...")
        print(f"[reason] Tool catalog:\n{state['tool_catalog']}")
        
        # Build dynamic system prompt with session context
        system_prompt = SYSTEM_PROMPT
        
        # Inject session context if available
        session_context = ""
        
        # Show available candidates from previous search
        if state.get("candidate_layouts"):
            candidates_str = "\n".join([
                f"  - layout: {c['layoutId']}, score: {c['score']}"
                for c in state.get("candidate_layouts", [])
            ])
            session_context += f"\n## Available Candidates from Previous Search\n{candidates_str}"
        
        if state.get("layout_id"):
            session_context += f"\n## Currently Selected Layout\n- Working on: {state['layout_id']}"
        
        if state.get("last_action"):
            session_context += f"\n- Last action: {state['last_action']}"
        
        if session_context:
            system_prompt = system_prompt + session_context
            print(f"[reason] Session context injected into prompt")
        
        print(f"[reason] System prompt length: {len(system_prompt)} chars")
        print(f"[reason] Messages count: {len(state['messages'])}")
        for i, msg in enumerate(state["messages"]):
            print(f"  Message {i} ({msg.get('role', '?')}): {len(msg.get('content', ''))} chars")
        
        result = call_llm(llm, system_prompt, state["messages"], state["tool_catalog"])
        
        print(f"[reason] LLM result type: {type(result)}")
        print(f"[reason] LLM result: {result}")
        
        if not isinstance(result, dict):
            raise RuntimeError(f"Expected dict from call_llm, got {type(result)}: {result}")

        # If the LLM decided no more actions are needed (action is final), set the final response in the state and clear pending tool calls
        if result["action"] == "final":
            print(f"[reason] Agent decided: FINAL - {result['final_response'][:100]}...")
            state["final_response"] = result["final_response"]
            state["pending_tool_calls"] = None

        # If the LLM decided the action is to use a tool, set the pending tool calls
        else:
            print(f"[reason] Agent decided: TOOL - {[t['name'] for t in result['tool_calls']]}")
            state["pending_tool_calls"] = result["tool_calls"]

        return state

    return reason_node
