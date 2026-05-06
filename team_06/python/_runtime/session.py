"""Session persistence — save/load minimal working context between CLI runs.

Only persists essential state (current_layout_id, last action summary).
Does NOT save full message history to avoid token bloat.
"""

import json
from pathlib import Path


SESSION_FILE = Path(__file__).parent.parent / ".session.json"


def save_session_state(state: dict) -> None:
    """Save minimal essential state to disk for next run.
    
    Only saves:
    - candidate_layouts: list of search results with layoutId and score
    - current_layout_id: which layout is selected
    - last_action: brief summary of what was done
    
    Does NOT save messages to avoid bloat on next call.
    """
    persistent_state = {
        "candidate_layouts": state.get("candidate_layouts"),
        "layout_id": state.get("layout_id"),
        "last_action": state.get("last_action"),
    }
    with open(SESSION_FILE, "w") as f:
        json.dump(persistent_state, f, indent=2)
    print(f"[Session saved: candidates={len(state.get('candidate_layouts', []))} layout={persistent_state.get('layout_id')}]")


def load_session_state() -> dict | None:
    """Load minimal session context from disk, or None if no session."""
    if SESSION_FILE.exists():
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[Session load error: {e}]")
            return None
    return None


def clear_session() -> None:
    """Clear the saved session (for starting fresh conversation)."""
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
        print("[Session cleared]")
