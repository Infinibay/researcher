"""Tool for creating a git repository for a project."""

import re
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool


class CreateRepositoryInput(BaseModel):
    project_id: int = Field(..., description="Project ID to create the repository for")
    repo_name: str = Field(
        ...,
        description=(
            "Repository name. Must be lowercase, alphanumeric with hyphens, "
            "between 2 and 40 characters. Example: 'my-cool-app'"
        ),
    )
    description: str = Field(
        default="",
        description="Optional description for the Forgejo repository",
    )


_REPO_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{0,38}[a-z0-9]$")


class CreateRepositoryTool(PabadaBaseTool):
    name: str = "create_repository"
    description: str = (
        "Create a new git repository for the project. The repository is "
        "initialized locally and automatically created on Forgejo if configured. "
        "Parameters: project_id, repo_name (lowercase, hyphens, 2-40 chars), "
        "description (optional)."
    )
    args_schema: Type[BaseModel] = CreateRepositoryInput

    def _run(
        self,
        project_id: int,
        repo_name: str,
        description: str = "",
    ) -> str:
        # Validate name format
        if not _REPO_NAME_RE.match(repo_name):
            return self._error(
                f"Invalid repo name '{repo_name}'. Must be lowercase, "
                "alphanumeric with hyphens, 2-40 characters, and cannot "
                "start or end with a hyphen."
            )

        # Lazy imports to avoid circular import chain
        from backend.config.settings import settings
        from backend.git.repository_manager import RepositoryManager

        local_path = f"{settings.WORKSPACE_BASE_DIR}/projects/{project_id}/{repo_name}"

        repo_manager = RepositoryManager()

        try:
            repo = repo_manager.init_repo(
                project_id=project_id,
                name=repo_name,
                local_path=local_path,
                description=description,
            )
        except Exception as e:
            return self._error(f"Failed to create repository: {e}")

        # Log the event
        try:
            from backend.flows.helpers import log_flow_event

            log_flow_event(
                project_id,
                "repo_created",
                self.agent_id or "project_lead",
                "project",
                project_id,
                {"repo_name": repo_name, "local_path": local_path},
            )
        except Exception:
            pass  # Non-critical — don't fail if event logging fails

        self._log_tool_usage(f"Created repository '{repo_name}' for project {project_id}")
        return self._success({
            "repo_name": repo_name,
            "local_path": local_path,
            "remote_url": repo.get("remote_url", ""),
            "default_branch": repo.get("default_branch", "main"),
            "status": "active",
        })
