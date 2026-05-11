from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from _runtime.llm import write_tool_result


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
                # Optional overrides: if the LLM passes a custom rate_per_m2 or
                # area_m2, patch them into the matching room of the layout BEFORE
                # injecting. Recompute total_cost when both are known.
                override_rate = tool_args.pop("rate_per_m2", None)
                override_area = tool_args.pop("area_m2", None)
                room_name = tool_args.get("room_name")
                if (override_rate is not None or override_area is not None) and room_name:
                    try:
                        _layout_obj = json.loads(state["layout_json_string"])
                        for _room in _layout_obj.get("rooms", []):
                            if str(_room.get("name", "")).strip().lower() == str(room_name).strip().lower():
                                if override_rate is not None:
                                    _room["rate_per_m2"] = override_rate
                                    print(f"[OVERRIDE] {room_name} rate_per_m2 -> {override_rate}")
                                if override_area is not None:
                                    _room["area_m2"] = override_area
                                    # Invalidate polygon so the GH script trusts area_m2
                                    _room.pop("polygon", None)
                                    print(f"[OVERRIDE] {room_name} area_m2 -> {override_area} (polygon dropped)")
                                _r = _room.get("rate_per_m2")
                                _a = _room.get("area_m2")
                                if _r is not None and _a is not None:
                                    _room["total_cost"] = round(float(_r) * float(_a), 2)
                                break
                        state["layout_json_string"] = json.dumps(_layout_obj)
                    except (json.JSONDecodeError, AttributeError, TypeError) as exc:
                        print(f"[OVERRIDE] Failed to apply overrides ({exc})")
                tool_args["layout_schema"] = state["layout_json_string"]
                print(
                    f"[ENFORCE] compute_room_cost via Grasshopper MCP | room='{tool_args.get('room_name')}' | "
                    f"layout_schema bytes={len(state['layout_json_string'])}"
                )

            # Call the tool (local cost DB lookup or MCP)
            if tool_name == "get_unit_cost_by_type" and cost_db is not None:
                element_type = str(tool_args.get("element_type", ""))
                norm = element_type.lower().strip().replace(" ", "_").replace("-", "_")
                flat = cost_db.get("_flat") if isinstance(cost_db, dict) else None
                # Backward compat: cost_db may be a flat dict from a legacy bootstrap.
                if not isinstance(flat, dict):
                    flat = {k: v for k, v in (cost_db or {}).items() if not str(k).startswith("_")}
                cost = flat.get(norm)
                if cost is None:
                    # Tolerate partial matches (e.g. "porcelain" -> "porcelain_tile")
                    for k, v in flat.items():
                        if norm and (norm in k or k in norm):
                            cost = v
                            break
                currency = (cost_db or {}).get("_currency", "AED") if isinstance(cost_db, dict) else "AED"
                tool_output = json.dumps(
                    {"element_type": norm, "unit_cost": cost, "currency": currency}
                    if cost is not None
                    else {"error": f"No cost data for '{element_type}'", "known_types": sorted(flat.keys())}
                )
            else:
                tool_output = mcp_client.call_tool(tool_name, tool_args)

            # Store the updated layout returned by the MCP tool to a json file.
            # Only persist when the response is a full layout schema (has rooms),
            # so non-layout tools (e.g. count_elements_by_type) don't overwrite it.
            try:
                _parsed_for_persist = json.loads(tool_output.strip())
            except (json.JSONDecodeError, AttributeError):
                _parsed_for_persist = None
            if isinstance(_parsed_for_persist, dict) and isinstance(_parsed_for_persist.get("rooms"), list) and _parsed_for_persist["rooms"]:
                write_tool_result(tool_output, edited_layout_path)
                print(f"[PERSIST] Updated layout saved to {edited_layout_path.name}")

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
