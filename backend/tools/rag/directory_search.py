"""Tool for semantic search across files in a directory."""

import hashlib
import logging
import os
from typing import Type

from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.rag.base import (
    _chunk_text,
    embed_and_store,
    query_collection,
    validate_path_in_sandbox,
)

logger = logging.getLogger(__name__)

# Directories to always skip
_SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".tox", ".mypy_cache"}

# Maximum number of chunks to index from a single directory
_MAX_CHUNKS = 10_000


class DirectorySearchInput(BaseModel):
    query: str = Field(..., description="Semantic search query")
    directory: str = Field(..., description="Absolute path to the directory to search")
    file_extensions: list[str] | None = Field(
        default=None,
        description="Filter by file extensions (e.g. ['.py', '.md', '.txt'])",
    )
    n_results: int = Field(
        default=5, ge=1, le=20, description="Number of results to return"
    )


class DirectorySearchTool(PabadaBaseTool):
    name: str = "directory_search"
    description: str = (
        "Search across all files in a directory using semantic similarity. "
        "Indexes text files in the directory, then returns the most relevant "
        "passages for your query. Useful for finding code, documentation, or "
        "configuration by meaning rather than exact text match. Complements "
        "CodeSearchTool (which does exact/regex search)."
    )
    args_schema: Type[BaseModel] = DirectorySearchInput

    def _run(
        self,
        query: str,
        directory: str,
        file_extensions: list[str] | None = None,
        n_results: int = 5,
    ) -> str:
        directory = os.path.expanduser(directory)
        if not os.path.isabs(directory):
            directory = os.path.abspath(directory)

        error = validate_path_in_sandbox(directory)
        if error:
            return self._error(error)

        if not os.path.isdir(directory):
            return self._error(f"Not a directory: {directory}")

        # Build a hash of file paths + mtimes for cache key
        try:
            dir_hash = self._directory_hash(directory, file_extensions)
        except Exception as e:
            return self._error(f"Failed to scan directory: {e}")

        collection_name = f"dir-{dir_hash}"

        # Index if not already done
        try:
            self._ensure_indexed(collection_name, directory, file_extensions)
        except Exception as e:
            return self._error(f"Directory indexing failed: {e}")

        # Query
        results = query_collection(collection_name, query, n_results)

        self._log_tool_usage(
            f"Directory search in {directory}: "
            f"'{query[:50]}' → {len(results)} results"
        )

        return self._success({
            "query": query,
            "directory": directory,
            "results": results,
            "result_count": len(results),
        })

    @staticmethod
    def _directory_hash(
        directory: str,
        file_extensions: list[str] | None,
    ) -> str:
        """Hash of file paths + mtimes for collection naming."""
        h = hashlib.sha256()
        for root, dirs, files in os.walk(directory):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            dirs.sort()

            for fname in sorted(files):
                fpath = os.path.join(root, fname)
                if file_extensions:
                    ext = os.path.splitext(fname)[1].lower()
                    if ext not in file_extensions:
                        continue
                try:
                    mtime = os.path.getmtime(fpath)
                    h.update(f"{fpath}:{mtime}".encode())
                except OSError:
                    continue
        return h.hexdigest()[:16]

    @staticmethod
    def _is_binary(path: str) -> bool:
        """Check if a file is binary by looking for null bytes."""
        try:
            with open(path, "rb") as f:
                chunk = f.read(512)
                return b"\x00" in chunk
        except OSError:
            return True

    @staticmethod
    def _ensure_indexed(
        collection_name: str,
        directory: str,
        file_extensions: list[str] | None,
    ) -> None:
        """Walk directory, read text files, chunk and embed."""
        from backend.tools.rag.base import get_chroma_client, get_embedding_function

        client = get_chroma_client()
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=get_embedding_function(),
        )
        if collection.count() > 0:
            return  # Already indexed

        chunks: list[str] = []
        metadatas: list[dict] = []
        ids: list[str] = []
        file_count = 0

        for root, dirs, files in os.walk(directory):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            dirs.sort()

            for fname in sorted(files):
                if len(chunks) >= _MAX_CHUNKS:
                    break

                fpath = os.path.join(root, fname)
                ext = os.path.splitext(fname)[1].lower()

                if file_extensions and ext not in file_extensions:
                    continue

                # Skip large files
                try:
                    size = os.path.getsize(fpath)
                except OSError:
                    continue
                if size > settings.MAX_FILE_SIZE_BYTES or size == 0:
                    continue

                # Skip binary files
                if DirectorySearchTool._is_binary(fpath):
                    continue

                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                        content = f.read()
                except Exception:
                    continue

                rel_path = os.path.relpath(fpath, directory)
                file_chunks = _chunk_text(content)
                for chunk_idx, chunk in enumerate(file_chunks):
                    if len(chunks) >= _MAX_CHUNKS:
                        break
                    chunks.append(chunk)
                    metadatas.append({
                        "source_file": rel_path,
                        "file_extension": ext,
                        "chunk_index": chunk_idx,
                    })
                    ids.append(f"f{file_count}-c{chunk_idx}")

                file_count += 1

        if not chunks:
            logger.warning("No indexable text files found in %s", directory)
            return

        embed_and_store(collection_name, chunks, metadatas, ids)
        logger.info(
            "Indexed %d files (%d chunks) from %s",
            file_count, len(chunks), directory,
        )
