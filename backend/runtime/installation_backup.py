"""Create and verify bounded consistent data backups of explicitly prepared native installations.

Original authority witnesses are archived as evidence, never as portable launch
permits. External toolchains, model caches and account files remain references.
"""

import hashlib
import json
import os
import sqlite3
import re
import time
from contextlib import ExitStack, closing
from pathlib import Path
from uuid import uuid4

from backend.runtime.authority_journal import WitnessedAuthorityJournal
from backend.runtime.bootstrap import _sync_directory
from backend.runtime.host_installation import _read_json, _write_new, host_environment
from backend.runtime.snapshot_files import CopyBudget, copy_regular, digest_file, inventory, open_file, relative_name

FORMAT = 1
MANIFEST_LIMIT = 128 * 1024**2


def new_directory(path):
    """Create a private new output root without following or replacing an existing destination."""
    supplied = Path(path).absolute()
    path = supplied.parent.resolve(strict=True) / supplied.name
    path.mkdir(mode=0o700)
    _sync_directory(path.parent)
    return path


def database_receipt(connection, budget=None):
    """Check SQLite integrity/references and count all retained tables without reading row contents."""
    if budget is not None:
        connection.set_progress_handler(lambda: int(time.monotonic() > budget.deadline), 10000)
    if connection.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
        raise ValueError('Snapshot database integrity check failed')
    if connection.execute('PRAGMA foreign_key_check').fetchall():
        raise ValueError('Snapshot database has broken foreign-key references')
    names = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    counts = {name: connection.execute('SELECT count(*) FROM "' + name.replace('"', '""') + '"').fetchone()[0] for name in names}
    version = connection.execute('SELECT max(version) FROM schema_migrations').fetchone()[0] if 'schema_migrations' in names else None
    return {'tables': counts, 'schema_version': version, 'integrity': 'ok', 'foreign_keys': 'ok'}


def _database_copy(source, destination, budget):
    """Snapshot a separately locked SQLite writer into a closed, self-contained ordinary database file."""
    with closing(sqlite3.connect(source.as_uri() + '?mode=ro', uri=True, timeout=0)) as reader:
        pages = reader.execute('PRAGMA page_count').fetchone()[0]
        page_size = reader.execute('PRAGMA page_size').fetchone()[0]
        budget.check(size=pages * page_size)
        fd = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.close(fd)
        with closing(sqlite3.connect(destination)) as target:
            reader.backup(target, pages=256, progress=lambda *_: budget.check(), sleep=0)
            target.execute('PRAGMA journal_mode=DELETE')
            receipt = database_receipt(target, budget)
    with destination.open('rb') as stream:
        os.fsync(stream.fileno())
    return receipt


def _without_sidecars(items, databases):
    """Exclude only SQLite transient journals; their committed contents are captured through backup()."""
    excluded = {name + suffix for name in databases for suffix in ('-wal', '-shm', '-journal')}
    return {key: value for key, value in items.items() if key not in excluded}


def _stable_inventory(items):
    """Ignore directory timestamps affected by SQLite sidecars while retaining membership and file identities."""
    return {name: ({'kind': 'directory', 'mode': item['mode'], 'identity': item['identity'][:2]} if item['kind'] == 'directory' else item) for name, item in items.items()}


def _registered_paths(db, root, items):
    """Require every currently registered upload, repository and active legacy worktree to be included."""
    for table, column, kind, condition in (
        ('reference_files', 'file_path', 'file', ''),
        ('repositories', 'local_path', 'directory', ''),
        ('agent_worktrees', 'worktree_path', 'directory', " WHERE status='active'"),
    ):
        for (value,) in db.execute(f'SELECT {column} FROM {table}{condition}'):
            try:
                name = str(Path(value).relative_to(root))
            except ValueError as exc:
                raise ValueError(f'Registered {table} path is outside this managed installation; include/migrate its storage explicitly first') from exc
            if name not in items or items[name]['kind'] != kind:
                raise ValueError(f'Registered {table} storage is missing or not a regular {kind}')


