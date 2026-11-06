"""FastAPI application factory for the INFINIBAY API."""

from __future__ import annotations

import asyncio
import logging
import time
from contextlib import ExitStack, asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.api import config as api_config
from backend.api.exceptions import register_exception_handlers
from backend.api.local_access import LocalAccess, OwnerAccessMiddleware
from backend.api.websocket import manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize before serving and reconcile active work on shutdown."""
    from backend.api.run import setup_file_logging
    from backend.tools.base.db import ensure_migrations

    with ExitStack() as cleanup:
        runtime = None
        entered = False
        serving = False
        try:
            file_handler = setup_file_logging()
            if file_handler is not None:
                cleanup.callback(file_handler.close)
                cleanup.callback(logging.getLogger().removeHandler, file_handler)
            await asyncio.to_thread(ensure_migrations, existing_only=True)
            # A cancelled to_thread await does not stop the file-creating worker.
            # Drain it before finally removes its pairing file and sessions.
            starting_access = asyncio.create_task(
                asyncio.to_thread(app.state.local_access.start)
            )
            try:
                await asyncio.shield(starting_access)
            except asyncio.CancelledError:
                try:
                    await starting_access
                finally:
                    raise
            if app.state.runtime_service is None:
                from backend.api.runtime_dependencies import configured_runtime

                app.state.runtime_service = await asyncio.to_thread(
                    configured_runtime, app.state.live_grants, app=app
                )
            runtime = app.state.runtime_service
            if runtime is not None:
                await runtime.__aenter__()
                entered = True
            serving = True
            yield
        finally:
            try:
                if entered:
                    await runtime.__aexit__(None, None, None)
            finally:
                try:
                    app.state.live_grants.close()
                    await asyncio.to_thread(app.state.live_grants.wait_closed)
                finally:
                    try:
                        app.state.local_access.close()
                    finally:
                        if serving:
                            await _stop_active_flows()


async def _stop_active_flows():
    """Reconcile legacy flows only after this server reached serving state."""
    logger.info("Shutdown signal received — stopping active flows")
    from backend.api.flow_manager import flow_manager

    active_ids = (
        set(flow_manager._flows)
        | set(flow_manager._autonomy)
        | set(flow_manager._listeners)
    )
    for pid in active_ids:
        try:
            logger.info(
                "Stopping project %d: snapshotting state, stopping agents & listeners…",
                pid,
            )
            await asyncio.to_thread(flow_manager.stop_project_flow, pid)
            logger.info("Project %d stopped successfully", pid)
        except Exception:
            logger.warning(
                "Error stopping project %d during shutdown", pid, exc_info=True
            )
    logger.info(
        "Shutdown reconciliation finished for %d active project(s)", len(active_ids)
    )


def create_app(*, access: LocalAccess | None = None, runtime_service=None) -> FastAPI:
    """Construct routes without inference, database writes or maintenance jobs."""
    app = FastAPI(
        title="INFINIBAY API",
        description="REST API for the INFINIBAY project management system",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    app.state.local_access = access or LocalAccess()
    from backend.runtime.live_grants import LiveGrants

    app.state.live_grants = (
        runtime_service.live_grants if runtime_service is not None else LiveGrants()
    )
    app.state.runtime_service = runtime_service
    from backend.config.settings import settings
    from backend.research.semantic import SemanticRetriever
    from backend.research.web_policy import WebAccessPolicy

    app.state.retrieval = SemanticRetriever(settings.RETRIEVAL_ASSET_DIR)
    app.state.web_access_policy = WebAccessPolicy(
        requests_per_minute=settings.WEB_RPM_LIMIT,
        cache_ttl=settings.WEB_ROBOTS_CACHE_TTL,
    )

    from backend.api.request_limits import ToolRequestLimits

    app.add_middleware(ToolRequestLimits)

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(app.state.local_access.allowed_origins),
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
            logger.warning(
                "Slow request: %s %s took %.2fs",
                request.method,
                request.url.path,
                elapsed,
            )
        return response

    app.add_middleware(OwnerAccessMiddleware, access=app.state.local_access)

    # Exception handlers
    register_exception_handlers(app)

    # Register routers
    from backend.api.routes.agents import router as agents_router
    from backend.api.routes.artifacts import router as artifacts_router
    from backend.api.routes.chat import router as chat_router
    from backend.api.routes.epics import router as epics_router
    from backend.api.routes.events import router as events_router
    from backend.api.routes.files import router as files_router
    from backend.api.routes.findings import router as findings_router
    from backend.api.routes.flow_state import router as flow_state_router
    from backend.api.routes.git import router as git_router
    from backend.api.routes.source_operations import router as source_operations_router
    from backend.api.routes.model_settings import router as model_settings_router
    from backend.api.routes.health import router as health_router
    from backend.api.routes.internal import router as internal_router
    from backend.api.routes.internal_findings import router as internal_findings_router
    from backend.api.routes.internal_tasks import router as internal_tasks_router
    from backend.api.routes.milestones import router as milestones_router
    from backend.api.routes.projects import router as projects_router
    from backend.api.routes.research import install_research_errors
    from backend.api.routes.research import router as research_router
    from backend.api.routes.runs import install_run_errors
    from backend.api.routes.runs import router as runs_router
    from backend.api.routes.session import router as session_router
    from backend.api.routes.tasks import router as tasks_router
    from backend.api.routes.task_workspace import router as task_workspace_router
    from backend.api.routes.agent_messages import router as agent_messages_router
    from backend.api.routes.user_requests import router as user_requests_router
    from backend.api.routes.wiki import router as wiki_router

    app.include_router(session_router)
    install_run_errors(app)
    app.include_router(runs_router)
    app.include_router(model_settings_router)
    install_research_errors(app)
    app.include_router(research_router)
    app.include_router(task_workspace_router)
    app.include_router(agent_messages_router)
    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(epics_router)
    app.include_router(milestones_router)
    app.include_router(tasks_router)
    app.include_router(wiki_router)
    app.include_router(chat_router)
    app.include_router(files_router)
    app.include_router(git_router)
    app.include_router(source_operations_router)
    app.include_router(agents_router)
    app.include_router(user_requests_router)
    app.include_router(events_router)
    app.include_router(flow_state_router)
    app.include_router(internal_router)
    app.include_router(internal_findings_router)
    app.include_router(internal_tasks_router)
    app.include_router(findings_router)
    app.include_router(artifacts_router)

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
            pass
        finally:
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
            if full_path.startswith(("api/", "docs", "redoc")):
                return JSONResponse(status_code=404, content={"error": "Not found"})
            index = static_dir / "index.html"
            if index.exists():
                return FileResponse(str(index))
            return JSONResponse(
                status_code=404, content={"error": "Frontend not built"}
            )

    return app
