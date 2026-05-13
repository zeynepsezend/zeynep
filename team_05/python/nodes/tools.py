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

            # Call the tool (local handlers, OpenCost lookup, or MCP)
            if tool_name == "compute_slab_cost":
                tool_output = _compute_slab_cost_local(
                    tool_args, state, cost_db, mcp_client, allowed_names
                )
            elif tool_name == "compute_finish_cost":
                tool_output = _compute_finish_cost_local(
                    tool_args, state, cost_db, mcp_client, allowed_names
                )
            elif tool_name == "get_unit_cost_by_type":
                element_type = str(tool_args.get("element_type", "")).lower().replace(" ", "_")
                # Query OpenCost instead of cost_db
                cost = sheets_db.get_cost(element_type)
                currency = "AED"
                tool_output = json.dumps(
                    {"element_type": element_type, "unit_cost": cost, "currency": currency}
                    if cost is not None
                    else {"error": f"No cost data for '{element_type}'"}
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
            elif tool_name == "compute_slab_cost":
                # Slab handler updates state["layout_json_string"] in-place but
                # returns only the slab summary. Persist the in-state layout so
                # the on-disk file reflects the new slab fields.
                try:
                    _state_layout = json.loads(state.get("layout_json_string", "") or "{}")
                except (json.JSONDecodeError, TypeError):
                    _state_layout = None
                if isinstance(_state_layout, dict) and isinstance(_state_layout.get("rooms"), list):
                    write_tool_result(state["layout_json_string"], edited_layout_path)
                    print(f"[PERSIST] Slab fields saved to {edited_layout_path.name}")
            elif tool_name == "compute_finish_cost":
                try:
                    _state_layout = json.loads(state.get("layout_json_string", "") or "{}")
                except (json.JSONDecodeError, TypeError):
                    _state_layout = None
                if isinstance(_state_layout, dict) and isinstance(_state_layout.get("rooms"), list):
                    write_tool_result(state["layout_json_string"], edited_layout_path)
                    print(f"[PERSIST] Finish fields saved to {edited_layout_path.name}")

            # If the tool returned a full layout (has a non-empty rooms list),
            # update the in-state layout so subsequent tool calls in this loop
            # see the latest version. Don't overwrite the layout with arbitrary
            # tool results (e.g. compute_slab_cost / get_unit_cost_by_type).
            try:
                updated = json.loads(tool_output.strip())
                if (
                    isinstance(updated, dict)
                    and isinstance(updated.get("rooms"), list)
                    and updated["rooms"]
                ):
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


# ---------------------------------------------------------------------------
# Local handler: compute_slab_cost
#   cost = area_m2 * thickness_m * rate_per_m3
#   rate looked up in cost_db._rates.room_finishes.slab_material; falls back
#   to OnlineCostFetcher when the material is not in cost_rates.json.
# ---------------------------------------------------------------------------

def _norm(s: Any) -> str:
    return str(s or "").strip().lower().replace(" ", "_").replace("-", "_")


def _sync_rate_to_extras(room: dict) -> None:
    """Bump room['rate_per_m2'] so GH's total_cost = area*rate reflects the
    sum of base room rate + slab costs + finish costs. Stores the original
    rate in 'base_rate_per_m2' on first call so repeated edits stay correct."""
    try:
        area = float(room.get("area_m2") or 0)
    except (TypeError, ValueError):
        area = 0.0
    if area <= 0:
        return
    if "base_rate_per_m2" not in room:
        try:
            room["base_rate_per_m2"] = float(room.get("rate_per_m2") or 0)
        except (TypeError, ValueError):
            room["base_rate_per_m2"] = 0.0
    base = float(room.get("base_rate_per_m2") or 0)
    slabs_total = sum(float(s.get("cost") or 0) for s in (room.get("slabs") or []))
    finishes_total = sum(float(f.get("cost") or 0) for f in (room.get("finishes") or []))
    extras_per_m2 = (slabs_total + finishes_total) / area
    new_rate = round(base + extras_per_m2, 2)
    room["rate_per_m2"] = new_rate
    room["total_cost"] = round(new_rate * area, 2)


def _compute_slab_cost_local(
    args: dict, state: dict, cost_db: dict | None,
    mcp_client=None, allowed_names: set | None = None,
) -> str:
    layout_json_string = state.get("layout_json_string", "")
    room_name = args.get("room_name")
    material = args.get("material")
    try:
        thickness = float(args.get("thickness_m"))
    except (TypeError, ValueError):
        return json.dumps({"error": "thickness_m is required and must be a number"})

    if not room_name or not material:
        return json.dumps({"error": "room_name and material are required"})

    # Resolve area: arg override -> layout lookup
    area = args.get("area_m2")
    try:
        area = float(area) if area is not None else None
    except (TypeError, ValueError):
        area = None
    if area is None:
        try:
            layout_obj = json.loads(layout_json_string) if layout_json_string else {}
        except (json.JSONDecodeError, TypeError):
            layout_obj = {}
        for room in layout_obj.get("rooms", []) or []:
            if _norm(room.get("name")) == _norm(room_name):
                a = room.get("area_m2")
                if a is not None:
                    try:
                        area = float(a)
                    except (TypeError, ValueError):
                        pass
                break
    if area is None:
        return json.dumps({
            "error": f"Could not resolve area_m2 for room '{room_name}'. "
                     "Pass area_m2 explicitly or run compute_room_cost first."
        })

    # Resolve rate: cost_rates.json slab_material -> default -> OnlineCostFetcher
    rates = (cost_db or {}).get("_rates") or {}
    slab_section = (rates.get("room_finishes") or {}).get("slab_material") or {}
    by_material = {_norm(k): v for k, v in (slab_section.get("by_material") or {}).items()}
    rate = by_material.get(_norm(material))
    rate_source = "cost_rates.json"
    if rate is None and slab_section.get("default") is not None:
        rate = slab_section["default"]
        rate_source = "cost_rates.json (default)"
    if rate is None:
        try:
            from online_cost_lookup import OnlineCostFetcher  # type: ignore
            fetcher = OnlineCostFetcher()
            online = fetcher.fetch("slab_material", material)
            if online is not None:
                rate = online
                rate_source = "online (OnlineCostFetcher)"
        except Exception as exc:  # pragma: no cover
            print(f"[compute_slab_cost] online fallback failed: {exc}")

    if rate is None:
        return json.dumps({
            "error": f"No slab rate available for material '{material}'.",
            "known_materials": sorted(by_material.keys()),
        })

    rate = float(rate)
    cost = round(area * thickness * rate, 2)
    currency = (cost_db or {}).get("_currency", "AED")
    print(
        f"[compute_slab_cost] room='{room_name}' material='{material}' "
        f"area={area} thickness={thickness} rate={rate} {currency}/m3 -> {cost} {currency}"
    )

    # Inject slab fields into the layout and forward to Grasshopper via MCP so
    # the GH definition can re-bake / update its visualization.
    gh_status = "skipped"
    try:
        layout_obj = json.loads(layout_json_string) if layout_json_string else {}
    except (json.JSONDecodeError, TypeError):
        layout_obj = {}
    target_room = None
    for room in layout_obj.get("rooms", []) or []:
        if _norm(room.get("name")) == _norm(room_name):
            target_room = room
            break
    if target_room is not None:
        # Replace any existing slab entry with matching material so repeated
        # calls overwrite instead of duplicating, then mirror flat fields.
        slabs = target_room.setdefault("slabs", [])
        slabs[:] = [s for s in slabs if _norm(s.get("material")) != _norm(material)]
        slabs.append({
            "material": material,
            "thickness_m": thickness,
            "rate_per_m3": rate,
            "cost": cost,
            "currency": currency,
        })
        target_room["thickness_m"] = thickness
        target_room["slab_material"] = material
        target_room["slab_rate_per_m3"] = rate
        target_room["slab_cost"] = cost
        # Aggregate of all slabs for this room
        target_room["slabs_total_cost"] = round(
            sum(float(s.get("cost") or 0) for s in slabs), 2
        )
        # Bump rate_per_m2 so GH's area*rate total_cost reflects the slab.
        _sync_rate_to_extras(target_room)

        updated_layout_str = json.dumps(layout_obj)
        state["layout_json_string"] = updated_layout_str

        # Forward to Grasshopper if compute_element_cost is exposed via MCP.
        if mcp_client is not None and (allowed_names is None or "compute_element_cost" in allowed_names):
            try:
                gh_payload = {
                    "update elentmet json": room_name,  # GH tool uses this exact key
                    "layout_schema": updated_layout_str,
                }
                gh_response = mcp_client.call_tool("compute_element_cost", gh_payload)
                # If GH returned a full layout, adopt it.
                try:
                    gh_parsed = json.loads(gh_response)
                    if isinstance(gh_parsed, dict) and isinstance(gh_parsed.get("rooms"), list) and gh_parsed["rooms"]:
                        state["layout_json_string"] = json.dumps(gh_parsed)
                except (json.JSONDecodeError, TypeError):
                    pass
                gh_status = "updated"
                print(f"[compute_slab_cost] Grasshopper updated via compute_element_cost for '{room_name}'")
            except Exception as exc:  # pragma: no cover
                gh_status = f"error: {exc}"
                print(f"[compute_slab_cost] GH update failed: {exc}")

    return json.dumps({
        "room_name": room_name,
        "material": material,
        "area_m2": area,
        "thickness_m": thickness,
        "rate_per_m3": rate,
        "rate_source": rate_source,
        "currency": currency,
        "slab_cost": cost,
        "grasshopper_update": gh_status,
    })


# ---------------------------------------------------------------------------
# Local handler: compute_finish_cost
#   cost = surface_area_m2 * rate_per_m2
#   surface in {floor, wall, ceiling}. Rate looked up from
#   cost_db._rates.room_finishes.{floor_finish|wall_finish|ceiling_material}.
#   Floor/ceiling area = room.area_m2. Wall area = perimeter * height_m.
# ---------------------------------------------------------------------------

def _polygon_perimeter(poly) -> float:
    if not isinstance(poly, list) or len(poly) < 2:
        return 0.0
    pts = []
    for p in poly:
        try:
            pts.append((float(p[0]), float(p[1])))
        except (TypeError, ValueError, IndexError):
            return 0.0
    total = 0.0
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        total += ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
    return total


_SURFACE_KEYS = {
    "floor": ("floor_finish", "floor"),
    "wall": ("wall_finish", "wall"),
    "ceiling": ("ceiling_material", "ceiling"),
}


def _compute_finish_cost_local(
    args: dict, state: dict, cost_db: dict | None,
    mcp_client=None, allowed_names: set | None = None,
) -> str:
    layout_json_string = state.get("layout_json_string", "")
    room_name = args.get("room_name")
    material = args.get("material")
    surface = _norm(args.get("surface"))
    if not room_name or not material or surface not in _SURFACE_KEYS:
        return json.dumps({
            "error": "room_name, surface (floor|wall|ceiling), and material are required",
        })

    section_key, prefix = _SURFACE_KEYS[surface]

    # Locate room
    try:
        layout_obj = json.loads(layout_json_string) if layout_json_string else {}
    except (json.JSONDecodeError, TypeError):
        layout_obj = {}
    target_room = None
    for room in layout_obj.get("rooms", []) or []:
        if _norm(room.get("name")) == _norm(room_name):
            target_room = room
            break

    # Resolve area
    area = args.get("area_m2")
    height = args.get("height_m")
    try:
        area = float(area) if area is not None else None
    except (TypeError, ValueError):
        area = None
    try:
        height = float(height) if height is not None else None
    except (TypeError, ValueError):
        height = None

    if area is None and target_room is not None:
        if surface in ("floor", "ceiling"):
            a = target_room.get("area_m2")
            if a is not None:
                try:
                    area = float(a)
                except (TypeError, ValueError):
                    pass
        elif surface == "wall":
            perim = _polygon_perimeter(target_room.get("polygon"))
            h = height if height is not None else 3.0
            if perim > 0:
                area = perim * h

    if area is None:
        return json.dumps({
            "error": f"Could not resolve area for room '{room_name}' surface '{surface}'. "
                     "Pass area_m2 explicitly.",
        })

    # Resolve rate
    rates = (cost_db or {}).get("_rates") or {}
    section = (rates.get("room_finishes") or {}).get(section_key) or {}
    by_material = {_norm(k): v for k, v in (section.get("by_material") or {}).items()}
    rate = by_material.get(_norm(material))
    rate_source = "cost_rates.json"
    if rate is None and section.get("default") is not None:
        rate = section["default"]
        rate_source = "cost_rates.json (default)"
    if rate is None:
        try:
            from online_cost_lookup import OnlineCostFetcher  # type: ignore
            online = OnlineCostFetcher().fetch(section_key, material)
            if online is not None:
                rate = online
                rate_source = "online (OnlineCostFetcher)"
        except Exception as exc:  # pragma: no cover
            print(f"[compute_finish_cost] online fallback failed: {exc}")

    if rate is None:
        return json.dumps({
            "error": f"No rate available for {surface} material '{material}'.",
            "known_materials": sorted(by_material.keys()),
        })

    rate = float(rate)
    cost = round(area * rate, 2)
    currency = (cost_db or {}).get("_currency", "AED")
    print(
        f"[compute_finish_cost] room='{room_name}' surface='{surface}' "
        f"material='{material}' area={area} rate={rate} {currency}/m2 -> {cost} {currency}"
    )

    # Inject into layout
    gh_status = "skipped"
    if target_room is not None:
        finishes = target_room.setdefault("finishes", [])
        # Replace any existing entry for the same surface so repeated calls
        # overwrite instead of duplicating.
        finishes[:] = [f for f in finishes if _norm(f.get("surface")) != surface]
        finishes.append({
            "surface": surface,
            "material": material,
            "area_m2": area,
            "rate_per_m2": rate,
            "cost": cost,
            "currency": currency,
        })
        target_room[f"{prefix}_material"] = material
        target_room[f"{prefix}_rate_per_m2"] = rate
        target_room[f"{prefix}_area_m2"] = area
        target_room[f"{prefix}_cost"] = cost
        if surface == "wall" and height is not None:
            target_room["wall_height_m"] = height
        target_room["finishes_total_cost"] = round(
            sum(float(f.get("cost") or 0) for f in finishes), 2
        )
        # Bump rate_per_m2 so GH's area*rate total_cost reflects the finish.
        _sync_rate_to_extras(target_room)

        updated_layout_str = json.dumps(layout_obj)
        state["layout_json_string"] = updated_layout_str

        if mcp_client is not None and (allowed_names is None or "compute_element_cost" in allowed_names):
            try:
                gh_payload = {
                    "update elentmet json": room_name,
                    "layout_schema": updated_layout_str,
                }
                gh_response = mcp_client.call_tool("compute_element_cost", gh_payload)
                try:
                    gh_parsed = json.loads(gh_response)
                    if isinstance(gh_parsed, dict) and isinstance(gh_parsed.get("rooms"), list) and gh_parsed["rooms"]:
                        state["layout_json_string"] = json.dumps(gh_parsed)
                except (json.JSONDecodeError, TypeError):
                    pass
                gh_status = "updated"
                print(f"[compute_finish_cost] Grasshopper updated via compute_element_cost for '{room_name}'")
            except Exception as exc:  # pragma: no cover
                gh_status = f"error: {exc}"
                print(f"[compute_finish_cost] GH update failed: {exc}")

    return json.dumps({
        "room_name": room_name,
        "surface": surface,
        "material": material,
        "area_m2": area,
        "rate_per_m2": rate,
        "rate_source": rate_source,
        "currency": currency,
        "finish_cost": cost,
        "grasshopper_update": gh_status,
    })
