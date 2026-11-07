"""Journal owner attachment mutations before filesystem work and recover only their original scoped intent.

No automatic filesystem retry, overwrite, inference or orphan deletion occurs.
Interrupted uploads retain a named operation even when their bytes are incomplete.
Deletion removes metadata and records its intent atomically before unlinking bytes.
"""

import hashlib
import json
import re
import time
from uuid import uuid4

from backend.research.models import OperationConflict, ReferenceRecord, ResearchNotFound


def _json(value):
    """Encode exact intent and receipt data deterministically for duplicate-request comparison."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'))


class ReferenceOperations:
    """Own durable upload/delete receipts while preserving the existing scoped file readers."""

    def __init__(self, connection, storage):
        """Bind the serving connection context and confined storage without creating directories."""
        self.connection = connection
        self.storage = storage

    @staticmethod
    def _row(conn, project_id, key):
        """Resolve an operation only inside its original project; keys are never global authority."""
        row = conn.execute('SELECT * FROM reference_file_operations WHERE project_id=? AND operation_key=?', (project_id, key)).fetchone()
        if row is None:
            raise ResearchNotFound('Attachment operation not found in this project')
        return row

    @staticmethod
    def _view(row):
        """Expose owner-readable history without treating a pending operation as a published attachment."""
        intent = json.loads(row['request_json'])
        return {'project_id': row['project_id'], 'operation_key': row['operation_key'],
                'kind': row['kind'], 'state': row['state'], 'reference_id': row['reference_id'],
                'filename': intent['filename'], 'created_at': row['created_at'], 'updated_at': row['updated_at'],
                'receipt': json.loads(row['receipt_json']) if row['receipt_json'] else None}

    def history(self, project_id, *, limit=50, offset=0):
        """Read bounded, stable operation history; inspection never completes or repeats an effect."""
        with self.connection() as conn:
            return [self._view(row) for row in conn.execute(
                'SELECT * FROM reference_file_operations WHERE project_id=? ORDER BY created_at DESC,operation_key LIMIT ? OFFSET ?',
                (project_id, limit, offset),
            )]

    def _reference(self, row):
        """Resolve a relative operation path against the current configured root, including a restored installation."""
        intent = json.loads(row['request_json'])
        reference = ReferenceRecord(row['reference_id'] or 1, row['project_id'], intent['filename'],
                                    str(self.storage.root / row['relative_path']), intent.get('mime_type') or 'application/octet-stream')
        self.storage._parts(reference)
        return reference

    def upload(self, project_id, filename, content, mime_type, description, *, operation_key=None):
        """Admit the exact owner upload before writing bytes; duplicate keys recover without writing again."""
        key = uuid4().hex if operation_key is None else operation_key
        if not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', key) or key.startswith('delete:'):
            raise ValueError('Invalid attachment operation key')
        if len(content) > 1000000:
            raise ValueError('Attachment exceeds its admitted byte limit')
        intent = {'filename': filename, 'size': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                  'mime_type': mime_type, 'description': description}
        created = False
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            if conn.execute('SELECT 1 FROM projects WHERE id=?', (project_id,)).fetchone() is None:
                raise ResearchNotFound('Project not found')
            row = conn.execute('SELECT * FROM reference_file_operations WHERE project_id=? AND operation_key=?', (project_id, key)).fetchone()
            if row is not None:
                if row['kind'] != 'upload' or row['request_json'] != _json(intent):
                    raise OperationConflict('La clave ya pertenece a otra carga; consulta su operación original.')
            else:
                relative = f'{project_id}/uploads/{uuid4().hex}'
                now = time.time()
                conn.execute("INSERT INTO reference_file_operations(project_id,operation_key,kind,state,request_json,relative_path,created_at,updated_at) VALUES(?,?,'upload','pending',?,?,?,?)", (project_id,key,_json(intent),relative,now,now))
                row = self._row(conn, project_id, key)
                created = True
        if created:
            self.storage.save(project_id, content, name=row['relative_path'].split('/')[-1])
        result = self.reconcile(project_id, key)
        if result['state'] != 'published':
            raise OperationConflict('La carga fue cerrada sin publicar; sus restos se conservan en el historial.')
        return result['receipt']

    def delete(self, project_id, file_id):
        """Commit the original delete intent and metadata removal together before touching file bytes."""
        key = f'delete:{file_id}'
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            previous = conn.execute('SELECT * FROM reference_file_operations WHERE project_id=? AND operation_key=?', (project_id,key)).fetchone()
            if previous is not None and (previous['kind'] != 'delete' or previous['reference_id'] != file_id):
                raise OperationConflict('La operación original no corresponde a este borrado.')
            if previous is None:
                file = conn.execute('SELECT * FROM reference_files WHERE id=? AND project_id=?', (file_id,project_id)).fetchone()
                if file is None:
                    raise ResearchNotFound('Attachment not found in this project')
                reference = ReferenceRecord(file_id,project_id,file['file_name'],file['file_path'],file['file_type'] or 'application/octet-stream')
                relative = '/'.join(self.storage._parts(reference))
                intent = {'filename': file['file_name'], 'mime_type': file['file_type'],
                          'identity': self.storage.identity(reference)}
                now = time.time()
                conn.execute("INSERT INTO reference_file_operations(project_id,operation_key,kind,state,request_json,relative_path,reference_id,created_at,updated_at) VALUES(?,?,'delete','pending',?,?,?,?,?)", (project_id,key,_json(intent),relative,file_id,now,now))
                conn.execute('DELETE FROM reference_files WHERE id=? AND project_id=?', (file_id,project_id))
        return self.reconcile(project_id, key)

    def reconcile(self, project_id, key):
        """Complete only verified original bytes or the original deletion; completed receipts never resurrect references."""
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = self._row(conn, project_id, key)
            if row['state'] != 'pending':
                return self._view(row)
            intent = json.loads(row['request_json'])
            reference = self._reference(row)
            if row['kind'] == 'upload':
                self.storage.confirm(reference, size=intent['size'], sha256=intent['sha256'])
                cursor = conn.execute('INSERT INTO reference_files(project_id,file_name,file_path,file_size,file_type,description) VALUES(?,?,?,?,?,?)',
                                      (project_id,intent['filename'],reference.path,intent['size'],intent['mime_type'],intent['description']))
                record = conn.execute('SELECT id,project_id,file_name AS filename,file_path AS filepath,file_size,file_type AS mime_type,description,uploaded_at FROM reference_files WHERE id=?', (cursor.lastrowid,)).fetchone()
                conn.execute("UPDATE reference_file_operations SET state='published',reference_id=?,receipt_json=?,updated_at=? WHERE project_id=? AND operation_key=?", (cursor.lastrowid,_json(dict(record)),time.time(),project_id,key))
            else:
                self.storage.remove(reference, expected_identity=intent['identity'])
                conn.execute("UPDATE reference_file_operations SET state='deleted',updated_at=? WHERE project_id=? AND operation_key=?", (time.time(),project_id,key))
            return self._view(self._row(conn, project_id, key))

    def abandon(self, project_id, key):
        """Close an unpublished upload without deleting its uncertain retained bytes or permitting later publication."""
        with self.connection() as conn:
            conn.execute('BEGIN IMMEDIATE')
            row = self._row(conn, project_id, key)
            if row['state'] == 'abandoned':
                return self._view(row)
            if row['kind'] != 'upload' or row['state'] != 'pending':
                raise OperationConflict('Sólo se puede cerrar una carga que todavía no fue publicada.')
            conn.execute("UPDATE reference_file_operations SET state='abandoned',updated_at=? WHERE project_id=? AND operation_key=?", (time.time(),project_id,key))
            return self._view(self._row(conn, project_id, key))
