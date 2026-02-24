from __future__ import annotations

from copy import deepcopy
from typing import Any


def _enforce_schema_node(node: Any) -> Any:
    if isinstance(node, list):
        return [_enforce_schema_node(item) for item in node]
    if not isinstance(node, dict):
        return node

    normalized: dict[str, Any] = {key: _enforce_schema_node(value) for key, value in node.items()}

    node_type = normalized.get("type")
    if node_type == "object":
        properties = normalized.get("properties")
        if not isinstance(properties, dict):
            properties = {}
        normalized["properties"] = {key: _enforce_schema_node(value) for key, value in properties.items()}
        normalized.setdefault("required", [])
        normalized["additionalProperties"] = False

    if node_type == "array" and "items" in normalized:
        normalized["items"] = _enforce_schema_node(normalized["items"])

    for combinator in ("allOf", "anyOf", "oneOf"):
        if combinator in normalized:
            normalized[combinator] = _enforce_schema_node(normalized[combinator])

    for branch in ("not", "if", "then", "else"):
        if branch in normalized:
            normalized[branch] = _enforce_schema_node(normalized[branch])

    return normalized


def enforce_no_additional_properties(schema: dict[str, Any]) -> dict[str, Any]:
    return _enforce_schema_node(deepcopy(schema))
