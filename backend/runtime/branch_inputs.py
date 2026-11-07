"""Capture exact retained Git changes through the original owned preparation, then freeze data in existing receipts without transferring historical authority."""

import base64
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from backend.runtime.contracts import InputTooLarge, RunConflict, RunNotFound
from backend.runtime.development_workspace import (
    MAX_OUTPUT_BYTES, GitResult, _POLICY, _SHA, _source_identity, git_environment,
)


def _packet(snapshot):
    """Fingerprint the complete selected or acquired data with explicit absence of acceptance/publication authority."""
    from backend.runtime.code_carryover import _encoded

    encoded = _encoded(snapshot).encode()
    if len(encoded) > 600000:
        raise InputTooLarge('Complete branch input exceeds its600000-byte budget; no changes were omitted')
    return {
        'snapshot': snapshot, 'snapshot_sha256': hashlib.sha256(encoded).hexdigest(),
        'authority': 'data_only', 'acceptance': 'not_granted', 'publication': 'not_granted',
        'explanation': 'These are selected historical changes against the current preparation base, not a cherry-pick instruction or proof of original context. A fresh author must inspect/adapt them under current requirements; checks, distinct review and current owner acceptance/publication are required again.',
    }


@dataclass(frozen=True)
class PriorBranchTarget:
    """Owner-selected recorded branch and complete immutable commit identity; labels and old approval carry no authority."""

    branch_id: int
    commit_sha: str
    source_kind: str = 'legacy_branch'

    def __post_init__(self):
        """Reject moving/abbreviated identities and ambiguous record identifiers before any receipt lookup or Git command."""
        if type(self.branch_id) is not int or self.branch_id <= 0 or self.source_kind != 'legacy_branch':
            raise ValueError('Select a positive recorded legacy branch identifier')
        if not isinstance(self.commit_sha, str) or not _SHA.fullmatch(self.commit_sha):
            raise ValueError('Select a complete canonical40or64-character commit SHA')


