"""Use the MCP SDK over owned pipes; no additional child launch or inference."""

import asyncio
from pathlib import Path

import pytest

from backend.tests.runtime.test_broker_ken import ken_peer


@pytest.fixture
def mcp_installation(ken_installation):
    from backend.runtime.ken_worker import KenInstallation

    ken_installation.write_text(
        "#!"
        + str(ken_installation.parent / "python")
        + "\n"
        + Path(__file__).with_name("fake_mcp_peer.py").read_text()
    )
    return KenInstallation.inspect(ken_installation)


async def test_mcp_owned_session_initializes_reads_and_drains_stderr(
    broker_setup, mcp_installation
):
    from backend.runtime.broker_mcp import broker_mcp
    from backend.runtime.broker_stdio import AsyncPeerBroker

    s, registry, command, broker, storage, path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    peer = ken_peer(registry, command)
    async with AsyncPeerBroker(broker) as owner:
        endpoint = owner.ken(
            registry, peer, operation_key="mcp", installation=mcp_installation
        )
        async with broker_mcp(endpoint, request_timeout=1) as client:
            assert [tool.name for tool in (await client.list_tools()).tools] == ["read"]
            result = await client.call_tool("read", {"action": "stderr"})
            assert not result.isError and result.content[0].text == "137"
        assert registry.inspect(peer)["state"] == "closed"
        assert storage.load().records["broker:op:" + endpoint._operation][
            "execution_closed"
        ]
        assert path.exists()
    assert not path.exists()


@pytest.mark.parametrize("action", ["invalid", "oversized", "exit", "hold"])
async def test_mcp_wire_failure_is_bounded_redacted_and_physically_closed(
    broker_setup, mcp_installation, action, caplog
):
    from backend.runtime.broker_mcp import McpTransportError, broker_mcp
    from backend.runtime.broker_stdio import AsyncPeerBroker

    s, registry, command, broker, _storage, _path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    peer = ken_peer(registry, command)
    async with AsyncPeerBroker(broker) as owner:
        endpoint = owner.ken(
            registry, peer, operation_key=action, installation=mcp_installation
        )
        async with broker_mcp(
            endpoint, request_timeout=0.2, max_message_bytes=4096
        ) as client:
            with pytest.raises(McpTransportError) as error:
                await client.call_tool("read", {"action": action})
            assert "PRIVATE_CANARY" not in str(error.value)
        assert registry.inspect(peer)["state"] == "closed"
    assert "PRIVATE_CANARY" not in caplog.text


async def test_cancelled_mcp_scope_closes_only_ken_peer(broker_setup, mcp_installation):
    from backend.runtime.broker_mcp import broker_mcp
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient
    from backend.tests.runtime.test_broker_rpc import code

    s, registry, command, broker, _storage, path = broker_setup
    (s.workspace / "fact.txt").write_text("137")
    peer = ken_peer(registry, command)
    ready = asyncio.Event()
    async with (
        AsyncPeerBroker(broker) as owner,
        JsonRpcClient(
            owner.peer(registry, command, operation_key="sibling", code=code())
        ) as sibling,
    ):

        async def scope():
            async with broker_mcp(
                owner.ken(
                    registry,
                    peer,
                    operation_key="cancel-mcp",
                    installation=mcp_installation,
                )
            ) as client:
                ready.set()
                await client.call_tool("read", {"action": "hold"})

        task = asyncio.create_task(scope())
        await asyncio.wait_for(ready.wait(), 3)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert registry.inspect(peer)["state"] == "closed" and path.exists()
        assert await sibling.request("echo", {"value": 200}) == {"value": 200}
