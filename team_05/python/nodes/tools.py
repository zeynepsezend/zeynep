from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from _runtime.llm import write_tool_result
from opencost_database import get_opencost_db

# Initialize OpenCost database
sheets_db = get_opencost_db()


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


            # Get the tool name and check its valid
            tool_name = call["name"]
            if tool_name not in allowed_names:
                raise RuntimeError(f"Tool '{tool_name}' is not in the allowed tools list")
            
            print(f"Calling tool: {tool_name} with arguments: {call['arguments']}")

            # Cleanup any null values accidentally included by the LLM
            tool_args = {k: v for k, v in call["arguments"].items() if v is not None}

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

            # Call the tool (OpenCost lookup or MCP)
            if tool_name == "get_unit_cost_by_type":
                element_type = str(tool_args.get("element_type", "")).lower().replace(" ", "_")
                # Query OpenCost instead of cost_db
                cost = sheets_db.get_cost(element_type)
                tool_output = json.dumps(
                    {"element_type": element_type, "unit_cost": cost, "currency": "EUR"}
                    if cost is not None
                    else {"error": f"No cost data for '{element_type}' in OpenCost"}
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
        return state

    return tool_node