"""Exercise current host-bound tool credentials against cross-project resources and owner-only APIs without borrowing an owner session."""

from pathlib import Path

import httpx

from backend.tests.runtime.test_owned_factory import owned_config

__all__ = ["owned_config"]


async def test_current_attempt_cannot_inherit_owner_or_foreign_resource_authority(owned_config):
    """A live grant from the configured factory reads only its project, rejects scope substitution and becomes unusable on withdrawal."""
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime
    from backend.runtime.peer_registry import AttemptPeers

    c = owned_config
    app = create_app()
    runtime = configured_runtime(app.state.live_grants, app=app)
    run = runtime.store.admit(c.s.c.spec, binding=runtime.workspaces.bind(101, 11))
    lease, peers = AttemptPeers.claim(runtime.store, 101, run.run_id, "isolation-acceptance", lease_seconds=60)
    token = runtime.research.issue_grant(project_id=101, task_id=1001, agent_id=lease.actor_id,
                                        permissions={"sources.read", "sources.capture", "reports.read"}, ttl_seconds=60)
    scope = runtime.research.authorize(token)
    runtime.store.bind_grant(lease, scope.grant_id)
    runtime.live_grants.activate(scope.grant_id)
    own = c.s.c.conn.execute("SELECT file_path FROM reference_files WHERE id=7").fetchone()[0]
    foreign = Path(own).parents[2] / "202" / "uploads" / "fixture.txt"
    foreign.parent.mkdir(parents=True)
    foreign.write_text("SYNTHETIC_OTHER_PROJECT_CANARY")
    c.s.c.conn.execute("INSERT INTO reference_files(id,project_id,file_name,file_path,file_size,file_type) VALUES(8,202,'fixture.txt',?,30,'text/plain')", (str(foreign),))
    c.s.c.conn.execute("INSERT INTO artifacts(id,project_id,task_id,type,file_path,description,content) VALUES(81,101,1001,'report','/not-opened/own.md','Same report','OWN RETAINED REPORT'),(82,202,2002,'report','/not-opened/foreign.md','Same report','SYNTHETIC_OTHER_PROJECT_CANARY')")
    c.s.c.conn.commit()
    root = "/api/research-tools"
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1",
                                     headers={"Authorization": "Bearer " + token}) as client:
            listing = await client.get(root + "/references")
            assert listing.status_code == 200 and [r["id"] for r in listing.json()["references"]] == [7]
            own_report = await client.get(root + "/reports/81")
            assert own_report.status_code == 200 and own_report.json()["content"] == "OWN RETAINED REPORT"
            foreign_report = await client.get(root + "/reports/82")
            assert foreign_report.status_code == 404 and "SYNTHETIC_OTHER_PROJECT_CANARY" not in foreign_report.text
            denied = await client.post(root + "/sources/reference", json={"operation_key": "foreign", "reference_file_id": 8})
            assert denied.status_code == 404 and "SYNTHETIC_OTHER_PROJECT_CANARY" not in denied.text
            assert (await client.get(root + "/references", params={"project_id": 202})).status_code == 422
            assert (await client.post(root + "/sources/reference", json={"operation_key": "forged", "reference_file_id": 7, "project_id": 202})).status_code == 422
            for path in ("/api/projects", "/api/artifacts?project_id=202", "/api/projects/202/retained-work"):
                assert (await client.get(path)).status_code == 401
            assert (await client.post("/api/internal/query", json={"sql_query": "SELECT * FROM tool_grants"})).status_code == 401
            assert c.s.c.conn.execute("SELECT count(*) FROM research_sources").fetchone()[0] == 0
            body = {"operation_key": "own-snapshot", "reference_file_id": 7}
            captured = await client.post(root + "/sources/reference", json=body)
            assert captured.status_code == 200, captured.text
            source = captured.json()["source_id"]
            saved = await client.get(root + f"/sources/{source}")
            assert saved.status_code == 200 and "Fixture base 137 units." in saved.text
            runtime.live_grants.withdraw(scope.grant_id)
            assert (await client.get(root + f"/sources/{source}")).status_code == 401
            assert (await client.post(root + "/sources/reference", json=body)).status_code == 401
            assert c.s.c.conn.execute("SELECT count(*) FROM research_sources WHERE project_id=101").fetchone()[0] == 1
            assert foreign.read_text() == "SYNTHETIC_OTHER_PROJECT_CANARY"
    finally:
        runtime.live_grants.withdraw(scope.grant_id)
        await peers.aclose()
