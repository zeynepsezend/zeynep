from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from _runtime.config import load_settings
from _runtime.mcp_client import McpClient
from _runtime.llm import create_chat_llm, get_llm_response_format


@dataclass
class Context:
    """Everything the agent graph needs to run — passed from main.py into graph.py."""
    llm: Any
    mcp_client: McpClient
    tools: list[dict[str, Any]]
    layout_data: dict[str, Any]
    max_iterations: int
    edited_layout_path: Path
    cost_db: dict[str, Any]


# ---------------------------------------------------------------------------
# cost_rates.json helpers — single source of truth for all unit prices.
# ---------------------------------------------------------------------------

def _norm_key(s: Any) -> str:
    """Normalize a lookup key: lower-case and treat spaces/-/_ as equivalent."""
    return str(s or "").strip().lower().replace(" ", "_").replace("-", "_")


def _norm_dict(d: dict | None) -> dict:
    """Return a copy of ``d`` with normalized keys for tolerant lookups."""
    return {_norm_key(k): v for k, v in (d or {}).items()}


def _lookup_finish(section: dict, material: Any) -> float | None:
    """Look up a material rate in a finishes section (default + by_material)."""
    if not isinstance(section, dict):
        return None
    by_material = _norm_dict(section.get("by_material"))
    key = _norm_key(material)
    if key and key in by_material:
        return float(by_material[key])
    if section.get("default") is not None:
        return float(section["default"])
    return None


def _room_finish_rate(room_finishes: dict, room: dict) -> float | None:
    """Sum floor + wall + ceiling + slab finish rates from cost_rates.json.

    Returns ``None`` when the room declares no finish materials at all — in
    that case the caller should fall back to the lump-sum ``rooms`` section.
    """
    if not isinstance(room_finishes, dict):
        return None
    finish_keys = [
        ("floor_finish", room.get("floor-finish") or room.get("floor_finish")),
        ("wall_finish", room.get("wall-finish") or room.get("wall_finish")),
        ("ceiling_material", room.get("ceiling-material") or room.get("ceiling_material")),
        ("slab_material", room.get("slab-material") or room.get("slab_material")),
    ]
    if not any(material for _, material in finish_keys):
        return None
    total = 0.0
    for section_key, material in finish_keys:
        section = room_finishes.get(section_key)
        if not isinstance(section, dict):
            continue
        rate = _lookup_finish(section, material)
        if rate is not None:
            total += rate
    return total if total > 0 else None


def _resolve_room_rate(rates: dict, room: dict) -> float | None:
    """Pick a room rate_per_m2 from cost_rates.json: id -> category -> default.

    If the room declares finish materials, prefer the summed finish rate.
    """
    finish_rate = _room_finish_rate(rates.get("room_finishes", {}), room)
    if finish_rate is not None and finish_rate > 0:
        return finish_rate

    rooms_section = rates.get("rooms", {}) or {}
    by_id = _norm_dict(rooms_section.get("by_id"))
    by_cat = _norm_dict(rooms_section.get("by_category"))
    rid = _norm_key(room.get("id"))
    cat = _norm_key(room.get("category"))
    if rid and rid in by_id:
        return float(by_id[rid])
    if cat and cat in by_cat:
        return float(by_cat[cat])
    if rooms_section.get("default") is not None:
        return float(rooms_section["default"])
    return None


def _resolve_element_cost(section: dict, elem: dict) -> float | None:
    """Pick a lump-sum cost for an opening/column: id -> subtype -> default."""
    if not isinstance(section, dict):
        return None
    by_id = _norm_dict(section.get("by_id"))
    by_subtype = _norm_dict(section.get("by_subtype"))
    eid = _norm_key(elem.get("id"))
    sub = _norm_key(elem.get("subtype"))
    if eid and eid in by_id:
        return float(by_id[eid])
    if sub and sub in by_subtype:
        return float(by_subtype[sub])
    if section.get("default") is not None:
        return float(section["default"])
    return None


