"""Atomic owner-note receipts reuse task metadata without granting native work authority.

The existing metadata_json column retains the original request and response next
to its note. Supported owner/native APIs only append comments; task deletion
removes its notes and a later retry fails with the absent original task. No
historical row is rewritten or treated as a recoverable keyed owner request.
"""

import json
from uuid import uuid4

from backend.runtime.contracts import RunConflict, RunNotFound, command_key, identity


class TaskComments:
    """Own scoped append/deduplication in the existing source-store transaction."""

    def __init__(self, runs):
        """Bind the same source transaction boundary used by task metadata writers."""
        self.runs = runs

    @staticmethod
    def _project(conn, task_id, expected=None):
        """Derive the original project from the task and reject a mismatched captured scope."""
        identity(task_id)
        row = conn.execute('SELECT project_id FROM tasks WHERE id=?', (task_id,)).fetchone()
        if row is None or (expected is not None and expected != row['project_id']):
            raise RunNotFound('La tarea no pertenece al proyecto de este comentario.')
        return row['project_id']

    @staticmethod
    def _response(row, project_id, operation_key=None):
        """Expose note data and exact recovery identity without publishing private metadata."""
        return {**{name: row[name] for name in ('id', 'task_id', 'author', 'comment_type', 'content', 'created_at')},
                'project_id': project_id, 'operation_key': operation_key, 'authorizes_work': False}

    def list(self, task_id):
        """Read chronological notes; historical labels and metadata never accept native results."""
        with self.runs._transaction() as conn:
            project = self._project(conn, task_id)
            return [self._response(row, project) for row in conn.execute(
                'SELECT * FROM task_comments WHERE task_id=? ORDER BY created_at,id', (task_id,))]

    def create(self, task_id, *, author, content, comment_type, project_id=None, operation_key=None):
        """Return the immutable original receipt or append one advisory note and its receipt atomically.

        A legacy caller without a key creates an independent note each time. New
        clients capture a key and project before delivery; retries must preserve
        every literal field. BEGIN IMMEDIATE serializes lookup and append across
        independent handles, without relying on a process-local cache or lock.
        """
        key = operation_key if operation_key is not None else uuid4().hex
        command_key(key)
        if not isinstance(content, str) or not content.strip() or len(content) > 50000:
            raise ValueError('El comentario necesita texto de hasta50000caracteres.')
        if not isinstance(author, str) or not 1 <= len(author) <= 128:
            raise ValueError('Etiqueta de autor no válida.')
        if comment_type not in {'comment', 'change_request', 'approval', 'question', 'answer'}:
            raise ValueError('Tipo de comentario no válido.')
        with self.runs._transaction(write=True) as conn:
            project = self._project(conn, task_id, project_id)
            intent = dict(project_id=project, task_id=task_id, author=author, content=content, comment_type=comment_type)
            rows = conn.execute("""SELECT metadata_json FROM task_comments WHERE task_id=? AND
                CASE WHEN json_valid(metadata_json) THEN json_extract(metadata_json,'$.owner_comment.operation_key') END=?""", (task_id, key)).fetchall()
            if rows:
                if len(rows) != 1:
                    raise RunConflict('El recibo original requiere revisión; no se añadió otro comentario.')
                original = json.loads(rows[0]['metadata_json'])['owner_comment']
                if original['intent'] != intent:
                    raise RunConflict('La clave original pertenece a otro comentario; se conserva su contenido.')
                return original['receipt']
            cursor = conn.execute('INSERT INTO task_comments(task_id,author,comment_type,content) VALUES(?,?,?,?)',
                                  (task_id, author, comment_type, content))
            row = conn.execute('SELECT * FROM task_comments WHERE id=?', (cursor.lastrowid,)).fetchone()
            receipt = self._response(row, project, key)
            conn.execute('UPDATE task_comments SET metadata_json=? WHERE id=?',
                         (json.dumps({'owner_comment': {'operation_key': key, 'intent': intent, 'receipt': receipt}}, ensure_ascii=False), row['id']))
            return receipt
