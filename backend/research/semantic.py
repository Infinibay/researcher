"""Project-source semantic recovery with pinned offline weights and exact text windows.

No vector DB/global cache is reused: every successful response considered every
bounded source chunk. Application capacity is held through physical worker exit.
"""

import hashlib
import json
import math
import os
import sys
import time
from dataclasses import asdict, dataclass
from importlib.util import find_spec
from pathlib import Path
from threading import BoundedSemaphore, Event

from backend.research.models import (
    ResearchForbidden,
    ResearchInputError,
    SourceTooLarge,
    SourceUnavailable,
    WorkerBusy,
)
from backend.research.provenance import intersecting_units
from backend.research.retrieval_assets import (
    FINGERPRINT,
    MODEL,
    RetrievalBusy,
    RetrievalUnavailable,
    pinned_assets,
)
from backend.research.worker_transport import exchange

WORKER = Path(__file__).with_name("semantic_worker.py")
# Adapters and API applications in one process share the same physical-worker budget.
_PROCESS_CAPACITY = BoundedSemaphore(1)


@dataclass(frozen=True)
class SemanticLimits:
    """Fixed host budgets for one CPU encoder: address space is not an aggregate RSS quota."""

    cpu_seconds: int = 15
    memory_bytes: int = 2147483648
    wall_seconds: float = 30
    max_input_bytes: int = 300000
    max_output_bytes: int = 512000

    def __post_init__(self):
        """Refuse disabled/unbounded host resource limits before admission."""
        if type(self.cpu_seconds) is not int or not 1 <= self.cpu_seconds <= 30:
            raise ValueError("Semantic CPU budget must be 1–30 seconds")
        if (
            type(self.memory_bytes) is not int
            or not 67108864 <= self.memory_bytes <= 4294967296
        ):
            raise ValueError("Semantic address-space budget must be 64–4096 MiB")
        if (
            type(self.wall_seconds) not in (int, float)
            or not math.isfinite(self.wall_seconds)
            or not 0.1 <= self.wall_seconds <= 60
        ):
            raise ValueError("Semantic wall budget must be finite and 0.1–60 seconds")
        if any(
            type(value) is not int or not 1 <= value <= 1000000
            for value in (self.max_input_bytes, self.max_output_bytes)
        ):
            raise ValueError("Semantic IPC budgets must be 1–1000000 bytes")


