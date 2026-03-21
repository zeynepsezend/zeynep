from __future__ import annotations

import json
from typing import Any, Callable


# This tiny schema keeps the classifier honest: it must return only one route.
CLASSIFIER_RESPONSE_FORMAT: dict[str, Any] = {
    "response_format": {
        "type": "json_schema",
        "json_schema": {
            "name": "domain_route",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "route": {
                        "type": "string",
                        "enum": ["volume", "area", "both"],
                    }
                },
                "required": ["route"],
                "additionalProperties": False,
            },
        },
    }
}


CLASSIFIER_PROMPT = """You are routing a geometry request inside a LangGraph workflow.
Choose exactly one route:
- volume: the user is asking only about volume
- area: the user is asking only about area or surface area
- both: the user is asking about both volume and area

Return strictly valid JSON with exactly this shape:
{
  \"route\": \"volume\" | \"area\" | \"both\"
}

Output rules:
- Return JSON only.
- Do not use markdown code fences.
- Do not add explanation before or after the JSON object.
"""


def _strip_markdown_code_fence(content: str) -> str:
    stripped = content.strip()
    if not stripped.startswith("```"):
        return stripped

    lines = stripped.splitlines()
    if len(lines) < 3:
        return stripped
    if not lines[-1].strip().startswith("```"):
        return stripped

    return "\n".join(lines[1:-1]).strip()


def create_classifier_node(llm: Any, dbg: Callable[[str], None]) -> Callable[[dict[str, Any]], dict[str, Any]]:
    """
    Build a very small node whose only job is to decide which domain workflow
    should run next.
    """

    def classifier_node(state: dict[str, Any]) -> dict[str, Any]:
        dbg("[graph][classify] Enter node")

        result = llm.invoke(
            [
                {"role": "system", "content": CLASSIFIER_PROMPT},
                {"role": "user", "content": state["user_prompt"]},
            ]
        )
        content = result.content
        if not isinstance(content, str):
            raise RuntimeError("Classifier response content must be a string")

        parsed = json.loads(_strip_markdown_code_fence(content))
        route = parsed.get("route")
        if route not in {"volume", "area", "both"}:
            raise RuntimeError("Classifier must return route='volume', 'area', or 'both'")

        state["route"] = route
        dbg(f"[graph][classify] Decision={route}")
        return state

    return classifier_node