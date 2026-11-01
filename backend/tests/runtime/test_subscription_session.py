"""Refresh is host control while native admission/turn receipts are pending."""

import asyncio
import json
import sys
from pathlib import Path

import pytest

from backend.tests.runtime.test_subscription_auth import jwt


def session(tmp_path, source):
    from backend.runtime.codex_rpc import StdioRpcClient
    from backend.runtime.codex_session import CodexSession, ExecutionLimits
    from backend.runtime.subscription_auth import ExternalChatGPTAuth

    rpc = StdioRpcClient(
        (
            sys.executable,
            "-u",
            str(Path(__file__).with_name("fake_subscription_server.py")),
        ),
        cwd=tmp_path,
        request_timeout=0.5,
        close_timeout=0.03,
    )
    auth = ExternalChatGPTAuth(source, timeout=0.3)
    return CodexSession(
        rpc,
        workspace=tmp_path,
        model="test-model",
        limits=ExecutionLimits(2, 1, 1, 2, 1000),
        subscription_auth=auth,
    ), auth


@pytest.mark.parametrize("phase", ["thread", "turn"])
async def test_refresh_precedes_native_receipt_without_replay_or_public_secret(
    tmp_path, phase
):
    from backend.runtime.subscription_auth import ChatGPTCredentials

    (tmp_path / "phase").write_text(phase)
    calls = []

    async def source(**kwargs):
        calls.append(kwargs)
        return ChatGPTCredentials(jwt(str(len(calls))), "account-A")

    native, auth = session(tmp_path, source)
    events = []
    async with native:
        result = await native.run("answer", on_event=lambda e: events.append(e))
        assert result.text == "ok"
        summary = await native.rpc.request("test/summary")
        assert summary["private_responses"] == 1 and summary["token_changed"]
        assert summary["methods"].count("turn/start") == 1
        assert summary["initial_keys"] == [
            "accessToken",
            "chatgptAccountId",
            "chatgptPlanType",
            "type",
        ]
        assert summary["response_keys"] == [
            "accessToken",
            "chatgptAccountId",
            "chatgptPlanType",
        ]
    assert len(calls) == 2 and calls[1] == {
        "reason": "unauthorized",
        "account_id": "account-A",
    }
    assert "accessToken" not in json.dumps(events)
    assert "account/chatgptAuthTokens/refresh" not in json.dumps(events)
    assert auth.account_id is None


@pytest.mark.parametrize("condition", ["wrong-account", "unchanged", "switch-account"])
async def test_refresh_failure_retires_connection_without_using_another_account(
    tmp_path, condition
):
    from backend.runtime.codex_rpc import RpcDisconnected
    from backend.runtime.subscription_auth import ChatGPTCredentials

    (tmp_path / "phase").write_text(
        "wrong-account" if condition == "wrong-account" else "thread"
    )
    calls = []

    async def source(**kwargs):
        calls.append(kwargs)
        return ChatGPTCredentials(
            jwt("same" if condition == "unchanged" else str(len(calls))),
            "account-B"
            if condition == "switch-account" and len(calls) > 1
            else "account-A",
        )

    native, auth = session(tmp_path, source)
    with pytest.raises(RpcDisconnected):
        async with native:
            pass
    summary = json.loads((tmp_path / "wire-summary.json").read_text())
    assert summary["private_responses"] == 0 and "turn/start" not in summary["methods"]
    assert native.rpc._process.returncode is not None
    assert auth.account_id is None and auth.failure_code


async def test_withdrawal_during_credential_read_cannot_send_late_access_token(
    tmp_path,
):
    from backend.runtime.codex_rpc import RpcDisconnected
    from backend.runtime.subscription_auth import ChatGPTCredentials

    entered, release = asyncio.Event(), asyncio.Event()
    active = [True]

    async def source(**kwargs):
        if kwargs["reason"] is not None:
            entered.set()
            await release.wait()
        return ChatGPTCredentials(
            jwt("new" if kwargs["reason"] else "old"), "account-A"
        )

    native, auth = session(tmp_path, source)
    auth.active = lambda: active[0]
    opening = asyncio.create_task(native.__aenter__())
    await asyncio.wait_for(entered.wait(), 0.5)
    active[0] = False
    release.set()
    with pytest.raises(RpcDisconnected):
        await opening
    assert (
        json.loads((tmp_path / "wire-summary.json").read_text())["private_responses"]
        == 0
    )
    assert auth.failure_code == "inactive" and auth.account_id is None


async def test_refresh_budget_stops_repeated_challenges_without_host_turn_replay(
    tmp_path,
):
    from backend.runtime.codex_rpc import RpcDisconnected
    from backend.runtime.subscription_auth import ChatGPTCredentials

    (tmp_path / "phase").write_text("both")
    calls = []

    async def source(**kwargs):
        calls.append(kwargs)
        return ChatGPTCredentials(jwt(str(len(calls))), "account-A")

    native, auth = session(tmp_path, source)
    auth.max_refreshes = 1
    async with native:
        with pytest.raises(RpcDisconnected):
            await native.run("answer")
    summary = json.loads((tmp_path / "wire-summary.json").read_text())
    assert len(calls) == 2 and summary["private_responses"] == 1
    assert (
        summary["methods"].count("turn/start") == 1
        and auth.failure_code == "refresh_limit"
    )


async def test_initial_provider_exception_does_not_expose_credentials(tmp_path):
    from backend.runtime.codex_session import SubscriptionRequired

    async def source(**_):
        raise ValueError("SECRET-ACCESS-TOKEN")

    native, auth = session(tmp_path, source)
    with pytest.raises(SubscriptionRequired) as error:
        async with native:
            pass
    assert "SECRET" not in str(error.value)
    assert error.value.__suppress_context__
    assert auth.failure_code == "credentials_unavailable"


async def test_session_cancel_withdraws_a_pending_auth_refresh_before_turn_receipt(
    tmp_path,
):
    from backend.runtime.codex_rpc import RpcDisconnected
    from backend.runtime.subscription_auth import ChatGPTCredentials

    (tmp_path / "phase").write_text("turn")
    entered, release = asyncio.Event(), asyncio.Event()

    async def source(**kwargs):
        if kwargs["reason"] is not None:
            entered.set()
            await release.wait()
        return ChatGPTCredentials(
            jwt("fresh" if kwargs["reason"] else "first"), "account-A"
        )

    native, auth = session(tmp_path, source)
    async with native:
        turn = asyncio.create_task(native.run("answer"))
        await asyncio.wait_for(entered.wait(), 0.5)
        cancel = asyncio.create_task(native.cancel())
        await asyncio.wait_for(native._cancel_requested.wait(), 0.5)
        release.set()
        with pytest.raises(RpcDisconnected):
            await turn
        await cancel
    assert (
        json.loads((tmp_path / "wire-summary.json").read_text())["private_responses"]
        == 0
    )
    assert auth.failure_code == "inactive"