def backup_installation(directory, destination, **limits):
    """Freeze current data/authority, copy stable files and publish the manifest only after all checks pass."""
    budget = CopyBudget(**limits)
    environment = host_environment(directory)
    root = Path(directory).resolve(strict=True)
    supplied = Path(destination).absolute()
    output = supplied.parent.resolve(strict=True) / supplied.name
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Backup destination must not overlap source installation')
    config = _read_json(environment['INFINIBAY_RUNTIME_CONFIG'])
    for key, name in (('workspace_root', 'sources'), ('control_root', 'control')):
        if Path(config[key]).resolve(strict=True) != root / name:
            raise ValueError('Managed backup requires the registered source/control roots inside the installation')
    authority = config['authority']
    witness_root = Path(authority['witness']).parent.resolve(strict=True)
    if output.is_relative_to(witness_root) or witness_root.is_relative_to(output):
        raise ValueError('Backup destination must not overlap the independent witness')
    authority_db = Path(authority['database']).resolve(strict=True)
    if authority_db != root / 'authority/authority.db':
        raise ValueError('Authority database must belong to this installation backup domain')
    with ExitStack() as stack:
        journal = stack.enter_context(WitnessedAuthorityJournal(**authority))
        state = stack.enter_context(journal.frozen_snapshot())
        if state.records.get('broker:active') is not None or any(
            (key.startswith('broker:grant:') and (value.get('state') != 'retired' or value.get('domain_removed') is not True))
            or (key.startswith('broker:op:') and value.get('execution_closed') is not True)
            for key, value in state.records.items() if isinstance(value, dict)
        ):
            raise ValueError('Close or reconcile native authority before taking a portable data backup')
        first = inventory(root, budget)
        databases = set()
        for name, item in first.items():
            if item['kind'] == 'file':
                with open_file(root, name) as stream:
                    if stream.read(16) == b'SQLite format 3\x00':
                        databases.add(name)
        if 'source.db' not in databases:
            raise ValueError('Source database is not recognizable SQLite storage')
        connections = {}
        for name in sorted(databases):
            if root / name == authority_db:
                continue
            conn = stack.enter_context(closing(sqlite3.connect((root / name).as_uri() + '?mode=rw', uri=True, timeout=0)))
            conn.execute('BEGIN IMMEDIATE')
            connections[name] = conn
        db = connections['source.db']
        if db.execute("SELECT 1 FROM runtime_peers WHERE state!='closed' LIMIT 1").fetchone():
            raise ValueError('Reconcile original unclosed peers before backup')
        before = _without_sidecars(inventory(root, budget), databases)
        _registered_paths(db, root, before)
        from backend.runtime.installation_restore import _git_metadata

        _git_metadata(root, [{'path':name, **item} for name,item in before.items()], root, write=False)
        output = new_directory(output)
        objects = output / 'objects';objects.mkdir(mode=0o700)
        entries = []
        for name, item in sorted(before.items()):
            entry = {'path': name, 'kind': item['kind'], 'mode': item['mode'] & 0o777}
            if item['kind'] == 'symlink':
                entry['target'] = item['target']
            elif item['kind'] == 'file':
                entry['object'] = f'objects/{len(entries):08d}'
                target = output / entry['object']
                if name in databases:
                    entry['database'] = _database_copy(root / name, target, budget)
                    details = digest_file(output, entry['object'], budget)
                    budget.check(size=details['bytes']);budget.bytes += details['bytes']
                else:
                    details = copy_regular(root, name, target, budget)
                entry.update(details)
            entries.append(entry)
        external = []
        for key in ('witness', 'mutex'):
            source = Path(authority[key])
            object_name = 'objects/authority-' + key
            details = copy_regular(source.parent, source.name, output / object_name, budget)
            external.append({'role': key, 'source_path': str(source), 'object': object_name, **details})
        after = _without_sidecars(inventory(root, budget), databases)
        if _stable_inventory(before) != _stable_inventory(after):
            raise ValueError('Installation changed while copying; partial backup retained without completion marker')
        # File hashes also catch changes from non-cooperating editors within the frozen DB interval.
        for entry in entries:
            if entry['kind'] == 'file' and 'database' not in entry:
                observed = digest_file(root, entry['path'], budget)
                if observed != {key: entry[key] for key in ('sha256','bytes')}:
                    raise ValueError('Installation file content changed while copying')
            budget.check()
        manifest = {'format': FORMAT, 'kind': 'researcher-installation-data', 'status': 'complete',
                    'snapshot_id': uuid4().hex, 'source_root': str(root), 'entries': entries,
                    'authority_evidence': {'authority_id': authority['authority_id'], 'sequence': state.sequence, 'state_hash': state.state_hash, 'external': external},
                    'external_resources': {key: config[key] for key in ('codex_binary','code_mode_host','ken_command','model_cache','token_file','cgroup_parent','static_dir') if key in config},
                    'bytes': budget.bytes, 'restore_requires_fresh_enrollment': True}
        _sync_directory(objects)
        _write_new(output / 'manifest.pending', manifest)
        os.rename(output / 'manifest.pending', output / 'manifest.json')
        _sync_directory(output)
        return {'status': 'complete', 'snapshot_id': manifest['snapshot_id'], 'entries': len(entries), 'bytes': budget.bytes, 'directory': str(output)}


