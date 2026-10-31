"""The model sees a tool schema/result; only the host owns its business client."""


class BusinessPeer:
    def __init__(self):
        self.calls = []

    async def list_tools(self):
        from types import SimpleNamespace

        return SimpleNamespace(
            tools=[
                SimpleNamespace(
                    name="researcher_source_read",
                    description="Read scoped source",
                    inputSchema={
                        "type": "object",
                        "properties": {"source_id": {"type": "integer"}},
                        "required": ["source_id"],
                        "additionalProperties": False,
                    },
                )
            ]
        )

    async def call_tool(self, name, arguments):
        from types import SimpleNamespace

        self.calls.append((name, arguments))
        return SimpleNamespace(
            isError=False,
            content=[
                SimpleNamespace(
                    type="text", text='{"source_id":7,"content":"EVIDENCE_ONLY"}'
                )
            ],
        )


async def test_host_mediation_copies_real_mcp_schema_and_returns_native_result():
    from backend.runtime.business_mediation import BusinessTools

    peer = BusinessPeer()
    tools = await BusinessTools.connect(peer)
    assert tools.catalog == [
        {
            "type": "function",
            "name": "researcher_source_read",
            "description": "Read scoped source",
            "inputSchema": {
                "type": "object",
                "properties": {"source_id": {"type": "integer"}},
                "required": ["source_id"],
                "additionalProperties": False,
            },
        }
    ]
    result = await tools.call(
        {"tool": "researcher_source_read", "arguments": {"source_id": 7}}
    )
    assert result == {
        "success": True,
        "contentItems": [
            {"type": "inputText", "text": '{"source_id":7,"content":"EVIDENCE_ONLY"}'}
        ],
    }
    assert peer.calls == [("researcher_source_read", {"source_id": 7})]


async def test_unknown_native_tool_never_reaches_business_peer():
    from backend.runtime.business_mediation import BusinessTools

    peer = BusinessPeer()
    tools = await BusinessTools.connect(peer)
    response = await tools.call(
        {"tool": "query_database", "arguments": {"sql": "SELECT * FROM projects"}}
    )
    assert response["success"] is False
    assert peer.calls == []


async def test_withdrawn_host_tool_authority_does_not_dispatch_even_a_reader():
    from backend.runtime.business_mediation import BusinessTools

    active = [True]
    peer = BusinessPeer()
    tools = await BusinessTools.connect(peer, active=lambda: active[0])
    active[0] = False
    response = await tools.call(
        {"tool": "researcher_source_read", "arguments": {"source_id": 7}}
    )
    assert response["success"] is False
    assert peer.calls == []
