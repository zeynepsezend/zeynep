from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from _runtime.llm import write_tool_result
from live_material_api import live_db

# live_db is already initialized in the imported file, 
# so we just assign it to sheets_db to keep your variable names intact!
sheets_db = live_db


# ---------------------------------------------------------------------------
# Tool node — executes MCP tool calls requested by the reason node.
# ---------------------------------------------------------------------------

def build_tool_node(mcp_client, allowed_tools, edited_layout_path, cost_db: dict | None = None):
    """Return a tool node function ready to be added to a LangGraph StateGraph."""

    allowed_names = {t["name"] for t in allowed_tools if t.get("name")}

    def tool_node(state):

        # Iterate over the pending tool calls
        for call in state["pending_tool_calls"]:

            # Stop the process if max number of iterations is reached
            state["iteration"] += 1
            if state["iteration"] > state["max_iterations"]:
                raise RuntimeError("Max iterations exceeded")


            # Get the tool name and check it is valid. Older graph stubs used
            # {"tool": ..., "action": ..., "args": ...}; the LLM uses
            # {"name": ..., "arguments": ...}. Accept both shapes.
            tool_name = call.get("name") or call.get("action")
            if not tool_name:
                raise RuntimeError(f"Tool call is missing a name/action: {call}")

            if tool_name not in allowed_names:
                raise RuntimeError(f"Tool '{tool_name}' is not in the allowed tools list")

            raw_args = call.get("arguments", call.get("args", {}))
            if raw_args is None:
                raw_args = {}
            if not isinstance(raw_args, dict):
                raise RuntimeError(f"Tool call arguments must be an object: {call}")

            print(f"Calling tool: {tool_name} with arguments: {raw_args}")

            # Cleanup any null values accidentally included by the LLM
            tool_args = {k: v for k, v in raw_args.items() if v is not None}

            # Inject layout_json for any tool that needs it
            if "layout_json" in tool_args:
                tool_args["layout_json"] = state["layout_json_string"]
            
            # ENFORCE: compute_room_cost always receives the FULL layout_schema JSON.
            # This is the ONLY sanctioned path for room/space area + cost.
            if tool_name == "compute_room_cost":
                tool_args["layout_schema"] = state["layout_json_string"]
                print(
                    f"[ENFORCE] compute_room_cost via Grasshopper MCP | room='{tool_args.get('room_name')}' | "
                    f"layout_schema bytes={len(state['layout_json_string'])}"
                )

            # Call the tool (Live Supabase + FRED lookup or MCP)
            if tool_name == "get_unit_cost_by_type":
                element_type = str(tool_args.get("element_type", "")).lower().replace(" ", "_")
                
                # Query our live database instead of OpenCost. 
                # We are passing a default base_rate of 500.0, which the database will multiply by the FRED index.
                cost = sheets_db.get_live_rate(element_type, base_rate=500.0)
                
                tool_output = json.dumps(
                    {"element_type": element_type, "unit_cost": cost, "currency": "USD"}
                    if cost is not None
                    else {"error": f"No live cost data for '{element_type}'"}
                )
            else:
                tool_output = mcp_client.call_tool(tool_name, tool_args)

            # Store the updated layout returned by the MCP tool to a json file
            write_tool_result(tool_output, edited_layout_path)

            # If the tool returned valid JSON, update the layout in state so
            # subsequent tool calls in this loop receive the latest layout.
            try:
                updated = json.loads(tool_output.strip())
                if isinstance(updated, dict):
                    state["layout_json_string"] = json.dumps(updated)
                    state["layout_data"] = updated
                    state["has_layout"] = True
            except (json.JSONDecodeError, AttributeError):
                pass

            # Append the tool call and its result to the conversation history
            state["messages"].append({
                "role": "assistant",
                "content": json.dumps({
                    "action": "tool",
                    "final_response": "",
                    "tool_calls": [{"name": tool_name, "arguments": tool_args}],
                }),
            })
            
            state["messages"].append({
                "role": "user",
                "content": f"Tool result: {tool_output}",
            })
            print(f"Tool result: {tool_output}")

        state["pending_tool_calls"] = None
        state["return_to"] = state.get("return_to", "reasoning")
        return state

    return tool_node
