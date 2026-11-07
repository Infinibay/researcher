"""Verify coherent historical migration prefixes and recovery after abrupt writer death."""

import json
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pytest
from backend.db.migration_catalog import LATEST_VERSION


def logical_snapshot(database):
    """Compare schema and retained business rows independently of WAL pages and file layout."""
    with closing(sqlite3.connect(database)) as db:
        return {
            'schema': db.execute("SELECT type,name,tbl_name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%' ORDER BY name").fetchall(),
            'projects': db.execute('SELECT * FROM projects ORDER BY id').fetchall(),
            'tasks': db.execute('SELECT * FROM tasks ORDER BY id').fetchall(),
            'history': db.execute('SELECT * FROM schema_migrations ORDER BY version').fetchall(),
        }


def test_forward_targets_form_one_complete_history_and_preserve_seeded_data(tmp_path):
    """Reach every supported post-legacy version, then repeat startup without losing IDs or relations."""
    from backend.tools.base.db import ensure_migrations
    from backend.db.migration_catalog import LATEST_VERSION, MIGRATIONS

    assert [step.version for step in MIGRATIONS] == list(range(18, LATEST_VERSION + 1))
    database = tmp_path / 'chain.db'
    ensure_migrations(str(database), target_version=17)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("INSERT INTO projects(id,name) VALUES(101,'Retained project')")
        db.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Retained task')")
    for target in range(18, LATEST_VERSION + 1):
        ensure_migrations(str(database), target_version=target, existing_only=True)
        before = logical_snapshot(database)
        ensure_migrations(str(database), target_version=target, existing_only=True)
        assert logical_snapshot(database) == before
        with closing(sqlite3.connect(database)) as db:
            assert db.execute('SELECT MAX(version) FROM schema_migrations').fetchone() == (target,)
            assert db.execute('SELECT id,project_id,title FROM tasks').fetchall() == [(1001,101,'Retained task')]
            assert db.execute('PRAGMA foreign_key_check').fetchall() == []
            assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)


@pytest.mark.parametrize('version', range(18, LATEST_VERSION + 1))
def test_writer_crash_before_version_commit_preserves_prior_schema_and_resumes(tmp_path, version):
    """Abruptly kill only a new migration child before its history insert, then recover that same DB."""
    from backend.tools.base.db import ensure_migrations

    database = tmp_path / 'interrupted.db'
    ensure_migrations(str(database), target_version=version-1)
    with closing(sqlite3.connect(database)) as db, db:
        db.execute("INSERT INTO projects(id,name) VALUES(101,'Crash survivor')")
        db.execute("INSERT INTO tasks(id,project_id,type,title) VALUES(1001,101,'research','Preserve me')")
    before = logical_snapshot(database)
    program = '''import os,sqlite3,sys
from backend.tools.base import db as migrations
from backend.db.connection import connect
connection=connect(sys.argv[1],existing_only=True)
def interrupt(action, table, *args):
    """Terminate this owned child before the original migration records completion."""
    if action==sqlite3.SQLITE_INSERT and table=='schema_migrations':os._exit(91)
    return sqlite3.SQLITE_OK
connection.set_authorizer(interrupt)
migrations.connect=lambda *args,**kwargs:connection
migrations.ensure_migrations(sys.argv[1],existing_only=True,target_version=int(sys.argv[2]))
'''
    result = subprocess.run([sys.executable,'-c',program,str(database),str(version)],
                            cwd=Path(__file__).resolve().parents[3],capture_output=True,timeout=30)
    assert result.returncode == 91, result.stderr.decode(errors='replace')[-2000:]
    assert logical_snapshot(database) == before
    ensure_migrations(str(database), target_version=version, existing_only=True)
    with closing(sqlite3.connect(database)) as db:
        assert db.execute('SELECT MAX(version) FROM schema_migrations').fetchone() == (version,)
        assert db.execute('PRAGMA foreign_key_check').fetchall() == []
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)


@pytest.mark.parametrize('target', [True,16,LATEST_VERSION + 1,'29'])
def test_invalid_forward_target_never_creates_storage(tmp_path, target):
    """Unknown targets and booleans cannot create a partial installation as a side effect."""
    from backend.tools.base.db import ensure_migrations

    database = tmp_path / 'missing' / 'data.db'
    with pytest.raises(ValueError):
        ensure_migrations(str(database), target_version=target)
    assert not database.parent.exists()


@pytest.mark.parametrize('history', ['future','gap','downgrade'])
def test_forward_rejects_unsupported_history_without_rewriting_rows(tmp_path, history):
    """A forward migration cannot hide a future version, fill a fabricated gap or act as downgrade."""
    from backend.tools.base.db import ensure_migrations

    database = tmp_path / 'data.db'
    ensure_migrations(str(database), target_version=20)
    with closing(sqlite3.connect(database)) as db, db:
        if history=='future':db.execute("INSERT INTO schema_migrations(version,name) VALUES(?,'future')", (LATEST_VERSION + 1,))
        if history=='gap':db.execute('DELETE FROM schema_migrations WHERE version=19')
    before = logical_snapshot(database)
    with pytest.raises(RuntimeError):
        ensure_migrations(str(database), target_version=19 if history=='downgrade' else 63)
    assert logical_snapshot(database) == before
