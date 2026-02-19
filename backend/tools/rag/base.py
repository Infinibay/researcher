"""Shared RAG infrastructure for PDF, Directory, and CSV search tools.

Provides embedding, chunking, ChromaDB client management, and sandbox
path validation — consumed by the three RAG tool modules.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Any

import chromadb

from backend.config.settings import settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Text chunking (same algorithm as backend/knowledge/sources.py)
# ---------------------------------------------------------------------------

def _chunk_text(
    text: str,
    chunk_size: int | None = None,
    chunk_overlap: int | None = None,
) -> list[str]:
    """Split *text* into overlapping chunks.

    Returns the original text as a single-element list when it fits
    within *chunk_size*.
    """
    if chunk_size is None:
        chunk_size = settings.KNOWLEDGE_CHUNK_SIZE
    if chunk_overlap is None:
        chunk_overlap = settings.KNOWLEDGE_CHUNK_OVERLAP

    if len(text) <= chunk_size:
        return [text]

    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - chunk_overlap
    return chunks


# ---------------------------------------------------------------------------
# Hashing helpers
# ---------------------------------------------------------------------------

def content_hash(content: str) -> str:
    """Return a short SHA-256 hex digest (16 chars) for *content*."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def file_content_hash(path: str) -> str:
    """Return a short SHA-256 hex digest (16 chars) of the file at *path*."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(8192), b""):
            h.update(block)
    return h.hexdigest()[:16]


# ---------------------------------------------------------------------------
# ChromaDB client & embedding function
# ---------------------------------------------------------------------------

_chroma_client: chromadb.PersistentClient | None = None


def get_chroma_client() -> chromadb.PersistentClient:
    """Return a singleton ChromaDB persistent client."""
    global _chroma_client
    if _chroma_client is None:
        os.makedirs(settings.RAG_PERSIST_DIR, exist_ok=True)
        _chroma_client = chromadb.PersistentClient(
            path=settings.RAG_PERSIST_DIR,
        )
    return _chroma_client


class _OpenAIEmbeddingFunction(chromadb.EmbeddingFunction):
    """Wraps the OpenAI embeddings API for ChromaDB compatibility."""

    def __init__(self) -> None:
        import openai

        kwargs: dict[str, Any] = {}
        if settings.EMBEDDING_BASE_URL:
            kwargs["base_url"] = settings.EMBEDDING_BASE_URL
        self._client = openai.OpenAI(**kwargs)
        self._model = settings.EMBEDDING_MODEL

    def __call__(self, input: list[str]) -> list[list[float]]:  # noqa: A002
        response = self._client.embeddings.create(
            input=input,
            model=self._model,
        )
        return [item.embedding for item in response.data]


_embedding_fn: _OpenAIEmbeddingFunction | None = None


def get_embedding_function() -> _OpenAIEmbeddingFunction:
    """Return a singleton embedding function instance."""
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = _OpenAIEmbeddingFunction()
    return _embedding_fn


# ---------------------------------------------------------------------------
# Collection helpers
# ---------------------------------------------------------------------------

def embed_and_store(
    collection_name: str,
    chunks: list[str],
    metadatas: list[dict[str, Any]],
    ids: list[str],
) -> None:
    """Create or get a ChromaDB collection and upsert chunks.

    Skips the upsert if the collection already contains documents
    (content-hash based caching).
    """
    client = get_chroma_client()
    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=get_embedding_function(),
    )
    if collection.count() > 0:
        logger.debug("Collection %s already populated (%d docs), skipping embed",
                      collection_name, collection.count())
        return

    # ChromaDB has a batch limit; chunk into batches of 500
    batch_size = 500
    for i in range(0, len(chunks), batch_size):
        end = min(i + batch_size, len(chunks))
        collection.add(
            documents=chunks[i:end],
            metadatas=metadatas[i:end],
            ids=ids[i:end],
        )
    logger.info("Embedded %d chunks into collection %s", len(chunks), collection_name)


def query_collection(
    collection_name: str,
    query: str,
    n_results: int = 5,
) -> list[dict[str, Any]]:
    """Query a ChromaDB collection, filtering by similarity threshold.

    Returns list of ``{content, metadata, distance}`` dicts.
    """
    client = get_chroma_client()
    try:
        collection = client.get_collection(
            name=collection_name,
            embedding_function=get_embedding_function(),
        )
    except Exception:
        return []

    if collection.count() == 0:
        return []

    results = collection.query(
        query_texts=[query],
        n_results=min(n_results, collection.count()),
    )

    output: list[dict[str, Any]] = []
    if not results or not results.get("documents"):
        return output

    documents = results["documents"][0]
    metadatas = results["metadatas"][0] if results.get("metadatas") else [{}] * len(documents)
    distances = results["distances"][0] if results.get("distances") else [0.0] * len(documents)

    for doc, meta, dist in zip(documents, metadatas, distances):
        if dist > settings.RAG_SIMILARITY_THRESHOLD:
            continue  # ChromaDB distances: lower = more similar
        output.append({
            "content": doc,
            "metadata": meta,
            "distance": dist,
        })
    return output


# ---------------------------------------------------------------------------
# Sandbox path validation (same pattern as ReadFileTool:30-35)
# ---------------------------------------------------------------------------

def validate_path_in_sandbox(path: str) -> str | None:
    """Check that *path* is inside allowed directories.

    Resolves symlinks and checks proper directory boundaries.
    Returns ``None`` if valid, or an error message string if invalid.
    """
    path = os.path.expanduser(path)
    if not os.path.isabs(path):
        path = os.path.abspath(path)

    if not settings.SANDBOX_ENABLED:
        return None

    real = os.path.realpath(path)
    for allowed in settings.ALLOWED_BASE_DIRS:
        allowed_real = os.path.realpath(allowed)
        if real == allowed_real or real.startswith(allowed_real + os.sep):
            return None

    return (
        f"Access denied: path '{path}' is outside allowed directories "
        f"({settings.ALLOWED_BASE_DIRS})"
    )