def _build_flat_lookup(rates: dict) -> dict[str, float]:
    """Flatten every named rate into a single dict for ``get_unit_cost_by_type``.

    Keys come from rooms (by_id/by_category), doors/windows/columns (by_id/by_subtype),
    and every material under room_finishes / door_finishes / window_finishes /
    column_finishes. Later keys overwrite earlier ones — more specific sections
    are merged last so they win on collision.
    """
    flat: dict[str, float] = {}

    def _ingest(section: dict | None, *sub_keys: str) -> None:
        if not isinstance(section, dict):
            return
        for sk in sub_keys:
            for k, v in (_norm_dict(section.get(sk)) or {}).items():
                try:
                    flat[k] = float(v)
                except (TypeError, ValueError):
                    continue
        if section.get("default") is not None:
            try:
                flat[_norm_key(sub_keys[0]) if sub_keys else "default"] = float(section["default"])
            except (TypeError, ValueError):
                pass

    # Material finish rates
    rf = rates.get("room_finishes", {}) or {}
    for finish_section in ("floor_finish", "wall_finish", "ceiling_material", "slab_material"):
        sec = rf.get(finish_section)
        if isinstance(sec, dict):
            for k, v in _norm_dict(sec.get("by_material")).items():
                try:
                    flat[k] = float(v)
                except (TypeError, ValueError):
                    pass

    df = rates.get("door_finishes", {}) or {}
    for sec_key in ("leaf_material", "frame_material"):
        sec = df.get(sec_key)
        if isinstance(sec, dict):
            for k, v in _norm_dict(sec.get("by_material")).items():
                try:
                    flat[k] = float(v)
                except (TypeError, ValueError):
                    pass

    for top in ("window_finishes", "column_finishes"):
        sec = rates.get(top, {}) or {}
        for k, v in _norm_dict(sec.get("by_material")).items():
            try:
                flat[k] = float(v)
            except (TypeError, ValueError):
                pass

    # Element-level lump sums
    _ingest(rates.get("rooms"), "by_id", "by_category")
    _ingest(rates.get("doors"), "by_id", "by_subtype")
    _ingest(rates.get("windows"), "by_id", "by_subtype")
    _ingest(rates.get("columns"), "by_id", "by_subtype")

    return flat


def _apply_rates_to_layout(layout: dict, rates: dict) -> None:
    """Overwrite per-element rates/costs in ``layout`` with values from cost_rates.json.

    Mutates the layout in place. Recomputes room ``total_cost`` and the
    project ``summary`` totals so downstream consumers see consistent numbers.
    """
    if not isinstance(layout, dict):
        return

    # Rooms: rate_per_m2 + total_cost
    rooms_total = 0.0
    for room in layout.get("rooms", []) or []:
        rate = _resolve_room_rate(rates, room)
        if rate is not None:
            room["rate_per_m2"] = rate
        area = room.get("area_m2")
        if room.get("rate_per_m2") is not None and area is not None:
            try:
                room["total_cost"] = round(float(room["rate_per_m2"]) * float(area), 2)
                rooms_total += float(room["total_cost"])
            except (TypeError, ValueError):
                pass

    # Openings (doors + windows)
    doors_total = 0.0
    windows_total = 0.0
    for opening in layout.get("openings", []) or []:
        otype = _norm_key(opening.get("type"))
        if otype == "door":
            cost = _resolve_element_cost(rates.get("doors", {}), opening)
            if cost is not None:
                opening["cost"] = cost
                doors_total += cost
        elif otype == "window":
            cost = _resolve_element_cost(rates.get("windows", {}), opening)
            if cost is not None:
                opening["cost"] = cost
                windows_total += cost

    # Columns
    columns_total = 0.0
    for col in layout.get("columns", []) or []:
        cost = _resolve_element_cost(rates.get("columns", {}), col)
        if cost is not None:
            col["cost"] = cost
            columns_total += cost

    # Refresh summary if present
    summary = layout.get("summary")
    if isinstance(summary, dict):
        summary["rooms_total"] = round(rooms_total, 2)
        summary["doors_total"] = round(doors_total, 2)
        summary["windows_total"] = round(windows_total, 2)
        summary["columns_total"] = round(columns_total, 2)
        summary["openings_total"] = round(doors_total + windows_total, 2)
        summary["structure_total"] = round(columns_total, 2)
        summary["grand_total"] = round(
            rooms_total + doors_total + windows_total + columns_total, 2
        )


