"""Owner project dossier: observed activity, exact plan/report locators, explicit source registration and original-target Stop using existing authority and receipts."""

import json
import re
from pathlib import Path

from backend.knowledge.reviews import digest
from backend.runtime.contracts import RunConflict, RunNotFound, command_key, text


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
        if len(runs) + len(graphs) > 256:
            raise RunConflict('El proyecto supera el límite de observación; no se omitieron intentos de Stop.')
        return {'project_id': project, 'runs': runs, 'graphs': graphs, 'legacy_registered': legacy}

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
            history = any(conn.execute(f'SELECT 1 FROM {table} WHERE project_id=? LIMIT 1', (project,)).fetchone() for table in ('runtime_runs','agent_runs','flow_snapshots','agent_events'))
            return {'project':owner, 'project_id':project, 'metadata_sha256':digest({k:owner[k] for k in ('name','description','original_description')}), 'history_present':history, 'runtime_available':self.workspaces is not None,
                    'workspace_root':str(self.workspaces.root) if self.workspaces else None, 'sources':sources,
                    'activity':scope['runs'], 'graphs':scope['graphs'], 'legacy_registered':scope['legacy_registered'],
                    'plans':plans, 'reports':reports, 'report_validity':'not_rechecked',
                    'stop':{'task_id':task_ids[0], 'scope_sha256':digest(scope)} if task_ids and not scope['legacy_registered'] else None}

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
            existing = conn.execute('SELECT * FROM repositories WHERE project_id=? AND (name=? OR local_path=?)', (project,name,path)).fetchone()
            if existing is not None:
                if existing['name'] != name or existing['local_path'] != path or existing['status'] != 'active':
                    raise RunConflict('Ese registro ya identifica otra selección o está archivado; no se reemplazó.')
                rid = existing['id']
            else:
                rid = conn.execute("INSERT INTO repositories(project_id,name,local_path,status)VALUES(?,?,?,'active')", (project,name,path)).lastrowid
            self.workspaces._bind(conn, project, rid)
            return {'project_id':project, 'repository_id':rid, 'name':name, 'path':path, 'filesystem_changed':False, 'remote_changed':False}

    def request_stop(self, project, *, task_id, operation_key, scope_sha256):
        """Atomically pause exactly observed graphs and withdraw exactly observed run authority before acknowledging intent; replay never retargets new work or claims closure."""
        command_key(operation_key)
        intent = {'kind':'project.stop','project_id':project,'task_id':task_id,'scope_sha256':scope_sha256}
        with self.runs._transaction(write=True) as conn:
            self._project(conn, project)
            old = self.runs._receipt(conn,project,task_id,operation_key,intent)
            if old is not None:
                return old, False
            scope = self._stop_scope(conn,project)
            tasks = sorted({r['task_id'] for r in scope['runs']} | {g['task_id'] for g in scope['graphs']})
            if scope['legacy_registered'] or not tasks or task_id != tasks[0] or digest(scope) != scope_sha256:
                raise RunConflict('La actividad cambió o hay un dueño anterior registrado; consulta los intentos originales antes de detener.')
            for graph in scope['graphs']:
                conn.execute("UPDATE runtime_plan_executions SET status='paused',updated_at=? WHERE project_id=? AND id=?", (self.runs.clock(),project,graph['execution_id']))
            for run in scope['runs']:
                self.runs._cancel(conn,project,run['run_id'])
            conn.execute("UPDATE projects SET status='paused' WHERE id=?", (project,))
            receipt = {'kind':'project.stop','project_id':project,'task_id':task_id,'operation_key':operation_key,'scope_sha256':scope_sha256,
                       'run_ids':[r['run_id'] for r in scope['runs']], 'execution_ids':[g['execution_id'] for g in scope['graphs']], 'closure':'unconfirmed','status':'requested'}
            self.runs._save_receipt(conn,project,task_id,operation_key,intent,receipt)
            self.runs._event(conn,project,task_id,'project.stop_requested',receipt)
            return receipt, True
