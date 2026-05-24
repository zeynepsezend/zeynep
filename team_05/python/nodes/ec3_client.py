from __future__ import annotations
import os
import requests
from typing import Optional

EC3_BASE_URL = "https://api.buildingtransparency.org"
_TOKEN_ENV = "EC3_BEARER_TOKEN"

# Maps our material keys to EC3 API category names
_EC3_CATEGORY_MAP: dict[str, str] = {
    # Structural slabs
    "rc_solid": "ReadyMix Concrete",
    "rc_waffle": "ReadyMix Concrete",
    "rc_ribbed": "ReadyMix Concrete",
    "post_tensioned": "ReadyMix Concrete",
    "hollow_core": "Precast Concrete",
    "composite_steel": "Steel",
    "precast": "Precast Concrete",
    "timber_joist": "Wood",
    # Floor finishes
    "porcelain_tile": "Ceramic Tile",
    "ceramic_tile": "Ceramic Tile",
    "marble": "Stone",
    "granite": "Stone",
    "natural_stone": "Stone",
    "engineered_wood": "Wood",
    "solid_wood": "Wood",
    "laminate": "Wood",
    "vinyl": "Resilient Flooring",
    "epoxy": "Coatings",
    "polished_concrete": "ReadyMix Concrete",
    "carpet": "Carpet",
    "terrazzo": "Stone",
    # Wall finishes
    "paint": "Coatings",
    "emulsion_paint": "Coatings",
    "gypsum_paint": "Gypsum",
    "wallpaper": "Coatings",
    "wood_panel": "Wood",
    "veneer": "Wood",
    "exposed_concrete": "ReadyMix Concrete",
    "stucco": "Gypsum",
    "cladding": "Cladding",
    # Ceiling materials
    "gypsum_board": "Gypsum",
    "gypsum_painted": "Gypsum",
    "suspended_gypsum": "Gypsum",
    "acoustic_tile": "Acoustical Ceiling Tiles",
    "metal_panel": "Steel",
    "wood_slat": "Wood",
    "paint_on_slab": "Coatings",
    "stretch_ceiling": "Coatings",
    # Door leaf
    "mdf_painted": "Wood",
    "mdf_veneer": "Wood",
    "hdf_laminate": "Wood",
    "flush_hollow_core": "Wood",
    "steel": "Steel",
    "aluminum": "Aluminum",
    "upvc": "Plastic",
    "glass_frameless": "Glass",
    "fire_rated_60": "Steel",
    "fire_rated_120": "Steel",
    # Door frame
    "wood": "Wood",
    "hardwood": "Wood",
    # Window types
    "aluminum_single": "Aluminum",
    "aluminum_double": "Aluminum",
    "thermal_aluminum_double": "Aluminum",
    "thermal_aluminum_low_e": "Aluminum",
    "upvc_double": "Plastic",
    "upvc_double_low_e": "Plastic",
    "wood_double": "Wood",
    "wood_clad_aluminum": "Aluminum",
    "steel_single": "Steel",
    "steel_double": "Steel",
    "curtain_wall": "Glazing",
    # Column finishes
    "plaster_paint": "Gypsum",
    "fair_face_concrete": "ReadyMix Concrete",
    "marble_clad": "Stone",
    "metal_clad": "Steel",
    "grc_clad": "ReadyMix Concrete",
    "wood_clad": "Wood",
}

# Per-session cache: category → median GWP to avoid redundant API calls
_gwp_cache: dict[str, Optional[float]] = {}


def _normalise_key(material_key: str) -> str:
    return material_key.lower().replace(" ", "_").replace("-", "_")


def get_ec3_gwp(material_key: str) -> Optional[float]:
    """Return median GWP (kgCO2e per declared unit) from EC3 for a material.

    Falls back to None if the token is missing, the category is unmapped,
    or the API call fails — the caller should use the static fallback value.
    """
    key = _normalise_key(material_key)
    category = _EC3_CATEGORY_MAP.get(key)
    if not category:
        return None

    if category in _gwp_cache:
        return _gwp_cache[category]

    token = os.environ.get(_TOKEN_ENV)
    if not token:
        print(f"[ec3_client] {_TOKEN_ENV} not set — using static fallback for '{material_key}'")
        _gwp_cache[category] = None
        return None

    try:
        resp = requests.get(
            f"{EC3_BASE_URL}/api/v1/epds/",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "category__name": category,
                "page_size": 25,
                "format": "json",
            },
            timeout=8,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", data) if isinstance(data, dict) else data

        gwp_values: list[float] = []
        for epd in results:
            raw = epd.get("gwp_per_category_declared_unit") or epd.get("gwp_per_kg")
            if raw is not None:
                try:
                    gwp_values.append(float(raw))
                except (TypeError, ValueError):
                    pass

        result = round(sum(gwp_values) / len(gwp_values), 2) if gwp_values else None
        _gwp_cache[category] = result
        print(f"[ec3_client] EC3 GWP for '{category}': {result} kgCO2e (n={len(gwp_values)})")
        return result

    except requests.RequestException as exc:
        print(f"[ec3_client] API error for '{category}': {exc} — using static fallback")
        _gwp_cache[category] = None
        return None
