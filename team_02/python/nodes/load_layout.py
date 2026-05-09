"""
nodes/load_layout.py — LOAD_LAYOUT node for the Comfort Copilot state graph.

Pure Python — no LLM, no MCP calls. Runs after PREPROCESS on the comfort path.

Responsibilities:
  1. If a layout_id was detected in the prompt (e.g. "201"), find and load
     the matching JSON file from layout_input_dir automatically.
  2. If no layout_id was found (or the file is not found), show the
     interactive terminal picker so the user can select a layout.
  3. Skip loading entirely if a layout is already in state from a previous
     turn in the multi-turn session.

Writes to state:
  layout_json_string  (str)  — full JSON of the loaded layout
  layout_id           (str)  — confirmed layout ID (e.g. "201")
"""

from __future__ import annotations
import json
from pathlib import Path


def build_load_layout_node(layout_input_dir: Path):
    """Return the load_layout node function, capturing layout_input_dir."""

    def load_layout_node(state: dict) -> dict:

        # ── Skip if layout already loaded in this session ─────────────────
        if state.get("layout_json_string"):
            existing_id = state.get("layout_id", "?")
            print(f"[load_layout] Layout {existing_id} already loaded — skipping.")
            return state

        layout_id: str | None = state.get("layout_id")

        # ── Try to load by ID first ───────────────────────────────────────
        selected: Path | None = None

        if layout_id:
            matches = sorted(layout_input_dir.glob(f"*{layout_id}*.json"))
            if matches:
                selected = matches[0]
                print(f"[load_layout] Found layout for ID {layout_id}: {selected.name}")

        # ── Fall back to interactive picker ──────────────────────────────
        if selected is None:
            selected = _pick_layout_interactively(layout_input_dir)

        # ── Read and store ────────────────────────────────────────────────
        try:
            layout_data = json.loads(selected.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"[load_layout] Failed to read {selected.name}: {exc}") from exc

        # Confirm the layout ID from the file itself (more reliable than prompt)
        confirmed_id = str(layout_data.get("layoutId", layout_id or "?"))
        print(f"[load_layout] Loaded layout {confirmed_id} from {selected.name}")

        return {
            **state,
            "layout_json_string": json.dumps(layout_data),
            "layout_id":          confirmed_id,
        }

    return load_layout_node


# ---------------------------------------------------------------------------
# Interactive picker (terminal)
# ---------------------------------------------------------------------------

def _pick_layout_interactively(layout_input_dir: Path) -> Path:
    """List JSON files in layout_input_dir and prompt the user to pick one."""
    if not layout_input_dir.exists():
        raise RuntimeError(f"[load_layout] Layout directory not found: {layout_input_dir}")

    layout_files = sorted(layout_input_dir.glob("*.json"))
    if not layout_files:
        raise RuntimeError(f"[load_layout] No JSON files found in {layout_input_dir}")

    if len(layout_files) == 1:
        print(f"[load_layout] Using the only available layout: {layout_files[0].name}")
        return layout_files[0]

    print("\nAvailable layouts:")
    for i, f in enumerate(layout_files, 1):
        print(f"  {i}. {f.name}")

    while True:
        try:
            choice = input("\nSelect a layout (enter number): ").strip()
            index = int(choice) - 1
            if 0 <= index < len(layout_files):
                selected = layout_files[index]
                print(f"Selected: {selected.name}\n")
                return selected
            print(f"Please enter a number between 1 and {len(layout_files)}")
        except ValueError:
            print("Invalid input. Please enter a number.")
