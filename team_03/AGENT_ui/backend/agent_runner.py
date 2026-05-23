"""
Stub agent runner — simulates the full LangGraph pipeline.
Agent B will replace this with real LangGraph integration.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict, Optional

from websocket_manager import ConnectionManager, MessageType

# Ordered list of pipeline nodes, matching the real LangGraph graph.
PIPELINE_NODES = [
    "profile_agent",
    "space_type_agent",
    "reason",
    "add_objects",
    "collision",
    "visibility",
    "path_analysis",
    "reachability",
    "orientation",
    "scoring",
    "checkpoint",
    "explain",
]


async def run_agent(
    prompt: str,
    layout: Optional[Dict[str, Any]],
    ws_manager: ConnectionManager,
    websocket: Any,
) -> None:
    """
    Simulate the agent pipeline by emitting started/completed events for each
    node, then a final agent_response summary.

    Replace the body of this function with real LangGraph calls when ready.
    """
    layout_id = (layout or {}).get("layout", {}) if isinstance(layout, dict) else {}
    if isinstance(layout, dict):
        layout_id = layout.get("layout_name", "unknown")
    else:
        layout_id = "unknown"

    # Emit events for each pipeline node
    for node in PIPELINE_NODES:
        # started
        await ws_manager.send_personal(
            websocket,
            {
                "type": MessageType.agent_event,
                "node": node,
                "status": "started",
            },
        )
        await asyncio.sleep(1)

        # completed
        await ws_manager.send_personal(
            websocket,
            {
                "type": MessageType.agent_event,
                "node": node,
                "status": "completed",
            },
        )

    # Final agent response
    await ws_manager.send_personal(
        websocket,
        {
            "type": MessageType.agent_response,
            "content": (
                f"[STUB] Analysis complete for layout '{layout_id}'. "
                f"Processed prompt: \"{prompt}\". "
                "All pipeline nodes ran successfully. "
                "Replace agent_runner.py with real LangGraph integration."
            ),
            "tool_calls": [],
        },
    )