class BranchInputs:
    """Bind admitted selection to one original acquisition receipt; no new persistence table, execution controller or model loop."""

    def __init__(self, runs):
        """Use the existing run store and its immutable command receipts."""
        self.runs = runs

    def sources(self, project_id, task_id):
        """List scoped historical branch records; stored commit hashes are suggestions, not live Git observations."""
        with self.runs._transaction() as conn:
            self.runs._existing_task(conn, project_id, task_id)
            return [
                {'source_kind': 'legacy_branch', 'branch_id': row['id'],
                 'repository_id': row['repository_id'], 'branch': row['branch_name'],
                 'recorded_commit_sha': row['last_commit_hash'], 'recorded_task_id': row['task_id'],
                 'recorded_status': row['status'], 'availability': 'not_inspected'}
                for row in conn.execute(
                    'SELECT b.*,r.id AS repository_id FROM branches b JOIN repositories r ON r.project_id=b.project_id AND r.id=b.repo_id WHERE b.project_id=? ORDER BY b.id', (project_id,)
                )
            ]

    def select(self, conn, spec, binding, target):
        """Freeze only the actual scoped record and owner-chosen immutable commit; original context and bytes are not guessed at admission."""
        self.runs._check_registration(conn, spec.project_id, binding)
        row = conn.execute(
            'SELECT b.* FROM branches b JOIN repositories r ON r.project_id=b.project_id AND r.id=b.repo_id WHERE b.id=? AND b.project_id=? AND r.id=?',
            (target.branch_id, spec.project_id, binding.repository_id),
        ).fetchone()
        if row is None:
            raise RunNotFound('Historical branch not found in this project and registered repository')
        branch = row['branch_name']
        if not isinstance(branch, str) or not branch or len(branch.encode()) > 1024 or '\0' in branch:
            raise RunConflict('Recorded branch label is invalid')
        return _packet({
            'schema_version': 1, 'acquisition': 'awaiting_owned_preparation',
            'origin': {'kind': 'selected_legacy_branch', 'branch_id': row['id'],
                       'project_id': spec.project_id, 'repository_id': binding.repository_id,
                       'recorded_branch': branch, 'recorded_task_id': row['task_id'],
                       'recorded_status': row['status'], 'task_relation': 'selected_by_owner_not_historically_verified'},
            'source': asdict(binding), 'selected_commit_sha': target.commit_sha,
            'original_input': None, 'original_input_status': 'unknown',
        })

    def requested(self, lease):
        """Read selected metadata only for the live original development owner, without starting a Git process or a model."""
        from backend.runtime.code_carryover import CodeCarryovers

        with self.runs._transaction() as conn:
            row = self.runs._authority(conn, lease)
            packet = CodeCarryovers.admitted(conn, row)
            if packet is None or packet['snapshot']['origin']['kind'] != 'selected_legacy_branch':
                return None
            if row['execution_kind'] != 'development':
                raise RunConflict('Branch input requires original development preparation')
            return packet

    @staticmethod
    def _intent(row, selected):
        """Bind acquisition to the immutable original attempt/fence/context and selection, independently of a later owner label."""
        return {'kind': 'capture_prior_branch', 'run_id': row['id'], 'attempt_id': row['current_attempt_id'],
                'context_version': row['context_version'], 'fence': row['attempt_fence'],
                'selection_sha256': selected['snapshot_sha256']}

    @staticmethod
    def _key(row):
        """Reserve a bounded internal identity for this attempt; collisions fail through the existing receipt contract."""
        return 'prior-branch-' + row['current_attempt_id']

    @staticmethod
    def _verify(selected, packet):
        """Reject incomplete or altered acquired data before persistence or input composition."""
        from backend.runtime.code_carryover import _encoded

        if (packet is None or packet.get('authority') != 'data_only'
            or packet.get('acceptance') != 'not_granted' or packet.get('publication') != 'not_granted'
            or packet['snapshot'].get('acquisition') != 'captured'
            or packet['snapshot'].get('selection_sha256') != selected['snapshot_sha256']
            or packet['snapshot'].get('selection') != selected['snapshot']
            or hashlib.sha256(_encoded(packet['snapshot']).encode()).hexdigest() != packet['snapshot_sha256']):
            raise RunConflict('Exact branch input has not completed owned capture or is inconsistent')
        return packet

    def save(self, conn, lease, prepared, packet):
        """Atomically retain captured input with ready preparation under current source/lease authority; never mutate an admission receipt."""
        from backend.runtime.code_carryover import CodeCarryovers

        row = self.runs._authority(conn, lease)
        selected = CodeCarryovers.admitted(conn, row)
        branch = selected is not None and selected['snapshot']['origin']['kind'] == 'selected_legacy_branch'
        if not branch:
            if packet is not None:
                raise RunConflict('Unexpected branch capture without an admitted selection')
            return
        self._verify(selected, packet)
        if (packet['snapshot']['candidate']['base_sha'] != prepared.base_sha
            or packet['snapshot']['candidate']['base_tree_sha'] != prepared.base_tree_sha):
            raise RunConflict('Branch data differs from its original prepared base')
        intent = self._intent(row, selected)
        key = self._key(row)
        previous = self.runs._receipt(conn, lease.project_id, lease.task_id, key, intent)
        if previous is not None:
            if previous != packet:
                raise RunConflict('Original branch acquisition already contains other data')
            return
        self.runs._save_receipt(conn, lease.project_id, lease.task_id, key, intent, packet)

    @classmethod
    def input(cls, conn, row, selected):
        """Read exact original acquired bytes for input; a pending selection can never be sent to a model as a completed snapshot."""
        from backend.runtime.sqlite_runs import SQLiteRunStore

        if not row['current_attempt_id']:
            raise RunConflict('Branch input requires its original preparation attempt')
        packet = SQLiteRunStore._receipt(conn, row['project_id'], row['task_id'], cls._key(row), cls._intent(row, selected))
        return cls._verify(selected, packet)


