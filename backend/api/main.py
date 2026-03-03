"""FastAPI application factory for the PABADA API."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import config as api_config
from backend.api.exceptions import register_exception_handlers
from backend.api.websocket import manager
from backend.config.settings import settings

# Set provider env vars at import time so uvicorn reload picks them up.
from backend.config.llm import setup_provider_env_vars as _setup_env
_setup_env()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: snapshot and stop all active flows on shutdown."""
    yield
    # --- Shutdown ---
    logger.info("Shutdown signal received — stopping active flows")
    from backend.api.flow_manager import flow_manager

    active_ids = list(flow_manager._flows.keys())
    for pid in active_ids:
        try:
            logger.info("Stopping project %d: snapshotting state, stopping agents & listeners…", pid)
            flow_manager.stop_project_flow(pid)
            logger.info("Project %d stopped successfully", pid)
        except Exception:
            logger.warning("Error stopping project %d during shutdown", pid, exc_info=True)
    logger.info("Graceful shutdown complete: saved snapshots for %d active project(s)", len(active_ids))


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    # With reload=True, uvicorn runs the app in a child process.
    # setup_file_logging() in run.py only configures the parent (reloader),
    # so we must also configure it here for the actual worker process.
    from backend.api.run import setup_file_logging
    setup_file_logging()

    app = FastAPI(
        title="PABADA API",
        description="REST API for the PABADA project management system",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Run pending DB migrations for existing databases
    from backend.tools.base.db import ensure_migrations
    ensure_migrations()

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=api_config.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request timing middleware
    @app.middleware("http")
    async def timing_middleware(request: Request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - start
        response.headers["X-Process-Time"] = f"{elapsed:.4f}"
        if elapsed > 1.0:
            logger.warning("Slow request: %s %s took %.2fs",
                           request.method, request.url.path, elapsed)
        return response

    # Exception handlers
    register_exception_handlers(app)

    # Register routers
    from backend.api.routes.health import router as health_router
    from backend.api.routes.projects import router as projects_router
    from backend.api.routes.epics import router as epics_router
    from backend.api.routes.milestones import router as milestones_router
    from backend.api.routes.tasks import router as tasks_router
    from backend.api.routes.wiki import router as wiki_router
    from backend.api.routes.chat import router as chat_router
    from backend.api.routes.files import router as files_router
    from backend.api.routes.git import router as git_router
    from backend.api.routes.agents import router as agents_router
    from backend.api.routes.user_requests import router as user_requests_router
    from backend.api.routes.events import router as events_router
    from backend.api.routes.flow_state import router as flow_state_router
    from backend.api.routes.internal import router as internal_router

    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(epics_router)
    app.include_router(milestones_router)
    app.include_router(tasks_router)
    app.include_router(wiki_router)
    app.include_router(chat_router)
    app.include_router(files_router)
    app.include_router(git_router)
    app.include_router(agents_router)
    app.include_router(user_requests_router)
    app.include_router(events_router)
    app.include_router(flow_state_router)
    app.include_router(internal_router)

    # Start periodic cleanup of stale sandbox containers
    from backend.security.cleanup import cleanup_manager
    cleanup_manager.schedule_periodic_cleanup(settings.CLEANUP_INTERVAL_SECONDS)

    # Start periodic cleanup of merged git branches
    from backend.git import cleanup_service
    cleanup_service.schedule_periodic_cleanup(settings.CLEANUP_INTERVAL_SECONDS)

    # WebSocket endpoint
    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket, project_id: int):
        await manager.connect(websocket, project_id)
        try:
            while True:
                # Keep connection alive; listen for client messages
                data = await websocket.receive_text()
                # Client can send ping/pong or commands
                if data == "ping":
                    await manager.send_personal_message({"type": "pong"}, websocket)
        except WebSocketDisconnect:
            manager.disconnect(websocket, project_id)

    # Serve static frontend files if they exist
    static_dir = Path(api_config.STATIC_DIR)
    if static_dir.exists() and static_dir.is_dir():
        # Serve static assets
        assets_dir = static_dir / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

        # Catch-all for client-side routing
        @app.get("/{full_path:path}", include_in_schema=False)
        async def serve_spa(full_path: str):
            # Don't serve SPA for API routes
            if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("redoc"):
                return JSONResponse(status_code=404, content={"error": "Not found"})
            index = static_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return JSONResponse(status_code=404, content={"error": "Frontend not built"})

    return app


# Module-level instance required by uvicorn when using import string with reload=True
app = create_app()
