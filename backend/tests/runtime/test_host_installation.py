"""Fresh host preparation composes real storage without adopting existing state."""

import json
import os
import sqlite3
from pathlib import Path

import pytest


@pytest.fixture
def host_assets(tmp_path, native_asset, code_host_asset, ken_installation):
    """Use real native executables and delegated cgroups with synthetic credentials/Ken."""
    parent = (Path('/sys/fs/cgroup') / Path('/proc/self/cgroup').read_text().strip().split(':', 2)[2].lstrip('/')).parent
    if not os.access(parent, os.W_OK) or not {'memory', 'pids'} <= set((parent / 'cgroup.subtree_control').read_text().split()):
        pytest.skip('Requires delegated memory/pids controllers')
    token = tmp_path / 'subscription.json'
    token.write_text(json.dumps({'auth_mode': 'chatgpt', 'tokens': {'access_token': 'fixture.header.signature', 'account_id': 'fixture-account'}}))
    token.chmod(0o600)
    cache = tmp_path / 'models'
    cache.mkdir()
    return {'model': 'controlled-only', 'codex_binary': native_asset.path,
            'code_mode_host': code_host_asset.path, 'ken_command': str(ken_installation),
            'model_cache': str(cache), 'token_file': str(token), 'cgroup_parent': str(parent)}


def test_fresh_host_composes_storage_and_configured_product(tmp_path, host_assets, monkeypatch):
    """Create a fresh usable installation and compose its real factory without inference."""
    from backend.runtime.host_installation import initialize_host, inspect_host
    from backend.api.main import create_app
    from backend.api.runtime_dependencies import configured_runtime

    root, witness = tmp_path / 'installation', tmp_path / 'external-witness'
    credential_before = Path(host_assets['token_file']).read_bytes()
    result = initialize_host(root, witness_dir=witness, assets=host_assets)
    environment = result['environment']
    for key, value in environment.items():
        monkeypatch.setenv(key, value)
    config = json.loads(Path(environment['INFINIBAY_RUNTIME_CONFIG']).read_text())
    assert config['runtime_profile'] == 'owned-codex-v1'
    assert config['service_limits'] == {'memory_bytes':2*1024**3,'pids':128,'cpu_millis':2000}
    assert Path(config['workspace_root']).is_dir()
    assert not Path(config['authority']['witness']).is_relative_to(root)
    with sqlite3.connect(environment['INFINIBAY_DB']) as db:
        assert db.execute('PRAGMA integrity_check').fetchone() == ('ok',)
        assert db.execute('SELECT COUNT(*) FROM runtime_runs').fetchone() == (0,)
    app = create_app()
    service = configured_runtime(app.state.live_grants, app=app)
    assert type(service.runtime).__name__ == 'OwnedCodexRuntime'
    assert inspect_host(root)['status'] == 'resources_verified'
    assert 'fixture.header.signature' not in json.dumps(result)
    assert Path(host_assets['token_file']).read_bytes() == credential_before


def test_reinitialization_preserves_the_original_host(tmp_path, host_assets):
    """Refuse an existing installation without changing its authority or database."""
    from backend.runtime.host_installation import initialize_host

    root, witness = tmp_path / 'installation', tmp_path / 'external-witness'
    initialize_host(root, witness_dir=witness, assets=host_assets)
    before = {p: p.read_bytes() for tree in (root, witness) for p in tree.rglob('*') if p.is_file()}
    with pytest.raises(FileExistsError):
        initialize_host(root, witness_dir=witness, assets=host_assets)
    assert all(p.read_bytes() == data for p, data in before.items())


@pytest.mark.parametrize('case', ['existing', 'nested_witness', 'missing_asset', 'unknown_field', 'service_limits'])
def test_invalid_host_setup_creates_no_partial_installation(tmp_path, host_assets, case):
    """Reject pre-existing destinations, overlapping witness and invalid assets before writes."""
    from backend.runtime.host_installation import initialize_host

    root, witness = tmp_path / 'installation', tmp_path / 'external-witness'
    if case == 'existing':
        root.mkdir()
    elif case == 'nested_witness':
        witness = root / 'witness'
    elif case == 'missing_asset':
        host_assets['code_mode_host'] = str(tmp_path / 'absent')
    elif case == 'service_limits':
        host_assets['service_limits'] = {'memory_bytes':1}
    else:
        host_assets['OPENAI_API_KEY'] = 'not-a-subscription'
    with pytest.raises((OSError, ValueError)):
        initialize_host(root, witness_dir=witness, assets=host_assets)
    assert not witness.exists()
    assert not root.exists() or list(root.iterdir()) == []


def test_host_probe_observes_and_retires_its_own_domain(tmp_path, host_assets):
    """Exercise kernel birth/limits/closure in a unique sibling without a model turn."""
    from backend.runtime.host_installation import initialize_host, inspect_host

    root = tmp_path / 'installation'
    initialize_host(root, witness_dir=tmp_path / 'external-witness', assets=host_assets)
    result = inspect_host(root, probe=True)
    assert result['kernel_probe']['child_exit_code'] == 0
    assert result['kernel_probe']['domain_removed'] is True
    assert result['model_turns'] == 0
    assert result['kernel_probe']['resource_observation']['observed'] is True
    assert result['kernel_probe']['resource_observation']['limits']['cpu_max'] == '200000 100000'


