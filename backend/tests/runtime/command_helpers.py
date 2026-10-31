"""Control event-consumer scheduling without changing native wire results."""

from backend.runtime.codex_rpc import StdioRpcClient
from backend.runtime.command_jobs import OwnedCommandExecutor


class ReplyObservedClient(StdioRpcClient):
    def __init__(self, *args, reply_received, **kwargs):
        super().__init__(*args, **kwargs)
        self.reply_received = reply_received

    async def request_ordered(self, method, params=None, *, timeout=None):
        reply = await super().request_ordered(method, params, timeout=timeout)
        if method == "command/exec":
            self.reply_received.set()
        return reply


class PausedOutputExecutor(OwnedCommandExecutor):
    def __init__(self, *args, output_gate, **kwargs):
        super().__init__(*args, **kwargs)
        self.output_gate = output_gate

    async def _read_events(self):
        await self.output_gate.wait()
        await super()._read_events()
