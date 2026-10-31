"""Candidate native session/control boundary, independent of the legacy engine.

Native completion describes a turn, never acceptance of a product task. Tool
and token bounds are observation-triggered fuses: they cannot revoke an action
already dispatched by the native runtime or predict unreported consumption.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Self

from backend.runtime.codex_rpc import RpcDisconnected, RpcError, StdioRpcClient


class SubscriptionRequired(RuntimeError):
    """No managed ChatGPT account is available; never fall back to an API key."""


class ExecutionLimitExceeded(RuntimeError):
    """Execution stopped at an explicit resource/progress boundary."""


class NativeInputRequired(RuntimeError):
    """A request needs an explicit host decision before execution can continue."""

    def __init__(self, request: dict[str, Any]) -> None:
        super().__init__("Native runtime requested input; execution was interrupted")
        self.request = request


@dataclass(frozen=True)
class ExecutionLimits:
    wall_seconds: float
    no_progress_seconds: float
    max_turns: int
    max_tool_calls: int
    max_observed_tokens: int

    def __post_init__(self) -> None:
        if min(self.wall_seconds, self.no_progress_seconds, self.max_turns,
               self.max_tool_calls, self.max_observed_tokens) <= 0:
            raise ValueError("All execution limits must be positive")


@dataclass(frozen=True)
class NativeTurnResult:
    thread_id: str
    turn_id: str
    status: str
    text: str
    tool_calls: int
    observed_tokens: int | None
    error: dict | None


_TOOL_TYPES = frozenset({
    "commandExecution", "fileChange", "mcpToolCall", "dynamicToolCall",
    "collabAgentToolCall", "webSearch", "imageView", "imageGeneration",
})


class CodexSession:
    """Own one native thread/connection; serialize turns and correlate control.

    The product service must persist context/attempt identity and aggregate
    budgets across process restarts. Interrupted sessions retire their connection;
    further work must reopen the durable native thread. This class does not decide
    whether a correction was applied, an artifact accepted, or a task done.
    """

    def __init__(self, rpc: StdioRpcClient, *, workspace: Path, model: str,
                 limits: ExecutionLimits, resume_thread_id: str | None = None,
                 developer_instructions: str | None = None) -> None:
        self.rpc = rpc
        self.workspace = workspace.resolve()
        self.model = model
        self.limits = limits
        self.resume_thread_id = resume_thread_id
        self.developer_instructions = developer_instructions
        self.thread_id: str | None = None
        self.turn_id: str | None = None
        self.turns_sent = 0
        self.observed_tokens: int | None = None
        self._active = False
        self._turn_ready = asyncio.Event()
        self._cancellation: asyncio.Task[None] | None = None
        self._tool_items: set[tuple[str, str]] = set()

    async def __aenter__(self) -> Self:
        await self.rpc.__aenter__()
        try:
            await self.rpc.request("initialize", {"clientInfo": {
                "name": "researcher", "version": "0.1.0", "title": "Researcher",
            }})
            await self.rpc.notify("initialized")
            account = await self.rpc.request("account/read", {"refreshToken": False})
            if (account.get("account") or {}).get("type") != "chatgpt":
                raise SubscriptionRequired("Sign in using codex login with your ChatGPT subscription")
            params = {
                "cwd": str(self.workspace), "model": self.model, "modelProvider": "openai",
                "approvalPolicy": "on-request", "sandbox": "workspace-write",
            }
            if self.developer_instructions:
                params["developerInstructions"] = self.developer_instructions
            if self.resume_thread_id:
                params["threadId"] = self.resume_thread_id
                params["excludeTurns"] = True
                result = await self.rpc.request("thread/resume", params)
            else:
                result = await self.rpc.request("thread/start", params)
            if result.get("modelProvider") != "openai":
                raise SubscriptionRequired("Native runtime did not select the OpenAI subscription provider")
            self.thread_id = result["thread"]["id"]
            if self.resume_thread_id and self.thread_id != self.resume_thread_id:
                raise RpcDisconnected("Resume returned another thread; reconcile before continuing")
            return self
        except BaseException:
            await self.rpc.aclose()
            raise

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        await self.rpc.aclose()

    async def run(self, text: str, *, on_event: Callable[[dict], None] | None = None,
                  on_request: Callable[[dict], Awaitable[dict]] | None = None) -> NativeTurnResult:
        if self._active:
            raise RuntimeError("A native turn is already active")
        if self.thread_id is None:
            raise RuntimeError("Open the native session first")
        if self.turns_sent >= self.limits.max_turns:
            raise ExecutionLimitExceeded("Session turn budget exhausted; no new turn was sent")
        self._active = True
        self._turn_ready.clear()
        self._cancellation = None
        started = last_progress = time.monotonic()
        answers: dict[str, str] = {}
        self.turns_sent += 1  # A lost receipt is still a potentially dispatched turn.
        try:
            async with asyncio.timeout(self.limits.wall_seconds):
                response = await self.rpc.request("turn/start", {
                    "threadId": self.thread_id, "input": [{"type": "text", "text": text}],
                    "effort": "low",
                })
                self.turn_id = response["turn"]["id"]
                self._turn_ready.set()
                while True:
                    remaining_progress = self.limits.no_progress_seconds - (time.monotonic() - last_progress)
                    if remaining_progress <= 0:
                        raise ExecutionLimitExceeded("No observable progress before the deadline")
                    try:
                        message = await self.rpc.next_message(timeout=remaining_progress)
                    except TimeoutError as exc:
                        raise ExecutionLimitExceeded("No observable progress before the deadline") from exc
                    params = message.get("params", {})
                    if params.get("threadId") != self.thread_id:
                        continue
                    event_turn = params.get("turnId") or params.get("turn", {}).get("id")
                    if event_turn is not None and event_turn != self.turn_id:
                        continue
                    if on_event:
                        on_event(message)
                    if "id" in message:
                        if on_request is None:
                            raise NativeInputRequired(message)
                        decision = await on_request(message)
                        await self.rpc.respond(message["id"], decision)
                        continue
                    method = message["method"]
                    item = params.get("item", {})
                    item_key = (self.turn_id, item.get("id", ""))
                    if method == "item/started" and item.get("type") in _TOOL_TYPES:
                        self._tool_items.add(item_key)
                        if len(self._tool_items) > self.limits.max_tool_calls:
                            raise ExecutionLimitExceeded("Session tool budget exceeded")
                    if method == "item/completed" and item.get("type") in _TOOL_TYPES:
                        last_progress = time.monotonic()
                    if method == "thread/tokenUsage/updated":
                        self.observed_tokens = params["tokenUsage"]["total"]["totalTokens"]
                        if self.observed_tokens > self.limits.max_observed_tokens:
                            raise ExecutionLimitExceeded("Observed token budget exceeded")
                    if (method == "item/completed" and item.get("type") == "agentMessage"
                            and item.get("phase") in (None, "final_answer")):
                        answers[item["id"]] = item["text"]
                    if method == "turn/completed":
                        turn = params["turn"]
                        if turn["status"] == "interrupted" or self._cancellation is not None:
                            # Native turn interruption is not a tool-exit receipt.
                            # Retire this connection before returning control; a
                            # future attempt must reopen the durable native thread.
                            if self._cancellation is not None:
                                try:
                                    await asyncio.shield(self._cancellation)
                                except (TimeoutError, RpcDisconnected, RpcError):
                                    pass  # Preserve the observed terminal result.
                            await self.rpc.aclose()
                        return NativeTurnResult(
                            self.thread_id, self.turn_id, turn["status"], "\n\n".join(answers.values()),
                            len(self._tool_items), self.observed_tokens, turn.get("error"),
                        )
        except TimeoutError as exc:
            await self._abort()
            raise ExecutionLimitExceeded("Native turn wall deadline exceeded") from exc
        except BaseException:
            await self._abort()
            raise
        finally:
            self._active = False
            self.turn_id = None
            self._turn_ready.set()
            # A completed turn can still have spent its entire wall allowance.
            self.last_duration_seconds = time.monotonic() - started

    async def cancel(self) -> None:
        """Share one interruption request, including cancellation during start.

        Receipt proves only interruption was requested, not that it finished.
        If start cannot provide an identity promptly, stop the owned process
        instead of letting cancellation silently miss a submitted native turn.
        """
        if not self._active:
            return
        if self._cancellation is None:
            self._cancellation = asyncio.create_task(self._cancel_active())
        await asyncio.shield(self._cancellation)

    async def _cancel_active(self) -> None:
        try:
            await asyncio.wait_for(self._turn_ready.wait(), timeout=2)
        except TimeoutError:
            await self.rpc.aclose()
            return
        if self.turn_id is not None:
            await self.rpc.request("turn/interrupt", {"threadId": self.thread_id, "turnId": self.turn_id}, timeout=2)

    async def steer(self, correction: str) -> dict:
        """Deliver to exactly the active turn; receipt does not prove application."""
        if self.turn_id is None:
            raise RuntimeError("No active native turn to correct")
        return await self.rpc.request("turn/steer", {
            "threadId": self.thread_id, "expectedTurnId": self.turn_id,
            "input": [{"type": "text", "text": correction}],
        })

    async def _abort(self) -> None:
        try:
            await self.cancel()
        except (TimeoutError, RpcDisconnected, RpcError):
            pass  # Lost receipt: process ownership, not automatic replay, ends work.
        finally:
            await self.rpc.aclose()
