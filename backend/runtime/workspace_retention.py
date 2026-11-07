"""Owner-selected quarantine, recovery archives and recoverable removal of closed native attempt data.

History and filesystem availability are separate. Quarantine never changes the
original execution view, and restored bytes never inherit old grants or acceptance.
"""

import json
import os
from pathlib import Path
from uuid import uuid4

from backend.runtime.bootstrap import _sync_directory
from backend.runtime.contracts import RunConflict, RunNotFound, command_key, identity
from backend.runtime.development_state import DevelopmentWorkspaces
from backend.runtime.retention_files import (CopyBudget, copy_snapshot, directory, encoded, fingerprint, git_changes,
                                           matches_directory, move_new, new_directory, remove_original, sealed_inventory, verify_copy)

ACTIVE = ('queued','running','cancelling','reconciling','waiting_input')


class WorkspaceRetention:
    """Journal original owner decisions and run bounded filesystem effects through an explicitly supplied trusted closure observer."""

    def __init__(self, runs, control_root, source_root, *, closed):
        """Capture configured private roots and the host closure port; HTTP cannot provide paths or witnesses."""
        self.runs=runs;self.control=directory(control_root,private=False);self.sources=directory(source_root,private=False);self.closed=closed

    def _roots(self):
        """Reject a replaced control/source root before any local effect or archive lookup."""
        matches_directory(self.control['path'],self.control);matches_directory(self.sources['path'],self.sources)

    @staticmethod
    def _view(row):
        """Expose bounded owner history and immutable receipts, excluding manifest internals and closure witnesses."""
        return {key:row[key] for key in ('project_id','attempt_id','operation_key','kind','state','issue','created_at','updated_at')} | {'receipt':json.loads(row['receipt_json']) if row['receipt_json'] else None}

    @staticmethod
    def _operation(conn, project_id, key):
        """Resolve only one original project-scoped operation; names and later choices cannot substitute for it."""
        row=conn.execute('SELECT * FROM workspace_retention_operations WHERE project_id=? AND operation_key=?',(project_id,key)).fetchone()
        if row is None:raise RunNotFound('No se encontró esa operación de conservación en el proyecto.')
        return dict(row)

    @staticmethod
    def _record(conn, project_id, attempt_id):
        """Require the exact original retained attempt inside its project."""
        row=conn.execute('SELECT * FROM workspace_retention WHERE project_id=? AND attempt_id=?',(project_id,attempt_id)).fetchone()
        if row is None:raise RunNotFound('La copia no está en cuarentena en este proyecto.')
        return dict(row)

    def _prior(self, conn, project_id, key, intent):
        """Return an existing original decision only when every owner-selected input is identical."""
        row=conn.execute('SELECT * FROM workspace_retention_operations WHERE project_id=? AND operation_key=?',(project_id,key)).fetchone()
        if row is None:return None
        if row['intent_json']!=encoded(intent):raise RunConflict('La misma operación ya contiene otra decisión; consulta su recibo.')
        return self._view(row)

    def _insert(self, conn, project_id, attempt_id, key, kind, intent, *, operation_id=None, work=None):
        """Persist the original effect intent before starting any copy, move, deletion or restoration."""
        now=self.runs.clock();operation_id=operation_id or str(uuid4())
        conn.execute('INSERT INTO workspace_retention_operations(id,project_id,attempt_id,operation_key,kind,intent_json,work_json,state,created_at,updated_at) VALUES(?,?,?,?,?,?,?,\'pending\',?,?)',
                     (operation_id,project_id,attempt_id,key,kind,encoded(intent),encoded(work) if work else None,now,now))
        return self._view(self._operation(conn,project_id,key))

    def _idle(self, conn, workspace):
        """Refuse active task consumers and require actual original closure under the same lock that excludes new dependent admissions."""
        if conn.execute("SELECT 1 FROM runtime_runs WHERE project_id=? AND task_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input') LIMIT 1",(workspace['project_id'],workspace['task_id'])).fetchone():
            raise RunConflict('Esta tarea todavía tiene trabajo activo o pendiente de reconciliar. Conserva sus copias hasta resolverlo.')
        return self.closed(conn,workspace)

    def quarantine(self, project_id, attempt_id, key, *, retention_days, acknowledge_unavailability):
        """Atomically fence new use of one closed allocation, keeping its original path and requiring an explicit retention period."""
        identity(project_id);command_key(key)
        if type(retention_days) is not int or not 1<=retention_days<=3650 or acknowledge_unavailability is not True:
            raise ValueError('Elige de1a3650días y reconoce que la copia dejará de estar disponible para publicar o reutilizar.')
        intent={'attempt_id':attempt_id,'kind':'archive','retention_days':retention_days,'acknowledge_unavailability':True}
        with self.runs._transaction(write=True) as conn:
            prior=self._prior(conn,project_id,key,intent)
            if prior is not None:return prior,False
            self._roots();workspace=DevelopmentWorkspaces._row(conn,project_id,attempt_id)
            existing=conn.execute('SELECT * FROM workspace_retention WHERE attempt_id=?',(attempt_id,)).fetchone()
            if existing and existing['state'] in ('removing','removed'):
                raise RunConflict('Hay un borrado original registrado; reconcilia esa operación antes de otra decisión.')
            proof=self._idle(conn,workspace)
            expected=Path(self.control['path'])/'development'/workspace['run_id']/attempt_id
            if str(expected)!=workspace['allocation']:raise RunConflict('La asignación no pertenece a esta instalación.')
            root=directory(expected);parent=directory(expected.parent)
            if existing:
                original=json.loads(existing['original_json']);matches_directory(expected,original['root'])
            else:
                original={'workspace':workspace,'root':root,'parent':parent,'control':self.control,'closure':proof}
            now=self.runs.clock();operation_id=str(uuid4())
            if existing:
                conn.execute("UPDATE workspace_retention_operations SET state='superseded',receipt_json=?,updated_at=? WHERE attempt_id=? AND kind='archive' AND state='pending'",(encoded({'superseded_by':key,'bytes_deleted':False}),now,attempt_id))
                conn.execute("UPDATE workspace_retention SET state='quarantined',archive_id=?,archive_sha256=NULL,manifest_json=NULL,retain_until=?,updated_at=? WHERE attempt_id=?",(operation_id,now+retention_days*86400,now,attempt_id))
            else:
                conn.execute("INSERT INTO workspace_retention(attempt_id,project_id,task_id,original_json,state,archive_id,retain_until,created_at,updated_at) VALUES(?,?,?,?,'quarantined',?,?,?,?)",(attempt_id,project_id,workspace['task_id'],encoded(original),operation_id,now+retention_days*86400,now,now))
            conn.execute("UPDATE runtime_development_workspaces SET state='quarantined',updated_at=? WHERE attempt_id=?",(now,attempt_id))
            self.runs._event(conn,project_id,workspace['task_id'],'workspace.quarantined',{'attempt_id':attempt_id,'operation_key':key,'retention_days':retention_days})
            return self._insert(conn,project_id,attempt_id,key,'archive',intent,operation_id=operation_id),True

    def request(self, project_id, attempt_id, key, kind, archive_sha256):
        """Admit removal only after retention, or a new-data restore; preserve the exact selected archive across later decisions."""
        identity(project_id);command_key(key)
        if kind not in ('remove','restore'):raise ValueError('Operación de conservación desconocida.')
        intent={'attempt_id':attempt_id,'kind':kind,'archive_sha256':archive_sha256}
        with self.runs._transaction(write=True) as conn:
            prior=self._prior(conn,project_id,key,intent)
            if prior is not None:return prior,False
            record=self._record(conn,project_id,attempt_id)
            if not record['manifest_json'] or record['archive_sha256']!=archive_sha256:
                raise RunConflict('El archivo observado cambió o todavía no se verificó; actualiza su estado.')
            if kind=='remove':
                if record['state']!='retained':raise RunConflict('La copia ya tiene una operación de borrado; consulta el historial.')
                if self.runs.clock()<record['retain_until']:raise RunConflict('El período de retención todavía no terminó.')
                original=json.loads(record['original_json']);self._roots();matches_directory(original['root']['path'],original['root'])
                self._idle(conn,original['workspace'])
                conn.execute("UPDATE workspace_retention SET state='removing',updated_at=? WHERE attempt_id=?",(self.runs.clock(),attempt_id))
            work={'archive_id':record['archive_id'],'manifest':json.loads(record['manifest_json']),'archive_sha256':archive_sha256,'original':json.loads(record['original_json'])}
            return self._insert(conn,project_id,attempt_id,key,kind,intent,work=work),True

    def operation(self, project_id, key):
        """Read one original receipt without running a pending effect."""
        with self.runs._transaction() as conn:return self._view(self._operation(conn,project_id,key))

    def operations(self, project_id, *, offset=0, limit=100):
        """Page owner history without truncating it into an implication that no other operations exist."""
        with self.runs._transaction() as conn:
            return [self._view(row) for row in conn.execute('SELECT * FROM workspace_retention_operations WHERE project_id=? ORDER BY created_at DESC,rowid DESC LIMIT ? OFFSET ?',(project_id,limit,offset))]

    def list(self, project_id, *, offset=0, limit=100):
        """Show original native copies, documentary availability and retained archive metadata; listing never executes Git or cleanup."""
        with self.runs._transaction() as conn:
            rows=conn.execute('SELECT w.*,t.title FROM runtime_development_workspaces w JOIN tasks t ON t.id=w.task_id AND t.project_id=w.project_id WHERE w.project_id=? ORDER BY w.created_at DESC,w.attempt_id LIMIT ? OFFSET ?',(project_id,limit,offset)).fetchall()
            result=[]
            for row in rows:
                record=conn.execute('SELECT * FROM workspace_retention WHERE attempt_id=?',(row['attempt_id'],)).fetchone()
                manifest=json.loads(record['manifest_json']) if record and record['manifest_json'] else None
                result.append({'project_id':project_id,'attempt_id':row['attempt_id'],'run_id':row['run_id'],'task_id':row['task_id'],'title':row['title'],
                               'state':record['state'] if record else 'available','preparation_state':row['state'],
                               'retain_until':record['retain_until'] if record else None,'archive_sha256':record['archive_sha256'] if record else None,
                               'bytes':sum(v.get('bytes',0) for v in manifest['items'].values()) if manifest else None,
                               'changes':manifest['changes'] if manifest else None})
            return result

    def _bucket(self, operation):
        """Create or verify host-owned operation directories; UUIDs come from durable rows, never paths supplied by a caller."""
        self._roots();base=Path(self.control['path'])/'retention'
        if not base.exists():new_directory(base)
        directory(base)
        bucket=base/operation['id']
        if not bucket.exists():new_directory(bucket)
        directory(bucket)
        temporary=bucket/'partial'
        if not temporary.exists():new_directory(temporary)
        directory(temporary)
        return bucket,temporary

    def _work(self, operation, work):
        """Freeze filesystem scope before dependent effects, refusing a superseded or completed operation."""
        with self.runs._transaction(write=True) as conn:
            fresh=self._operation(conn,operation['project_id'],operation['operation_key'])
            if fresh['state']!='pending':raise RunConflict('La operación original ya no está pendiente.')
            conn.execute('UPDATE workspace_retention_operations SET work_json=?,updated_at=? WHERE id=?',(encoded(work),self.runs.clock(),operation['id']))

    def _archive(self, operation, record, budget):
        """Seal the first complete observation, resume exact file copies and confirm retained recovery bytes before enabling removal."""
        original=json.loads(record['original_json']);root=Path(original['root']['path'])
        if original['control']!=self.control:raise RunConflict('Esta decisión pertenece a otra instalación; sus rutas antiguas no se reutilizan.')
        self._roots();matches_directory(root.parent,original['parent']);matches_directory(root,original['root'])
        bucket,temporary=self._bucket(operation);archive=bucket/'snapshot'
        work=json.loads(operation['work_json']) if operation['work_json'] else None
        if work is None:
            changes=git_changes(root,budget);items=sealed_inventory(root,budget)
            if os.path.lexists(archive):raise RunConflict('Hay un archivo parcial sin identidad registrada; se conserva. Solicita otro archivo explícitamente.')
            archive_identity=new_directory(archive)
            work={'manifest':{'items':items,'changes':changes},'archive_root':archive_identity}
            self._work(operation,work)
        matches_directory(archive,work['archive_root'])
        if sealed_inventory(root,budget)!=work['manifest']['items']:raise RunConflict('La copia cambió desde la decisión original; solicita un nuevo archivo, sin borrar estos cambios.')
        copy_snapshot(root,archive,work['manifest']['items'],temporary,budget)
        if sealed_inventory(root,budget)!=work['manifest']['items']:raise RunConflict('El origen cambió durante el archivo; se conserva y requiere otra observación.')
        return {'manifest':work['manifest'],'archive_sha256':fingerprint(work['manifest']),'archive_root':work['archive_root'],'bytes_deleted':False}

    def _remove(self, operation, work, budget):
        """Verify the original recovery archive, move the original directory into private disposal and reconcile only that revision."""
        original=work['original'];root=Path(original['root']['path']);self._roots()
        if original['control']!=self.control:raise RunConflict('Una instalación restaurada no hereda el permiso de borrar archivos del host original.')
        with self.runs._transaction(write=True) as conn:self._idle(conn,original['workspace'])
        matches_directory(original['control']['path'],original['control']);matches_directory(root.parent,original['parent'])
        archive=Path(self.control['path'])/'retention'/work['archive_id']/'snapshot'
        verify_copy(archive,work['manifest']['items'],budget)
        bucket,_=self._bucket(operation);held=bucket/'original'
        if not work.get('move_planned'):
            matches_directory(root,original['root'])
            if sealed_inventory(root,budget)!=work['manifest']['items']:raise RunConflict('Hay cambios posteriores al archivo; no heredan este borrado.')
            if os.path.lexists(held):raise RunConflict('Ya existe otro destino de conservación; no se sustituye.')
            work['move_planned']=True;self._work(operation,work)
        if os.path.lexists(held):matches_directory(held,original['root'])
        elif work.get('moved'):
            if os.path.lexists(root):
                current=directory(root)
                if (current['device'],current['inode'])==(original['root']['device'],original['root']['inode']):
                    raise RunConflict('La copia original volvió a su ubicación; no se infiere un borrado.')
        elif os.path.lexists(root):
            matches_directory(root,original['root'])
            if sealed_inventory(root,budget)!=work['manifest']['items']:raise RunConflict('La revisión original cambió antes de moverla; se conserva.')
            move_new(root,held);_sync_directory(root.parent);_sync_directory(bucket)
        else:
            # Absence alone is insufficient until a prior move identity was recorded durably.
            if not work.get('moved'):raise RunConflict('No se pudo localizar la revisión original; no se confirma el borrado.')
        if os.path.lexists(held):
            work['moved']=True;self._work(operation,work)
            remove_original(held,work['manifest']['items'],original['root'],budget)
        _sync_directory(bucket)
        return {'original_revision_removed':True,'replacement_preserved':os.path.lexists(root),'archive_sha256':work['archive_sha256'],'publication_performed':False}

    def _restore(self, operation, work, budget):
        """Recover one selected archive to a new scoped source directory, preserving receipt identity across response loss."""
        self._roots();archive=Path(self.control['path'])/'retention'/work['archive_id']/'snapshot'
        verify_copy(archive,work['manifest']['items'],budget)
        _,temporary=self._bucket(operation)
        destination=Path(self.sources['path'])/f"recovered-{operation['project_id']}-{operation['id']}"
        if not work.get('destination'):
            if os.path.lexists(destination):raise RunConflict('El destino ya existe sin identidad registrada; se conserva. Solicita otra recuperación a una carpeta nueva.')
            work['destination']=new_directory(destination);self._work(operation,work)
        matches_directory(destination,work['destination'])
        copy_snapshot(archive,destination,work['manifest']['items'],temporary,budget)
        return {'restored_path':str(destination),'archive_sha256':work['archive_sha256'],'execution_started':False,'publication_performed':False,'original_authority_restored':False}

    def execute(self, project_id, key):
        """Run or explicitly reconcile the original pending effect; failures retain intent and bytes and never become completed receipts."""
        with self.runs._transaction() as conn:
            operation=self._operation(conn,project_id,key);record=self._record(conn,project_id,operation['attempt_id'])
        if operation['state']!='pending':return self._view(operation)
        budget=CopyBudget();work=json.loads(operation['work_json']) if operation['work_json'] else None
        try:
            if operation['kind']=='archive':
                if record['archive_id']!=operation['id']:raise RunConflict('Este archivo fue reemplazado por otra decisión explícita.')
                result=self._archive(operation,record,budget)
            elif operation['kind']=='remove':
                if record['archive_sha256']!=work['archive_sha256']:raise RunConflict('La decisión original se refiere a otro archivo.')
                result=self._remove(operation,work,budget)
            else:result=self._restore(operation,work,budget)
            with self.runs._transaction(write=True) as conn:
                fresh=self._operation(conn,project_id,key)
                if fresh['state']!='pending':return self._view(fresh)
                now=self.runs.clock()
                if operation['kind']=='archive':
                    current=self._record(conn,project_id,operation['attempt_id'])
                    if current['archive_id']!=operation['id']:raise RunConflict('Otra decisión ya reemplazó este archivo.')
                    conn.execute("UPDATE workspace_retention SET state='retained',archive_sha256=?,manifest_json=?,updated_at=? WHERE attempt_id=?",(result['archive_sha256'],encoded(result['manifest']),now,operation['attempt_id']))
                    result={k:v for k,v in result.items() if k not in ('manifest','archive_root')}
                elif operation['kind']=='remove':conn.execute("UPDATE workspace_retention SET state='removed',updated_at=? WHERE attempt_id=?",(now,operation['attempt_id']))
                receipt={'project_id':project_id,'attempt_id':operation['attempt_id'],'operation_key':key,'kind':operation['kind'],**result}
                conn.execute("UPDATE workspace_retention_operations SET state='completed',issue=NULL,receipt_json=?,updated_at=? WHERE id=?",(encoded(receipt),now,operation['id']))
                self.runs._event(conn,project_id,record['task_id'],'workspace.retention_completed',receipt)
        except Exception as error:
            with self.runs._transaction(write=True) as conn:
                issue=str(error) if isinstance(error,(RunConflict,ValueError)) else f'La operación no se confirmó ({type(error).__name__}); se conserva su intención para comprobarla.'
                conn.execute("UPDATE workspace_retention_operations SET issue=?,updated_at=? WHERE id=? AND state='pending'",(issue,self.runs.clock(),operation['id']))
        return self.operation(project_id,key)
