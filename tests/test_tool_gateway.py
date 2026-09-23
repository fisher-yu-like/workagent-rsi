import pytest

from workagent_rsi.contracts import ToolCall
from workagent_rsi.tool_gateway import ToolGateway


def test_tool_gateway_rejects_unknown_tool():
    gateway = ToolGateway({"echo": lambda args: {"value": args["value"]}})
    result = gateway.invoke(ToolCall(name="shell", arguments={"command": "dir"}))
    assert result.ok is False
    assert "not allowlisted" in result.error


def test_tool_gateway_invokes_allowlisted_tool():
    gateway = ToolGateway({"echo": lambda args: {"value": args["value"]}})
    result = gateway.invoke(ToolCall(name="echo", arguments={"value": "ok"}))
    assert result.ok is True
    assert result.output == {"value": "ok"}

