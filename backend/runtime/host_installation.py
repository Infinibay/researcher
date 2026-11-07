"""Explicit fresh native host setup and bounded diagnostics, never automatic repair.

Resource checks are observations, not grants or remote subscription entitlement.
Existing installations, sources and authority witnesses are never adopted here.
"""

import hashlib
import json
import os
import sqlite3
import stat
import sys
from contextlib import closing
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from backend.runtime.bootstrap import initialize_authority, initialize_database, _sync_directory
from backend.runtime.storage_volume import StorageVolume, configured_storage

_PATHS = ('codex_binary', 'code_mode_host', 'ken_command', 'model_cache', 'token_file', 'cgroup_parent')
_OPTIONS = {'model', 'reasoning_effort', 'web_search', 'broker_limits', 'limits', 'static_dir',
            'project_turn_limit', 'project_token_limit', 'resolver', 'ca_bundle', 'development_checks', 'storage'}


def _read_json(path):
    """Read a bounded operator object without including its contents in errors."""
    path = Path(path)
    if path.stat().st_size > 65536:
        raise ValueError('Host configuration exceeds 64 KiB')
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError('Host configuration must be an object')
    return value


def _write_new(path, value):
    """Durably create private JSON, preserving partial state if writing fails."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    _sync_directory(path.parent)


def _resources(assets):
    """Check explicit native/Ken/account/network/cgroup inputs without inference or downloads."""
    from backend.runtime.broker_profile import CodexAsset
    from backend.runtime.codex_session import ExecutionLimits
    from backend.runtime.contracts import text
    from backend.runtime.development_policy import parse_development_checks
    from backend.runtime.ken_worker import KenInstallation, KEN_VERSION
    from backend.runtime.native_commands import VERSION, _version
    from backend.runtime.native_network import NativeNetwork
    from backend.runtime.peer_broker import BrokerLimits
    from backend.runtime.subscription_auth import ManagedTokenFile
    from backend.research.worker_sandbox import requirements

    if not isinstance(assets, dict) or set(assets) - (set(_PATHS) | _OPTIONS):
        raise ValueError('Unknown host asset configuration fields')
    if not set(_PATHS) | {'model'} <= set(assets):
        raise ValueError('Explicit model and all native host asset paths are required')
    text(assets['model'], 'native model', 128)
    config = dict(assets)
    worker_landlock_abi = requirements()
    for key in _PATHS:
        if not isinstance(assets[key], str):
            raise ValueError(f'{key} must be an absolute host path string')
        value = Path(assets[key])
        if not value.is_absolute():
            raise ValueError(f'{key} must be an absolute host path')
        config[key] = str(value.resolve(strict=True))
    if not Path(config['model_cache']).is_dir():
        raise ValueError('Ken model cache must be an existing directory')
    if 'static_dir' in config:
        static = Path(config['static_dir']).resolve(strict=True)
        if not (static / 'index.html').is_file():
            raise ValueError('Static directory must contain the compiled web index.html')
        config['static_dir'] = str(static)
    native = CodexAsset.inspect(config['codex_binary'])
    code_host = CodexAsset.inspect(config['code_mode_host'])
    if _version(Path(native.path), {'PATH': os.defpath, 'LANG': 'C.UTF-8', 'HOME': '/nonexistent', 'CODEX_HOME': '/nonexistent'}) != VERSION:
        raise ValueError(f'Host requires {VERSION}; no model call was sent')
    installation = KenInstallation.inspect(Path(config['ken_command']))
    artifacts = 0
    for model in installation.assets:
        snapshot = Path(config['model_cache']) / ('models--' + model['model_id'].replace('/', '--')) / 'snapshots' / model['revision']
        for name, expected in model['artifacts'].items():
            with (snapshot / name).open('rb') as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != expected['bytes'] or hashlib.file_digest(stream, 'sha256').hexdigest() != expected['sha256']:
                    raise ValueError('Prepare the pinned public Ken model assets before host initialization')
            artifacts += 1
    ManagedTokenFile(config['token_file']).read()
    network = NativeNetwork.inspect(resolver=config.get('resolver', '/etc/resolv.conf'), ca_bundle=config.get('ca_bundle', '/etc/ssl/certs/ca-certificates.crt'))
    parent = Path(config['cgroup_parent'])
    if not parent.is_relative_to('/sys/fs/cgroup') or not parent.is_dir() or not os.access(parent, os.W_OK):
        raise ValueError('Host requires an existing writable delegated cgroup v2 parent')
    if not {'cpu', 'memory', 'pids'} <= set((parent / 'cgroup.subtree_control').read_text().split()):
        raise ValueError('Delegate CPU, memory and pids controllers before initializing the host')
    limits = BrokerLimits(**config.get('broker_limits', {'memory_bytes': 2 * 1024**3, 'pids': 128}))
    config['broker_limits'] = asdict(limits)
    if 'limits' in config:
        ExecutionLimits(**config['limits'])
    parse_development_checks(config.get('development_checks', []))
    config.update(resolver=network.resolver.path, ca_bundle=network.ca_bundle.path)
    return config, {'native_version': VERSION, 'native_sha256': native.sha256,
                    'code_host_sha256': code_host.sha256, 'ken_version': KEN_VERSION,
                    'ken_artifacts_verified': artifacts, 'credential_snapshot_valid': True,
                    'document_worker_landlock_abi': worker_landlock_abi,
                    'remote_entitlement_verified': False}


def _environment(root):
    """Derive the fixed service environment from one explicit installation root."""
    return {'INFINIBAY_DB': str(root / 'source.db'),
            'INFINIBAY_DATA': str(root / 'logs'),
            'INFINIBAY_UPLOAD_BASE_DIR': str(root / 'uploads'),
            'INFINIBAY_AUTH_DIR': str(root / 'auth'),
            'INFINIBAY_RUNTIME_CONFIG': str(root / 'runtime.json')}


def host_environment(directory):
    """Open a completed installation marker; never initialize missing service data."""
    root = Path(directory).resolve(strict=True)
    info = root.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('Host installation must be private and owned by the serving user')
    marker = _read_json(root / 'installation.json')
    if marker.get('format') != 1 or marker.get('status') != 'prepared':
        raise ValueError('Host preparation is incomplete; preserve partial paths for inspection')
    for name in ('source.db', 'runtime.json'):
        if not (root / name).is_file():
            raise ValueError('Host state is missing; restore the original installation')
    environment = _environment(root)
    config = _read_json(root / 'runtime.json')
    configured_storage(config, [root, *[config['authority'][key] for key in ('database', 'witness', 'mutex')]])
    if config.get('static_dir'):
        environment['INFINIBAY_STATIC_DIR'] = config['static_dir']
    return environment


def initialize_host(directory, *, witness_dir, assets):
    """Create NEW product/authority/control/source roots after validating existing host assets."""
    supplied = [Path(directory).absolute(), Path(witness_dir).absolute()]
    root, witness = [p.parent.resolve(strict=True) / p.name for p in supplied]
    if root.is_relative_to(witness) or witness.is_relative_to(root):
        raise ValueError('Host data and independent witness must not overlap')
    if any(os.path.lexists(p) for p in (root, witness)):
        raise FileExistsError('Host and witness directories must both be NEW; never reinitialize existing state')
    config, evidence = _resources(assets)
    volume = StorageVolume.capture(config['storage']) if 'storage' in config else None
    storage = {'enforced': False, 'reason': 'No aggregate storage policy configured'}
    if volume is not None:
        storage = volume.check([root, witness], admission=True)
        config['storage_receipt'] = volume.receipt
    root.mkdir(mode=0o700)
    _sync_directory(root.parent)
    for name in ('sources', 'control', 'uploads', 'auth', 'logs', 'service'):
        (root / name).mkdir(mode=0o700)
    database = initialize_database(root / 'source.db')
    authority = initialize_authority(database_dir=root / 'authority', witness_dir=witness)
    config.update(runtime_profile='owned-codex-v1', workspace_root=str(root / 'sources'),
                  control_root=str(root / 'control'), authority=authority, max_concurrent=1)
    _write_new(root / 'runtime.json', config)
    environment = _environment(root)
    if config.get('static_dir'):
        environment['INFINIBAY_STATIC_DIR'] = config['static_dir']
    result = {'format': 1, 'status': 'prepared', 'environment': environment,
              'storage': storage,
              'authority_id': authority['authority_id'], 'resource_observations': evidence,
              'source_database': str(database), 'model_turns': 0,
              'limits': 'Fresh storage and local resources only; no prior-actor adoption, remote entitlement or product admission proven.'}
    _write_new(root / 'installation.json', result)
    return result


def _probe_domain(config):
    """Birth one fixed no-op child in a fresh domain and observe exact retirement."""
    from backend.runtime.execution_domain import ExecutionDomain

    path = Path(config['cgroup_parent']) / ('researcher-host-probe-' + uuid4().hex)
    path.mkdir(mode=0o700)
    domain = child = None
    retired = False
    try:
        domain = ExecutionDomain.open(path)
        domain.limit(**config['broker_limits'])
        child = domain.spawn([sys.executable, '-I', '-S', '-c', 'pass'])
        child.stdin.close()
        code = child.wait(timeout=5)
        closure = domain.retire(timeout=5)
        retired = closure.removed
        if code != 0 or not closure.removed:
            raise RuntimeError('Host kernel probe did not close successfully')
        return {'child_exit_code': code, 'domain_removed': closure.removed, 'resource_observation': closure.resources}
    finally:
        if domain is not None:
            try:
                if not retired:
                    domain.retire(timeout=5)
            finally:
                domain.close()
        elif path.exists():
            path.rmdir()
        if child is not None:
            child.close_handles()


def inspect_host(directory, *, probe=False):
    """Revalidate prepared resources; optionally run a bounded kernel probe without inference."""
    from backend.runtime.authority_journal import WitnessedAuthorityJournal

    environment = host_environment(directory)
    config = _read_json(environment['INFINIBAY_RUNTIME_CONFIG'])
    if config.get('runtime_profile') != 'owned-codex-v1':
        raise ValueError('Prepared host requires owned-codex-v1')
    assets = {k: v for k, v in config.items() if k in set(_PATHS) | _OPTIONS}
    validated, evidence = _resources(assets)
    with WitnessedAuthorityJournal(**config['authority']) as journal:
        state = journal.load()
    uri = Path(environment['INFINIBAY_DB']).as_uri() + '?mode=ro'
    with closing(sqlite3.connect(uri, uri=True)) as db:
        if db.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('Host source database integrity check failed')
    result = {'status': 'resources_verified', 'environment': environment,
              'resource_observations': evidence, 'authority_sequence': state.sequence,
              'model_turns': 0, 'product_admission_verified': False}
    volume = configured_storage(config, [Path(directory)])
    result['storage'] = volume.check() if volume is not None else {
        'enforced': False, 'reason': 'No aggregate storage policy configured'}
    if probe:
        result['kernel_probe'] = _probe_domain(validated)
    return result
