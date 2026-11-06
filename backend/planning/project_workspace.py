"""Owner project dossier: observed activity, exact plan/report locators, explicit source registration and original-target Stop using existing authority and receipts."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from backend.git.source_operations import SourceOperations
from backend.knowledge.reviews import digest
from backend.runtime.contracts import RunConflict, RunNotFound, command_key, text


@dataclass(frozen=True)
class PreparedProjectStop:
    """Read-validated original project intent and immutable serialized scope; this host-only value is never accepted from an HTTP caller."""

    intent_json: str
    scope_json: str | None
    receipt_json: str | None

    @property
    def scope(self):
        """Return a detached original target set; mutating a consumer's copy cannot change the prepared authorization snapshot."""
        return json.loads(self.scope_json) if self.scope_json is not None else None

    @property
    def receipt(self):
        """Recover a prior exact receipt without withdrawing any newer local owner."""
        return json.loads(self.receipt_json) if self.receipt_json is not None else None


class ProjectWorkspace:
    """Project real saved state without treating metadata as activity/closure or inventing a plan choice; no model, Git, remote setup or second coordinator."""

    def __init__(self, runs, *, workspaces, legacy_active):
        """Use the actual host root when configured and an explicit observation of registered legacy owners; absent policy stays unknown."""
        self.runs, self.workspaces = runs, workspaces
        if not callable(legacy_active):
            raise TypeError('Actual registered legacy-owner observation required')
        self.legacy_active = legacy_active

    def create(self, *, name, description, operation_key):
        """Create one project resource from an exact original owner intent; its immutable creation metadata recovers the same ID after response loss or later edits."""
        command_key(operation_key)
        text(name, 'project name', 1024)
        if not isinstance(description, str) or len(description.encode()) > 200000:
            raise RunConflict('La descripción excede el límite de creación.')
        intent = {'operation_key':operation_key, 'name':name, 'description':description}
        with self.runs._transaction(write=True) as conn:
            rows = conn.execute("SELECT id,metadata_json FROM projects WHERE json_extract(CASE WHEN json_valid(metadata_json) THEN metadata_json ELSE '{}' END,'$.owner_creation.operation_key')=?", (operation_key,)).fetchall()
            if rows:
                if len(rows) != 1 or json.loads(rows[0]['metadata_json'])['owner_creation'] != intent:
                    raise RunConflict('La solicitud original de creación identifica otro alcance; no se creó otro proyecto.')
                return {'project_id':rows[0]['id'], 'request':intent}
            pid = conn.execute("INSERT INTO projects(name,description,original_description,status,metadata_json,created_by)VALUES(?,?,?,'new',?,'user')", (name,description,description,json.dumps({'owner_creation':intent},ensure_ascii=False))).lastrowid
            return {'project_id':pid, 'request':intent}

    @staticmethod
    def _project(conn, project):
        """Read one real owner project; never reinterpret foreign scope as an empty project."""
        row = conn.execute('SELECT id,name,description,original_description,status,completed_at FROM projects WHERE id=?', (project,)).fetchone()
        if row is None:
            raise RunNotFound('Project not found')
        return dict(row)

    def _stop_scope(self, conn, project):
        """Freeze only original active/uncertain runs and active graph authorizations; closed reviewable proposals remain intact."""
        runs = [dict(row) for row in conn.execute("SELECT r.id AS run_id,r.task_id,r.context_version,r.fence,r.current_attempt_id AS attempt_id,r.status FROM runtime_runs r LEFT JOIN runtime_attempts a ON a.id=r.current_attempt_id WHERE r.project_id=? AND (r.status IN ('queued','running','cancelling','reconciling','waiting_input') OR (r.status='needs_review' AND (coalesce(a.status,'missing')!='finished' OR EXISTS(SELECT 1 FROM runtime_peers p WHERE p.attempt_id=a.id AND p.state!='closed')))) ORDER BY r.id", (project,))]
        graphs = [dict(row) for row in conn.execute("SELECT e.id AS execution_id,e.plan_run_id,r.task_id,e.manifest_sha256,e.authorization_revision FROM runtime_plan_effective_executions e JOIN runtime_runs r ON r.id=e.plan_run_id WHERE e.project_id=? AND e.status='active' ORDER BY e.id", (project,))]
        legacy = self.legacy_active(project) is not False
        metadata = conn.execute('SELECT metadata_json FROM projects WHERE id=?',(project,)).fetchone()[0]
        sources = [{k: row[k] for k in ('operation_key','operation_id','fence','status')} for row in SourceOperations.summaries(metadata) if row['status'] not in ('completed','rejected','stopped')]
        if len(runs) + len(graphs) + len(sources) > 256:
            raise RunConflict('El proyecto supera el límite de observación; no se omitieron intentos de Stop.')
        return {'project_id': project, 'runs': runs, 'graphs': graphs, 'legacy_registered': legacy, **({'source_operations':sources} if sources else {})}

    def state(self, project):
        """Read directory-policy observations, metadata and exact historical links without probing Git/remotes or selecting an arbitrary newest plan."""
        with self.runs._transaction() as conn:
            owner = self._project(conn, project)
            scope = self._stop_scope(conn, project)
            sources = []
            rows = conn.execute("SELECT id,name,local_path FROM repositories WHERE project_id=? AND status='active' ORDER BY id LIMIT 257", (project,)).fetchall()
            if len(rows) > 256:
                raise RunConflict('Hay demasiadas fuentes para una observación completa; no se omitieron registros.')
            for row in rows:
                availability, reason = 'unknown', 'No hay configuración de runtime para comprobar la carpeta admitida.'
                if self.workspaces is not None:
                    try:
                        self.workspaces._bind(conn, project, row['id'])
                        availability, reason = 'available', 'Carpeta comprobada contra la política del host. Git y remotos no se han comprobado aquí.'
                    except (RunConflict, RunNotFound, OSError):
                        availability, reason = 'unavailable', 'La carpeta registrada falta, cambió o no cumple la política del host. No elegimos otra.'
                sources.append({'repository_id':row['id'], 'name':row['name'], 'path':row['local_path'], 'availability':availability, 'message':reason, 'git_state':'not_checked'})
            plans = [dict(row) for row in conn.execute('SELECT q.run_id,q.task_id,q.context_version,r.status,t.title,EXISTS(SELECT 1 FROM runtime_project_plan_acceptances a WHERE a.run_id=q.run_id) AS accepted,EXISTS(SELECT 1 FROM runtime_project_plan_proposals p WHERE p.run_id=q.run_id) AS proposed FROM runtime_project_plan_requests q JOIN runtime_runs r ON r.id=q.run_id JOIN tasks t ON t.id=q.task_id WHERE q.project_id=? ORDER BY r.created_at DESC,r.id LIMIT 257', (project,))]
            if len(plans) > 256:
                raise RunConflict('El historial de planes supera esta vista; no se eligió uno por su fecha.')
            for plan in plans:
                plan['context_current'] = plan['context_version'] == self.runs._context(conn, plan['task_id'])
            reports = []
            for row in conn.execute("SELECT result_json FROM runtime_commands WHERE project_id=? AND json_extract(result_json,'$.kind')='project.completion' ORDER BY created_at DESC,rowid DESC LIMIT 257", (project,)):
                value = json.loads(row[0])
                reports.append({key:value[key] for key in ('task_id','plan_run_id','operation_key','report_sha256','accepted_at')})
            if len(reports) > 256:
                raise RunConflict('El historial de cierres supera esta vista; no se omitieron decisiones.')
            task_ids = sorted({r['task_id'] for r in scope['runs']} | {g['task_id'] for g in scope['graphs']})
            source_operations = SourceOperations.summaries(conn.execute('SELECT metadata_json FROM projects WHERE id=?', (project,)).fetchone()[0])
            history = bool(source_operations) or any(conn.execute(f'SELECT 1 FROM {table} WHERE project_id=? LIMIT 1', (project,)).fetchone() for table in ('runtime_runs','agent_runs','flow_snapshots','agent_events'))
            return {'project':owner, 'project_id':project, 'metadata_sha256':digest({k:owner[k] for k in ('name','description','original_description')}), 'history_present':history, 'runtime_available':self.workspaces is not None,
                    'workspace_root':str(self.workspaces.root) if self.workspaces else None, 'sources':sources, 'source_operations':source_operations,
                    'activity':scope['runs'], 'graphs':scope['graphs'], 'legacy_registered':scope['legacy_registered'],
                    'plans':plans, 'reports':reports, 'report_validity':'not_rechecked',
                    'stop':{'task_id':task_ids[0] if task_ids else None, 'scope_sha256':digest(scope)} if (task_ids or scope.get('source_operations')) and not scope['legacy_registered'] else None}

    def register_source(self, project, *, name, path):
        """Register only an existing directory under the real managed root; same resource intent returns the original ID without Git/init/clone/origin/network effects."""
        if self.workspaces is None:
            raise RunConflict('Configura el runtime y su raíz de trabajo antes de registrar una fuente.')
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,80}', name):
            raise RunConflict('Usa un nombre de registro de1a81caracteres, letras, números, puntos, guiones o guiones bajos.')
        text(path, 'source path', 4096)
        if not Path(path).is_absolute():
            raise RunConflict('Selecciona una ruta absoluta existente, no el directorio supuesto de otro agente.')
        with self.runs._transaction(write=True) as conn:
            self._project(conn, project)
            SourceOperations.assert_unreserved(conn, path)
            existing = conn.execute('SELECT * FROM repositories WHERE project_id=? AND (name=? OR local_path=?)', (project,name,path)).fetchone()
            if existing is not None:
                if existing['name'] != name or existing['local_path'] != path or existing['status'] != 'active':
                    raise RunConflict('Ese registro ya identifica otra selección o está archivado; no se reemplazó.')
                rid = existing['id']
            else:
                rid = conn.execute("INSERT INTO repositories(project_id,name,local_path,status)VALUES(?,?,?,'active')", (project,name,path)).lastrowid
            self.workspaces._bind(conn, project, rid)
            return {'project_id':project, 'repository_id':rid, 'name':name, 'path':path, 'filesystem_changed':False, 'remote_changed':False}

    def _stop_receipt(self, conn, project, task_id, operation_key, intent):
        """Read exact native or administrative project Stop history before observing or withdrawing current work."""
        metadata = SourceOperations._load(conn,project)
        administrative = metadata.get('owner_project_stops_v1',{}).get(operation_key)
        if administrative is not None:
            if administrative['intent'] != intent:
                raise RunConflict('La solicitud Stop original identifica otro alcance.')
            return administrative['receipt']
        return self.runs._receipt(conn,project,task_id,operation_key,intent) if task_id is not None else None

    def prepare_stop(self, project, *, task_id, operation_key, scope_sha256):
        """Validate the owner's complete observed scope in a readonly transaction before physical withdrawal; a history replay targets nothing new."""
        command_key(operation_key)
        intent = {'kind':'project.stop','project_id':project,'task_id':task_id,'scope_sha256':scope_sha256}
        with self.runs._transaction() as conn:
            self._project(conn, project)
            receipt = self._stop_receipt(conn, project, task_id, operation_key, intent)
            if receipt is not None:
                return PreparedProjectStop(json.dumps(intent),None,json.dumps(receipt))
            scope = self._stop_scope(conn,project)
            tasks = sorted({r['task_id'] for r in scope['runs']} | {g['task_id'] for g in scope['graphs']})
            if scope['legacy_registered'] or not (tasks or scope.get('source_operations')) or task_id != (tasks[0] if tasks else None) or digest(scope) != scope_sha256:
                raise RunConflict('La actividad cambió o hay un dueño anterior registrado; consulta los intentos originales antes de detener.')
            return PreparedProjectStop(json.dumps(intent),json.dumps(scope),None)

    def request_stop(self, project, *, task_id, operation_key, scope_sha256, prepared=None):
        """Atomically pause exactly observed graphs and withdraw exactly observed run authority before acknowledging intent; replay never retargets new work or claims closure."""
        command_key(operation_key)
        intent = {'kind':'project.stop','project_id':project,'task_id':task_id,'scope_sha256':scope_sha256}
        with self.runs._transaction(write=True) as conn:
            self._project(conn, project)
            old = self._stop_receipt(conn, project, task_id, operation_key, intent)
            if old is not None:
                return old, False
            if prepared is None:
                scope = self._stop_scope(conn,project)
                tasks = sorted({r['task_id'] for r in scope['runs']} | {g['task_id'] for g in scope['graphs']})
                if scope['legacy_registered'] or not (tasks or scope.get('source_operations')) or task_id != (tasks[0] if tasks else None) or digest(scope) != scope_sha256:
                    raise RunConflict('La actividad cambió o hay un dueño anterior registrado; consulta los intentos originales antes de detener.')
            else:
                if not isinstance(prepared, PreparedProjectStop) or json.loads(prepared.intent_json) != intent or prepared.scope is None or digest(prepared.scope) != scope_sha256:
                    raise RunConflict('La preparación del Stop no corresponde a la solicitud original.')
                scope = prepared.scope
            for graph in scope['graphs']:
                current = conn.execute('SELECT plan_run_id,manifest_sha256,authorization_revision FROM runtime_plan_effective_executions WHERE project_id=? AND id=?',(project,graph['execution_id'])).fetchone()
                if current is None or any(current[key] != graph[key] for key in ('plan_run_id','manifest_sha256','authorization_revision')):
                    raise RunConflict('La autorización del grafo original cambió; no se pausó una revisión posterior.')
                conn.execute("UPDATE runtime_plan_executions SET status='paused',updated_at=? WHERE project_id=? AND id=?", (self.runs.clock(),project,graph['execution_id']))
            for run in scope['runs']:
                current = self.runs._row(conn,project,run['run_id'])
                if any(current[key] != run[key] for key in ('task_id','context_version','fence')) or current['current_attempt_id'] != run['attempt_id']:
                    raise RunConflict('El intento nativo original cambió; no se detuvo un intento posterior.')
                self.runs._cancel(conn,project,run['run_id'])
            for source in scope.get('source_operations',[]):
                SourceOperations.withdraw(conn,project,source['operation_key'],operation_id=source['operation_id'],fence=source['fence'])
            conn.execute("UPDATE projects SET status='paused' WHERE id=?", (project,))
            receipt = {'kind':'project.stop','project_id':project,'task_id':task_id,'operation_key':operation_key,'scope_sha256':scope_sha256,
                       'run_ids':[r['run_id'] for r in scope['runs']], 'execution_ids':[g['execution_id'] for g in scope['graphs']], 'closure':'unconfirmed','status':'requested'}
            if scope.get('source_operations'):
                receipt['source_operations'] = scope['source_operations']
            if task_id is not None:
                self.runs._save_receipt(conn,project,task_id,operation_key,intent,receipt)
                self.runs._event(conn,project,task_id,'project.stop_requested',receipt)
            else:
                metadata = SourceOperations._load(conn,project)
                stops = metadata.setdefault('owner_project_stops_v1',{})
                if len(stops) >= 64:
                    raise RunConflict('Se alcanzó el límite de solicitudes Stop conservadas; no se borró historia.')
                stops[operation_key] = {'intent':intent,'receipt':receipt}
                SourceOperations._save(conn,project,metadata)
            return receipt, True
