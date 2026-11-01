"""Structured-source paging preserves recoverability without flooding ordinary text reads."""

import json

from backend.tests.research.test_acquisition import reference
from backend.tests.research.test_http import (
    credentials,
)
from backend.tests.research.test_http import (
    research_client as client_fixture,
)

research_client = client_fixture


def test_structure_pages_recover_all_units_and_exact_saved_ranges(
    research_client, research_store, db_conn, tmp_path
):
    """Use real scoped HTTP to recover a late JSON value and deny a foreign reader."""
    data = json.dumps({f"item-{i}": f"value-{i}" for i in range(160)}).encode()
    _, _, ref = reference(research_store, db_conn, tmp_path, content=data)
    db_conn.execute(
        "UPDATE reference_files SET file_type='application/json' WHERE id=?", (ref.id,)
    )
    db_conn.commit()
    headers = credentials(research_store)
    captured = research_client.post(
        "/api/research-tools/sources/reference",
        headers=headers,
        json={"operation_key": "structured", "reference_file_id": ref.id},
    )
    assert captured.status_code == 200, captured.text
    path = f"/api/research-tools/sources/{captured.json()['source_id']}"
    snapshot = research_client.get(path, headers=headers).json()
    assert "units" not in snapshot["provenance"]
    assert snapshot["provenance"]["unit_count"] == 160
    all_units, after = [], 0
    while after is not None:
        response = research_client.get(
            path + "/units", headers=headers, params={"after_index": after, "limit": 37}
        )
        assert response.status_code == 200, response.text
        page = response.json()
        assert len(response.content) <= 14000
        assert (
            page["source_id"] == snapshot["source_id"]
            and page["sha256"] == snapshot["sha256"]
        )
        assert page["total_units"] == 160 and len(page["units"]) <= 37
        all_units.extend(page["units"])
        after = page["next_index"]
    assert [u["index"] for u in all_units] == list(range(160))
    assert all_units[-1]["locator"] == "/item-159"
    last = all_units[-1]
    text = research_client.get(
        path,
        headers=headers,
        params={
            "offset": last["start_offset"],
            "max_chars": last["end_offset"] - last["start_offset"],
        },
    ).json()
    assert text["content"] == '"value-159"'
    match = research_client.get(
        path + "/search", headers=headers, params={"needle": "value-159"}
    ).json()
    assert 159 in match["matches"][0]["unit_indices"]
    assert (
        research_client.get(
            path + "/units", headers=credentials(research_store, 202, 2002)
        ).status_code
        == 404
    )
    assert (
        research_client.get(
            path + "/units", headers=headers, params={"limit": 101}
        ).status_code
        == 422
    )
    assert (
        research_client.get(
            path + "/units", headers=headers, params={"after_index": -1}
        ).status_code
        == 422
    )


def test_structure_page_has_a_byte_budget_even_for_long_locators():
    """Continuation addresses the first omitted unit when metadata reaches the wire budget."""
    from backend.research.provenance import structure_page

    units = [
        {
            "index": i,
            "kind": "value",
            "locator": "/" + str(i) + "x" * 1000,
            "start_offset": i * 10,
            "end_offset": i * 10 + 1,
        }
        for i in range(100)
    ]
    page = structure_page({"units": units}, after_index=0, limit=100)
    assert 0 < len(page["units"]) < 100
    assert page["next_index"] == len(page["units"])
    assert len(json.dumps(page, ensure_ascii=False).encode()) <= 12500


def test_nonstructured_source_returns_an_explicit_empty_structure_page():
    """A text/PDF snapshot without unit metadata must remain readable with no guessed structure."""
    from backend.research.provenance import structure_page

    assert structure_page({"extraction": "utf8-v1"}, after_index=0, limit=50) == {
        "units": [],
        "total_units": 0,
        "after_index": 0,
        "next_index": None,
    }
