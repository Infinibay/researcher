"""Native evaluation fixtures preserve fresh authority, bounded work and original closure."""

import json
import sqlite3
from contextlib import closing

import pytest


@pytest.fixture
def evaluation_assets(tmp_path, monkeypatch):
    """Keep real storage/bootstrap while replacing only host asset validation, without inference."""
    from backend.runtime import host_installation

    monkeypatch.setattr(host_installation, '_resources', lambda value: (dict(value), {}))
    path = tmp_path / 'assets.json'
    path.write_text(json.dumps({'model': 'controlled', 'project_turn_limit': 2,
                                'project_token_limit': 700000, 'limits': {'wall_seconds': 60}}))
    return path


def test_native_trial_requires_live_before_creating_anything(tmp_path, evaluation_assets):
    """A missing explicit live opt-in must not prepare storage or subscribe to a model."""
    from evals.runtime.native_trial import prepare

    root = tmp_path / 'trial'
    with pytest.raises(ValueError, match='--live'):
        prepare(root, evaluation_assets, live=False, turns=2)
    assert not root.exists()


def test_trials_get_independent_authorities_and_synthetic_sources(tmp_path, evaluation_assets):
    """Each scenario gets new authority, sources and DB while preserving the resource file."""
    from evals.runtime.native_trial import prepare

    original = evaluation_assets.read_bytes()
    first = prepare(tmp_path / 'first', evaluation_assets, live=True, turns=2)
    second = prepare(tmp_path / 'second', evaluation_assets, live=True, turns=1)
    configs = [json.loads((trial.installation / 'runtime.json').read_text()) for trial in (first, second)]
    assert configs[0]['authority']['authority_id'] != configs[1]['authority']['authority_id']
    for trial, config in zip((first, second), configs):
        assert config['runtime_profile'] == 'owned-codex-v1'
        assert config['limits']['wall_seconds'] == 60
        assert config['limits']['max_turns'] == 1
        assert trial.workspace.is_relative_to(trial.installation / 'sources')
        assert not (trial.installation / 'auth').is_relative_to(trial.workspace)
        assert not __import__('pathlib').Path(config['authority']['witness']).is_relative_to(trial.installation)
        assert (trial.workspace / 'invoice.py').read_bytes() == (trial.fixture / 'invoice.py').read_bytes()
        with closing(sqlite3.connect(trial.database)) as conn:
            assert conn.execute('SELECT COUNT(*) FROM runtime_runs').fetchone() == (0,)
            assert conn.execute('SELECT COUNT(*) FROM reference_files').fetchone() == (2,)
            assert conn.execute('SELECT local_path FROM repositories WHERE id=11').fetchone() == (str(trial.workspace),)
            assert conn.execute('PRAGMA foreign_key_check').fetchall() == []
        assert trial.root.stat().st_mode & 0o077 == 0
    assert configs[1]['project_turn_limit'] == 1
    assert evaluation_assets.read_bytes() == original
    with pytest.raises(FileExistsError):
        prepare(first.root, evaluation_assets, live=True, turns=2)


@pytest.mark.parametrize('extra', [{'authority': {'authority_id': 'old'}}, {'runtime_profile': 'owned-codex-v1'}, {'project_turn_limit': 1}])
def test_trial_rejects_old_authority_or_insufficient_turn_budget(tmp_path, evaluation_assets, extra):
    """An installation config or insufficient explicit budget cannot silently become a new trial."""
    from evals.runtime.native_trial import prepare

    assets = json.loads(evaluation_assets.read_text()) | extra
    evaluation_assets.write_text(json.dumps(assets))
    root = tmp_path / 'trial'
    with pytest.raises(ValueError):
        prepare(root, evaluation_assets, live=True, turns=2)
    assert not root.exists()


async def test_scenario_failure_records_original_service_closure(tmp_path, evaluation_assets, monkeypatch, socket_enabled):
    """A failing scenario still closes its original service and retains its lifecycle receipt."""
    import httpx
    from evals.operation import host_smoke
    from evals.runtime.native_trial import backend, prepare

    trial = prepare(tmp_path / 'trial', evaluation_assets, live=True, turns=1)
    (trial.installation / 'auth' / 'owner-test.key').write_text('synthetic-pairing')
    handle = object()
    monkeypatch.setattr(host_smoke, 'start', lambda *args: (handle, None))

    def stop(process, log):
        """Observe the exact original fixture handle rather than resolving a PID file."""
        assert process is handle
        return 143

    monkeypatch.setattr(host_smoke, 'stop', stop)
    client_class = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={'csrf_token': 'synthetic-csrf'}))
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: client_class(**kwargs, transport=transport))
    evidence = {}
    with pytest.raises(RuntimeError, match='scenario failed'):
        async with backend(trial, evidence):
            raise RuntimeError('scenario failed')
    receipt = json.loads((trial.root / 'service-lifecycle.json').read_text())
    assert receipt == {'service_exit': 143, 'owned_backend_terminal': True}
    assert evidence['owned_backend_terminal'] is True
