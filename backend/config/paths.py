"""Resolve database identity before any connection or startup side effect."""

from __future__ import annotations

import os
from pathlib import Path


def resolve_database_path(
    workspace: str | Path | None = None,
    explicit_path: str | Path | None = None,
) -> str:
    """Select existing data without moving it or silently choosing among databases.

    INFINIBAY_DB remains the primary environment override for compatibility.
    INFINIBAY_DB_PATH is also accepted. Relative paths belong to the workspace.
    """
    root = Path(workspace or Path.cwd()).resolve()
    override = explicit_path or os.environ.get("INFINIBAY_DB") or os.environ.get("INFINIBAY_DB_PATH")
    if override:
        path = Path(override).expanduser()
        return str((root / path).resolve())

    default = root / ".data" / "infinibay.db"
    candidates = [default, root / ".researcher" / "researcher.db", Path("/research/infinibay.db")]
    existing = sorted({path.resolve() for path in candidates if path.is_file()})
    if len(existing) > 1:
        paths = ", ".join(str(path) for path in existing)
        raise RuntimeError(
            f"Multiple existing databases found: {paths}. "
            "Set INFINIBAY_DB to choose which database to use; no data has been moved."
        )
    return str(existing[0] if existing else default)
