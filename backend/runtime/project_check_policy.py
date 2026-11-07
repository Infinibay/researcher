"""Owner-controlled CI evidence policy for future acceptances, with recoverable original decisions."""

import json

from backend.knowledge.reviews import canonical
from backend.runtime.contracts import RunConflict, RunNotFound, command_key, identity

MAX_REVISION = 9007199254740991
CHECK_POLICY_MODES = {'require_tests', 'allow_missing'}


class ProjectCheckPolicies:
    """Serialize project policy revisions with acceptance transactions; never run checks or change accepted history."""

    def __init__(self, runs):
        """Reuse the owner store's scoped database transactions and durable events."""
        self.runs = runs

    @staticmethod
    def current(conn, project_id):
        """Return the explicit policy, or revision zero without implying an owner choice."""
        identity(project_id)
        if conn.execute('SELECT 1 FROM projects WHERE id=?', (project_id,)).fetchone() is None:
            raise RunNotFound('Project not found')
        row = conn.execute('SELECT revision,mode FROM runtime_project_check_policies WHERE project_id=?', (project_id,)).fetchone()
        return dict(row) if row else {'revision': 0, 'mode': None}

    def state(self, project_id):
        """Inspect a project decision without starting execution or altering task state."""
        with self.runs._transaction() as conn:
            return self.current(conn, project_id)

    def receipt(self, project_id, operation_key):
        """Recover only the exact original decision, independently of newer policy revisions."""
        command_key(operation_key)
        with self.runs._transaction() as conn:
            self.current(conn, project_id)
            row = conn.execute('SELECT receipt_json FROM runtime_project_check_policy_changes WHERE project_id=? AND operation_key=?', (project_id, operation_key)).fetchone()
            if row is None:
                raise RunNotFound('No hay recibo guardado para esta política de comprobaciones.')
            return json.loads(row[0])

    def update(self, project_id, *, operation_key, expected_revision, mode):
        """Commit a revision-checked choice and immutable receipt; identical retries preserve the original result."""
        command_key(operation_key)
        if type(expected_revision) is not int or not 0 <= expected_revision < MAX_REVISION:
            raise ValueError('Invalid check policy revision')
        if not isinstance(mode, str) or mode not in CHECK_POLICY_MODES:
            raise ValueError('Invalid check policy mode')
        request = {'expected_revision': expected_revision, 'mode': mode}
        encoded = canonical(request)
        with self.runs._transaction(write=True) as conn:
            policy = self.current(conn, project_id)
            previous = conn.execute('SELECT request_json,receipt_json FROM runtime_project_check_policy_changes WHERE project_id=? AND operation_key=?', (project_id, operation_key)).fetchone()
            if previous:
                if previous['request_json'] != encoded:
                    raise RunConflict('La operación identifica otra decisión de comprobaciones.')
                return json.loads(previous['receipt_json'])
            if policy['revision'] != expected_revision:
                raise RunConflict('La política cambió. Consulta la revisión vigente antes de decidir de nuevo.')
            receipt = {'project_id': project_id, 'operation_key': operation_key, **request,
                       'revision': expected_revision + 1, 'previous_policy': policy,
                       'actor_source': 'paired_owner_action', 'recorded_at': self.runs.clock(),
                       'inference_started': False, 'applies_to': 'future_code_acceptances'}
            conn.execute('INSERT INTO runtime_project_check_policies VALUES(?,?,?) ON CONFLICT(project_id) DO UPDATE SET revision=excluded.revision,mode=excluded.mode', (project_id, receipt['revision'], mode))
            conn.execute('INSERT INTO runtime_project_check_policy_changes VALUES(?,?,?,?)', (project_id, operation_key, encoded, canonical(receipt)))
            self.runs._event(conn, project_id, None, 'project.check_policy_changed', receipt)
            return receipt