class SemanticRetriever:
    """One process-owned capacity slot and an explicitly prepared offline asset directory."""

    def __init__(self, directory, *, limits=None):
        """Bind configuration without reading assets, loading a model, downloading or creating state."""
        self.directory = Path(directory).absolute() if directory else None
        self.limits = limits or SemanticLimits()
        self._capacity = _PROCESS_CAPACITY

    def status(self):
        """Declare setup state without reading weights or mistaking configuration for readiness."""
        return {
            "method": "semantic_cosine",
            "assets_status": "verification_required"
            if self.directory
            else "not_configured",
            "model_id": MODEL["id"],
            "revision": MODEL["revision"],
        }

    def query(self, source, query, *, limit=5, after_rank=0, cancelled=None):
        """Rank a complete saved revision, preserving exact offsets and honest availability failures."""
        if not isinstance(query, str) or not query.strip() or len(query) > 1000:
            raise ResearchInputError("Semantic query must contain 1–1000 characters")
        if (
            type(limit) is not int
            or not 1 <= limit <= 20
            or type(after_rank) is not int
            or not 0 <= after_rank <= 2048
        ):
            raise ResearchInputError("Invalid semantic result page")
        if hashlib.sha256(source["content"].encode()).hexdigest() != source["sha256"]:
            raise RetrievalUnavailable("Saved source hash differs from its text")
        if self.directory is None:
            raise RetrievalUnavailable(
                "Local semantic retrieval is not prepared/configured; literal source search remains available"
            )
        if sys.platform != "linux":
            raise RetrievalUnavailable(
                "Semantic retrieval requires the Linux owned worker"
            )
        if not self._capacity.acquire(blocking=False):
            raise RetrievalBusy(
                "Local semantic retrieval is busy; no worker was started"
            )
        cancelled = cancelled or Event()
        deadline = time.monotonic() + self.limits.wall_seconds
        try:
            if cancelled.is_set():
                raise ResearchForbidden("Semantic query authority was withdrawn")
            spec = find_spec("onnxruntime")
            if spec is None or spec.origin is None:
                raise RetrievalUnavailable("Local semantic dependency is unavailable")
            options = asdict(self.limits) | {
                "parent": os.getpid(),
                "package_root": str(Path(__file__).resolve().parents[2]),
                "dependencies": str(Path(spec.origin).resolve().parent.parent),
            }
            raw = json.dumps(
                {"text": source["content"], "query": query}, ensure_ascii=False
            ).encode()
            if len(raw) > self.limits.max_input_bytes:
                raise SourceTooLarge(
                    "Semantic request exceeds its complete byte budget"
                )
            with pinned_assets(self.directory, cancelled, deadline=deadline) as files:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise SourceTooLarge(
                        "Semantic query exceeded its complete wall budget"
                    )
                options["wall_seconds"] = remaining
                options["assets"] = files
                payload = exchange(
                    raw,
                    worker=WORKER,
                    options=options,
                    limits=self.limits,
                    cancelled=cancelled,
                    label="Semantic",
                    pass_fds=tuple(files.values()),
                )
            result = json.loads(payload)
            if not isinstance(result, dict):
                raise TypeError("Invalid semantic receipt shape")
            if result.get("ok") is not True:
                if result.get("code") == "too_large":
                    raise SourceTooLarge(
                        "Semantic query exceeded local execution budgets; no partial results"
                    )
                raise RetrievalUnavailable(
                    "Local semantic encoder did not return a complete result"
                )
            chunks = result["chunks"]
            if result["fingerprint"] != FINGERPRINT or not 1 <= len(chunks) <= 2048:
                raise ValueError("Invalid semantic identity or coverage")
            end = 0
            for row in chunks:
                if (
                    type(row["start"]) is not int
                    or type(row["end"]) is not int
                    or not 0
                    <= row["start"]
                    <= end
                    < row["end"]
                    <= len(source["content"])
                    or row["end"] - row["start"] > 1200
                    or type(row["score"]) not in (int, float)
                    or not math.isfinite(row["score"])
                    or not -1 <= row["score"] <= 1
                ):
                    raise ValueError("Invalid semantic chunk receipt")
                end = row["end"]
            if end != len(source["content"]):
                raise ValueError("Incomplete semantic source coverage")
            ordered = sorted(chunks, key=lambda row: (-row["score"], row["start"]))
            selected = ordered[after_rank : after_rank + limit]
            pages = source.get("provenance", {}).get("pages", [])
            matches = [
                {
                    "rank": after_rank + index,
                    "start_offset": row["start"],
                    "end_offset": row["end"],
                    "excerpt": source["content"][row["start"] : row["end"]],
                    "score": row["score"],
                    "unit_indices": intersecting_units(
                        source.get("provenance", {}), row["start"], row["end"]
                    ),
                    "page_numbers": [
                        p["page_number"]
                        for p in pages
                        if p["text_start_offset"] < row["end"]
                        and p["end_offset"] > row["start"]
                    ],
                }
                for index, row in enumerate(selected)
            ]
            if cancelled.is_set():
                raise ResearchForbidden("Semantic query authority was withdrawn")
            if time.monotonic() > deadline:
                raise SourceTooLarge("Semantic query exceeded its complete wall budget")
            return {
                "source_id": source["id"],
                "sha256": source["sha256"],
                "query": query,
                "search_kind": "semantic_cosine",
                "model": MODEL
                | {
                    "fingerprint": FINGERPRINT,
                    "encoder_policy": "masked-mean-l2-v1",
                    **result["model_runtime"],
                },
                "chunk_policy": {
                    "version": "chars1200-tokens96-overlap96-v1",
                    "max_chars": 1200,
                    "max_model_tokens": 128,
                    "truncation": False,
                    "cache": "none; rebuild each query",
                },
                "usage": {
                    "query_tokens": result["query_tokens"],
                    "local_embedding_batches": result["encoder_usage"]["batches"],
                    "local_embedded_vectors": result["encoder_usage"]["vectors"],
                },
                "total_chunks": len(chunks),
                "considered_chunks": len(chunks),
                "full_coverage": True,
                "matches": matches,
                "next_rank": after_rank + len(selected)
                if after_rank + len(selected) < len(chunks)
                else None,
                "execution": result["execution"]
                | {
                    "worker_closed": True,
                    "wall_limit_seconds": self.limits.wall_seconds,
                },
            }
        except WorkerBusy as exc:
            raise RetrievalBusy(str(exc)) from exc
        except SourceUnavailable as exc:
            raise RetrievalUnavailable(
                "Local semantic worker could not complete safely"
            ) from exc
        except (KeyError, TypeError, ValueError) as exc:
            if isinstance(exc, (ResearchInputError, SourceTooLarge)):
                raise
            raise RetrievalUnavailable(
                "Local semantic worker returned an invalid receipt"
            ) from exc
        finally:
            self._capacity.release()
