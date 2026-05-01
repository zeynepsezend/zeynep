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


def select_layout(repo_root: Path) -> Path:
    """Discover available layout files and prompt the user to select one.
    
    Searches for JSON files in layout_input/ directory.
    Returns the Path to the selected layout file.
    """
    layout_dir = repo_root / "layout_input"
    
    # Find all JSON files in the layout_input directory
    layout_files = sorted(layout_dir.glob("*.json"))
    
    if not layout_files:
        raise FileNotFoundError(f"No JSON files found in {layout_dir}")
    
    # If only one file exists, use it without prompting
    if len(layout_files) == 1:
        print(f"Using layout: {layout_files[0].name}")
        return layout_files[0]
    
    # Multiple files: prompt the user to select
    print("\nAvailable layouts:")
    for i, file in enumerate(layout_files, 1):
        print(f"  {i}. {file.name}")
    
    while True:
        try:
            choice = input("\nSelect a layout (enter number): ").strip()
            index = int(choice) - 1
            if 0 <= index < len(layout_files):
                selected = layout_files[index]
                print(f"Selected: {selected.name}\n")
                return selected
            else:
                print(f"Please enter a number between 1 and {len(layout_files)}")
        except ValueError:
            print("Invalid input. Please enter a number.")


def bootstrap(layout_path: Path | None = None) -> Context:
    """Load settings, connect to the MCP server, discover tools, and build the LLM.

    Call this once from main.py and pass the returned Context into run_agent().
    
    Args:
        layout_path: Optional Path to a specific layout file. If not provided,
                    will use the default layout_input/layout_schema.json.
    """
    settings = load_settings()

    # Determine which layout file to use
    repo_root = Path(__file__).resolve().parents[3]
    if layout_path is None:
        layout_path = repo_root / "layout_input" / "layout_schema.json"
    
    # Read the layout schema that will be given to the agent as context
    layout_data: dict[str, Any] = json.loads(layout_path.read_text(encoding="utf-8"))

    # Connect to the Grasshopper MCP server and list available tools
    mcp_client = McpClient(settings.mcp_endpoint, settings.request_timeout_seconds)
    mcp_client.initialize()
    tools = mcp_client.list_tools()
    print(f"Discovered MCP tools: {[t.get('name') for t in tools]}")

    # Build the LLM with a structured-output schema tailored to the available tools
    llm = create_chat_llm(
        api_key=settings.api_key,
        base_url=settings.base_url,
        llm_model=settings.llm_model,
        timeout_seconds=settings.request_timeout_seconds,
        model_kwargs=get_llm_response_format(tools),
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
    )
