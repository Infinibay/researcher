"""Historical Git labels must never select another project's repository or mutate its branch metadata."""

import pytest
import sqlite3


@pytest.fixture
def named_repositories(db_conn, _isolated_db):
    """Seed two independent repositories with deliberately identical human-readable names."""
    from backend.tools.base.db import ensure_migrations
    ensure_migrations(_isolated_db)
    db_conn.execute('PRAGMA foreign_keys=ON')
    db_conn.execute("INSERT INTO projects(id,name) VALUES(1,'One'),(2,'Two')")
    db_conn.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,1,'app','/unavailable/one'),(22,2,'app','/unavailable/two')")
    db_conn.commit()
    return db_conn


def test_closing_pr_does_not_abandon_same_named_branch_in_another_project(named_repositories):
    """A PR without a matching branch in its own repository cannot adopt another project's same-named history."""
    from backend.git.pr_service import PRService
    db = named_repositories
    db.execute("INSERT INTO branches(id,project_id,repo_name,branch_name,created_by) VALUES(41,2,'app','task/1','history')")
    db.execute("INSERT INTO code_reviews(id,project_id,repo_name,branch,agent_run_id) VALUES(31,1,'app','task/1','historical')")
    db.commit()
    assert PRService().close_pr(31)
    assert db.execute('SELECT status FROM branches WHERE id=41').fetchone()[0] == 'active'


def test_identical_branch_names_coexist_and_http_closure_is_scoped_atomic_and_idempotent(named_repositories, client):
    """Two projects may retain app/task/1; owner closure changes exactly one branch and publishes one transactional event."""
    db = named_repositories
    db.execute("INSERT INTO branches(id,project_id,repo_name,branch_name,created_by) VALUES(41,1,'app','task/1','history'),(42,2,'app','task/1','history')")
    db.execute("INSERT INTO code_reviews(id,project_id,repo_name,branch,agent_run_id) VALUES(31,1,'app','task/1','historical')")
    db.commit()
    assert [tuple(r) for r in db.execute('SELECT id,repo_id FROM branches ORDER BY id')] == [(41,11),(42,22)]
    response = client.post('/api/git/prs/31/close')
    assert response.status_code == 200, response.text
    assert response.json()['repo_id'] == 11
    assert client.post('/api/git/prs/31/close').json() == response.json()
    assert [tuple(r) for r in db.execute('SELECT id,status FROM branches ORDER BY id')] == [(41,'abandoned'),(42,'active')]
    assert db.execute("SELECT count(*) FROM events_log WHERE event_type='pr_closed' AND entity_id=31").fetchone()[0] == 1
    assert [r['id'] for r in client.get('/api/git/branches?project_id=2').json()] == [42]


def test_close_failure_rolls_back_pr_branch_and_event(named_repositories):
    """A failed durable event cannot leave a closed review or abandoned branch behind."""
    from backend.git.pr_service import PRService
    db = named_repositories
    db.execute("INSERT INTO branches(id,project_id,repo_name,branch_name,created_by) VALUES(41,1,'app','task/1','history')")
    db.execute("INSERT INTO code_reviews(id,project_id,repo_name,branch,agent_run_id) VALUES(31,1,'app','task/1','historical')")
    db.execute("CREATE TRIGGER reject_close BEFORE INSERT ON events_log WHEN NEW.event_type='pr_closed' BEGIN SELECT RAISE(ABORT,'close event rejected'); END")
    db.commit()
    with pytest.raises(sqlite3.IntegrityError,match='close event rejected'): PRService().close_pr(31)
    assert db.execute('SELECT status FROM branches WHERE id=41').fetchone()[0] == 'active'
    assert db.execute('SELECT status FROM code_reviews WHERE id=31').fetchone()[0] == 'pending'


