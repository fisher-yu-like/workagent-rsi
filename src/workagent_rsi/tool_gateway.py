from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .contracts import ToolCall, ToolResult


class ToolGateway:
    def __init__(self, allowlisted_tools: dict[str, Callable[[dict[str, Any]], dict[str, Any]]]) -> None:
        self.allowlisted_tools = dict(allowlisted_tools)

    def invoke(self, call: ToolCall) -> ToolResult:
        handler = self.allowlisted_tools.get(call.name)
        if handler is None:
            return ToolResult(ok=False, error=f"tool not allowlisted: {call.name}")
        try:
            return ToolResult(ok=True, output=handler(call.arguments))
        except Exception as exc:
            return ToolResult(ok=False, error=str(exc))

