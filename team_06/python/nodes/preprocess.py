from typing import Any
import json

def build_preprocessing_node() -> Any:
    """Check: do we have a layout with rooms?"""
    def preprocessing(state: dict) -> dict:
        layout_json = state.get("layout_json_string", "")
        
        if not layout_json:
            return {
                "preprocessing_result": "error",
                "final_response": "No layout provided."
            }
        
        try:
            layout = json.loads(layout_json)
            has_rooms = len(layout.get("rooms", [])) > 0
        except:
            return {
                "preprocessing_result": "error",
                "final_response": "Invalid layout JSON."
            }
        
        if has_rooms:
            return {"preprocessing_result": "evaluate"}
        else:
            return {"preprocessing_result": "parse"}
    
    return preprocessing