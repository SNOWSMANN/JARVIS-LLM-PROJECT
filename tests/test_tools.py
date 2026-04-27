from jarvis.tools.registry import Tool, ToolRegistry


def test_registry_call_ok() -> None:
    reg = ToolRegistry()
    reg.register(
        Tool(
            name="add",
            description="add two numbers",
            parameters={
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"},
                },
                "required": ["a", "b"],
            },
            func=lambda a, b: {"ok": True, "sum": a + b},
        )
    )
    res = reg.call("add", {"a": 2, "b": 3})
    assert res == {"ok": True, "sum": 5}


def test_registry_unknown_tool() -> None:
    reg = ToolRegistry()
    res = reg.call("nope", {})
    assert res["ok"] is False
    assert "Unknown" in res["error"]


def test_registry_bad_args() -> None:
    reg = ToolRegistry()
    reg.register(
        Tool(
            name="needs",
            description="",
            parameters={"type": "object", "properties": {}},
            func=lambda x: {"ok": True, "x": x},
        )
    )
    res = reg.call("needs", {})
    assert res["ok"] is False


def test_schemas_shape() -> None:
    reg = ToolRegistry()
    reg.register(
        Tool(
            name="t",
            description="desc",
            parameters={"type": "object", "properties": {}},
            func=lambda: {"ok": True},
        )
    )
    schemas = reg.schemas()
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "t"
