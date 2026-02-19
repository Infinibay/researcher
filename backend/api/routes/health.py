"""Health check endpoints."""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter

from backend.tools.base.db import execute_with_retry

router = APIRouter(prefix="/api/health", tags=["health"])


@router.get("")
async def health_check():
    """Basic health check — verifies DB and filesystem access."""
    db_ok = False
    fs_ok = False

    # Check DB
    try:
        def _ping(conn):
            conn.execute("SELECT 1").fetchone()
            return True
        db_ok = execute_with_retry(_ping)
    except Exception:
        pass

    # Check filesystem
    try:
        fs_ok = os.access("/research", os.W_OK)
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
async def readiness_check():
    """Readiness probe — returns 503 if not ready."""
    try:
        def _ping(conn):
            conn.execute("SELECT 1").fetchone()
            return True
        execute_with_retry(_ping)
        return {"ready": True}
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=503, content={"ready": False})