def test_repository_rename_and_name_reuse_do_not_rebind_original_history(named_repositories):
    """A later repository named app cannot receive closure, navigation or prior-code selection intended for the original ID."""
    from backend.git.pr_service import PRService
    from backend.runtime.branch_inputs import BranchInputs
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.tools.base.db import get_db_path
    db = named_repositories
    db.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(51,1,'code','Current task')")
    db.execute("INSERT INTO branches(id,project_id,repo_name,branch_name,created_by) VALUES(41,1,'app','task/1','history')")
    db.execute("INSERT INTO code_reviews(id,project_id,repo_name,branch,agent_run_id) VALUES(31,1,'app','task/1','historical')")
    db.execute("UPDATE repositories SET name='renamed' WHERE id=11")
    db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(33,1,'app','/unavailable/replacement')")
    db.execute("INSERT INTO branches(id,project_id,repo_name,branch_name,created_by) VALUES(43,1,'app','task/1','new history')")
    db.commit()
    entry = PRService().owner_entry(31)
    assert entry['repository_id'] == 11 and entry['branch_id'] == 41
    listed = BranchInputs(SQLiteRunStore(get_db_path())).sources(1,51)
    assert {r['branch_id']:r['repository_id'] for r in listed} == {41:11,43:33}
    assert PRService().close_pr(31)
    assert db.execute('SELECT status FROM branches WHERE id=43').fetchone()[0] == 'active'


@pytest.mark.parametrize('endpoint', ['branches', 'tree', 'contents'])
def test_repository_reads_keep_original_id_across_rename_and_name_reuse(named_repositories, client, tmp_path, endpoint):
    """Actual Git reads use the selected ID even after its name is reused, and never fall back after a foreign or missing ID."""
    from backend.tests.runtime.test_installation_backup import git
    db = named_repositories
    for repository_id, label in [(11, 'original'), (33, 'replacement')]:
        source = tmp_path/label; source.mkdir()
        git(source, 'init', '-b', 'main')
        (source/f'{label}.txt').write_text(f'{label} bytes\n')
        git(source, 'add', '.'); git(source, 'commit', '-m', label)
        if repository_id == 11:
            db.execute("UPDATE repositories SET name='renamed',local_path=? WHERE id=11", (str(source),))
        else:
            db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(33,1,'app',?)", (str(source),))
    db.commit()
    path = f'/api/git/repos/app/{endpoint}'
    params = {'project_id': 1, 'repository_id': 11, 'ref': 'main', 'path': 'original.txt'}
    response = client.get(path, params=params)
    assert response.status_code == 200, response.text
    value = response.json()
    if endpoint == 'branches':
        assert value[0]['last_commit_message'] == 'original'
    elif endpoint == 'tree':
        assert [entry['path'] for entry in value] == ['original.txt']
    else:
        assert value['content'] == 'original bytes\n'
    for missing_or_foreign in [22, 999]:
        assert client.get(path, params={**params, 'repository_id': missing_or_foreign}).status_code == 404


def test_pr_remote_uses_bound_repository_snapshot_after_name_reuse(named_repositories, monkeypatch):
    """Historical remote comments remain bound to the original repository rather than a replacement sharing its old display name."""
    from backend.api.routes import git
    from backend.git.pr_service import PRService
    db = named_repositories
    db.execute("UPDATE repositories SET remote_url='https://forgejo.test/original/app.git' WHERE id=11")
    db.execute("INSERT INTO code_reviews(id,project_id,repo_name,branch,agent_run_id,forgejo_pr_index) VALUES(31,1,'app','task/1','historical',7)")
    db.execute("UPDATE repositories SET name='renamed' WHERE id=11")
    db.execute("INSERT INTO repositories(id,project_id,name,local_path,remote_url) VALUES(33,1,'app','/unavailable/new','https://forgejo.test/replacement/app.git')")
    db.commit()
    monkeypatch.setattr(git.settings, 'FORGEJO_API_URL', 'https://forgejo.test/api/v1')
    assert git._require_pr_remote(PRService().get_pr(31)) == 'original/app'


