"""Tool for semantic search within CSV files."""

import csv
import logging
import os
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.rag.base import (
    embed_and_store,
    file_content_hash,
    query_collection,
    validate_path_in_sandbox,
)

logger = logging.getLogger(__name__)

# Number of data rows per chunk (headers are prepended to each chunk)
_ROWS_PER_CHUNK = 20


class CSVSearchInput(BaseModel):
    query: str = Field(..., description="Semantic search query")
    csv_path: str = Field(..., description="Absolute path to the CSV file")
    n_results: int = Field(
        default=5, ge=1, le=20, description="Number of results to return"
    )


class CSVSearchTool(PabadaBaseTool):
    name: str = "csv_search"
    description: str = (
        "Search within a CSV file using semantic similarity. "
        "Groups rows into chunks with column headers preserved, embeds them, "
        "then returns the most relevant row groups for your query. "
        "Use this to find specific data in large CSV files."
    )
    args_schema: Type[BaseModel] = CSVSearchInput

    def _run(
        self,
        query: str,
        csv_path: str,
        n_results: int = 5,
    ) -> str:
        csv_path = os.path.expanduser(csv_path)
        if not os.path.isabs(csv_path):
            csv_path = os.path.abspath(csv_path)

        error = validate_path_in_sandbox(csv_path)
        if error:
            return self._error(error)

        if not os.path.exists(csv_path):
            return self._error(f"File not found: {csv_path}")

        # Build collection name from content hash
        try:
            fhash = file_content_hash(csv_path)
        except Exception as e:
            return self._error(f"Failed to hash file: {e}")

        collection_name = f"csv-{fhash}"

        # Index if not already done
        try:
            self._ensure_indexed(collection_name, csv_path)
        except Exception as e:
            return self._error(f"CSV indexing failed: {e}")

        # Query
        results = query_collection(collection_name, query, n_results)

        self._log_tool_usage(
            f"CSV search in {os.path.basename(csv_path)}: "
            f"'{query[:50]}' → {len(results)} results"
        )

        return self._success({
            "query": query,
            "csv_path": csv_path,
            "results": results,
            "result_count": len(results),
        })

    @staticmethod
    def _ensure_indexed(collection_name: str, csv_path: str) -> None:
        """Read CSV, group rows into chunks with headers, and embed."""
        from backend.tools.rag.base import get_chroma_client, get_embedding_function

        client = get_chroma_client()
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=get_embedding_function(),
        )
        if collection.count() > 0:
            return  # Already indexed

        with open(csv_path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            try:
                headers = next(reader)
            except StopIteration:
                raise RuntimeError("CSV file is empty")

            header_line = ",".join(headers)

            chunks: list[str] = []
            metadatas: list[dict] = []
            ids: list[str] = []

            batch_rows: list[list[str]] = []
            row_start = 1  # 1-indexed (row after header)
            row_num = 0

            for row in reader:
                row_num += 1
                batch_rows.append(row)

                if len(batch_rows) >= _ROWS_PER_CHUNK:
                    chunk_text = _format_chunk(header_line, headers, batch_rows)
                    row_end = row_start + len(batch_rows) - 1
                    chunks.append(chunk_text)
                    metadatas.append({
                        "source": os.path.basename(csv_path),
                        "row_range": f"{row_start}-{row_end}",
                    })
                    ids.append(f"rows-{row_start}-{row_end}")
                    row_start = row_end + 1
                    batch_rows = []

            # Remaining rows
            if batch_rows:
                chunk_text = _format_chunk(header_line, headers, batch_rows)
                row_end = row_start + len(batch_rows) - 1
                chunks.append(chunk_text)
                metadatas.append({
                    "source": os.path.basename(csv_path),
                    "row_range": f"{row_start}-{row_end}",
                })
                ids.append(f"rows-{row_start}-{row_end}")

        if not chunks:
            raise RuntimeError("No data rows found in CSV")

        embed_and_store(collection_name, chunks, metadatas, ids)


def _format_chunk(
    header_line: str,
    headers: list[str],
    rows: list[list[str]],
) -> str:
    """Format a group of rows as text with column headers for embedding."""
    lines = [f"Columns: {header_line}"]
    for row in rows:
        # Pair headers with values for readability
        pairs = []
        for h, v in zip(headers, row):
            pairs.append(f"{h}: {v}")
        # Handle rows with more values than headers
        for extra in row[len(headers):]:
            pairs.append(extra)
        lines.append(" | ".join(pairs))
    return "\n".join(lines)
