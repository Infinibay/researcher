"""Technology detection for project repositories."""

from __future__ import annotations

import logging
from pathlib import Path

from backend.tools.base.db import execute_with_retry

logger = logging.getLogger(__name__)


def detect_tech_hints(project_id: int) -> list[str]:
    """Scan project repositories for technology indicator files.

    Checks for common config files, file extensions, and dependency declarations
    in each repository's ``local_path``. Returns a deduplicated list of technology
    names that can be fed to the developer prompt builder.

    Never raises — returns ``[]`` on any error so agent creation is never blocked.
    """
    try:
        def _query(conn):
            rows = conn.execute(
                "SELECT local_path FROM repositories WHERE project_id = ? AND status = 'active'",
                (project_id,),
            ).fetchall()
            return [r["local_path"] for r in rows if r["local_path"]]

        local_paths = execute_with_retry(_query)

        hints: list[str] = []
        for path_str in local_paths:
            root = Path(path_str)
            if not root.is_dir():
                continue
            _detect_from_dir(root, hints)

        # Deduplicate preserving insertion order
        return list(dict.fromkeys(hints))

    except Exception:
        logger.warning(
            "detect_tech_hints: failed for project %d, returning empty list",
            project_id,
            exc_info=True,
        )
        return []


def _detect_from_dir(root: Path, hints: list[str]) -> None:
    """Populate *hints* by scanning *root* for technology indicators.

    Searches both the repo root and common subdirectories (``src``, ``apps``,
    ``packages``, ``lib``, ``cmd``) so that nested source trees are detected.
    For file-extension checks, uses ``rglob`` with an early-break ``any()``
    to avoid walking the entire tree unnecessarily.
    """

    # Directories to check for indicator files (config files like
    # pyproject.toml, tsconfig.json, etc.).  The root is always checked;
    # subdirectories cover monorepo / nested-source layouts.
    _SEARCH_DIRS = [
        root,
        root / "src",
        root / "apps",
        root / "packages",
        root / "lib",
        root / "cmd",
    ]

    def _has(name: str) -> bool:
        """True if *name* exists in the root or any search directory."""
        return any((d / name).exists() for d in _SEARCH_DIRS)

    def _any_ext(*exts: str) -> bool:
        """True if any file with one of *exts* exists anywhere in the tree.

        Uses ``rglob`` with ``any()`` so iteration stops at the first match.
        """
        return any(
            any(root.rglob(f"*{ext}"))
            for ext in exts
        )

    def _file_contains(name: str, *needles: str) -> bool:
        """Check if *name* (relative to any search dir) contains a needle."""
        for d in _SEARCH_DIRS:
            p = d / name
            if not p.is_file():
                continue
            try:
                content = p.read_text(errors="ignore")
                if any(n in content for n in needles):
                    return True
            except OSError:
                continue
        return False

    # Languages
    if _has("pyproject.toml") or _has("setup.py") or _has("requirements.txt") or _any_ext(".py"):
        hints.append("python")
    if _has("tsconfig.json"):
        hints.append("typescript")
    elif _has("package.json"):
        hints.append("javascript")
    if _has("Cargo.toml"):
        hints.append("rust")

    has_cpp = _has("CMakeLists.txt") or _any_ext(".cpp", ".cc", ".cxx")
    if has_cpp:
        hints.append("cpp")
    if not has_cpp and _any_ext(".c"):
        hints.append("c")

    if _has("Gemfile"):
        hints.append("ruby")
    if _any_ext(".sql"):
        hints.append("sql")

    # Containers
    if _has("docker-compose.yml") or _has("docker-compose.yaml") or _has("Dockerfile"):
        hints.append("docker")
    if _has("Containerfile"):
        hints.append("podman")

    # Shell
    if _any_ext(".sh"):
        hints.append("bash")

    # Databases / stores (check dependency files)
    deps_files = ("requirements.txt", "package.json", "Cargo.toml")
    if any(_file_contains(f, "redis") for f in deps_files):
        hints.append("redis")
    if any(_file_contains(f, "psycopg", "asyncpg", "postgres") for f in deps_files):
        hints.append("postgres")
    if any(_file_contains(f, "mysql", "pymysql", "mysqlclient") for f in deps_files):
        hints.append("mysql")
