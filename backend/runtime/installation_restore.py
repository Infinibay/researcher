"""Restore complete installation data elsewhere without adopting original authority or replaying work."""

import os
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import uuid4

from backend.runtime.bootstrap import _sync_directory
from backend.runtime.host_installation import _write_new
from backend.runtime.installation_backup import database_receipt, new_directory, _verify_backup
from backend.runtime.snapshot_files import CopyBudget, copy_regular, open_file
from backend.runtime.recovery_receipt import write_restoration_receipt


def relocated(value, original, destination):
    """Translate an absolute path under the original root while retaining unrelated historical text verbatim."""
    try:
        return str(destination / Path(value).relative_to(original))
    except ValueError:
        return value


def _git_metadata(root, entries, original, *, write=True, remap=None):
    """Repair only Git administrative path files, preserving commits, branches, indexes and dirty worktrees."""
    changes = []
    for entry in entries:
        name = entry['path']
        if Path(name).name == '.git' and entry['kind'] == 'symlink':
            raise ValueError('Git metadata is a symbolic reference outside the captured directory tree')
        if entry['kind'] != 'file':
            continue
        path = Path(name)
        is_gitfile = path.name == '.git'
        is_link = '/.git/worktrees/' in '/' + name and path.name in ('gitdir','commondir')
        is_alternates = name.endswith('/.git/objects/info/alternates')
        if not (is_gitfile or is_link or is_alternates):
            continue
        with open_file(root, name) as stream:
            raw = stream.read(65537)
        if len(raw) > 65536:
            raise ValueError('Git administrative path file is unexpectedly large')
        text = raw.decode('utf-8')
        lines = []
        for line in text.splitlines(keepends=True):
            newline = '\n' if line.endswith('\n') else ''
            value = line.removesuffix('\n')
            prefix = 'gitdir: ' if is_gitfile else ''
            if prefix and not value.startswith(prefix):
                raise ValueError('Invalid linked Git worktree pointer')
            old = value.removeprefix(prefix)
            base = original / path.parent.parent if is_alternates else original / path.parent
            referenced = Path(os.path.normpath(base / old))
            if remap is None and not referenced.is_relative_to(original):
                raise ValueError('Git metadata references storage outside the captured installation')
            new = str(remap(referenced)) if remap is not None else relocated(old, original, root)
            lines.append(prefix + new + newline)
        updated = ''.join(lines).encode()
        if updated != raw and write:
            with (root / name).open('wb') as target:
                target.write(updated);target.flush();os.fsync(target.fileno())
            changes.append(name)
    return changes


def _relocate_registrations(database, original, destination, budget):
    """Move current storage registrations only; immutable run/candidate/grant/history bindings remain original."""
    changes = []
    with closing(sqlite3.connect(database)) as db, db:
        db.execute('PRAGMA foreign_keys=ON')
        db.execute('BEGIN IMMEDIATE')
        for table, column in (('repositories','local_path'),('reference_files','file_path'),('agent_worktrees','worktree_path')):
            for identity, old in db.execute(f'SELECT id,{column} FROM {table}').fetchall():
                new = relocated(old, original, destination)
                if new != old:
                    db.execute(f'UPDATE {table} SET {column}=? WHERE id=?', (new, identity))
                    changes.append({'table': table, 'id': identity, 'column': column, 'original': old, 'restored': new})
        receipt = database_receipt(db, budget)
    return changes, receipt


def restore_installation(backup, destination, **limits):
    """Verify first, then restore new private storage with an explicit pending-enrollment barrier.

    Failure retains inspectable partial paths. Completion preserves data and
    historical evidence but does not authorize the new host to run old work.
    """
    budget = CopyBudget(**limits)
    manifest = _verify_backup(backup, budget)
    budget.bytes = 0
    source = Path(backup).resolve(strict=True)
    original = Path(manifest['source_root'])
    supplied = Path(destination).absolute()
    output = supplied.parent.resolve(strict=True) / supplied.name
    if output.is_relative_to(source) or source.is_relative_to(output):
        raise ValueError('Restoration destination must not overlap its backup')
    if output.is_relative_to(original) or original.is_relative_to(output):
        raise ValueError('Restoration must preserve the original installation at a separate path')
    root = new_directory(output)
    evidence = Path('.restorations') / uuid4().hex
    (root / evidence).mkdir(parents=True, mode=0o700)

    def target_name(name):
        """Archive original launch/access authority and enrollment receipts so copied control files cannot activate or block a fresh host."""
        path = Path(name)
        if name in ('runtime.json','installation.json','enrollment.json','runtime.enrolled.json','installation.enrolled.json','service/service-resources.json','service/service-owner.lock') or path.parts[0] in ('authority','auth'):
            return evidence / 'original' / path
        return path

    directories = []
    links = []
    for entry in sorted(manifest['entries'], key=lambda item: (len(Path(item['path']).parts),item['path'])):
        relative = target_name(entry['path'])
        target = root / relative
        target.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
        if entry['kind'] == 'directory':
            target.mkdir(exist_ok=True,mode=0o700)
            directories.append((target,entry['mode']))
        elif entry['kind'] == 'symlink':
            links.append((target,entry['target']))
        else:
            observed = copy_regular(source, entry['object'], target, budget)
            if observed != {key: entry[key] for key in ('sha256','bytes')}:
                raise ValueError('Backup changed after verification; partial restore remains inactive')
            os.chmod(target, entry['mode'])
    for external in manifest['authority_evidence']['external']:
        target = root / evidence / ('original-authority-' + external['role'])
        observed = copy_regular(source, external['object'], target, budget)
        if observed != {key: external[key] for key in ('sha256','bytes')}:
            raise ValueError('Authority archive changed after verification')
    git_changes = _git_metadata(root, manifest['entries'], original)
    changes, database = _relocate_registrations(root / 'source.db', original, root, budget)
    for target, value in links:
        os.symlink(relocated(value, original, root), target)
    # Pairing and actor enrollment are deliberately fresh, never copied sessions.
    (root / 'auth').mkdir(mode=0o700)
    _write_new(root / 'runtime.json', {'status':'pending_enrollment','snapshot_id':manifest['snapshot_id']})
    receipt = {'format':1,'status':'pending_enrollment','snapshot_id':manifest['snapshot_id'],
               'source_root':str(original),'restored_root':str(root),'evidence_directory':str(evidence),
               'database':database,'relocations':changes,'git_path_files_repaired':git_changes,
               'old_authority_id':manifest['authority_evidence']['authority_id'],
               'model_turns':0,'old_work_replayed':False}
    if 'reboot_evidence' in manifest:
        receipt['reboot_evidence'] = manifest['reboot_evidence']
    write_restoration_receipt(root, evidence, receipt, budget)
    for target, mode in reversed(directories):
        os.chmod(target, mode)
        _sync_directory(target)
    # Include newly introduced evidence parents, not only original manifest dirs.
    for directory, _, _ in os.walk(root, topdown=False, followlinks=False):
        budget.check()
        _sync_directory(Path(directory))
    _write_new(root / 'installation.json', {'format':1,'status':'restored_pending_enrollment',
                                          'snapshot_id':manifest['snapshot_id'],'restoration':str(evidence / 'restoration.json')})
    _sync_directory(root)
    return receipt
