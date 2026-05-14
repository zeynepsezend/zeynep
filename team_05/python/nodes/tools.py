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


            # Get the tool name and check it is valid.
            # Some workflows may request local helpers that are not advertised
            # by MCP in allowed_tools.
            tool_name = call["name"]
            local_fallback_tools = {"compute_room_cost", "compute_surface_cost", "compute_volume_cost"}
            if tool_name not in allowed_names and tool_name not in local_fallback_tools:
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
            elif tool_name == "compute_surface_cost":
                tool_output = compute_surface_cost(
                    tool_args, state, cost_db, mcp_client, allowed_names
                )
            elif tool_name == "compute_volume_cost":
                tool_output = compute_volume_cost(
                    tool_args, state, cost_db, mcp_client, allowed_names
                )
            elif tool_name == "compute_room_cost":
                # Prefer MCP implementation when available; otherwise use local fallback.
                try:
                    tool_output = mcp_client.call_tool(tool_name, tool_args)
                except Exception as exc:
                    print(f"[compute_room_cost] MCP unavailable, using local fallback: {exc}")
                    tool_output = _compute_room_cost_local(
                        tool_args, state, cost_db, mcp_client, allowed_names
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


def _forward_layout_update_to_gh(
    *,
    mcp_client,
    allowed_names: set | None,
    room_name: str,
    updated_layout_str: str,
    preferred_tool: str,
    context_label: str,
) -> tuple[str, str | None]:
    """Try to forward an updated layout to Grasshopper using available tools.

    Some GH definitions expose custom names (e.g. "Area-Based Cost Calculator Tool")
    and expect slightly different argument keys. Send a tolerant payload so both
    new and legacy clusters can consume it.
    """
    if mcp_client is None:
        return "skipped", None

    if allowed_names is None:
        candidates = [preferred_tool, "Area-Based Cost Calculator Tool", "Volume-Based Cost Calculator Tool", "compute_element_cost"]
    else:
        candidates = [
            name
            for name in [preferred_tool, "Area-Based Cost Calculator Tool", "Volume-Based Cost Calculator Tool", "compute_element_cost"]
            if name in allowed_names
        ]

    if not candidates:
        return "skipped", None

    # Include multiple key aliases to match varying GH cluster inputs.
    payload = {
        "room_name": room_name,
        "eoom_name": room_name,
        "layout_json": updated_layout_str,
        "layout_schema": updated_layout_str,
    }

    last_error = None
    for tool_name in candidates:
        try:
            gh_response = mcp_client.call_tool(tool_name, payload)
            print(f"[{context_label}] Grasshopper updated via {tool_name} for '{room_name}'")
            return f"updated ({tool_name})", gh_response
        except Exception as exc:  # pragma: no cover
            last_error = f"{tool_name}: {exc}"
            print(f"[{context_label}] GH update via {tool_name} failed: {exc}")

    return f"error: {last_error}", None


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

        # Always forward the updated layout to Grasshopper after any material/cost update
        gh_status, gh_response = _forward_layout_update_to_gh(
            mcp_client=mcp_client,
            allowed_names=allowed_names,
            room_name=room_name,
            updated_layout_str=updated_layout_str,
            preferred_tool="Volume-Based Cost Calculator Tool",
            context_label="Slab Cost Calculation"
        )
        # If GH returned a full layout, adopt it.
        if gh_response:
            try:
                gh_parsed = json.loads(gh_response)
                if isinstance(gh_parsed, dict) and isinstance(gh_parsed.get("rooms"), list) and gh_parsed["rooms"]:
                    state["layout_json_string"] = json.dumps(gh_parsed)
            except (json.JSONDecodeError, TypeError):
                pass

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

        gh_status, gh_response = _forward_layout_update_to_gh(
            mcp_client=mcp_client,
            allowed_names=allowed_names,
            room_name=room_name,
            updated_layout_str=updated_layout_str,
            preferred_tool="Area-Based Cost Calculator Tool",
            context_label="compute_finish_cost",
        )
        if gh_response:
            try:
                gh_parsed = json.loads(gh_response)
                if isinstance(gh_parsed, dict) and isinstance(gh_parsed.get("rooms"), list) and gh_parsed["rooms"]:
                    state["layout_json_string"] = json.dumps(gh_parsed)
            except (json.JSONDecodeError, TypeError):
                pass

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


def _compute_room_cost_local(
    args: dict,
    state: dict,
    cost_db: dict | None,
    mcp_client=None,
    allowed_names: set | None = None,
) -> str:
    """Local fallback for room total-cost requests when MCP compute_room_cost is unavailable."""
    layout_json_string = state.get("layout_json_string", "")
    room_name = args.get("room_name")
    if not room_name:
        return json.dumps({"error": "room_name is required"})

    try:
        layout_obj = json.loads(layout_json_string) if layout_json_string else {}
    except (json.JSONDecodeError, TypeError):
        layout_obj = {}

    target_room = None
    for room in layout_obj.get("rooms", []) or []:
        if _norm(room.get("name")) == _norm(room_name):
            target_room = room
            break

    if target_room is None:
        return json.dumps({"error": f"Room '{room_name}' not found in layout"})

    try:
        area = float(target_room.get("area_m2") or 0)
    except (TypeError, ValueError):
        area = 0.0
    try:
        rate = float(target_room.get("rate_per_m2") or 0)
    except (TypeError, ValueError):
        rate = 0.0

    base_total = round(area * rate, 2)
    finishes_total = round(sum(float(f.get("cost") or 0) for f in (target_room.get("finishes") or [])), 2)
    slabs_total = round(sum(float(s.get("cost") or 0) for s in (target_room.get("slabs") or [])), 2)

    # If rate_per_m2 already includes extras (via _sync_rate_to_extras), keep base_total as total.
    # Otherwise include explicit extras.
    if "base_rate_per_m2" in target_room:
        total_cost = base_total
    else:
        total_cost = round(base_total + finishes_total + slabs_total, 2)

    target_room["total_cost"] = total_cost
    updated_layout_str = json.dumps(layout_obj)
    state["layout_json_string"] = updated_layout_str

    gh_status, _ = _forward_layout_update_to_gh(
        mcp_client=mcp_client,
        allowed_names=allowed_names,
        room_name=room_name,
        updated_layout_str=updated_layout_str,
        preferred_tool="Area-Based Cost Calculator Tool",
        context_label="compute_room_cost_local",
    )

    currency = (cost_db or {}).get("_currency", "AED")
    return json.dumps(
        {
            "room_name": room_name,
            "area_m2": area,
            "rate_per_m2": rate,
            "finishes_total_cost": finishes_total,
            "slabs_total_cost": slabs_total,
            "total_cost": total_cost,
            "currency": currency,
            "grasshopper_update": gh_status,
        }
    )


# ---------------------------------------------------------------------------
# General-purpose surface cost calculator (area-based)
# ---------------------------------------------------------------------------
def compute_surface_cost(args: dict, state: dict, cost_db: dict | None,
    mcp_client=None, allowed_names: set | None = None) -> str:
    """
    Calculate cost for any surface (floor, wall, ceiling, etc.) or element by area.
    Args must include: room_name, surface (e.g. 'floor', 'wall'), material, area_m2.
    """
    layout_json_string = state.get("layout_json_string", "")
    room_name = args.get("room_name")
    material = args.get("material")
    surface = _norm(args.get("surface"))
    area = args.get("area_m2")
    try:
        area = float(area)
    except (TypeError, ValueError):
        return json.dumps({"error": "area_m2 is required and must be a number"})
    if not room_name or not material or not surface:
        return json.dumps({"error": "room_name, surface, and material are required"})
    # Rate lookup: cost_db._rates.room_finishes.{surface}_finish
    rates = (cost_db or {}).get("_rates") or {}
    section = (rates.get("room_finishes") or {}).get(f"{surface}_finish") or {}
    by_material = {_norm(k): v for k, v in (section.get("by_material") or {}).items()}
    rate = by_material.get(_norm(material))
    if rate is None and section.get("default") is not None:
        rate = section["default"]
    if rate is None:
        return json.dumps({"error": f"No rate available for {surface} material '{material}'."})
    rate = float(rate)
    cost = round(area * rate, 2)
    currency = (cost_db or {}).get("_currency", "AED")
    # Update layout
    try:
        layout_obj = json.loads(layout_json_string) if layout_json_string else {}
    except (json.JSONDecodeError, TypeError):
        layout_obj = {}
    for room in layout_obj.get("rooms", []):
        if _norm(room.get("name")) == _norm(room_name):
            finishes = room.setdefault("finishes", [])
            finishes[:] = [f for f in finishes if _norm(f.get("surface")) != surface]
            finishes.append({
                "surface": surface,
                "material": material,
                "area_m2": area,
                "rate_per_m2": rate,
                "cost": cost,
                "currency": currency,
            })
            room[f"{surface}_material"] = material
            room[f"{surface}_rate_per_m2"] = rate
            room[f"{surface}_area_m2"] = area
            room[f"{surface}_cost"] = cost
            break
    updated_layout_str = json.dumps(layout_obj)
    state["layout_json_string"] = updated_layout_str
    gh_status, gh_response = _forward_layout_update_to_gh(
        mcp_client=mcp_client,
        allowed_names=allowed_names,
        room_name=room_name,
        updated_layout_str=updated_layout_str,
        preferred_tool="Area-Based Cost Calculator Tool",
        context_label="compute_surface_cost",
    )
    return json.dumps({
        "room_name": room_name,
        "surface": surface,
        "material": material,
        "area_m2": area,
        "rate_per_m2": rate,
        "cost": cost,
        "currency": currency,
        "grasshopper_update": gh_status,
    })


# ---------------------------------------------------------------------------
# General-purpose volumetric cost calculator (volume-based)
# ---------------------------------------------------------------------------
def compute_volume_cost(args: dict, state: dict, cost_db: dict | None,
    mcp_client=None, allowed_names: set | None = None) -> str:
    """
    Calculate cost for any volumetric element (slab, beam, column, etc.).
    Args must include: element_name, material, volume_m3.
    """
    layout_json_string = state.get("layout_json_string", "")
    element_name = args.get("element_name") or args.get("room_name")
    material = args.get("material")
    volume = args.get("volume_m3")
    try:
        volume = float(volume)
    except (TypeError, ValueError):
        return json.dumps({"error": "volume_m3 is required and must be a number"})
    if not element_name or not material:
        return json.dumps({"error": "element_name and material are required"})
    # Rate lookup: cost_db._rates.room_finishes.slab_material (for slabs/beams/columns)
    rates = (cost_db or {}).get("_rates") or {}
    section = (rates.get("room_finishes") or {}).get("slab_material") or {}
    by_material = {_norm(k): v for k, v in (section.get("by_material") or {}).items()}
    rate = by_material.get(_norm(material))
    if rate is None and section.get("default") is not None:
        rate = section["default"]
    if rate is None:
        return json.dumps({"error": f"No rate available for volumetric material '{material}'."})
    rate = float(rate)
    cost = round(volume * rate, 2)
    currency = (cost_db or {}).get("_currency", "AED")
    # Update layout (store under 'volumes' for generality)
    try:
        layout_obj = json.loads(layout_json_string) if layout_json_string else {}
    except (json.JSONDecodeError, TypeError):
        layout_obj = {}
    for room in layout_obj.get("rooms", []):
        if _norm(room.get("name")) == _norm(element_name):
            volumes = room.setdefault("volumes", [])
            volumes.append({
                "material": material,
                "volume_m3": volume,
                "rate_per_m3": rate,
                "cost": cost,
                "currency": currency,
            })
            break
    updated_layout_str = json.dumps(layout_obj)
    state["layout_json_string"] = updated_layout_str
    gh_status, gh_response = _forward_layout_update_to_gh(
        mcp_client=mcp_client,
        allowed_names=allowed_names,
        room_name=element_name,
        updated_layout_str=updated_layout_str,
        preferred_tool="Volume-Based Cost Calculator Tool",
        context_label="compute_volume_cost",
    )
    return json.dumps({
        "element_name": element_name,
        "material": material,
        "volume_m3": volume,
        "rate_per_m3": rate,
        "cost": cost,
        "currency": currency,
        "grasshopper_update": gh_status,
    })
