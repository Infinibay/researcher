"""Candidate native session/control boundary, independent of the legacy engine.

Native completion describes a turn, never acceptance of a product task. Host
tool requests consume allowance before dispatch. Native-owned tool/token bounds
remain observation fuses: they cannot revoke an already dispatched native action
or predict unreported consumption.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import math
import time
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Self

from backend.runtime.codex_rpc import JsonRpcClient, RpcDisconnected, RpcError, RpcProtocolError
from backend.runtime.contracts import DeliveryReady


class SubscriptionRequired(RuntimeError):
    """No managed ChatGPT account is available; never fall back to an API key."""


class ExecutionLimitExceeded(RuntimeError):
    """Execution stopped at an explicit resource/progress boundary."""

    def __init__(self, message, *, kind="unknown", budget=None):
        """Preserve the observed boundary independently of private diagnostic text."""
        super().__init__(message)
        self.kind = kind
        self.budget = budget


class NativeInputRequired(RuntimeError):
    """A request needs an explicit host decision before execution can continue."""

    def __init__(self, request: dict[str, Any]) -> None:
        """Retain the exact native request for reconciliation without granting a host decision or silently dispatching work."""
        super().__init__("Native runtime requested input; execution was interrupted")
        self.request = request


@dataclass(frozen=True)
class ExecutionLimits:
    """Host-owned hard ceilings; advisory delivery margins never enlarge them."""

    wall_seconds: float
    no_progress_seconds: float
    max_turns: int
    max_tool_calls: int
    max_observed_tokens: int
    max_answer_bytes: int = 200000

    def __post_init__(self) -> None:
        """Reject missing, nonfinite and nonpositive execution allowances."""
        for value in (self.wall_seconds, self.no_progress_seconds):
            if type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError("Execution deadlines must be finite numbers")
        for value in (
            self.max_turns,
            self.max_tool_calls,
            self.max_observed_tokens,
            self.max_answer_bytes,
        ):
            if type(value) is not int:
                raise ValueError("Execution counts must be integers")
        if (
            min(
                self.wall_seconds,
                self.no_progress_seconds,
                self.max_turns,
                self.max_tool_calls,
                self.max_observed_tokens,
                self.max_answer_bytes,
            )
            <= 0
        ):
            raise ValueError("All execution limits must be positive")


@dataclass(frozen=True)
class NativeTurnResult:
    """Record a scoped native outcome and observed session usage, independently of product review, acceptance or publication."""

    thread_id: str
    turn_id: str
    status: str
    text: str
    tool_calls: int
    observed_tokens: int | None
    error: dict | None


_TOOL_TYPES = frozenset(
    {
        "commandExecution",
        "fileChange",
        "mcpToolCall",
        "dynamicToolCall",
        "collabAgentToolCall",
        "webSearch",
        "imageView",
        "imageGeneration",
    }
)


class CodexSession:
    """Own one native thread/connection; serialize turns and correlate control.

    The product service must persist context/attempt identity and aggregate
    budgets across process restarts. Interrupted sessions retire their connection;
    further work must reopen the durable native thread. This class does not decide
    whether a correction was applied, an artifact accepted, or a task done.
    """

    def __init__(
        self,
        rpc: JsonRpcClient,
        *,
        workspace: Path,
        model: str,
        limits: ExecutionLimits,
        reasoning_effort: str = "low",
        resume_thread_id: str | None = None,
        developer_instructions: str | None = None,
        sandbox: str = "workspace-write",
        permission_profile: str | None = None,
        before_thread: Callable[[JsonRpcClient], Awaitable[None]] | None = None,
        subscription_auth=None,
    ) -> None:
        """Bind one model/effort pair and bounded subscription session; construction sends no native request and grants no tool authority."""
        self.rpc = rpc
        self.workspace = workspace.resolve()
        self.model = model
        from backend.runtime.model_settings import model_profile

        self.reasoning_effort = model_profile(model, reasoning_effort)["reasoning_effort"]
        self.limits = limits
        self.resume_thread_id = resume_thread_id
        self.developer_instructions = developer_instructions
        if sandbox not in ("read-only", "workspace-write"):
            raise ValueError("Unsupported native filesystem scope")
        self.sandbox = sandbox
        self.permission_profile = permission_profile
        self.before_thread = before_thread
        self.subscription_auth = subscription_auth
        self.dynamic_tools = None
        self.thread_configuration = None
        self.thread_id: str | None = None
        self.turn_id: str | None = None
        self.turns_sent = 0
        self.observed_tokens: int | None = None
        self._largest_token_increment: int | None = None
        self._active = False
        self._turn_ready = asyncio.Event()
        self._cancel_requested = asyncio.Event()
        self._cancellation: asyncio.Task[None] | None = None
        self._tool_items: dict[tuple[str, str], str] = {}
        self._host_tool_calls: set[tuple[str, str]] = set()
        self._completed_tool_items: set[tuple[str, str]] = set()
        self._started_at: float | None = None

    def budget_status(self):
        """Report observed session consumption and turn time, never billing or guaranteed remaining quota.

        The historical tool_starts field now counts unique tool identities from
        host requests or native lifecycle observations, not only start events.
        Native token/item events may lag actual work. Reserve an advisory margin
        for the unreported step, artifact delivery and final explanation, with
        growth allowance. Update increments are observations, not guaranteed
        model-step costs; this never reserves quota or changes the hard ceiling.
        """
        elapsed = (
            time.monotonic() - self._started_at
            if self._active and self._started_at is not None
            else getattr(self, "last_duration_seconds", 0.0)
        )
        remaining = {
            "wall_seconds": max(0.0, self.limits.wall_seconds - elapsed),
            "tool_starts": max(0, self.limits.max_tool_calls - len(self._tool_items)),
            "observed_tokens": None if self.observed_tokens is None else max(
                0, self.limits.max_observed_tokens - self.observed_tokens
            ),
        }
        token_margin = max(
            math.ceil(self.limits.max_observed_tokens * 0.25),
            math.ceil((self._largest_token_increment or 0) * 3 * 1.25),
        )
        deliver = (
            remaining["wall_seconds"] <= self.limits.wall_seconds * 0.25
            or remaining["tool_starts"] <= self.limits.max_tool_calls * 0.25
            or (remaining["observed_tokens"] is not None
                and remaining["observed_tokens"] <= token_margin)
        )
        return {
            "limits": asdict(self.limits),
            "observed": {"elapsed_seconds": elapsed, "tool_starts": len(self._tool_items),
                         "host_tool_requests_admitted": len(self._host_tool_calls),
                         "tokens": self.observed_tokens},
            "tool_count_basis": "Unique tool identities from host requests or native start/completion observations. Host requests are bounded before dispatch; native-only effects may already have occurred.",
            "remaining": remaining,
            "delivery_advice": {
                "largest_token_increment": self._largest_token_increment,
                "token_margin": token_margin,
                "basis": "Quarter floor or three observed increments with 25% growth; heuristic, not reserved quota.",
            },
            "phase": "deliver" if deliver else "work",
        }

    def _observe_tokens(self, total):
        """Retain cumulative usage high water and its largest positive increment; stale updates cannot refund allowance or inflate later step cost."""
        increment = max(0, total - (self.observed_tokens or 0))
        self._largest_token_increment = max(self._largest_token_increment or 0, increment) or None
        self.observed_tokens = max(self.observed_tokens or 0, total)

    def _exceeded(self, kind, message):
        """Capture bounded host observations at detection, before process teardown changes elapsed time."""
        return ExecutionLimitExceeded(message, kind=kind, budget=self.budget_status())

    def _record_tool(self, identifier, kind):
        """Deduplicate one native tool identity across request/start/completion and retain the first over-limit observation without authorizing another host effect."""
        if not isinstance(identifier, str) or not identifier:
            raise RpcProtocolError('Native tool activity requires an original nonempty item identity')
        key = (self.turn_id, identifier)
        previous = self._tool_items.get(key)
        if previous is not None and previous != kind:
            raise RpcProtocolError('Native tool identity changed its tool kind')
        self._tool_items[key] = kind
        if len(self._tool_items) > self.limits.max_tool_calls:
            raise self._exceeded('tools', 'Session tool budget exceeded before any further host dispatch')
        return key

    def _reserve_host_tool(self, params):
        """Require original turn/call identity and consume its allowance before invoking the host; repeated RPCs never repeat an uncertain effect."""
        if params.get('turnId') != self.turn_id:
            raise RpcProtocolError('Host tool request requires its original active turn identity')
        identifier = params.get('callId')
        if isinstance(identifier, str) and (self.turn_id, identifier) in self._host_tool_calls:
            raise RpcProtocolError('Repeated host tool call identity; reconcile the original receipt without replay')
        key = self._record_tool(identifier, 'dynamicToolCall')
        self._host_tool_calls.add(key)

    async def __aenter__(self) -> Self:
        """Open the owned RPC peer, require the selected subscription provider and freeze thread configuration before any turn."""
        if self.resume_thread_id and self.dynamic_tools is not None:
            raise ValueError(
                "Native resume restores its catalog; dynamic tools cannot replace it"
            )
        try:
            if self.subscription_auth is not None:
                self.subscription_auth.bind(self.rpc)
            await self.rpc.__aenter__()
            initialization = {
                "clientInfo": {
                    "name": "researcher",
                    "version": "0.1.0",
                    "title": "Researcher",
                }
            }
            if (
                self.permission_profile is not None
                or self.dynamic_tools is not None
                or self.subscription_auth is not None
            ):
                initialization["capabilities"] = {"experimentalApi": True}
            await self.rpc.request("initialize", initialization)
            await self.rpc.notify("initialized")
            if self.subscription_auth is not None:
                await self.subscription_auth.login()
            account = await self.rpc.request("account/read", {"refreshToken": False})
            if (account.get("account") or {}).get("type") != "chatgpt":
                raise SubscriptionRequired(
                    "Sign in using codex login with your ChatGPT subscription"
                )
            if self.before_thread is not None:
                await self.before_thread(self.rpc)
            params = {
                "cwd": str(self.workspace),
                "model": self.model,
                "modelProvider": "openai",
                "approvalPolicy": "on-request",
            }
            if self.permission_profile is not None:
                params["permissions"] = self.permission_profile
            else:
                params["sandbox"] = self.sandbox
            if self.dynamic_tools is not None:
                params["dynamicTools"] = self.dynamic_tools
            if self.developer_instructions:
                params["developerInstructions"] = self.developer_instructions
            if self.resume_thread_id:
                params["threadId"] = self.resume_thread_id
                params["excludeTurns"] = True
                result = await self.rpc.request("thread/resume", params)
            else:
                result = await self.rpc.request("thread/start", params)
            self.thread_configuration = result
            if result.get("modelProvider") != "openai":
                raise SubscriptionRequired(
                    "Native runtime did not select the OpenAI subscription provider"
                )
            self.thread_id = result["thread"]["id"]
            if self.resume_thread_id and self.thread_id != self.resume_thread_id:
                raise RpcDisconnected(
                    "Resume returned another thread; reconcile before continuing"
                )
            return self
        except BaseException:
            try:
                await self.rpc.aclose()
            finally:
                if self.subscription_auth is not None:
                    self.subscription_auth.close()
            raise

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        """Close the owned connection and subscription bridge without replaying an uncertain native turn."""
        try:
            await self.rpc.aclose()
        finally:
            if self.subscription_auth is not None:
                self.subscription_auth.close()

    async def run(
        self,
        text: str,
        *,
        on_event: Callable[[dict], Awaitable[None] | None] | None = None,
        on_request: Callable[[dict], Awaitable[dict]] | None = None,
        on_started: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> NativeTurnResult:
        """Run one bounded turn; a completed scoped host response counts as progress while model chatter and pending decisions do not."""
        if self._active:
            raise RuntimeError("A native turn is already active")
        if self.thread_id is None:
            raise RuntimeError("Open the native session first")
        if self.turns_sent >= self.limits.max_turns:
            raise self._exceeded("turns",
                "Session turn budget exhausted; no new turn was sent"
            )
        self._active = True
        self._turn_ready.clear()
        self._cancel_requested.clear()
        self._cancellation = None
        started = last_progress = time.monotonic()
        self._started_at = started
        answers: dict[str, str] = {}
        self.turns_sent += 1  # A lost receipt is still a potentially dispatched turn.
        try:
            async with asyncio.timeout(self.limits.wall_seconds):
                response = await self.rpc.request(
                    "turn/start",
                    {
                        "threadId": self.thread_id,
                        "input": [{"type": "text", "text": text}],
                        "effort": self.reasoning_effort,
                    },
                )
                self.turn_id = response["turn"]["id"]
                self._turn_ready.set()
                if on_started is not None:
                    await self._callback(on_started(self.thread_id, self.turn_id))
                while True:
                    remaining_progress = self.limits.no_progress_seconds - (
                        time.monotonic() - last_progress
                    )
                    if remaining_progress <= 0:
                        raise self._exceeded("progress",
                            "No observable progress before the deadline"
                        )
                    try:
                        message = await self.rpc.next_message(
                            timeout=remaining_progress
                        )
                    except TimeoutError as exc:
                        raise self._exceeded("progress",
                            "No observable progress before the deadline"
                        ) from exc
                    params = message.get("params", {})
                    if params.get("threadId") != self.thread_id:
                        continue
                    event_turn = params.get("turnId") or params.get("turn", {}).get(
                        "id"
                    )
                    if event_turn is not None and event_turn != self.turn_id:
                        continue
                    method = message['method']
                    if 'id' in message and method == 'item/tool/call':
                        self._reserve_host_tool(params)
                    item = params.get('item', {})
                    completed_tool = False
                    if method in ('item/started', 'item/completed') and item.get('type') in _TOOL_TYPES:
                        if params.get('turnId') != self.turn_id:
                            raise RpcProtocolError('Native tool observation requires its original active turn identity')
                        key = self._record_tool(item.get('id'), item['type'])
                        if method == 'item/completed' and key not in self._completed_tool_items:
                            self._completed_tool_items.add(key)
                            completed_tool = True
                    if on_event:
                        observing = on_event(message)
                        if inspect.isawaitable(observing):
                            await self._callback(observing)
                    if "id" in message:
                        if on_request is None:
                            raise NativeInputRequired(message)
                        try:
                            completed, decision = await self._callback(on_request(message))
                        except DeliveryReady as delivery:
                            if delivery.answer_bytes > self.limits.max_answer_bytes:
                                raise self._exceeded("output", "Typed delivery answer exceeds output budget") from delivery
                            # The durable host operation has already fenced tools.
                            # Do not release a tool result that would generate more
                            # text. Consume actual usage/termination observations.
                            await self.cancel()
                            last_progress = time.monotonic()
                            continue
                        if completed:
                            if message["method"] == "item/tool/call":
                                # Keep source/tool data unchanged. This separate
                                # host item reports observations, not permissions.
                                decision = {**decision, "contentItems": [
                                    *decision["contentItems"],
                                    {"type": "inputText", "text": json.dumps({
                                        "researcher_execution_budget": self.budget_status()
                                    }, separators=(",", ":"))},
                                ]}
                            await self.rpc.respond(message["id"], decision)
                            last_progress = time.monotonic()
                        continue
                    if completed_tool:
                        last_progress = time.monotonic()
                    if method == "thread/tokenUsage/updated":
                        self._observe_tokens(params["tokenUsage"]["total"][
                            "totalTokens"
                        ])
                        if self.observed_tokens > self.limits.max_observed_tokens:
                            raise self._exceeded("tokens",
                                "Observed token budget exceeded"
                            )
                    if (
                        method == "item/completed"
                        and item.get("type") == "agentMessage"
                        and item.get("phase") in (None, "final_answer")
                    ):
                        incoming = item["text"]
                        total = sum(
                            len(value.encode("utf-8"))
                            for key, value in answers.items()
                            if key != item["id"]
                        )
                        if (
                            total + len(incoming.encode("utf-8"))
                            > self.limits.max_answer_bytes
                        ):
                            raise self._exceeded("output",
                                "Native answer output budget exceeded"
                            )
                        answers[item["id"]] = incoming
                    if method == "turn/completed":
                        turn = params["turn"]
                        if (
                            turn["status"] == "interrupted"
                            or self._cancellation is not None
                        ):
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
                            self.thread_id,
                            self.turn_id,
                            turn["status"],
                            "\n\n".join(answers.values()),
                            len(self._tool_items),
                            self.observed_tokens,
                            turn.get("error"),
                        )
        except TimeoutError as exc:
            stopped = self._exceeded("wall", "Native turn wall deadline exceeded")
            await self._abort()
            raise stopped from exc
        except BaseException:
            await self._abort()
            raise
        finally:
            self._active = False
            self.turn_id = None
            self._turn_ready.set()
            # A completed turn can still have spent its entire wall allowance.
            self.last_duration_seconds = time.monotonic() - started

    async def _callback(self, awaiting):
        """Host callbacks must cooperate with cancellation; Stop bypasses their I/O.

        Cancelling a to_thread wait does not undo its work. Product handlers must
        withdraw tool authority and revalidate at commit, then reconcile receipts.
        """
        operation = asyncio.ensure_future(awaiting)
        cancelled = asyncio.create_task(self._cancel_requested.wait())
        try:
            if self._cancel_requested.is_set():
                return False, None
            done, _ = await asyncio.wait(
                {operation, cancelled}, return_when=asyncio.FIRST_COMPLETED
            )
            if operation in done:
                return True, await operation
            return False, None
        finally:
            for task in (operation, cancelled):
                if not task.done():
                    task.cancel()
            await asyncio.gather(operation, cancelled, return_exceptions=True)

    async def cancel(self) -> None:
        """Share one interruption request, including cancellation during start.

        Receipt proves only interruption was requested, not that it finished.
        If start cannot provide an identity promptly, stop the owned process
        instead of letting cancellation silently miss a submitted native turn.
        """
        if not self._active:
            return
        self._cancel_requested.set()
        if self.subscription_auth is not None:
            self.subscription_auth.withdraw()
        if self._cancellation is None:
            self._cancellation = asyncio.create_task(self._cancel_active())
        await asyncio.shield(self._cancellation)

    async def _cancel_active(self) -> None:
        """Wait briefly for the original turn identity, then interrupt that turn or retire the peer when start remains uncertain."""
        try:
            await asyncio.wait_for(self._turn_ready.wait(), timeout=2)
        except TimeoutError:
            await self.rpc.aclose()
            return
        if self.turn_id is not None:
            await self.rpc.request(
                "turn/interrupt",
                {"threadId": self.thread_id, "turnId": self.turn_id},
                timeout=2,
            )

    async def steer(self, correction: str) -> dict:
        """Deliver to exactly the active turn; receipt does not prove application."""
        if self.turn_id is None:
            raise RuntimeError("No active native turn to correct")
        return await self.rpc.request(
            "turn/steer",
            {
                "threadId": self.thread_id,
                "expectedTurnId": self.turn_id,
                "input": [{"type": "text", "text": correction}],
            },
        )

    async def _abort(self) -> None:
        """Attempt original-turn cancellation and always close the owned peer; a missing receipt never authorizes another dispatch."""
        try:
            await self.cancel()
        except (TimeoutError, RpcDisconnected, RpcError):
            pass  # Lost receipt: process ownership, not automatic replay, ends work.
        finally:
            await self.rpc.aclose()
