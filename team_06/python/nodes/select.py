from typing import Any
import json
import re
from pathlib import Path
from tools.layout_utils import load_and_save_layout

def build_select_node(llm: Any):
    def select(state: dict) -> dict:
        user_prompt = state.get("user_prompt", "").lower()
        tried_layout_ids = state.get("tried_layout_ids", [])

        # Check if user provided a layout ID
        if "layout-" in user_prompt:
            match = re.search(r'layout-(\w+)', user_prompt)
            if match:
                layout_id = f"layout-{match.group(1)}"
                search_json = state.get("search_results_json_string", "[]")
                try:
                    results = json.loads(search_json)
                except Exception:
                    results = []
                found = any(f"layout-{r['id']}" == layout_id for r in results)
                if found and layout_id not in tried_layout_ids:
                    save_path = Path(__file__).parent.parent.parent / "team_06_edited_layout.json"
                    load_and_save_layout(layout_id, state, save_path)
                    tried_layout_ids.append(layout_id)
                    return {
                        "select_result": "success",
                        "selected_layout_id": layout_id,
                        "tried_layout_ids": tried_layout_ids,
                        "final_response": None
                    }
                else:
                    return {
                        "select_result": "failed",
                        "final_response": f"Layout {layout_id} not found or already tried.",
                        "tried_layout_ids": tried_layout_ids
                    }

        # Otherwise, pick the next untried layout from search results
        search_json = state.get("search_results_json_string", "[]")
        try:
            results = json.loads(search_json)
        except Exception:
            return {
                "select_result": "failed",
                "final_response": "No search results found.",
                "tried_layout_ids": tried_layout_ids
            }

        # Filter out already tried layouts
        untried = [r for r in results if r['id'] not in tried_layout_ids]

        if not untried:
            return {
                "select_result": "failed",
                "final_response": "No layouts left to try.",
                "tried_layout_ids": tried_layout_ids
            }

        # Pick the next untried layout
        next_layout = untried[0]
        layout_id = next_layout['id']
        save_path = Path(__file__).parent.parent.parent / "team_06_edited_layout.json"
        load_and_save_layout(layout_id, state, save_path)
        tried_layout_ids.append(layout_id)

        return {
            "select_result": "success",
            "selected_layout_id": layout_id,
            "tried_layout_ids": tried_layout_ids,
            "final_response": None
        }

    return select