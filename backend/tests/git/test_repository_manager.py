"""Historical source registration remains readable and archivable; current setup effects belong to original owner source operations."""

import pytest

from backend.git.repository_manager import RepositoryManager
from backend.runtime.contracts import RunConflict


@pytest.fixture
def manager():
    """Construct the historical record reader without Git, remote configuration or process side effects."""
    return RepositoryManager()


def test_historical_sources_remain_project_scoped_and_active_only(seeded_project, manager, db_conn):
    """Restored metadata can be browsed without recreating its repositories, remotes or old initialization effects."""
    db_conn.execute("INSERT INTO projects(id,name)VALUES(2,'Other project')")
    db_conn.executemany("INSERT INTO repositories(project_id,name,local_path,status)VALUES(?,?,?,?)", [(1,'active','/history/active','active'),(1,'archived','/history/archived','archived'),(2,'foreign','/history/foreign','active')])
    db_conn.commit()
    assert [row['name'] for row in manager.list_repos(1)] == ['active']
    assert manager.get_repo(1,'archived')['local_path'] == '/history/archived'
    assert manager.get_repo(1,'foreign') is None


def test_archive_changes_registration_only_and_preserves_files(seeded_project, manager, db_conn, tmp_path):
    """Archiving historical metadata never cleans the source folder or deletes retained work."""
    source=tmp_path/'retained';source.mkdir();(source/'fact.txt').write_text('137')
    db_conn.execute("INSERT INTO repositories(project_id,name,local_path)VALUES(1,'retained',?)",(str(source),));db_conn.commit()
    assert manager.archive_repo(1,'retained')
    assert manager.get_repo(1,'retained')['status'] == 'archived'
    assert (source/'fact.txt').read_text() == '137'
    assert manager.list_repos(1) == []
    assert manager.archive_repo(1,'missing') is False


def test_legacy_initialization_and_clone_cannot_create_a_registration(seeded_project, manager, db_conn, tmp_path):
    """Old callers must adopt explicit administrative ownership instead of receiving an automatic remote or an unowned Git process."""
    for remote in (None,'https://example.invalid/original.git'):
        with pytest.raises(RunConflict,match='Source operations'):
            manager.init_repo(1,'new',str(tmp_path/'new'),remote_url=remote)
    assert not (tmp_path/'new').exists()
    assert db_conn.execute('SELECT COUNT(*) FROM repositories').fetchone()[0] == 0


def test_old_model_tool_explains_owner_replacement_without_setup(seeded_project, db_conn):
    """The retained tool cannot grant itself authority by manufacturing a path or using ambient Forgejo settings."""
    import json

    from backend.tools.project.create_repository import CreateRepositoryTool

    result=json.loads(CreateRepositoryTool()._run(1,'new-source'))
    assert 'explicit owner source operations' in result['error']
    assert db_conn.execute('SELECT COUNT(*) FROM repositories').fetchone()[0] == 0
