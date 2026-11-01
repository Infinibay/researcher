"""A local login receipt cannot establish remote account access without a route."""

import os
from pathlib import Path

import pytest

from backend.tests.runtime.test_broker_native import native_peer
from backend.tests.runtime.test_subscription_auth import auth_file


async def test_native_installs_memory_only_rpc_tokens_but_cannot_validate_account_offline(
    broker_setup, native_asset, monkeypatch, tmp_path
):
    from backend.runtime.broker_profile import NativeCapsule
    from backend.runtime.broker_stdio import AsyncPeerBroker
    from backend.runtime.codex_rpc import JsonRpcClient, RpcError
    from backend.runtime.subscription_auth import ExternalChatGPTAuth, ManagedTokenFile

    # Keep the real native profile/filter/assets but remove host networking for
    # this synthetic-token test. No remote auth/model call can leave the capsule.
    monkeypatch.setattr(NativeCapsule, "_network", lambda _: [])
    _s, registry, command, broker, _storage, _path = broker_setup
    peer = native_peer(registry, command)
    source = ManagedTokenFile(auth_file(tmp_path))
    auth = ExternalChatGPTAuth(source.tokens)
    async with AsyncPeerBroker(broker) as owner:
        rpc = JsonRpcClient(
            owner.native(
                registry, peer, operation_key="offline-auth", asset=native_asset
            ),
            request_timeout=3,
        )
        auth.bind(rpc)
        try:
            async with rpc:
                await rpc.request(
                    "initialize",
                    {
                        "clientInfo": {
                            "name": "researcher-offline-auth-test",
                            "version": "0.1.0",
                        },
                        "capabilities": {"experimentalApi": True},
                    },
                )
                await rpc.notify("initialized")
                assert (await rpc.request("account/read", {"refreshToken": False}))[
                    "account"
                ] is None
                await auth.login()
                with pytest.raises(
                    RpcError, match="workspace routing discovery failed"
                ):
                    await rpc.request("account/read", {"refreshToken": False})
                identity = registry.inspect(peer)
                private_home = Path(
                    f"/proc/{identity['init_pid']}/root/home/actor/.codex"
                )
                assert private_home.is_dir()
                try:
                    os.stat(private_home / "auth.json")
                except FileNotFoundError:
                    pass
                else:
                    pytest.fail(
                        "External access credential was persisted by native SDK"
                    )
        finally:
            auth.close()
    assert auth.account_id is None and registry.inspect(peer)["state"] == "closed"