def test_launcher_consumes_prepared_host_without_shell_environment(tmp_path, host_assets, monkeypatch):
    """Start the API with original prepared paths and an auth-safe service working directory."""
    from backend.runtime.host_installation import initialize_host
    from backend.cli import launcher

    root = tmp_path / 'installation'
    prepared = initialize_host(root, witness_dir=tmp_path / 'external-witness', assets=host_assets)
    calls = []
    monkeypatch.setattr(launcher, 'run_services', lambda services: calls.extend(services) or 0)
    for key in prepared['environment']:
        monkeypatch.setenv(key, '')
        monkeypatch.delenv(key, raising=False)
    assert launcher.main(['--installation', str(root)]) == 0
    assert len(calls) == 1 and calls[0][0] == 'API'
    assert calls[0][2] == root / 'service'
    assert os.environ['INFINIBAY_RUNTIME_CONFIG'] == str(root / 'runtime.json')


def test_prepared_semantic_assets_reach_reopened_host_and_launcher(tmp_path, host_assets, monkeypatch):
    """Explicit pinned public weights survive installation/reopen and reach the API without loading an encoder."""
    from backend.cli import launcher
    from backend.research.retrieval_assets import FINGERPRINT
    from backend.runtime.host_installation import host_environment, initialize_host, inspect_host

    configured = os.environ.get('RESEARCHER_TEST_RETRIEVAL_ASSETS')
    if not configured or not Path(configured).is_dir():
        pytest.skip('Explicit pinned offline assets are required')
    assets = {**host_assets, 'retrieval_asset_dir': str(Path(configured).resolve())}
    root = tmp_path / 'installation'
    prepared = initialize_host(root, witness_dir=tmp_path / 'witness', assets=assets)
    assert prepared['environment']['INFINIBAY_RETRIEVAL_ASSET_DIR'] == assets['retrieval_asset_dir']
    assert host_environment(root)['INFINIBAY_RETRIEVAL_ASSET_DIR'] == assets['retrieval_asset_dir']
    assert json.loads((root / 'runtime.json').read_text())['retrieval_asset_dir'] == assets['retrieval_asset_dir']
    semantic = inspect_host(root)['resource_observations']['semantic_assets']
    assert semantic == {'configured': True, 'fingerprint': FINGERPRINT, 'files_verified': 2}
    # Track every key before the CLI exports directly into os.environ, then
    # start genuinely unset; teardown must not configure another test's app.
    for key in prepared['environment']:
        monkeypatch.setenv(key, '')
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(launcher, 'run_services', lambda _: 0)
    assert launcher.main(['--installation', str(root)]) == 0
    assert os.environ['INFINIBAY_RETRIEVAL_ASSET_DIR'] == assets['retrieval_asset_dir']
    assert {key: os.environ[key] for key in prepared['environment']} == prepared['environment']
    assert prepared['model_turns'] == 0


@pytest.mark.parametrize('case', ['none', 'relative', 'missing', 'changed'])
def test_invalid_semantic_assets_fail_before_any_host_or_witness_write(tmp_path, host_assets, case):
    """A path alone is not model preparation; invalid or unpinned bytes cannot create a usable installation."""
    from backend.runtime.host_installation import initialize_host

    value = {'none': None, 'relative': 'relative-assets', 'missing': str(tmp_path / 'missing')}.get(case)
    if case == 'changed':
        directory = tmp_path / 'changed-assets'
        directory.mkdir()
        (directory / 'model.onnx').write_bytes(b'Changed bytes')
        (directory / 'tokenizer.json').write_text('{}')
        value = str(directory)
    root, witness = tmp_path / 'installation', tmp_path / 'witness'
    with pytest.raises((ValueError, OSError, RuntimeError), match='(?i)retrieval|semantic|pinned'):
        initialize_host(root, witness_dir=witness, assets={**host_assets, 'retrieval_asset_dir': value})
    assert not root.exists() and not witness.exists()


def test_host_refuses_missing_cpu_controller_before_creating_installation(tmp_path, host_assets):
    """A delegated memory/process domain cannot silently omit the required shared CPU boundary."""
    from uuid import uuid4
    from backend.runtime.host_installation import initialize_host

    leaf = Path(host_assets['cgroup_parent']) / ('researcher-no-cpu-' + uuid4().hex)
    leaf.mkdir(mode=0o700)
    try:
        (leaf / 'cgroup.subtree_control').write_text('+memory +pids')
        assets = {**host_assets, 'cgroup_parent': str(leaf)}
        root = tmp_path / 'installation'
        with pytest.raises(ValueError, match='CPU'):
            initialize_host(root, witness_dir=tmp_path/'witness', assets=assets)
        assert not root.exists()
    finally:
        leaf.rmdir()
