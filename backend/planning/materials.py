"""Bounded accepted-code artifacts for actual owner-authorized causal deliveries; old inputs are data, never new instructions or current source mutation."""

import base64
import hashlib
import json
from dataclasses import asdict

from backend.knowledge.reviews import canonical
from backend.runtime.code_reviews import CodeReviews
from backend.runtime.contracts import RunConflict


class PredecessorMaterials:
    """Resolve exact accepted predecessors from the original delivery and expose byte windows without recursively copying parent prompts or granting effects."""

    def __init__(self, runs):
        """Reuse original run transactions, current lease checks and existing accepted-subject validation."""
        self.runs = runs

    def _validated(self, conn, source, expected_source=None):
        """Require actual acceptance, exact candidate and current original context/closure; a supplied label or another repository cannot substitute."""
        accepted = conn.execute(
            'SELECT * FROM runtime_code_acceptances WHERE id=? AND run_id=? AND attempt_id=?',
            (source['acceptance']['id'], source['run_id'], source['attempt_id']),
        ).fetchone()
        if accepted is None or any(accepted[key] != source['acceptance'][key] for key in ('subject_sha256', 'review_sha256')):
            raise RunConflict('Original predecessor code acceptance differs from the delivery')
        subject, candidate = CodeReviews(self.runs)._subject(conn, accepted['project_id'], accepted['attempt_id'], allow_accepted=True)
        if (candidate['task_id'] != source['task_id'] or candidate['run_id'] != source['run_id']
            or candidate['context_version'] != source['context_version']
            or subject['subject_sha256'] != accepted['subject_sha256']
            or any(source['snapshot'][key] != candidate[key] for key in ('attempt_id', 'head_sha', 'tree_sha', 'diff_sha256'))):
            raise RunConflict('Original predecessor candidate or context changed')
        if expected_source is not None and json.loads(candidate['source_json']) != expected_source:
            raise RunConflict('Accepted predecessor code belongs to another registered source; explicit source selection is required')
        return subject, candidate

    def describe(self, conn, source, *, expected_source=None):
        """Return small exact byte/source descriptors; the author's complete original input is available separately rather than recursively inlined."""
        subject, candidate = self._validated(conn, source, expected_source)
        original = subject['snapshot']['author_input']
        return {
            'schema_version': 1, 'read_tool': 'researcher_prerequisite_code',
            'source': json.loads(candidate['source_json']), 'base_sha': candidate['base_sha'],
            'head_sha': candidate['head_sha'], 'tree_sha': candidate['tree_sha'],
            'sections': {
                'packet': {'sha256': subject['subject_sha256'], 'bytes': len(canonical(subject['snapshot']).encode())},
                'diff': {'sha256': candidate['diff_sha256'], 'bytes': len(candidate['diff'])},
                'author_input': {'status': 'recorded' if original is not None else 'unknown',
                                 'sha256': original['input_sha256'] if original else None,
                                 'bytes': original['bytes'] if original else None},
            },
            'current_task_authority': 'data_only', 'source_publication': 'not_implied',
        }

    def _bound(self, conn, lease):
        """Resolve only this consumer's delivery, or the exact original author of its independent review; callers cannot choose an arbitrary run."""
        from backend.planning.execution import PlanExecutions

        row = self.runs._authority(conn, lease)
        if row['execution_kind'] == 'code_review':
            request = CodeReviews(self.runs)._request(conn, lease.project_id, lease.run_id, require_current=True)
            row = self.runs._row(conn, lease.project_id, request['author_run_id'])
        packet = PlanExecutions(self.runs).input(conn, row)
        if packet is None:
            return None, None
        binding = conn.execute('SELECT * FROM runtime_workspace_bindings WHERE run_id=?', (row['id'],)).fetchone()
        if binding is None:
            raise RunConflict('Original causal consumer has no registered source')
        return packet, asdict(self.runs._binding_view(binding))

    def available(self, lease):
        """Offer the readonly capability only for an actual current causal code source; malformed/stale delivery is not silently ignored."""
        with self.runs._transaction() as conn:
            packet, binding = self._bound(conn, lease)
            if packet is None:
                return False
            sources = [source for source in packet['prerequisites'] if source['kind'] == 'accepted_code_candidate']
            for source in sources:
                self.describe(conn, source, expected_source=binding)
            return bool(sources)

    @staticmethod
    def _window(data, offset, max_bytes):
        """Return complete raw-hash identity and explicit byte coverage; a later page never claims that earlier ranges were read."""
        if type(offset) is not int or type(max_bytes) is not int or offset < 0 or not 1 <= max_bytes <= 16384 or offset > len(data):
            raise ValueError('Use a valid byte offset and a window of1to16384bytes')
        end = min(len(data), offset + max_bytes)
        return {'sha256': hashlib.sha256(data).hexdigest(), 'total_bytes': len(data),
                'encoding': 'base64', 'data_base64': base64.b64encode(data[offset:end]).decode('ascii'),
                'offset': offset, 'end_offset': end, 'next_offset': end if end < len(data) else None,
                'complete_material': offset == 0 and end == len(data)}

    def read(self, lease, task_id, section='packet', *, offset=0, max_bytes=16384):
        """Read exact bytes only from an accepted code dependency actually bound by the original owner delivery and current scope."""
        if type(task_id) is not int or task_id <= 0:
            raise ValueError('Select an actual prerequisite task identifier')
        with self.runs._transaction() as conn:
            packet, binding = self._bound(conn, lease)
            source = next((item for item in packet['prerequisites'] if item['task_id'] == task_id and item['kind'] == 'accepted_code_candidate'), None) if packet else None
            if source is None:
                raise RunConflict('This attempt has no owner-authorized accepted code delivery for that task')
            subject, candidate = self._validated(conn, source, binding)
            if section == 'packet':
                data = canonical(subject['snapshot']).encode()
            elif section == 'diff':
                data = bytes(candidate['diff'])
            elif section == 'author_input':
                expected = subject['snapshot']['author_input']
                original = conn.execute('SELECT input_text,input_sha256 FROM runtime_input_snapshots WHERE attempt_id=?', (source['attempt_id'],)).fetchone()
                if expected is None or original is None:
                    raise RunConflict('Original predecessor input is unknown; do not reconstruct it from a role or task label')
                data = original['input_text'].encode()
                if hashlib.sha256(data).hexdigest() != expected['input_sha256'] or original['input_sha256'] != expected['input_sha256']:
                    raise RunConflict('Original predecessor input differs from its captured hash')
            else:
                raise ValueError('Unknown accepted predecessor material section')
            return {'source': {'project_id': lease.project_id, 'task_id': task_id, 'run_id': source['run_id'],
                               'attempt_id': source['attempt_id'], 'subject_sha256': source['acceptance']['subject_sha256'],
                               'acceptance_id': source['acceptance']['id']},
                    'section': section, 'authority': 'data_only', 'current_task_acceptance': 'not_granted',
                    'source_publication': 'not_implied', **self._window(data, offset, max_bytes)}
