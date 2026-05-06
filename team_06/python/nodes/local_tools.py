# ============================================================================
# local_tools.py — Local Python tools executed directly in the graph.
#
# These are tools that don't go through MCP — they're called directly
# from the local_tool node for simpler, faster execution.
# ============================================================================

from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from functools import lru_cache

from tools.embedding_matcher import match_layouts
from tools.layout_filter import select_layout
from tools.graph_searcher import GraphSearcher


# ---------------------------------------------------------------------------
# File loading — cache JSON files to avoid repeated disk reads.
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_all_layouts() -> list[dict[str, Any]]:
    """Load all layouts from sample_layouts.json."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    repo_root = Path(__file__).resolve().parent.parent.parent
    layouts_path = repo_root / "layout_inputs" / "sample_layouts.json"
    return json.loads(layouts_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _load_all_descriptions() -> list[dict[str, Any]]:
    """Load layout descriptions from sample_descriptions.json."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    repo_root = Path(__file__).resolve().parent.parent.parent
    descriptions_path = repo_root / "layout_inputs" / "sample_descriptions.json"
    return json.loads(descriptions_path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _get_graph_searcher() -> GraphSearcher:
    """Initialize and cache GraphSearcher instance."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    layouts_path = repo_root / "layout_inputs" / "sample_layouts.json"
    return GraphSearcher(str(layouts_path))



# ---------------------------------------------------------------------------
# Local tools catalog — tools available directly (not via MCP).
# ---------------------------------------------------------------------------

def get_local_tools() -> list[dict[str, Any]]:
    """Return definitions of all local (non-MCP) tools."""
    return [
        {
            "name": "layout_filter",
            "description": "This tool selects a layout based on its layoutId. Use this after layout_graph_search to get the full layout JSON for a selected match.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "layoutId": {
                        "type": "string",
                        "description": "The layout ID (e.g., 'layout-1', 'layout-4')"
                    }
                },
                "required": ["layoutId"]
            }
        },
        {
            "name": "layout_graph_search",
            "description": "Search layouts by graph topology. Use 'room_program' to find layouts with specific room types (e.g., find layouts with bed+kitchen+living). Use 'graph_similarity' to compare room connection patterns.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "search_type": {
                        "type": "string",
                        "enum": ["room_program", "graph_similarity"],
                        "description": "Type of graph search to perform"
                    },
                    "programs": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "For room_program: list of room types to find (e.g., ['bed', 'kitchen', 'living'])"
                    },
                    "min_match": {
                        "type": "integer",
                        "description": "For room_program: minimum number of programs to match (default: all programs)"
                    }
                },
                "required": ["search_type"]
            }
        },
        {
            "name": "layout_matcher",
            "description": "[OPTIONAL] Find layouts by semantic description. This tool is available but graph-based search is preferred.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "User's natural language description of desired apartment (e.g., 'cozy 2-bedroom with open kitchen')"
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of top results to return (default: 3)",
                        "default": 3
                    },
                    "min_score": {
                        "type": "number",
                        "description": "Minimum similarity score 0-1 to include results (default: 0.5)",
                        "default": 0.5
                    }
                },
                "required": ["query"]
            }
        }
    ]


# ---------------------------------------------------------------------------
# Local tool node — executes local Python tools.
# ---------------------------------------------------------------------------

def build_local_tool_node():
    """Return a local tool node function ready to be added to a LangGraph StateGraph."""

    def local_tool_node(state):
        """Execute pending local tool calls and append results to conversation history."""

        remaining_calls = []  # Tools that aren't local (to pass to run_tool)
        
        # Iterate over the pending local tool calls
        for call in state["pending_tool_calls"]:
            tool_name = call["name"]
            
            # Skip non-local tools
            if tool_name not in ["layout_filter", "layout_matcher", "layout_graph_search"]:
                remaining_calls.append(call)
                continue
            
            print(f"Calling local tool: {tool_name} with arguments: {call['arguments']}")

            # Cleanup any null values accidentally included by the LLM
            tool_args = {k: v for k, v in call["arguments"].items() if v is not None}

            # Execute the appropriate local tool
            if tool_name == "layout_filter":
                all_layouts = _load_all_layouts()
                tool_output = select_layout(
                    all_layouts=all_layouts,
                    layout_id=tool_args.get("layoutId")
                )
                state["layout_json_string"] = json.dumps(tool_output, indent=2)
                
                # Update session state with selected layout ID
                selected_id = tool_args.get("layoutId")
                state["layout_id"] = selected_id
                state["last_action"] = f"Selected layout {selected_id}"
                print(f"[local_tool] Updated state: layout_id={selected_id}")
                
            elif tool_name == "layout_matcher":
                all_descriptions = _load_all_descriptions()
                query_text = tool_args.get("query") or tool_args.get("description")
                
                raw_output = match_layouts(
                    query=query_text,
                    all_descriptions=all_descriptions,
                    top_k=tool_args.get("top_k", 3),
                    min_score=tool_args.get("min_score", 0.15)
                )
                tool_output = raw_output
                
                # Save candidate layouts with layoutId and score only
                candidates = []
                for match in raw_output.get("matches", []):
                    candidates.append({
                        "layoutId": match["layoutId"],
                        "score": match["score"]
                    })
                state["candidate_layouts"] = candidates
                
                # Update session state with search action
                state["last_action"] = f"Searched for: {query_text}"
                print(f"[local_tool] Updated state: candidate_layouts with {len(candidates)} results")
                
            elif tool_name == "layout_graph_search":
                graph_searcher = _get_graph_searcher()
                search_type = tool_args.get("search_type", "room_program")
                
                if search_type == "room_program":
                    programs = tool_args.get("programs", [])
                    min_match = tool_args.get("min_match")
                    results = graph_searcher.search_by_room_program(programs, min_match)
                    
                    # Format results: [(layout_id, count), ...]
                    candidates = [
                        {"layoutId": layout_id, "score": count / len(programs) if programs else 0}
                        for layout_id, count in results
                    ]
                    tool_output = {
                        "method": "room_program",
                        "programs": programs,
                        "matches": candidates,
                        "total": len(candidates)
                    }
                    state["last_action"] = f"Graph search for rooms: {', '.join(programs)}"
                    
                else:  # graph_similarity
                    # For graph similarity, we'd need a pattern graph from the user
                    # For now, return info message
                    tool_output = {
                        "method": "graph_similarity",
                        "note": "Graph similarity requires a reference layout pattern (not yet implemented)"
                    }
                    state["last_action"] = "Graph similarity search (not yet implemented)"
                
                state["candidate_layouts"] = candidates if search_type == "room_program" else []
                print(f"[local_tool] Graph search results: {len(candidates)} layouts found" if search_type == "room_program" else f"[local_tool] {tool_output}")
            else:
                tool_output = {"error": f"Unknown tool: {tool_name}"}

            # Append to conversation history
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
                "content": f"Tool result: {json.dumps(tool_output)}",
            })
            
            print(f"[local_tool] Result: {tool_output}")

        state["pending_tool_calls"] = remaining_calls if remaining_calls else None
        return state

    return local_tool_node