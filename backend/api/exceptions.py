"""Custom exception classes and global error handlers for the API."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


class APIError(Exception):
    """Base API error."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None):
        """Retain the API message, HTTP status and explicit detail used by the shared error envelope."""
        self.message = message
        self.status_code = status_code
        self.detail = detail or message
        super().__init__(message)


class ProjectNotFound(APIError):
    """Represent a missing project identity as an HTTP404 API error."""
    def __init__(self, project_id: int):
        """Bind the requested project ID to the missing-project error detail."""
        super().__init__(
            message="Project not found",
            status_code=404,
            detail=f"Project with id {project_id} does not exist",
        )


class EpicNotFound(APIError):
    """Represent a missing planning-group identity as an HTTP404 API error."""
    def __init__(self, epic_id: int):
        """Bind the requested group ID to the missing-epic compatibility error detail."""
        super().__init__(
            message="Epic not found",
            status_code=404,
            detail=f"Epic with id {epic_id} does not exist",
        )


class MilestoneNotFound(APIError):
    """Represent a missing milestone identity as an HTTP404 API error."""
    def __init__(self, milestone_id: int):
        """Bind the requested milestone ID to the missing-resource error detail."""
        super().__init__(
            message="Milestone not found",
            status_code=404,
            detail=f"Milestone with id {milestone_id} does not exist",
        )


class TaskNotFound(APIError):
    """Represent a missing task identity as an HTTP404 API error."""
    def __init__(self, task_id: int):
        """Bind the requested task ID to the missing-task error detail."""
        super().__init__(
            message="Task not found",
            status_code=404,
            detail=f"Task with id {task_id} does not exist",
        )


class InvalidTaskStatus(APIError):
    """Reject a task-status transition using the shared HTTP400 API envelope."""
    def __init__(self, detail: str):
        """Retain the transition-specific reason without granting a different lifecycle action."""
        super().__init__(
            message="Invalid task status transition",
            status_code=400,
            detail=detail,
        )


class FileNotFoundError_(APIError):
    """Represent a missing registered file independently of Python filesystem exceptions."""
    def __init__(self, file_id: int):
        """Bind the registered file ID to its HTTP404 API error detail."""
        super().__init__(
            message="File not found",
            status_code=404,
            detail=f"File with id {file_id} does not exist",
        )


class WikiPageNotFound(APIError):
    """Represent a missing wiki document path as an HTTP404 API error."""
    def __init__(self, path: str):
        """Bind the requested document path to the missing-page error detail."""
        super().__init__(
            message="Wiki page not found",
            status_code=404,
            detail=f"Wiki page at path '{path}' does not exist",
        )


class ProjectRunning(APIError):
    """Retain the project-running HTTP409 compatibility error; this label does not prove native activity."""
    def __init__(self, project_id: int):
        """Identify the project in the retained stop-first compatibility error message."""
        super().__init__(
            message="Project is currently running",
            status_code=409,
            detail=f"Project {project_id} is currently executing. Stop it first.",
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI app."""

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError) -> JSONResponse:
        """Serialize a declared APIError with its status, message and detail in the shared JSON envelope."""
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
        """Translate a ValueError into the HTTP400 bad-request JSON envelope."""
        return JSONResponse(
            status_code=400,
            content={
                "error": "Bad request",
                "detail": str(exc),
                "status_code": 400,
            },
        )
