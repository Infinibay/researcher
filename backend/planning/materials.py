"""Bounded accepted code and research evidence for owner-authorized causal deliveries; historical inputs remain data, never new authority."""

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

    def _research_subject(self, conn, project_id, source):
        """Resolve the exact accepted documentary subject and recheck its evidence, original scope and current review identity."""
        from backend.knowledge.results import result_state

        accepted = conn.execute(
            'SELECT a.subject_sha256,a.review_sha256,p.snapshot_json FROM runtime_result_acceptances a '
            'JOIN runtime_result_proposals p ON p.id=a.proposal_id WHERE a.project_id=? AND a.run_id=? AND a.id=?',
            (project_id, source['run_id'], source['acceptance']['id']),
        ).fetchone()
        if accepted is None or any(accepted[key] != source['acceptance'][key] for key in ('subject_sha256', 'review_sha256')):
            raise RunConflict('Original predecessor research acceptance differs from the delivery')
        subject = json.loads(accepted['snapshot_json'])
        if (hashlib.sha256(canonical(subject).encode()).hexdigest() != accepted['subject_sha256']
            or subject['scope']['project_id'] != project_id
            or any(subject['scope'][key] != source[key] for key in ('task_id', 'run_id', 'attempt_id', 'actor_id', 'context_version'))):
            raise RunConflict('Original predecessor research subject or scope changed')
        current = result_state(conn, project_id, source['run_id'])
        if (not current['acceptance_current']
            or current['candidate']['candidate_sha256'] != accepted['subject_sha256']
            or current['acceptance']['acceptance_id'] != source['acceptance']['id']):
            raise RunConflict('Accepted predecessor research evidence or review is no longer current')
        return subject

    @staticmethod
    def _research_input(conn, source):
        """Read only an actually frozen author input and verify its bytes; missing historical input is explicitly unknown."""
        original = conn.execute('SELECT input_text,input_sha256 FROM runtime_input_snapshots WHERE attempt_id=?', (source['attempt_id'],)).fetchone()
        if original is None:
            return None
        data = original['input_text'].encode()
        if hashlib.sha256(data).hexdigest() != original['input_sha256']:
            raise RunConflict('Original predecessor research input differs from its captured hash')
        return data

    def describe_research(self, conn, project_id, source):
        """Describe complete accepted evidence and report bytes without inlining large text; all limitations remain available in the exact packet."""
        subject = self._research_subject(conn, project_id, source)
        original = self._research_input(conn, source)
        return {
            'schema_version': 1, 'read_tool': 'researcher_prerequisite_research',
            'sections': {
                'packet': {'sha256': source['acceptance']['subject_sha256'], 'bytes': len(canonical(subject).encode())},
                'author_input': {'status': 'recorded' if original is not None else 'unknown',
                                 'sha256': hashlib.sha256(original).hexdigest() if original is not None else None,
                                 'bytes': len(original) if original is not None else None},
            },
            'reports': [{'artifact_id': report['artifact_id'], 'sha256': report['content_sha256'],
                         'bytes': len(report['content'].encode())} for report in subject['reports']],
            'scientific_confidence': None, 'current_task_authority': 'data_only',
            'current_task_acceptance': 'not_granted', 'source_publication': 'not_implied',
        }

    def _bound(self, conn, lease):
        """Resolve only this consumer's delivery, or the exact original author of its independent review; callers cannot choose an arbitrary run."""
        from backend.planning.execution import PlanExecutions

        row = self.runs._authority(conn, lease)
        from backend.planning.manual_prerequisites import causal_source_row

        row=causal_source_row(conn,row)
        packet = PlanExecutions(self.runs).input(conn, row)
        if packet is None:
            from backend.planning.manual_prerequisites import ManualPrerequisites

            packet=ManualPrerequisites(self.runs).input(conn,row)
            if packet is None:
                return None, None
        binding = conn.execute('SELECT * FROM runtime_workspace_bindings WHERE run_id=?', (row['id'],)).fetchone()
        if binding is None and packet.get('kind')!='manual_task_prerequisites':
            raise RunConflict('Original causal consumer has no registered source')
        if binding is None and any(source['kind']=='accepted_code_candidate' for source in packet['prerequisites']):
            raise RunConflict('Accepted code prerequisites require a registered consumer source')
        return packet, asdict(self.runs._binding_view(binding)) if binding else None

    def available(self, lease):
        """Offer readonly material tools for actual current causal sources; malformed or stale deliveries are never silently ignored."""
        with self.runs._transaction() as conn:
            packet, binding = self._bound(conn, lease)
            if packet is None:
                return False
            sources = packet['prerequisites']
            for source in sources:
                if source['kind'] == 'accepted_code_candidate':
                    self.describe(conn, source, expected_source=binding)
                elif source['kind'] == 'accepted_research_reports':
                    self.describe_research(conn, lease.project_id, source)
            return bool(sources) or packet['schema_version'] >= 5

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

    def read_research(self, lease, task_id, section='packet', *, report_id=None, path=(), mode='read', child_offset=0, offset=0, max_bytes=16384):
        """Read exact documentary bytes only through this attempt's bound predecessor, revalidating acceptance and evidence on every window."""
        from backend.planning.material_views import select_material

        if type(task_id) is not int or task_id <= 0:
            raise ValueError('Select an actual prerequisite task identifier')
        if section not in ('packet', 'report', 'author_input'):
            raise ValueError('Unknown accepted research material section')
        if section == 'report':
            if type(report_id) is not int or report_id <= 0:
                raise ValueError('Select an accepted report artifact identifier')
        elif report_id is not None:
            raise ValueError('A report identifier is only valid for the report section')
        if section != 'packet' and (path or mode != 'read' or child_offset):
            raise ValueError('JSON selection and inspection apply only to the accepted packet section')
        with self.runs._transaction() as conn:
            packet, _binding = self._bound(conn, lease)
            source = next((item for item in packet['prerequisites'] if item['task_id'] == task_id and item['kind'] == 'accepted_research_reports'), None) if packet else None
            if source is None:
                raise RunConflict('This attempt has no owner-authorized accepted research delivery for that task')
            subject = self._research_subject(conn, lease.project_id, source)
            if section == 'packet':
                data = select_material(subject, path=path, mode=mode, child_offset=child_offset)
            elif section == 'author_input':
                data = self._research_input(conn, source)
                if data is None:
                    raise RunConflict('Original predecessor input is unknown; do not reconstruct it from a role or task label')
            else:
                report = next((item for item in subject['reports'] if item['artifact_id'] == report_id), None)
                if report is None:
                    raise RunConflict('The report is not part of this accepted prerequisite')
                data = report['content'].encode()
                if hashlib.sha256(data).hexdigest() != report['content_sha256']:
                    raise RunConflict('Original predecessor report differs from its captured hash')
            window = self._window(data, offset, max_bytes)
            return {'source': {'project_id': lease.project_id, 'task_id': task_id, 'run_id': source['run_id'],
                               'attempt_id': source['attempt_id'], 'subject_sha256': source['acceptance']['subject_sha256'],
                               'acceptance_id': source['acceptance']['id']},
                    'section': section, 'report_id': report_id, 'authority': 'data_only',
                    'current_task_acceptance': 'not_granted', 'source_publication': 'not_implied',
                    'selection': {'path': list(path), 'mode': mode, 'whole_section_read': not path and mode == 'read' and window['complete_material']},
                    **window}

    def read_work(self, lease, section, *, path=(), mode='read', child_offset=0, offset=0, max_bytes=16384):
        """Read selected original plan or continuation evidence from this consumer's immutable delivery, rechecking owner decisions and closure before every read."""
        from backend.planning.material_views import WORK_SECTIONS, describe_value, select_material

        if section not in WORK_SECTIONS:
            raise ValueError('Select plan_context, continuation or reauthorization')
        with self.runs._transaction() as conn:
            packet, _binding = self._bound(conn, lease)
            if packet is None or section not in packet:
                raise RunConflict('This attempt has no owner-authorized delivery section of that kind')
            value = packet[section]
            data = select_material(value, path=path, mode=mode, child_offset=child_offset)
            window = self._window(data, offset, max_bytes)
            return {
                'source': {'project_id': lease.project_id, 'delivery_id': packet['delivery_id'],
                           'execution_id': packet['execution_id'], 'target': packet['target'],
                           'delivery_packet_sha256': describe_value(packet)['sha256'],
                           'section_sha256': describe_value(value)['sha256']},
                'section': section, 'authority': 'attributed_context', 'current_task_acceptance': 'not_granted',
                'selection': {'path': list(path), 'mode': mode, 'whole_section_read': not path and mode == 'read' and window['complete_material']},
                **window,
            }
