"""Tool for searching wiki pages by semantic similarity."""

import sqlite3
from typing import Type

import numpy as np
from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry, parse_query_or_terms


class SearchWikiInput(BaseModel):
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


class SearchWikiTool(PabadaBaseTool):
    name: str = "search_wiki"
    description: str = (
        "Search wiki pages by semantic similarity. Returns pages whose "
        "title or content is similar to the query, ranked by similarity score. "
        "Use this to find relevant wiki pages when you don't know exact keywords."
    )
    args_schema: Type[BaseModel] = SearchWikiInput

    def _run(
        self,
        query: str,
        threshold: float = 0.65,
        include_content: bool = False,
        limit: int = 20,
    ) -> str:
        project_id = self.project_id

        def _fetch(conn: sqlite3.Connection) -> list[dict]:
            cols = "id, path, title, parent_path, updated_at, embedding"
            if include_content:
                cols += ", content"

            rows = conn.execute(
                f"SELECT {cols} FROM wiki_pages "
                f"WHERE project_id = ? OR project_id IS NULL "
                f"ORDER BY updated_at DESC LIMIT 500",
                (project_id,),
            ).fetchall()
            return [dict(r) for r in rows]

        try:
            candidates = execute_with_retry(_fetch)
        except Exception as e:
            return self._error(f"Failed to fetch wiki pages: {e}")

        if not candidates:
            return self._success({"matches": [], "count": 0, "total_candidates": 0})

        try:
            from backend.tools.base.dedup import _get_embed_fn, _cosine_similarity
            from backend.tools.base.embeddings import embedding_from_blob

            embed_fn = _get_embed_fn()

            # Parse OR-terms: embed each sub-query, use max similarity
            or_terms = parse_query_or_terms(query)
            query_vecs = [np.asarray(v) for v in embed_fn(or_terms)]

            with_emb = [(i, c) for i, c in enumerate(candidates) if c.get("embedding")]
            without_emb = [(i, c) for i, c in enumerate(candidates) if not c.get("embedding")]

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
                    scores[i] = max(_cosine_similarity(qv, emb_vec) for qv in query_vecs)

            scored = []
            for i, c in enumerate(candidates):
                if scores[i] >= threshold:
                    match = dict(c)
                    match.pop("embedding", None)  # don't return raw blob
                    match["similarity"] = round(scores[i], 4)
                    if not include_content:
                        match.pop("content", None)
                    scored.append(match)

            scored.sort(key=lambda x: x["similarity"], reverse=True)
            scored = scored[:limit]

        except Exception as e:
            return self._error(f"Similarity search failed: {e}")

        return self._success({
            "matches": scored,
            "count": len(scored),
            "total_candidates": len(candidates),
            "threshold": threshold,
        })
