"""Independent semantic reader instances share the same process capacity after legacy adapters are retired."""

import pytest


def test_native_and_retained_semantic_instances_share_one_process_slot(tmp_path):
    """Constructing another adapter must not bypass the existing local-worker capacity limit."""
    import hashlib

    from backend.research.retrieval_assets import RetrievalBusy
    from backend.research.semantic import SemanticRetriever

    native = SemanticRetriever(tmp_path)
    retained = SemanticRetriever(tmp_path)
    assert native._capacity.acquire(blocking=False)
    try:
        text = "The sample contains 137 units."
        source = {
            "id": 1,
            "content": text,
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
        }
        with pytest.raises(RetrievalBusy):
            retained.query(source, "sample count")
    finally:
        native._capacity.release()
