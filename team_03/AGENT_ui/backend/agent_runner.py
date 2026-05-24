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
                "type": MessageType.agent_event.value,
                "node": node,
                "status": "started",
            },
        )
        await asyncio.sleep(1.0)

        # completed with simulated data
        await ws_manager.send_personal(
            websocket,
            {
                "type": MessageType.agent_event.value,
                "node": node,
                "status": "completed",
                "data": f"{node} analysis finished",
            },
        )

    # Final agent response
    await ws_manager.send_personal(
        websocket,
        {
            "type": MessageType.agent_response.value,
            "content": (
                f"Analysis complete for layout '{layout_id}'.\n\n"
                f"**Prompt**: \"{prompt}\"\n\n"
                "All 12 pipeline nodes ran successfully:\n"
                "- Profile Agent: identified space requirements\n"
                "- Space Type Agent: classified zones\n"
                "- Reasoning: determined optimal placement strategy\n"
                "- Add Objects: placed furniture and equipment\n"
                "- Collision/Visibility/Orientation: spatial analysis passed\n"
                "- Path/Reachability: connectivity verified\n"
                "- Scoring: layout scored and graded\n\n"
                "*This is a simulated response. Connect the LangGraph pipeline for real analysis.*"
            ),
            "tool_calls": [
                {"name": "collision_check", "status": "completed", "args": {"threshold": 0.3}, "result": "No collisions detected"},
                {"name": "visibility_analysis", "status": "completed", "args": {"sightlines": True}, "result": "All zones visible"},
                {"name": "scoring", "status": "completed", "args": {"weights": "default"}, "result": "Score: 82/100 (B)"},
            ],
        },
    )
