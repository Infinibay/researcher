"""Host-owned bounded PDF parsing with pidfd closure and credential-free IPC.

No executable/program/path is selected by a model. Linux resource limits apply to
one fixed child; this is not the native code-execution broker or a general sandbox.
"""

import json
import math
import os
import sys
from contextlib import nullcontext
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path
from threading import Event

from backend.research.models import ResearchForbidden, SourceTooLarge, SourceUnavailable
from backend.research.worker_transport import exchange

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

    def read(
        self, data: bytes, *, max_wall_seconds: float | None = None
    ) -> tuple[str, dict]:
        """Extract one complete PDF or fail, reaping the child before returning.

        Callers may reduce the remaining wall budget (for example after a URL
        download); they cannot extend the host's configured processing deadline.
        """
        if not isinstance(data, bytes) or len(data) > self.limits.max_input_bytes:
            raise SourceTooLarge("PDF input exceeds the parser byte budget")
        if sys.platform != "linux":
            raise SourceUnavailable(
                "PDF parsing requires the supported Linux pidfd worker; no in-process fallback"
            )
        wall_seconds = self.limits.wall_seconds
        if max_wall_seconds is not None:
            if (
                type(max_wall_seconds) not in (int, float)
                or not math.isfinite(max_wall_seconds)
                or max_wall_seconds <= 0
            ):
                raise ValueError(
                    "Remaining PDF wall budget must be finite and positive"
                )
            wall_seconds = min(wall_seconds, max_wall_seconds)
        operation = (
            self.owner.operation(self.grant_id) if self.owner else nullcontext(Event())
        )
        with operation as cancelled:
            if cancelled.is_set():
                raise ResearchForbidden("PDF operation authority was withdrawn")
            return self._run(data, cancelled, wall_seconds)

    def _run(self, data, cancelled, wall_seconds):
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
            "wall_seconds": wall_seconds,
            "package_root": str(Path(__file__).resolve().parents[2]),
            "dependencies": dependencies,
        }
        output = exchange(
            data,
            worker=WORKER,
            options=options,
            limits=self.limits,
            cancelled=cancelled,
        )
        try:
            result = json.loads(output)
            if (
                result["ok"] is True
                and isinstance(result["content"], str)
                and isinstance(result["provenance"], dict)
            ):
                result["provenance"]["execution"]["worker_closed"] = True
                result["provenance"]["execution"]["wall_limit_seconds"] = wall_seconds
                return result["content"], result["provenance"]
            if result["code"] == "too_large":
                raise SourceTooLarge(result["message"])
            raise SourceUnavailable(result["message"])
        except (ValueError, KeyError, TypeError) as exc:
            if isinstance(exc, SourceTooLarge):
                raise
            raise SourceUnavailable("PDF worker returned an invalid receipt") from exc
