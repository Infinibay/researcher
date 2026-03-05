"""Tool for searching findings by semantic similarity."""

import sqlite3
from typing import Type

import numpy as np
from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.base.db import execute_with_retry


class SearchFindingsInput(BaseModel):
    query: str = Field(
        ...,
        description=(
            "Text to search for among finding topics. "
            "Matches by semantic similarity, not exact keywords."
        ),
    )
    threshold: float = Field(
        default=0.85,
        ge=0.0,
        le=1.0,
        description="Minimum cosine similarity (0-1). Lower = broader matches.",
    )
    task_id: int | None = Field(
        default=None,
        description=(
            "Filter to a specific task. Omit to use current task context. "
            "Pass 0 to search all project findings."
        ),
    )
    include_content: bool = Field(
        default=False,
        description="Include full finding content (default: topics only for speed).",
    )
    limit: int = Field(default=20, ge=1, le=100, description="Max results")


class SearchFindingsTool(PabadaBaseTool):
    name: str = "search_findings"
    description: str = (
        "Search findings by semantic similarity. Returns findings whose "
        "topic is similar to the query, ranked by similarity score. "
        "Use this to check if a finding already exists before recording "
        "a new one, or to find related findings across tasks."
    )
    args_schema: Type[BaseModel] = SearchFindingsInput

    def _run(
        self,
        query: str,
        threshold: float = 0.85,
        task_id: int | None = None,
        include_content: bool = False,
        limit: int = 20,
    ) -> str:
        project_id = self.project_id

        # Resolve task_id
        if task_id is None:
            effective_task_id = self.task_id
        elif task_id == 0:
            effective_task_id = None
        else:
            effective_task_id = task_id

        # Fetch candidate findings
        def _fetch(conn: sqlite3.Connection) -> list[dict]:
            conditions = ["1=1"]
            params: list = []

            if project_id:
                conditions.append("project_id = ?")
                params.append(project_id)
            if effective_task_id:
                conditions.append("task_id = ?")
                params.append(effective_task_id)

            where = " AND ".join(conditions)

            cols = "id, topic, task_id, confidence, finding_type, status, created_at"
            if include_content:
                cols += ", content, sources_json"

            rows = conn.execute(
                f"SELECT {cols} FROM findings WHERE {where} "
                f"ORDER BY created_at DESC LIMIT 500",
                params,
            ).fetchall()
            return [dict(r) for r in rows]

        try:
            candidates = execute_with_retry(_fetch)
        except Exception as e:
            return self._error(f"Failed to fetch findings: {e}")

        if not candidates:
            return self._success({"matches": [], "count": 0, "total_candidates": 0})

        # Compute semantic similarity
        try:
            from backend.tools.base.dedup import _get_embed_fn, _cosine_similarity

            embed_fn = _get_embed_fn()
            topics = [c["topic"] for c in candidates]
            all_texts = [query] + topics
            embeddings = embed_fn(all_texts)

            query_vec = np.asarray(embeddings[0])
            scored = []
            for i, emb in enumerate(embeddings[1:]):
                sim = _cosine_similarity(query_vec, np.asarray(emb))
                if sim >= threshold:
                    match = dict(candidates[i])
                    match["similarity"] = round(sim, 4)
                    scored.append(match)

            # Sort by similarity descending
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
