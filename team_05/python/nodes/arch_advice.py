from __future__ import annotations
import json
import pathlib
from typing import Any

from nodes.ec3_client import get_ec3_gwp

# ---------------------------------------------------------------------------
# Static property database loader
# ---------------------------------------------------------------------------

_PROPS_CACHE: dict = {}

def _load_props() -> dict:
    global _PROPS_CACHE
    if _PROPS_CACHE:
        return _PROPS_CACHE

    candidates = [
        pathlib.Path(__file__).parent.parent / "material_properties.json",
        pathlib.Path("team_05/python/material_properties.json"),
        pathlib.Path("material_properties.json"),
    ]
    for p in candidates:
        if p.exists():
            _PROPS_CACHE = json.loads(p.read_text(encoding="utf-8"))
            return _PROPS_CACHE

    print("[arch_advice] WARNING: material_properties.json not found")
    return {}


def _lookup_static(material_key: str) -> dict:
    """Search all category sections of material_properties.json for material_key."""
    props = _load_props()
    key = material_key.lower().replace(" ", "_").replace("-", "_")
    for section_name, section in props.items():
        if section_name == "_meta" or not isinstance(section, dict):
            continue
        if key in section:
            return section[key]
    return {}

# ---------------------------------------------------------------------------
# Material extraction from layout JSON
# ---------------------------------------------------------------------------

_ROOM_FINISH_KEYS = ["floor_finish", "wall_finish", "ceiling_material", "slab_material"]
_OPENING_KEYS = ["leaf_material", "frame_material", "glazing", "window_material"]


def _extract_materials(state: dict[str, Any]) -> list[str]:
    """Collect unique material keys from tool call history, layout JSON, and input_data."""
    materials: list[str] = []

    # Primary source: tool call arguments in the message history.
    # compute_finish_cost and compute_slab_cost always carry a "material" argument.
    for msg in state.get("messages", []):
        if msg.get("role") != "assistant":
            continue
        try:
            body = json.loads(msg["content"])
            if body.get("action") != "tool":
                continue
            for call in body.get("tool_calls", []):
                args = call.get("arguments", {})
                val = args.get("material") or args.get("finish") or args.get("element")
                if val:
                    materials.append(str(val).lower().replace(" ", "_").replace("-", "_"))
        except (json.JSONDecodeError, KeyError, TypeError):
            continue

    # Secondary source: layout JSON room/opening finish fields
    layout_str = state.get("layout_json_string", "")
    if layout_str:
        try:
            layout = json.loads(layout_str)
            for room in layout.get("rooms", []):
                for k in _ROOM_FINISH_KEYS:
                    val = room.get(k)
                    if val:
                        materials.append(str(val).lower().replace(" ", "_").replace("-", "_"))
            for opening in layout.get("openings", []):
                for k in _OPENING_KEYS:
                    val = opening.get(k)
                    if val:
                        materials.append(str(val).lower().replace(" ", "_").replace("-", "_"))
        except (json.JSONDecodeError, AttributeError):
            pass

    # Tertiary source: input_data for single-material price calculation
    input_data = state.get("input_data") or {}
    for field in ("material", "element", "finish"):
        val = input_data.get(field)
        if val:
            materials.append(str(val).lower().replace(" ", "_").replace("-", "_"))

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique = [m for m in materials if not (m in seen or seen.add(m))]  # type: ignore[func-returns-value]
    return unique

# ---------------------------------------------------------------------------
# Advice formatter
# ---------------------------------------------------------------------------

def _format_material_advice(material_key: str, live_gwp: float | None) -> str:
    static = _lookup_static(material_key)
    label = material_key.replace("_", " ").title()

    if not static:
        return f"**{label}**\n  • No property data found in database\n"

    fire = static.get("fire_rating", "N/A")
    life = static.get("life_cycle_years", "N/A")
    gwp_fallback = static.get("gwp_fallback_kgco2e")
    gwp_unit = static.get("gwp_unit", "kgCO2e/m²")

    if live_gwp is not None:
        gwp_display = f"{live_gwp} {gwp_unit} (EC3 live average)"
    elif gwp_fallback is not None:
        gwp_display = f"{gwp_fallback} {gwp_unit} (reference value)"
    else:
        gwp_display = "N/A"

    return (
        f"**{label}**\n"
        f"  • Carbon footprint: {gwp_display}\n"
        f"  • Fire rating: {fire}\n"
        f"  • Expected lifespan: {life} years\n"
    )

# ---------------------------------------------------------------------------
# Node builder
# ---------------------------------------------------------------------------

# Cap materials per call to avoid overloading context and EC3 rate limits
_MAX_MATERIALS = 8


def build_architectural_advice_node():
    def _architectural_advice_node(state: dict[str, Any]) -> dict[str, Any]:
        print("\n[architectural_advice] Gathering material properties...")

        materials = _extract_materials(state)
        if not materials:
            return {"architectural_advice": None}

        capped = materials[:_MAX_MATERIALS]
        if len(materials) > _MAX_MATERIALS:
            print(f"[architectural_advice] {len(materials)} materials found — capped at {_MAX_MATERIALS}")

        sections: list[str] = ["## Architectural Material Advice\n"]
        for mat in capped:
            live_gwp = get_ec3_gwp(mat)
            sections.append(_format_material_advice(mat, live_gwp))

        advice_text = "\n".join(sections)
        print(f"[architectural_advice] Advice generated for {len(capped)} material(s).")
        return {"architectural_advice": advice_text}

    return _architectural_advice_node
