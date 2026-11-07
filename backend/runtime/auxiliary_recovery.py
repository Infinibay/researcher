"""Owner-visible local calculation history and explicit successor permission, without replay or refunds."""

import hashlib
import json
import re

from backend.runtime.auxiliary_execution import process_state
from backend.runtime.contracts import RunConflict, RunNotFound, identity, text


class AuxiliaryRecovery:
    """Keep immutable uncertain work and give each explicit owner decision at most one identical successor."""

    def __init__(self, runs):
        """Reuse the host's SQLite store; this service neither starts nor terminates any worker."""
        self.runs=runs

    @staticmethod
    def _project(conn, project_id):
        """Reject absent project scope before inspecting receipts or process metadata."""
        identity(project_id)
        if conn.execute('SELECT 1 FROM projects WHERE id=?',(project_id,)).fetchone() is None:raise RunNotFound('Project not found')

    @staticmethod
    def _diagnosis(conn, row):
        """Separate reusable evidence, active ownership and verified closure without exposing private process data."""
        def result(code, message, allowed=False):
            """Return a user-facing explanation with a machine-readable continuation decision."""
            return {'code':code,'message':message,'can_continue':allowed}
        if row['has_output']:return result('complete','El resultado guardado puede recuperarse sin otro cálculo.')
        if conn.execute('SELECT 1 FROM runtime_auxiliary_continuations WHERE project_id=? AND source_operation_id=?',(row['project_id'],row['operation_id'])).fetchone():
            return result('authorized','Ya autorizaste una sucesora. La próxima solicitud idéntica puede usarla; consulta su registro si ya se ejecutó.')
        record=conn.execute('SELECT * FROM runtime_auxiliary_executions WHERE project_id=? AND operation_id=?',(row['project_id'],row['operation_id'])).fetchone()
        if record is None:return result('identity_unavailable','Este registro antiguo no tiene identidad de proceso. Hace falta reconciliar el cierre de la instalación; no se puede autorizar desde aquí.')
        if record['phase']=='closed' and row['status']=='unknown':return result('ready','El trabajador terminó sin resultado recuperable. Puedes autorizar un nuevo cálculo conservando el consumo anterior.',True)
        try:owner=process_state(json.loads(record['owner_json']))
        except (ValueError,TypeError):owner='unknown'
        if owner=='alive':return result('running','El proceso original sigue activo. Espera su resultado o solicita su detención desde el control correspondiente.')
        if owner=='unknown':return result('closure_unknown','No se pudo comprobar la identidad del proceso original. Conservamos su reserva; hace falta reconciliar el cierre de la instalación.')
        if record['phase'] in ('closed','reserved'):return result('ready','Se comprobó que el dueño anterior terminó. Una nueva solicitud requiere tu autorización y otra reserva de consumo.',True)
        if record['phase']=='worker':
            try:worker=process_state(json.loads(record['worker_json']))
            except (ValueError,TypeError):worker='unknown'
            if worker=='closed':return result('ready','Se comprobó el cierre del dueño y del trabajador originales. Puedes autorizar una sucesora conservando ambas reservas.',True)
            if worker=='alive':return result('running','El trabajador original todavía está activo aunque su dueño terminó. Espera su cierre; no se iniciará otro.')
        return result('closure_unknown','La creación quedó interrumpida sin prueba suficiente del cierre del trabajador. Hace falta reconciliar el cierre de la instalación; no se repetirá automáticamente.')

    @staticmethod
    def _columns():
        """Select bounded metadata only, excluding original result blobs and host identity details."""
        return 'rowid AS sequence,project_id,operation_id,kind,input_bytes,attempt_id,status,observed_cpu_ms,cpu_ceiling_ms,created_at,finished_at,output IS NOT NULL AS has_output'

    def list(self, project_id, *, before=None, limit=20):
        """Page actual original operations and their current observed recoverability without modifying history."""
        if type(limit) is not int or not 1<=limit<=100:raise ValueError('Invalid page size')
        if before is not None and (type(before) is not int or before<1):raise ValueError('Invalid history cursor')
        with self.runs._transaction() as conn:
            self._project(conn,project_id)
            rows=conn.execute(f'SELECT {self._columns()} FROM runtime_auxiliary_work WHERE project_id=? AND (? IS NULL OR rowid<?) ORDER BY rowid DESC LIMIT ?',(project_id,before,before,limit+1)).fetchall()
            items=[{**dict(row),'diagnosis':self._diagnosis(conn,row)} for row in rows[:limit]]
            return {'project_id':project_id,'items':items,'next_before':items[-1]['sequence'] if len(rows)>limit else None}

    @staticmethod
    def _key(value):
        """Use the existing owner-command key alphabet without accepting an ambiguous or empty key."""
        if not isinstance(value,str) or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}',value):raise ValueError('Invalid operation key')

    def receipt(self, project_id, operation_key):
        """Recover the exact original permission after response loss, without resending or updating it."""
        self._key(operation_key)
        with self.runs._transaction() as conn:
            self._project(conn,project_id)
            row=conn.execute('SELECT receipt_json FROM runtime_auxiliary_continuations WHERE project_id=? AND operation_key=?',(project_id,operation_key)).fetchone()
            if row is None:raise RunNotFound('No se encontró el recibo original de esta autorización.')
            return json.loads(row['receipt_json'])

    def authorize(self, project_id, *, operation_key, source_operation_id, reason=''):
        """Authorize one exact successor only after fresh closure checks; capacity and current grants are checked later at execution."""
        self._key(operation_key)
        if not isinstance(source_operation_id,str) or not re.fullmatch('[0-9a-f]{64}',source_operation_id):raise ValueError('Invalid original calculation')
        if not isinstance(reason,str) or len(reason.encode())>2000:raise ValueError('Invalid continuation reason')
        request={'operation_key':operation_key,'source_operation_id':source_operation_id,'reason':reason}
        encoded=json.dumps(request,sort_keys=True)
        with self.runs._transaction(write=True) as conn:
            self._project(conn,project_id)
            prior=conn.execute('SELECT * FROM runtime_auxiliary_continuations WHERE project_id=? AND operation_key=?',(project_id,operation_key)).fetchone()
            if prior:
                if prior['request_json']!=encoded:raise RunConflict('Esta identidad corresponde a otra decisión original.')
                return json.loads(prior['receipt_json'])
            row=conn.execute(f'SELECT {self._columns()} FROM runtime_auxiliary_work WHERE project_id=? AND operation_id=?',(project_id,source_operation_id)).fetchone()
            if row is None:raise RunNotFound('No se encontró el cálculo original en este proyecto.')
            diagnosis=self._diagnosis(conn,row)
            if not diagnosis['can_continue']:raise RunConflict(diagnosis['message'])
            parent=conn.execute('SELECT root_operation_id,generation FROM runtime_auxiliary_continuations WHERE project_id=? AND successor_operation_id=?',(project_id,source_operation_id)).fetchone()
            root=parent['root_operation_id'] if parent else source_operation_id
            generation=parent['generation']+1 if parent else 1
            successor=hashlib.sha256(f'{root}:continuation:{generation}'.encode()).hexdigest()
            receipt={**request,'project_id':project_id,'root_operation_id':root,'successor_operation_id':successor,
                     'generation':generation,'work_started':False,'prior_cpu_ceiling_ms':row['cpu_ceiling_ms'],
                     'diagnosis_at_decision':diagnosis,'created_at':self.runs.clock()}
            conn.execute('INSERT INTO runtime_auxiliary_continuations VALUES(?,?,?,?,?,?,?,?,?)',
                         (project_id,operation_key,source_operation_id,successor,root,generation,encoded,json.dumps(receipt),receipt['created_at']))
            return receipt