def bootstrap() -> Context:
    """Load settings, connect to the MCP server, discover tools, and build the LLM.

    Call this once from main.py and pass the returned Context into run_agent().
    """
    settings = load_settings()

    # Read the layout schema that will be given to the agent as context (team_05-specific).
    # Prefer the previously edited layout (carries forward updated room costs across runs);
    # fall back to the original schema on first run or if the edited file is invalid.
    repo_root = Path(__file__).resolve().parents[3]
    layout_path = repo_root / "team_05" / "gh" / "layout_schema-team05.json"
    team_dir_for_layout = repo_root / "team_05"
    edited_layout_for_load = team_dir_for_layout / f"{team_dir_for_layout.name}_edited_layout.json"
    if edited_layout_for_load.exists():
        try:
            layout_data: dict[str, Any] = json.loads(edited_layout_for_load.read_text(encoding="utf-8"))
            if not (isinstance(layout_data, dict) and isinstance(layout_data.get("rooms"), list) and layout_data["rooms"]):
                raise ValueError("edited layout missing rooms")
            print(f"[BOOTSTRAP] Reusing edited layout: {edited_layout_for_load.name}")
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            print(f"[BOOTSTRAP] Edited layout unusable ({exc}); falling back to original schema")
            layout_data = json.loads(layout_path.read_text(encoding="utf-8"))
    else:
        layout_data = json.loads(layout_path.read_text(encoding="utf-8"))

    # Connect to the Grasshopper MCP server and list available tools
    mcp_client = McpClient(settings.mcp_endpoint, settings.request_timeout_seconds)
    mcp_client.initialize()
    tools = mcp_client.list_tools()
    print(f"Discovered MCP tools: {[t.get('name') for t in tools]}")

    # Load cost_rates.json — single source of truth for all unit prices.
    cost_rates_path = repo_root / "team_05" / "gh" / "cost_rates.json"
    try:
        cost_rates: dict[str, Any] = json.loads(cost_rates_path.read_text(encoding="utf-8"))
        print(f"[BOOTSTRAP] Loaded cost rates from {cost_rates_path.name}")
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[BOOTSTRAP] Failed to load {cost_rates_path.name} ({exc}); using empty rates")
        cost_rates = {}

    # Overlay the JSON rates onto the in-memory layout so every downstream
    # consumer (LLM context, compute_room_cost overrides, summary totals) sees
    # the cost_rates.json values rather than whatever was baked into the schema.
    _apply_rates_to_layout(layout_data, cost_rates)

    # Flat lookup powers the local ``get_unit_cost_by_type`` tool, while the
    # raw structured rates remain available for hierarchical lookups.
    cost_db: dict[str, Any] = {
        "_rates": cost_rates,
        "_flat": _build_flat_lookup(cost_rates),
        "_currency": (cost_rates.get("_meta") or {}).get("currency", "AED"),
    }
    print(
        f"[BOOTSTRAP] cost_db ready — {len(cost_db['_flat'])} named rates "
        f"(currency: {cost_db['_currency']})"
    )

    # Build the LLM with a structured-output schema tailored to the available tools
    llm = create_chat_llm(
        api_key=settings.api_key,
        base_url=settings.base_url,
        llm_model=settings.llm_model,
        timeout_seconds=settings.request_timeout_seconds,
        #model_kwargs=get_llm_response_format(tools),
    )

    team_dir = Path(__file__).resolve().parents[2]
    team_name = team_dir.name
    edited_layout_path = team_dir / f"{team_name}_edited_layout.json"

    return Context(
        llm=llm,
        mcp_client=mcp_client,
        tools=tools,
        layout_data=layout_data,
        max_iterations=settings.max_iterations,
        edited_layout_path=edited_layout_path,
        cost_db=cost_db,
    )
