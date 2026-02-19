"""Tool for semantic search within PDF documents."""

import logging
import os
from typing import Type

from pydantic import BaseModel, Field

from backend.tools.base.base_tool import PabadaBaseTool
from backend.tools.rag.base import (
    _chunk_text,
    embed_and_store,
    file_content_hash,
    query_collection,
    validate_path_in_sandbox,
)

logger = logging.getLogger(__name__)


class PDFSearchInput(BaseModel):
    query: str = Field(..., description="Semantic search query")
    pdf_path: str = Field(..., description="Absolute path to the PDF file")
    n_results: int = Field(
        default=5, ge=1, le=20, description="Number of results to return"
    )


class PDFSearchTool(PabadaBaseTool):
    name: str = "pdf_search"
    description: str = (
        "Search within a PDF document using semantic similarity. "
        "Extracts text from the PDF, chunks and embeds it, then returns "
        "the most relevant passages for your query. Use this to find "
        "specific information in large PDFs without reading the entire document."
    )
    args_schema: Type[BaseModel] = PDFSearchInput

    def _run(
        self,
        query: str,
        pdf_path: str,
        n_results: int = 5,
    ) -> str:
        # Validate path
        pdf_path = os.path.expanduser(pdf_path)
        if not os.path.isabs(pdf_path):
            pdf_path = os.path.abspath(pdf_path)

        error = validate_path_in_sandbox(pdf_path)
        if error:
            return self._error(error)

        if not os.path.exists(pdf_path):
            return self._error(f"File not found: {pdf_path}")
        if not pdf_path.lower().endswith(".pdf"):
            return self._error(f"Not a PDF file: {pdf_path}")

        # Build collection name from content hash
        try:
            fhash = file_content_hash(pdf_path)
        except Exception as e:
            return self._error(f"Failed to hash file: {e}")

        collection_name = f"pdf-{fhash}"

        # Extract, chunk, and embed if not already done
        try:
            self._ensure_indexed(collection_name, pdf_path)
        except Exception as e:
            return self._error(f"PDF indexing failed: {e}")

        # Query
        results = query_collection(collection_name, query, n_results)

        self._log_tool_usage(
            f"PDF search in {os.path.basename(pdf_path)}: "
            f"'{query[:50]}' → {len(results)} results"
        )

        return self._success({
            "query": query,
            "pdf_path": pdf_path,
            "results": results,
            "result_count": len(results),
        })

    @staticmethod
    def _ensure_indexed(collection_name: str, pdf_path: str) -> None:
        """Extract text from PDF, chunk, and embed into ChromaDB."""
        from backend.tools.rag.base import get_chroma_client, get_embedding_function

        client = get_chroma_client()
        collection = client.get_or_create_collection(
            name=collection_name,
            embedding_function=get_embedding_function(),
        )
        if collection.count() > 0:
            return  # Already indexed

        try:
            from pypdf import PdfReader
        except ImportError:
            raise RuntimeError("pypdf is not installed. Run: pip install pypdf")

        reader = PdfReader(pdf_path)

        chunks: list[str] = []
        metadatas: list[dict] = []
        ids: list[str] = []

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text or not text.strip():
                continue

            page_chunks = _chunk_text(text)
            for chunk_idx, chunk in enumerate(page_chunks):
                chunks.append(chunk)
                metadatas.append({
                    "source": os.path.basename(pdf_path),
                    "page": page_num,
                    "chunk_index": chunk_idx,
                })
                ids.append(f"p{page_num}-c{chunk_idx}")

        if not chunks:
            raise RuntimeError("No text could be extracted from the PDF")

        embed_and_store(collection_name, chunks, metadatas, ids)
