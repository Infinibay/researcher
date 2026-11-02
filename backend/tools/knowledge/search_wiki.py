"""Tool for searching wiki pages by semantic similarity."""

import sqlite3
from typing import Literal

import numpy as np
from pydantic import BaseModel, ConfigDict, Field

from backend.knowledge.wiki import namespace_filter
from backend.tools.base.base_tool import InfinibayBaseTool
from backend.tools.base.db import execute_with_retry, parse_query_or_terms


class SearchWikiInput(BaseModel):
    """Legacy semantic query, explicitly scoped and paged; scores are not scientific confidence."""

    model_config = ConfigDict(extra="forbid")

    namespace: Literal["project", "global"] = "project"
    after_id: int = Field(default=0, ge=0)
    query: str = Field(
        ...,
        description=(
            "Text to search for among wiki pages. "
            "Matches by semantic similarity, not exact keywords. "
            "Supports | for OR: 'architecture | design' matches pages similar to either term."
        ),
    )
    threshold: float = Field(
        default=0.65,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity (0-1). Lower = broader matches.",
    )
    include_content: bool = Field(
        default=False,
        description="Include full page content (default: titles/snippets only for speed).",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results")


class SearchWikiTool(InfinibayBaseTool):
    """Retain legacy embedding compatibility until role cutover; native wiki uses captured local retrieval."""

    name: str = "search_wiki"
    description: str = (
        "Search wiki pages by semantic similarity. Returns pages whose "
        "title or content is similar to the query, ranked by similarity score. "
        "Choose project/global namespace explicitly and follow next_after_id. Legacy configured embeddings remain; prefer native captured wiki collection/source_query in the owned runtime."
    )
    args_schema: type[BaseModel] = SearchWikiInput

    def _run(
        self,
        query: str,
        threshold: float = 0.65,
        include_content: bool = False,
        limit: int = 20,
        namespace: str = "project",
        after_id: int = 0,
    ) -> str:
        """Rank one explicit namespace/candidate page using the configured legacy embedding provider."""
        project_id = self.project_id
        where, parameters = namespace_filter(project_id, namespace)

        def _fetch(conn: sqlite3.Connection) -> list[dict]:
            """Read one stable candidate page from the selected project/global namespace."""
            cols = "id, project_id, revision, path, title, parent_path, updated_at, embedding, content"

            rows = conn.execute(
                f"SELECT {cols} FROM wiki_pages "
                f"WHERE {where} AND id > ? "
                f"ORDER BY id LIMIT 501",
                (*parameters, after_id),
            ).fetchall()
            return [dict(r) for r in rows]

        try:
            fetched = execute_with_retry(_fetch)
            candidates = fetched[:500]
            next_after_id = candidates[-1]["id"] if len(fetched) > 500 else None
        except sqlite3.Error:
            return self._error("Wiki storage could not read this scoped candidate page")

        if not candidates:
            return self._success(
                {
                    "matches": [],
                    "count": 0,
                    "total_candidates": 0,
                    "namespace": namespace,
                    "next_after_id": None,
                }
            )

        try:
            from backend.tools.base.dedup import _cosine_similarity, _get_embed_fn
            from backend.tools.base.embeddings import embedding_from_blob

            embed_fn = _get_embed_fn()

            # Parse OR-terms: embed each sub-query, use max similarity
            or_terms = parse_query_or_terms(query)
            query_vecs = [np.asarray(v) for v in embed_fn(or_terms)]

            with_emb = [(i, c) for i, c in enumerate(candidates) if c.get("embedding")]
            without_emb = [
                (i, c) for i, c in enumerate(candidates) if not c.get("embedding")
            ]

            scores = [0.0] * len(candidates)

            # Use stored embeddings (fast path)
            for i, c in with_emb:
                emb_vec = embedding_from_blob(c["embedding"])
                scores[i] = max(_cosine_similarity(qv, emb_vec) for qv in query_vecs)

            # Fallback: embed title + content prefix for candidates without stored embeddings
            if without_emb:
                texts = []
                for _, c in without_emb:
                    text = c["title"] or c["path"]
                    if c.get("content"):
                        text += " " + c["content"][:500]
                    texts.append(text)

                embeddings = embed_fn(texts)
                for j, (i, _) in enumerate(without_emb):
                    emb_vec = np.asarray(embeddings[j])
                    scores[i] = max(
                        _cosine_similarity(qv, emb_vec) for qv in query_vecs
                    )

            scored = []
            for i, c in enumerate(candidates):
                if scores[i] >= threshold:
                    match = dict(c)
                    match["namespace"] = namespace
                    match.pop("embedding", None)  # don't return raw blob
                    match["similarity"] = round(scores[i], 4)
                    if not include_content:
                        match.pop("content", None)
                    scored.append(match)

            scored.sort(key=lambda x: x["similarity"], reverse=True)
            scored = scored[:limit]

        except Exception:  # noqa: BLE001 — legacy provider boundary; never expose credential-bearing errors
            return self._error(
                "Legacy semantic provider unavailable; use the native captured wiki collection/local source query when configured"
            )

        return self._success(
            {
                "matches": scored,
                "count": len(scored),
                "total_candidates": len(candidates),
                "threshold": threshold,
                "namespace": namespace,
                "next_after_id": next_after_id,
                "coverage_note": "Legacy vectors or title/first500characters only within this candidate page; not full source review. Native wiki collections use complete bounded local source retrieval.",
            }
        )
