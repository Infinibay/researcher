"""Tool for creating a git repository for a project."""

from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import InfinibayBaseTool


class CreateRepositoryInput(BaseModel):
    """Historical argument compatibility only; these fields cannot authorize source or remote effects."""

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




class CreateRepositoryTool(InfinibayBaseTool):
    """Retained compatibility entry point that explains the explicit owner setup replacement without executing it."""

    name: str = "create_repository"
    description: str = "Retired repository setup. Ask the owner to use explicit source operations; this tool cannot create or configure local or remote repositories."
    args_schema: Type[BaseModel] = CreateRepositoryInput

    def _run(
        self,
        project_id: int,
        repo_name: str,
        description: str = "",
    ) -> str:
        # Validate name format
        """Reject model-origin repository setup; an owner must choose its exact directory, mode and original intent through source controls."""
        return self._error("Repository setup requires explicit owner source operations. Creating a source never implicitly creates a remote, changes origin or pushes.")
