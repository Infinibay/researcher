"""Tool for listing directory contents."""

import fnmatch
import os
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool


class ListDirectoryInput(BaseModel):
    path: str = Field(default=".", description="Directory path to list")
    recursive: bool = Field(default=False, description="Whether to list recursively")
    pattern: str | None = Field(
        default=None, description="Glob pattern to filter files (e.g. '*.py')"
    )


class ListDirectoryTool(PabadaBaseTool):
    name: str = "list_directory"
    description: str = (
        "List files and directories in a given path. "
        "Supports recursive listing and glob pattern filtering."
    )
    args_schema: Type[BaseModel] = ListDirectoryInput

    def _run(
        self, path: str = ".", recursive: bool = False, pattern: str | None = None
    ) -> str:
        path = os.path.expanduser(path)
        if not os.path.isabs(path):
            path = os.path.abspath(path)

        # Sandbox check (resolves symlinks, enforces directory boundaries)
        sandbox_err = self._validate_sandbox_path(path)
        if sandbox_err:
            return self._error(sandbox_err)

        if not os.path.exists(path):
            return self._error(f"Directory not found: {path}")
        if not os.path.isdir(path):
            return self._error(f"Not a directory: {path}")

        entries = []
        count = 0
        max_entries = settings.MAX_DIR_LISTING

        # Hidden dirs and .git excluded by default
        skip_dirs = {".git", "__pycache__", "node_modules", ".venv", ".tox"}

        try:
            if recursive:
                for root, dirs, files in os.walk(path):
                    # Prune hidden/skip dirs
                    dirs[:] = [
                        d for d in dirs
                        if d not in skip_dirs and not d.startswith(".")
                    ]
                    for name in files:
                        if count >= max_entries:
                            break
                        full = os.path.join(root, name)
                        rel = os.path.relpath(full, path)
                        if pattern and not fnmatch.fnmatch(name, pattern):
                            continue
                        try:
                            stat = os.stat(full)
                            entries.append({
                                "path": rel,
                                "size": stat.st_size,
                                "mtime": stat.st_mtime,
                                "type": "file",
                            })
                        except OSError:
                            entries.append({"path": rel, "type": "file"})
                        count += 1
                    if count >= max_entries:
                        break
            else:
                for name in sorted(os.listdir(path)):
                    if count >= max_entries:
                        break
                    if name in skip_dirs or name.startswith("."):
                        continue
                    full = os.path.join(path, name)
                    if pattern and not fnmatch.fnmatch(name, pattern):
                        continue
                    is_dir = os.path.isdir(full)
                    try:
                        stat = os.stat(full)
                        entries.append({
                            "path": name,
                            "size": stat.st_size if not is_dir else None,
                            "mtime": stat.st_mtime,
                            "type": "directory" if is_dir else "file",
                        })
                    except OSError:
                        entries.append({
                            "path": name,
                            "type": "directory" if is_dir else "file",
                        })
                    count += 1
        except PermissionError:
            return self._error(f"Permission denied: {path}")

        truncated = count >= max_entries
        return self._success({
            "path": path,
            "entries": entries,
            "total": len(entries),
            "truncated": truncated,
        })
