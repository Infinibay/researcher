"""Custom exception classes and global error handlers for the API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    """Base API error."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(message)


class ProjectNotFound(APIError):
    def __init__(self, project_id: int):
        super().__init__(
            message="Project not found",
            status_code=404,
            detail=f"Project with id {project_id} does not exist",
        )


class EpicNotFound(APIError):
    def __init__(self, epic_id: int):
        super().__init__(
            message="Epic not found",
            status_code=404,
            detail=f"Epic with id {epic_id} does not exist",
        )


class MilestoneNotFound(APIError):
    def __init__(self, milestone_id: int):
        super().__init__(
            message="Milestone not found",
            status_code=404,
            detail=f"Milestone with id {milestone_id} does not exist",
        )


class TaskNotFound(APIError):
    def __init__(self, task_id: int):
        super().__init__(
            message="Task not found",
            status_code=404,
            detail=f"Task with id {task_id} does not exist",
        )


class InvalidTaskStatus(APIError):
    def __init__(self, detail: str):
        super().__init__(
            message="Invalid task status transition",
            status_code=400,
            detail=detail,
        )


class FileNotFoundError_(APIError):
    def __init__(self, file_id: int):
        super().__init__(
            message="File not found",
            status_code=404,
            detail=f"File with id {file_id} does not exist",
        )


class WikiPageNotFound(APIError):
    def __init__(self, path: str):
        super().__init__(
            message="Wiki page not found",
            status_code=404,
            detail=f"Wiki page at path '{path}' does not exist",
        )


class ProjectRunning(APIError):
    def __init__(self, project_id: int):
        super().__init__(
            message="Project is currently running",
            status_code=409,
            detail=f"Project {project_id} is currently executing. Stop it first.",
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.message,
                "detail": exc.detail,
                "status_code": exc.status_code,
            },
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad request",
                "detail": str(exc),
                "status_code": 400,
            },
        )
