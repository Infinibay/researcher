"""Host-owned bounded PDF parsing with pidfd closure and credential-free IPC.

No executable/program/path is selected by a model. Linux resource limits apply to
one fixed child; this is not the native code-execution broker or a general sandbox.
"""

import json
import math
import os
import selectors
import signal
import subprocess
import sys
import time
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path
from threading import Event

from backend.research.models import ResearchForbidden, SourceTooLarge, SourceUnavailable
from backend.runtime.peer_process import _pidfd, _signal

WORKER = Path(__file__).with_name("parser_worker.py")


@dataclass(frozen=True)
class ParserLimits:
    """Host-chosen per-document CPU, virtual memory, wall clock and IPC budgets."""

    cpu_seconds: int = 2
    memory_bytes: int = 268435456
    wall_seconds: float = 5
    max_input_bytes: int = 1000000
    max_output_bytes: int = 2000000

    def __post_init__(self):
        """Reject invalid/unbounded host configuration before creating a process."""
        if type(self.cpu_seconds) is not int or not 1 <= self.cpu_seconds <= 10:
            raise ValueError("Parser CPU budget must be 1–10 integer seconds")
        if (
            type(self.memory_bytes) is not int
            or not 33554432 <= self.memory_bytes <= 1073741824
        ):
            raise ValueError("Parser memory budget must be 32–1024 MiB")
        if (
            type(self.wall_seconds) not in (int, float)
            or not math.isfinite(self.wall_seconds)
            or not 0.1 <= self.wall_seconds <= 30
        ):
            raise ValueError("Parser wall budget must be finite and 0.1–30 seconds")
        if any(
            type(value) is not int or not 1 <= value <= 10000000
            for value in (self.max_input_bytes, self.max_output_bytes)
        ):
            raise ValueError("Parser IPC budgets must be 1–10000000 bytes")


class PDFParser:
    """Keep parser processes inside a cancellable host operation until actual exit."""

    def __init__(self, *, owner=None, grant_id=None, limits=None):
        """Bind host authority and limits; direct library callers still receive OS limits."""
        if (owner is None) != (grant_id is None):
            raise ValueError(
                "Parser owner and grant identity must be supplied together"
            )
        self.owner, self.grant_id = owner, grant_id
        self.limits = limits or ParserLimits()

    def read(self, data: bytes) -> tuple[str, dict]:
        """Extract one complete PDF or fail, reaping the owned child before returning."""
        if not isinstance(data, bytes) or len(data) > self.limits.max_input_bytes:
            raise SourceTooLarge("PDF input exceeds the parser byte budget")
        if sys.platform != "linux":
            raise SourceUnavailable(
                "PDF parsing requires the supported Linux pidfd worker; no in-process fallback"
            )
        operation = (
            self.owner.operation(self.grant_id) if self.owner else nullcontext(Event())
        )
        with operation as cancelled:
            if cancelled.is_set():
                raise ResearchForbidden("PDF operation authority was withdrawn")
            return self._run(data, cancelled)

    def _run(self, data, cancelled):
        """Exchange bounded byte streams with one child; signal only its pinned pidfd."""
        # -I -S embedding can supply dependencies explicitly while sysconfig
        # still describes base Python. Resolve the actual installed parser root.
        try:
            spec = find_spec("pypdf")
            if spec is None or spec.origin is None:
                raise SourceUnavailable(
                    "The required PDF parser dependency is unavailable"
                )
            dependencies = str(Path(spec.origin).resolve(strict=True).parent.parent)
        except (ImportError, ValueError, OSError) as exc:
            raise SourceUnavailable(
                "The required PDF parser dependency is unavailable"
            ) from exc
        options = asdict(self.limits) | {
            "parent": os.getpid(),
            "package_root": str(Path(__file__).resolve().parents[2]),
            "dependencies": dependencies,
        }
        deadline = time.monotonic() + self.limits.wall_seconds
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", "-S", str(WORKER), json.dumps(options)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                cwd="/",
                env={"LANG": "C.UTF-8"},
                close_fds=True,
                bufsize=0,
            )
        except OSError as exc:
            raise SourceUnavailable("PDF worker could not be started") from exc
        pidfd = None
        output = bytearray()
        try:
            pidfd = _pidfd(process.pid)
            with selectors.DefaultSelector() as selector:
                for stream, event in (
                    (process.stdin, selectors.EVENT_WRITE),
                    (process.stdout, selectors.EVENT_READ),
                ):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, event)
                sent, eof = 0, False
                while True:
                    if cancelled.is_set():
                        raise ResearchForbidden(
                            "PDF operation authority was withdrawn during extraction"
                        )
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise SourceTooLarge(
                            "PDF parser exceeded its wall-clock budget; no partial source was saved"
                        )
                    for key, _ in selector.select(min(0.05, remaining)):
                        stream = key.fileobj
                        if stream is process.stdin:
                            try:
                                sent += os.write(
                                    stream.fileno(), data[sent : sent + 65536]
                                )
                            except BrokenPipeError:
                                sent = len(data)
                            if sent == len(data):
                                selector.unregister(stream)
                                stream.close()
                        else:
                            chunk = os.read(stream.fileno(), 65536)
                            if chunk:
                                if (
                                    len(output) + len(chunk)
                                    > self.limits.max_output_bytes
                                ):
                                    raise SourceTooLarge(
                                        "PDF worker exceeded its output byte budget"
                                    )
                                output.extend(chunk)
                            else:
                                selector.unregister(stream)
                                stream.close()
                                eof = True
                    if process.poll() is not None and eof:
                        break
            if process.returncode in (-signal.SIGXCPU, -signal.SIGALRM):
                raise SourceTooLarge("PDF parser exceeded its OS execution budget")
            if process.returncode != 0:
                raise SourceUnavailable(
                    "PDF worker terminated without a valid result; no partial source was saved"
                )
            try:
                result = json.loads(output)
                if (
                    result["ok"] is True
                    and isinstance(result["content"], str)
                    and isinstance(result["provenance"], dict)
                ):
                    result["provenance"]["execution"]["worker_closed"] = True
                    return result["content"], result["provenance"]
                if result["code"] == "too_large":
                    raise SourceTooLarge(result["message"])
                raise SourceUnavailable(result["message"])
            except (ValueError, KeyError, TypeError) as exc:
                if isinstance(exc, SourceTooLarge):
                    raise
                raise SourceUnavailable(
                    "PDF worker returned an invalid receipt"
                ) from exc
        except (ResearchForbidden, SourceTooLarge):
            raise
        except OSError as exc:
            raise SourceUnavailable(
                "PDF worker could not start or exchange its bounded snapshot"
            ) from exc
        finally:
            # Do not finish the registered operation until the original child is
            # actually reaped. A stalled kernel wait remains pending, never closed.
            try:
                if process.poll() is None and pidfd is not None:
                    _signal(pidfd)
            finally:
                # If pidfd admission failed, no input was released. EOF plus
                # the worker's own CPU/alarm fuse ends that trusted bootstrap.
                process.stdin.close()
                process.wait()
            for stream in (process.stdin, process.stdout):
                stream.close()
            if pidfd is not None:
                os.close(pidfd)
