"""Read-only health probes run in the bounded ASGI worker pool, outside the native control event loop."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from backend.api import config
from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
def health_check():
    """Inspect database access and configured upload storage without creating files.

For a not-yet-used upload directory, check its nearest existing ancestor.
This reports owner API storage health, not native execution admission readiness.
    """
    db_ok = False
    fs_ok = False

    # Check DB
    try:
        def _ping(conn):
            """Check the selected source connection without mutating business data."""
            conn.execute("SELECT 1").fetchone()
            return True
        db_ok = execute_with_retry(_ping)
    except Exception:
        pass

    # A package installation need not have the historical /research directory.
    try:
        storage = Path(config.UPLOAD_DIR)
        while not storage.exists() and storage != storage.parent:
            storage = storage.parent
        fs_ok = storage.is_dir() and os.access(storage, os.W_OK | os.X_OK)
    except Exception:
        pass

    status = "healthy" if (db_ok and fs_ok) else "degraded"
    return {
        "status": status,
        "db": "ok" if db_ok else "error",
        "filesystem": "ok" if fs_ok else "error",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready")
def readiness_check():
    """Return 503 unless the existing database has the complete current migration history."""
    try:
        from backend.db.readiness import verify_database
        from backend.tools.base.db import get_db_path

        verify_database(get_db_path(), integrity=False)
        return {"ready": True}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"ready": False})
