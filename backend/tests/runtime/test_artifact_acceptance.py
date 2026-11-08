"""Owner artifact readers expose original result decisions without promoting draft bytes or current validity."""

import hashlib

from backend.tests.runtime.test_result_acceptance import make_accepted_result


async def test_accepted_report_filter_reads_original_receipt_without_rewriting_draft(coordination):
    """A documentary acceptance must be discoverable separately from its immutable draft status."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c, lease = make_accepted_result(coordination)
    report = c.conn.execute("SELECT id,content FROM artifacts").fetchone()
    original_hash = hashlib.sha256(report["content"].encode()).hexdigest()
    app = create_app(access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"))
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        response = await owner.get("/api/artifacts?project_id=101&research_status=accepted")
        assert response.status_code == 200
        assert [row["id"] for row in response.json()] == [report["id"]]
        row = response.json()[0]
        assert row["research_status"] == "draft"
        assert row["owner_acceptance"]["run_id"] == lease.run_id
        assert row["owner_acceptance"]["context_version"] == lease.context_version
        assert row["owner_acceptance"]["report_sha256"] == original_hash
        assert row["owner_acceptance"]["validity"] == "not_rechecked"
        assert row["owner_acceptance"]["matches_current_content"] is None
        assert (await owner.get("/api/artifacts?project_id=101&research_status=draft")).json() == []
        assert (await owner.get("/api/artifacts?project_id=202&research_status=accepted")).json() == []
        assert (await owner.get(f"/api/artifacts/{report['id']}?project_id=202")).status_code == 404
        detail = (await owner.get(f"/api/artifacts/{report['id']}?project_id=101")).json()
        assert detail["owner_acceptance"]["matches_current_content"] is True
    assert c.conn.execute("SELECT status FROM research_reports").fetchone()[0] == "draft"
    assert c.conn.execute("SELECT content FROM artifacts").fetchone()[0] == report["content"]


async def test_historical_acceptance_does_not_certify_changed_content_or_context(coordination):
    """Keep original decision/hash after later changes, with explicit unmatched bytes and unassessed validity."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c, lease = make_accepted_result(coordination)
    report = c.conn.execute("SELECT id FROM artifacts").fetchone()[0]
    c.conn.execute("UPDATE artifacts SET content='Later changed body' WHERE id=?", (report,))
    c.conn.execute("UPDATE tasks SET description='Later changed requirement' WHERE id=1001")
    c.conn.commit()
    app = create_app(access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"))
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        detail = (await owner.get(f"/api/artifacts/{report}?project_id=101")).json()
        assert detail["content"] == "Later changed body"
        acceptance = detail["owner_acceptance"]
        assert acceptance["run_id"] == lease.run_id
        assert acceptance["context_version"] == lease.context_version
        assert acceptance["matches_current_content"] is False
        assert acceptance["validity"] == "not_rechecked"
        assert acceptance["report_sha256"] != hashlib.sha256(detail["content"].encode()).hexdigest()


async def test_legacy_accepted_label_does_not_fabricate_an_owner_receipt(coordination):
    """An inherited accepted report flag is retained as metadata, never reconstructed as an exact decision."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c = coordination
    report = c.conn.execute("INSERT INTO artifacts(project_id,task_id,type,file_path,content) VALUES(101,1001,'report','legacy.md','Legacy')").lastrowid
    c.conn.execute("INSERT INTO research_reports(artifact_id,title,report_type,status,content_sha256) VALUES(?,'Legacy','research','accepted',?)", (report, hashlib.sha256(b"Legacy").hexdigest()))
    c.conn.commit()
    app = create_app(access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"))
    async with app.router.lifespan_context(app), owner_client(app) as owner:
        row = (await owner.get("/api/artifacts?project_id=101&research_status=accepted")).json()[0]
        assert row["id"] == report and row["research_status"] == "accepted"
        assert row["owner_acceptance"] is None