def test_unresolved_history_never_adopts_a_repository_registered_later(named_repositories, monkeypatch):
    """Absence of an original repository ID remains explicit, including before any legacy remote request."""
    from backend.git.pr_service import PRService
    from backend.api.routes import git
    from fastapi import HTTPException
    db = named_repositories
    db.execute("INSERT INTO branches(id,project_id,repo_name,branch_name,created_by) VALUES(41,1,'missing','task/1','history')")
    db.execute("INSERT INTO code_reviews(id,project_id,repo_name,branch,agent_run_id,forgejo_pr_index) VALUES(31,1,'missing','task/1','historical',7)")
    db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(33,1,'missing','/unavailable/new')")
    db.commit()
    entry = PRService().owner_entry(31)
    assert entry['repository_id'] is None and entry['branch_id'] is None
    def unexpected(*args):
        """Fail if a missing historical association reaches remote resolution by display name."""
        raise AssertionError('Must not resolve the replacement repository')
    monkeypatch.setattr(git,'_forgejo_owner',unexpected)
    with pytest.raises(HTTPException) as error: git._require_pr_remote(PRService().get_pr(31))
    assert error.value.status_code == 409
    assert PRService().close_pr(31)
    assert db.execute('SELECT status FROM branches WHERE id=41').fetchone()[0] == 'active'


def test_branch_annotations_require_project_and_repository_identity(named_repositories):
    """Old unscoped calls cannot silently mutate every namesake; explicit matching identities affect one row."""
    from backend.git.branch_service import BranchService
    db = named_repositories
    db.execute("INSERT INTO branches(id,project_id,repo_name,branch_name,created_by) VALUES(41,1,'app','task/1','history'),(42,2,'app','task/1','history')")
    db.commit()
    service = BranchService()
    with pytest.raises(TypeError): service.mark_branch_merged('task/1','app')
    with pytest.raises(TypeError): service.mark_branch_stale('task/1','app')
    assert not service.mark_branch_merged('task/1','app',project_id=1,repository_id=22)
    assert service.mark_branch_merged('task/1','app',project_id=1,repository_id=11)
    assert db.execute('SELECT status FROM branches WHERE id=42').fetchone()[0] == 'active'


def test_git_identity_migration_preserves_rows_unresolved_history_and_id_high_watermark(tmp_path):
    """Migration67 keeps original rows and deleted-ID history while resolving only existing scoped registrations."""
    from backend.tools.base.db import ensure_migrations
    from backend.db.git_identity_migration import restore_git_identity_schema
    database = tmp_path/'historical.db'
    ensure_migrations(database,target_version=66)
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO projects(id,name) VALUES(1,'One')")
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,1,'app','/original')")
        db.execute("INSERT INTO branches(id,project_id,repo_name,branch_name,created_by) VALUES(41,1,'app','task/1','original'),(42,1,'missing','task/2','original'),(99,1,'app','deleted','original')")
        db.execute('DELETE FROM branches WHERE id=99')
        db.execute("INSERT INTO code_reviews(id,project_id,repo_name,branch,agent_run_id) VALUES(31,1,'app','task/1','historical')")
        before = db.execute('SELECT * FROM branches ORDER BY id').fetchall()
    ensure_migrations(database,target_version=67)
    with sqlite3.connect(database) as db:
        assert [row[:-1] for row in db.execute('SELECT * FROM branches ORDER BY id')] == before
        assert db.execute('SELECT repo_id FROM branches ORDER BY id').fetchall() == [(11,),(None,)]
        assert db.execute('SELECT repo_id FROM code_reviews').fetchone() == (11,)
        assert db.execute("INSERT INTO branches(project_id,repo_name,branch_name,created_by) VALUES(1,'app','new','new')").lastrowid == 100
        db.commit()
        with pytest.raises(RuntimeError,match='history'): restore_git_identity_schema(db)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []


def test_unused_git_identity_inverse_restores_exact_supported_prefix(tmp_path):
    """An unused schema67 can return to66 without dropping unrelated project data or bypassing later-schema guards."""
    from backend.tools.base.db import ensure_migrations
    from backend.db.git_identity_migration import restore_git_identity_schema
    database = tmp_path/'unused.db'
    ensure_migrations(database,target_version=67)
    with sqlite3.connect(database) as db:
        db.execute("INSERT INTO projects(id,name) VALUES(1,'Retained')");db.commit()
        restore_git_identity_schema(db)
        assert db.execute('SELECT max(version) FROM schema_migrations').fetchone() == (66,)
        assert 'repo_id' not in {row[1] for row in db.execute('PRAGMA table_info(code_reviews)')}
        assert db.execute('SELECT name FROM projects WHERE id=1').fetchone() == ('Retained',)
    ensure_migrations(database,target_version=67)