def verify_backup(directory, **limits):
    """Validate every path, parent, object hash and SQLite snapshot before any restoration writes."""
    return _verify_backup(directory, CopyBudget(**limits))


def _verify_backup(directory, budget):
    """Share the caller's deadline across verification and subsequent restoration."""
    root = Path(directory).resolve(strict=True)
    with open_file(root, 'manifest.json') as stream:
        if os.fstat(stream.fileno()).st_size > MANIFEST_LIMIT:
            raise ValueError('Backup manifest exceeds its bound')
        manifest = json.load(stream)
    if not isinstance(manifest,dict) or type(manifest.get('format')) is not int or manifest.get('format') != FORMAT or manifest.get('kind') != 'researcher-installation-data' or manifest.get('status') != 'complete':
        raise ValueError('Backup has no supported completion manifest')
    if not re.fullmatch('[a-f0-9]{32}', manifest.get('snapshot_id','')):
        raise ValueError('Backup snapshot identity is invalid')
    entries = manifest['entries']
    budget.check(entries=len(entries))
    by_path = {}
    for entry in entries:
        path = relative_name(entry['path'])
        if str(path) in by_path or entry['kind'] not in ('file','directory','symlink'):
            raise ValueError('Duplicate or unsupported snapshot entry')
        if type(entry.get('mode')) is not int or not 0 <= entry['mode'] <= 0o777:
            raise ValueError('Invalid snapshot permissions')
        if entry['kind'] == 'symlink' and (not isinstance(entry.get('target'),str) or '\x00' in entry['target']):
            raise ValueError('Invalid snapshot symbolic link')
        by_path[str(path)] = entry
    for name in by_path:
        for parent in relative_name(name).parents:
            if str(parent) != '.' and by_path.get(str(parent),{}).get('kind') != 'directory':
                raise ValueError('Snapshot entry has a missing or symbolic parent')
    objects = [entry for entry in entries if entry['kind'] == 'file'] + manifest['authority_evidence']['external']
    if sorted(entry['role'] for entry in manifest['authority_evidence']['external']) != ['mutex','witness']:
        raise ValueError('Backup lacks its exact independent authority evidence')
    for required in ('source.db','runtime.json','installation.json','authority/authority.db'):
        entry = by_path.get(required,{})
        if entry.get('kind') != 'file' or (required.endswith('.db') and 'database' not in entry):
            raise ValueError('Backup lacks required installation storage')
    seen = set()
    for entry in objects:
        name = relative_name(entry['object'])
        if len(name.parts) != 2 or name.parts[0] != 'objects' or str(name) in seen:
            raise ValueError('Invalid or reused snapshot content object')
        seen.add(str(name))
        observed = digest_file(root, str(name), budget)
        if observed != {key: entry[key] for key in ('sha256','bytes')}:
            raise ValueError('Backup content hash or byte count differs from manifest')
        budget.check(size=observed['bytes']);budget.bytes += observed['bytes']
        if 'database' in entry:
            with open_file(root, str(name)) as stream:
                with closing(sqlite3.connect(f'file:/proc/self/fd/{stream.fileno()}?mode=ro&immutable=1', uri=True, timeout=0)) as db:
                    if database_receipt(db, budget) != entry['database']:
                        raise ValueError('Backup database counts or integrity differ from manifest')
    if set(p.name for p in (root / 'objects').iterdir()) != {Path(name).name for name in seen}:
        raise ValueError('Backup contains unlisted or missing content objects')
    if 'source.db' not in by_path or not Path(manifest['source_root']).is_absolute():
        raise ValueError('Backup lacks its source database or original root identity')
    return manifest
