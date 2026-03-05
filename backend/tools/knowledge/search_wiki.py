"""Tool for searching wiki pages by semantic similarity."""

import sqlite3
from typing import Type

import numpy as np
from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class SearchWikiInput(BaseModel):
    query: str = Field(
        ...,
        description=(
            "Text to search for among wiki pages. "
            "Matches by semantic similarity, not exact keywords."
        ),
    )
    threshold: float = Field(
        default=0.75,
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
        threshold: float = 0.75,
        include_content: bool = False,
        limit: int = 20,
    ) -> str:
        project_id = self.project_id

        def _fetch(conn: sqlite3.Connection) -> list[dict]:
            cols = "id, path, title, parent_path, updated_at"
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

            embed_fn = _get_embed_fn()
            # Embed title + first 200 chars of content for better matching
            texts = []
            for c in candidates:
                text = c["title"] or c["path"]
                if include_content and c.get("content"):
                    text += " " + c["content"][:200]
                texts.append(text)

            all_texts = [query] + texts
            embeddings = embed_fn(all_texts)

            query_vec = np.asarray(embeddings[0])
            scored = []
            for i, emb in enumerate(embeddings[1:]):
                sim = _cosine_similarity(query_vec, np.asarray(emb))
                if sim >= threshold:
                    match = dict(candidates[i])
                    match["similarity"] = round(sim, 4)
                    # Truncate content in results for readability
                    if not include_content and "content" in match:
                        del match["content"]
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
