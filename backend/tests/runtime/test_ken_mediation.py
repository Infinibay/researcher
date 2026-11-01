"""Required Ken capabilities and argument schemas before native admission."""

import copy
from types import SimpleNamespace

import pytest

NAMES = ("ken_find", "ken_read", "ken_recall", "ken_related", "ken_remember")


def tool(name):
    return SimpleNamespace(
        name=name,
        description="Scoped " + name,
        inputSchema={
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
    )


class Peer:
    def __init__(self, tools=None):
        self.tools = tools if tools is not None else [tool(name) for name in NAMES]
        self.calls = []
        self.pages = []

    async def list_tools(self, *, cursor=None):
        self.pages.append(cursor)
        return SimpleNamespace(tools=self.tools, nextCursor=None)

    async def call_tool(self, name, arguments):
        self.calls.append((name, copy.deepcopy(arguments)))
        return SimpleNamespace(
            isError=False,
            content=[SimpleNamespace(type="text", text="source evidence")],
        )


async def test_required_ken_catalog_filters_extra_tools_and_uses_shared_result_boundary():
    from backend.runtime.ken_mediation import KenTools

    peer = Peer([tool("unrelated_write"), *[tool(name) for name in reversed(NAMES)]])
    tools = await KenTools.connect(peer)
    assert [row["name"] for row in tools.catalog] == sorted(NAMES)
    result = await tools.call({"tool": "ken_read", "arguments": {"path": "invoice.py"}})
    assert result == {
        "success": True,
        "contentItems": [{"type": "inputText", "text": "source evidence"}],
    }
    assert peer.calls == [("ken_read", {"path": "invoice.py"})]
    assert not (
        await tools.call({"tool": "unrelated_write", "arguments": {"path": "x"}})
    )["success"]
    assert len(peer.calls) == 1


@pytest.mark.parametrize(
    "defect", ["missing", "duplicate", "schema", "external_ref", "broken_ref"]
)
async def test_incomplete_or_invalid_ken_catalog_refuses_admission(defect):
    from backend.runtime.ken_mediation import KenNotReady, KenTools

    peer = Peer()
    if defect == "missing":
        peer.tools.pop()
    elif defect == "duplicate":
        peer.tools.append(tool("ken_find"))
    elif defect == "schema":
        peer.tools[0].inputSchema["properties"]["path"]["type"] = "PRIVATE_INVALID_TYPE"
    else:
        peer.tools[0].inputSchema["properties"]["path"] = {
            "$ref": "https://private.invalid/schema"
            if defect == "external_ref"
            else "#/$defs/missing"
        }
    with pytest.raises(KenNotReady) as error:
        await KenTools.connect(peer)
    assert "PRIVATE_INVALID_TYPE" not in str(error.value)
    assert not peer.calls


@pytest.mark.parametrize(
    "arguments", [{}, {"path": 137}, {"path": "x", "execute": True}]
)
async def test_invalid_arguments_never_reach_ken(arguments):
    from backend.runtime.ken_mediation import KenTools

    peer = Peer()
    tools = await KenTools.connect(peer)
    assert not (await tools.call({"tool": "ken_read", "arguments": arguments}))[
        "success"
    ]
    assert not peer.calls


async def test_ken_catalog_schema_is_snapshotted_and_accepts_local_refs():
    from backend.runtime.ken_mediation import KenTools

    peer = Peer()
    peer.tools[0].inputSchema.update(
        {
            "$defs": {"path": {"type": "string"}},
            "properties": {"path": {"$ref": "#/$defs/path"}},
        }
    )
    tools = await KenTools.connect(peer)
    peer.tools[0].inputSchema["$defs"]["path"]["type"] = "integer"
    assert (
        await tools.call({"tool": "ken_find", "arguments": {"path": "invoice.py"}})
    )["success"]
    assert not (await tools.call({"tool": "ken_find", "arguments": {"path": 137}}))[
        "success"
    ]
    assert len(peer.calls) == 1


async def test_paged_ken_catalog_is_complete_before_admission():
    from backend.runtime.ken_mediation import KenTools

    class Paged(Peer):
        async def list_tools(self, *, cursor=None):
            self.pages.append(cursor)
            return SimpleNamespace(
                tools=self.tools[:2] if cursor is None else self.tools[2:],
                nextCursor="second" if cursor is None else None,
            )

    peer = Paged()
    tools = await KenTools.connect(peer)
    assert len(tools.catalog) == 5 and peer.pages == [None, "second"]


async def test_looping_ken_catalog_and_withdrawn_readiness_are_rejected():
    from backend.runtime.ken_mediation import KenNotReady, KenTools

    class Loop(Peer):
        async def list_tools(self, *, cursor=None):
            self.pages.append(cursor)
            return SimpleNamespace(tools=[], nextCursor="loop")

    peer = Loop()
    with pytest.raises(KenNotReady):
        await KenTools.connect(peer)
    assert len(peer.pages) <= 3
    active = [True]

    class Withdrawn(Peer):
        async def list_tools(self, **kwargs):
            active[0] = False
            return await super().list_tools(**kwargs)

    peer = Withdrawn()
    with pytest.raises(KenNotReady):
        await KenTools.connect(peer, active=lambda: active[0])


async def test_ken_withdrawn_after_ready_never_dispatches():
    from backend.runtime.ken_mediation import KenTools

    peer = Peer()
    active = [True]
    tools = await KenTools.connect(peer, active=lambda: active[0])
    active[0] = False
    assert not (
        await tools.call({"tool": "ken_read", "arguments": {"path": "invoice.py"}})
    )["success"]
    assert not peer.calls


async def test_non_json_number_never_reaches_ken():
    from backend.runtime.ken_mediation import KenTools

    peer = Peer()
    peer.tools[0].inputSchema["properties"]["threshold"] = {"type": "number"}
    tools = await KenTools.connect(peer)
    response = await tools.call(
        {"tool": "ken_find", "arguments": {"path": "x", "threshold": float("nan")}}
    )
    assert not response["success"] and not peer.calls


async def test_project_catalog_routes_business_analysis_and_ken_to_their_owner():
    from backend.runtime.business_mediation import BusinessTools, ProjectTools
    from backend.runtime.ken_mediation import KenTools

    business_peer = Peer([tool("researcher_source_read")])
    analysis_peer = Peer()
    analysis = SimpleNamespace(
        catalog=[{"name": "analysis"}], call=analysis_peer.call_tool
    )

    # A distinct adapter with the same public call envelope, no child or inference.
    async def analysis_call(params):
        return await analysis_peer.call_tool(params["tool"], params["arguments"])

    analysis.call = analysis_call
    ken_peer = Peer()
    project = ProjectTools(
        await BusinessTools.connect(business_peer),
        analysis,
        await KenTools.connect(ken_peer),
    )
    for name in ("ken_read", "researcher_source_read", "analysis"):
        await project.call({"tool": name, "arguments": {"path": "x"}})
    assert (
        len(business_peer.calls) == len(analysis_peer.calls) == len(ken_peer.calls) == 1
    )
    with pytest.raises(ValueError, match="unique"):
        ProjectTools(project, analysis)
