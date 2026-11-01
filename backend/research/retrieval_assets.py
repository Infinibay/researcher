"""Pinned public multilingual weights, prepared explicitly and never downloaded by a query.

Uses Ken's verified-public-asset pattern without importing code-specific embedders.
Runtime opens only the two fixed regular files and passes their pinned FDs to a worker.
"""

import hashlib
import json
import os
import stat
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

from backend.research.models import ResearchForbidden, SourceTooLarge

MODEL_ID = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
REVISION = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"
ARTIFACTS = {
    "model.onnx": (
        "onnx/model_quint8_avx2.onnx",
        118453870,
        "98a01d88b7de996cdea58c32ca71208c09968d143798814b2ea09d3439dc334f",
    ),
    "tokenizer.json": (
        "tokenizer.json",
        9081518,
        "2c3387be76557bd40970cec13153b3bbf80407865484b209e655e5e4729076b8",
    ),
}
MODEL = {
    "id": MODEL_ID,
    "revision": REVISION,
    "dimension": 384,
    "max_tokens": 128,
    "license": "Apache-2.0",
    "artifacts": {
        name: {"bytes": row[1], "sha256": row[2]} for name, row in ARTIFACTS.items()
    },
}
FINGERPRINT = hashlib.sha256(
    json.dumps(MODEL, sort_keys=True, separators=(",", ":")).encode()
).hexdigest()


class RetrievalUnavailable(RuntimeError):
    """The configured local retrieval asset/dependency is absent, changed or unsupported."""


class RetrievalBusy(RuntimeError):
    """Another local semantic worker owns the application's retrieval capacity."""


@contextmanager
def pinned_assets(directory, cancelled=None, *, deadline=None):
    """Verify exact known bytes on no-follow FDs; keep handles pinned until worker closure."""
    handles = []
    try:
        root = os.open(
            directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
        )
        handles.append(root)
        files = {}
        for name, (_, size, digest) in ARTIFACTS.items():
            fd = os.open(
                name,
                os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC,
                dir_fd=root,
            )
            handles.append(fd)
            entry = os.fstat(fd)
            if not stat.S_ISREG(entry.st_mode) or entry.st_size != size:
                raise RetrievalUnavailable(
                    "Pinned semantic assets are missing or changed"
                )
            check = hashlib.sha256()
            read_bytes = 0
            while True:
                if cancelled is not None and cancelled.is_set():
                    raise ResearchForbidden("Semantic query authority was withdrawn")
                if deadline is not None and time.monotonic() > deadline:
                    raise SourceTooLarge(
                        "Semantic asset verification exceeded its wall budget"
                    )
                chunk = os.read(fd, min(131072, size + 1 - read_bytes))
                if not chunk:
                    break
                read_bytes += len(chunk)
                if read_bytes > size:
                    raise RetrievalUnavailable(
                        "Pinned semantic asset grew during verification"
                    )
                check.update(chunk)
            if check.hexdigest() != digest:
                raise RetrievalUnavailable("Pinned semantic asset hash differs")
            os.lseek(fd, 0, os.SEEK_SET)
            files[name] = fd
        yield files
    except ResearchForbidden:
        raise
    except OSError as exc:
        raise RetrievalUnavailable(
            "Pinned local semantic assets are unavailable; preparation is required"
        ) from exc
    finally:
        for fd in reversed(handles):
            os.close(fd)


def prepare(directory, *, cache_dir, offline=False):
    """Explicitly prepare exact public assets; never overwrite an existing unverified directory."""
    target = Path(directory).absolute()
    if target.exists() or target.is_symlink():
        with pinned_assets(target):
            pass
        return {
            "directory": str(target),
            "model": MODEL,
            "fingerprint": FINGERPRINT,
            "prepared": True,
        }
    if not target.parent.is_dir():
        raise ValueError("Retrieval asset parent must already exist")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    from huggingface_hub import hf_hub_download

    with tempfile.TemporaryDirectory(
        prefix="retrieval-preparation-", dir=target.parent
    ) as temporary:
        staging = Path(temporary)
        for name, (remote, size, digest) in ARTIFACTS.items():
            source = Path(
                hf_hub_download(
                    MODEL_ID,
                    remote,
                    revision=REVISION,
                    cache_dir=str(cache_dir),
                    local_files_only=offline,
                    token=False,
                    endpoint="https://huggingface.co",
                )
            )
            # Copy only declared bytes into a new private regular file, not a cache symlink.
            total = 0
            check = hashlib.sha256()
            with source.open("rb") as incoming, (staging / name).open("xb") as outgoing:
                while chunk := incoming.read(131072):
                    total += len(chunk)
                    if total > size:
                        raise RetrievalUnavailable(
                            "Public asset exceeds its declared size"
                        )
                    check.update(chunk)
                    outgoing.write(chunk)
                outgoing.flush()
                os.fsync(outgoing.fileno())
            if total != size or check.hexdigest() != digest:
                raise RetrievalUnavailable(
                    "Public asset differs from the pinned revision"
                )
            (staging / name).chmod(0o400)
        os.mkdir(
            target, mode=0o700
        )  # Reserve without replacing any raced/unknown path.
        for name in ARTIFACTS:
            os.rename(staging / name, target / name)
        (target / "manifest.json").write_text(
            json.dumps({"model": MODEL, "fingerprint": FINGERPRINT}, indent=2) + "\n"
        )
        fd = os.open(target, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    with pinned_assets(target):
        pass
    return {
        "directory": str(target),
        "model": MODEL,
        "fingerprint": FINGERPRINT,
        "prepared": True,
    }