async def capture_branch(binding, prepared, selected, *, executor, timeout=30):
    """Read a complete exact binary tree diff through the original trusted owned Git port; no ambient subprocess, writes, ancestry guess or automatic application."""
    from backend.runtime.file_imports import selected_paths

    _source_identity(binding)
    if selected['snapshot']['source'] != asdict(binding):
        raise RunConflict('Branch selection belongs to another registered source')
    if type(timeout) not in (int, float) or not 0 < timeout <= 300:
        raise ValueError('Branch acquisition requires a bounded deadline')
    deadline = time.monotonic() + timeout
    environment = git_environment(Path('/home/actor'))
    source = Path(binding.workspace)

    async def git(*arguments):
        """Consume only complete closed Git output under one total deadline and the existing fixed credential-free policy."""
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RunConflict('Branch capture deadline expired before complete evidence')
        result = await executor.run((str(executor.git_binary), *_POLICY, *arguments), cwd=executor.execution_path(source), env=dict(environment), timeout=remaining)
        if not isinstance(result, GitResult) or not result.local_execution_closed or not result.output_complete:
            raise RunConflict('Branch capture output or original physical closure is unconfirmed')
        if result.exit_code != 0:
            raise RunConflict('Selected branch/commit is unavailable or changed; no inference was authorized')
        if not isinstance(result.stdout, bytes) or len(result.stdout) > MAX_OUTPUT_BYTES:
            raise InputTooLarge('Branch capture exceeds its complete output budget')
        return result.stdout

    async def sha(expression):
        """Resolve a complete immutable identity with replacement objects disabled by the shared environment."""
        value = (await git('rev-parse', '--verify', '--end-of-options', expression)).decode('ascii').strip()
        if not _SHA.fullmatch(value):
            raise RunConflict('Branch capture did not return a complete Git identity')
        return value

    branch = selected['snapshot']['origin']['recorded_branch']
    ref = branch if branch.startswith('refs/heads/') else 'refs/heads/' + branch
    await git('check-ref-format', ref)
    head = await sha(ref + '^{commit}')
    if head != selected['snapshot']['selected_commit_sha']:
        raise RunConflict('Selected branch commit changed; inspect its immutable identity before a new request')
    base = prepared.base_sha
    base_tree = await sha(base + '^{tree}')
    if base_tree != prepared.base_tree_sha:
        raise RunConflict('Original prepared base tree changed')
    tree = await sha(head + '^{tree}')
    names = await git('diff', '--name-only', '-z', '--no-renames', base, head, '--')
    try:
        paths = selected_paths(names[:-1].decode('utf-8').split('\0')) if names.endswith(b'\0') else (() if not names else None)
    except (ValueError, UnicodeError) as error:
        raise RunConflict('Branch paths are invalid, include reserved metadata or exceed the complete selection budget') from error
    if paths is None:
        raise RunConflict('Branch changed-path output is incomplete')
    diff = await git('diff', '--binary', '--full-index', '--no-ext-diff', '--no-textconv', '--no-renames', '--no-color', '--src-prefix=a/', '--dst-prefix=b/', base, head, '--')
    if len(diff) > 400000:
        raise InputTooLarge('Complete branch diff exceeds400000bytes; no changes were omitted')
    if await sha(ref + '^{commit}') != head:
        raise RunConflict('Selected branch commit changed during acquisition')
    _source_identity(binding)
    return _packet({
        'schema_version': 1, 'acquisition': 'captured', 'origin': selected['snapshot']['origin'],
        'source': asdict(binding), 'selection': selected['snapshot'], 'selection_sha256': selected['snapshot_sha256'],
        'original_input': None, 'original_input_status': 'unknown',
        'candidate': {'base_sha': base, 'base_tree_sha': base_tree, 'head_sha': head, 'tree_sha': tree},
        'comparison': 'complete_tree_difference_against_current_prepared_base_not_ancestry_or_intent',
        'changed_paths': list(paths), 'diff_base64': base64.b64encode(diff).decode('ascii'),
        'diff_bytes': len(diff), 'diff_sha256': hashlib.sha256(diff).hexdigest(),
    })
