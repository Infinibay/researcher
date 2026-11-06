"""Whole-project evidence reports and exact owner closure; labels, native turn completion and accepted code never imply semantic success or publication."""

import json

from backend.knowledge.reviews import canonical, digest
from backend.knowledge.results import result_state
from backend.planning.execution import PlanExecutions
from backend.planning.store import ProjectPlans
from backend.runtime.code_acceptances import CodeAcceptances
from backend.runtime.contracts import RunConflict, RunNotFound, command_key, text

MAX_REPORT_BYTES = 4 * 1024 * 1024


class ProjectCompletion:
    """Compose attributed current evidence and atomically save a separate owner decision in the existing receipt transaction, without inference or Git."""

    def __init__(self, runs, *, legacy_active):
        """Reuse the original run store, contexts, acceptance policies, receipts and event ownership."""
        self.runs = runs
        self.executions = PlanExecutions(runs)
        if not callable(legacy_active):
            raise TypeError('An actual registered legacy-owner observation is required')
        self.legacy_active = legacy_active

    def _state(self, conn, project, plan_run):
        """Recompute all project scope and current original evidence; a previous report cannot silently stand in for changed requirements or work."""
        run = self.runs._row(conn, project, plan_run)
        request = ProjectPlans(self.runs)._request(conn, project, plan_run)
        owner_project = conn.execute('SELECT id,name,description,original_description,status FROM projects WHERE id=?', (project,)).fetchone()
        if owner_project is None:
            raise RunNotFound('Project not found')
        if conn.execute('SELECT COUNT(*) FROM tasks WHERE project_id=?', (project,)).fetchone()[0] > 256:
            raise RunConflict('El informe excede 256 tareas; no se omitió trabajo ni se cerró el proyecto.')
        blockers = []
        legacy = self.legacy_active(project) is not False
        if legacy:
            blockers.append({'code': 'legacy_work_registered', 'message': 'Hay ejecución anterior registrada o sin observar; detén y reconcilia su dueño antes del cierre.'})
        execution = conn.execute('SELECT * FROM runtime_plan_effective_executions WHERE project_id=? AND plan_run_id=?', (project, plan_run)).fetchone()
        manifest = None
        deliveries = []
        if execution is None:
            blockers.append({'code': 'execution_absent', 'message': 'Falta una ejecución autorizada del plan.'})
        else:
            try:
                manifest = self.executions._current(conn, execution, active=False)
                for delivery in conn.execute('SELECT d.* FROM runtime_plan_deliveries d WHERE d.execution_id=? AND NOT EXISTS(SELECT 1 FROM runtime_plan_deliveries s WHERE s.predecessor_delivery_id=d.id) ORDER BY d.task_id', (execution['id'],)):
                    self.executions._validate_delivery(conn, execution, delivery)
                    current = self.runs._row(conn, project, delivery['run_id']) if delivery['run_id'] else None
                    deliveries.append({'delivery_id': delivery['id'], 'task_id': delivery['task_id'], 'run_id': delivery['run_id'], 'status': current['status'] if current else 'pending'})
                    if current is None or current['status'] != 'accepted':
                        blockers.append({'code': 'delivery_unaccepted', 'task_id': delivery['task_id'], 'message': 'La entrega actual todavía no tiene aceptación.'})
            except RunConflict as error:
                blockers.append({'code': 'graph_obsolete', 'message': str(error)})
        tasks = []
        unpublished = []
        task_bytes = 0
        for task in conn.execute('SELECT id,type,title,description,acceptance_criteria,status,epic_id,milestone_id FROM tasks WHERE project_id=? ORDER BY id', (project,)):
            item = dict(task)
            item['context_version'] = self.runs._context(conn, task['id'])
            item['evidence'] = None
            try:
                if task['type'] == 'plan':
                    accepted = conn.execute('SELECT a.* FROM runtime_project_plan_acceptances a JOIN runtime_runs r ON r.id=a.run_id WHERE a.project_id=? AND a.task_id=? AND r.status=\'accepted\' ORDER BY a.created_at DESC,a.rowid DESC LIMIT 1', (project, task['id'])).fetchone()
                    if accepted is None or task['status'] != 'done':
                        raise RunConflict('El plan no tiene una aceptación vigente.')
                    if not (accepted['run_id'] == plan_run and manifest and manifest.get('owner_reauthorized')):
                        ProjectPlans(self.runs).current(conn, self.runs._row(conn, project, accepted['run_id']))
                    item['evidence'] = {'kind': 'accepted_plan', 'run_id': accepted['run_id'], 'context_version': accepted['context_version'], 'acceptance': json.loads(accepted['result_json']), 'owner_graph_revision': execution['authorization_revision'] if accepted['run_id'] == plan_run and execution else None}
                else:
                    sources = self.executions._prerequisites(conn, project, {'depends_on': [task['id']]})
                    if not sources:
                        raise RunConflict('La etiqueta de tarea no demuestra un resultado nativo aceptado.')
                    source = sources[0]
                    if source['kind'] == 'accepted_research_reports':
                        state = result_state(conn, project, source['run_id'])
                        if not state['acceptance_current']:
                            raise RunConflict('La aceptación documental ya no corresponde a la evidencia actual.')
                        source['owner_acceptance'] = state['acceptance']
                    else:
                        state = CodeAcceptances(self.runs)._state(conn, project, source['run_id'])
                        if not state['acceptance_current']:
                            raise RunConflict('La aceptación del código o su revisión ya no está vigente.')
                        source.update(owner_acceptance=state['acceptance'], checks=state['checks'], review=state['review'], publication=state['publication'])
                        if not state['publication']['performed']:
                            unpublished.append(source['attempt_id'])
                    item['evidence'] = source
            except RunConflict as error:
                blockers.append({'code': 'task_unaccepted', 'task_id': task['id'], 'message': str(error)})
            tasks.append(item)
            task_bytes += len(canonical(item).encode())
            if task_bytes > MAX_REPORT_BYTES:
                raise RunConflict('Los resultados completos exceden 4 MiB; no se omitió evidencia.')
        active = [dict(row) for row in conn.execute("SELECT id,task_id,status,execution_kind FROM runtime_runs WHERE project_id=? AND status IN ('queued','running','cancelling','reconciling','waiting_input','needs_review') ORDER BY id", (project,))]
        open_peers = [dict(row) for row in conn.execute("SELECT p.id,p.kind,p.state FROM runtime_peers p JOIN runtime_attempts a ON a.id=p.attempt_id JOIN runtime_runs r ON r.id=a.run_id WHERE r.project_id=? AND p.state!='closed' ORDER BY p.id", (project,))]
        grants = [row[0] for row in conn.execute('SELECT id FROM tool_grants WHERE project_id=? AND revoked_at IS NULL ORDER BY id', (project,))]
        if active or open_peers or grants:
            blockers.append({'code': 'work_unclosed', 'message': 'Hay trabajo pendiente, incierto o sin cierre comprobado; conserva sus efectos antes de cerrar el proyecto.'})
        scope = {}
        for table, field in [('epics', 'epic_id'), ('milestones', 'milestone_id')]:
            if conn.execute(f'SELECT COUNT(*) FROM {table} WHERE project_id=?', (project,)).fetchone()[0] > 256:
                raise RunConflict('El alcance completo excede los límites del informe; no se truncó contenido.')
            scope[table] = [dict(row) for row in conn.execute(f'SELECT id,title,description,status FROM {table} WHERE project_id=? ORDER BY id', (project,))]
            for entry in scope[table]:
                if not any(task[field] == entry['id'] for task in tasks):
                    blockers.append({'code': 'uncovered_scope', 'message': f'{entry["title"]}: no tiene tareas con resultados que permitan revisar su cobertura.'})
        snapshot = {'schema_version': 1, 'project': {key: owner_project[key] for key in ('id','name','description','original_description')},
                    'plan_run_id': plan_run, 'original_plan_input': json.loads(request['snapshot_json']), 'manifest': manifest,
                    'deliveries': deliveries, 'tasks': tasks, **scope, 'active_work': active, 'open_peers': open_peers,
                    'unrevoked_grants': grants, 'registered_legacy_work': legacy, 'unpublished_attempts': sorted(unpublished), 'blockers': blockers,
                    'interpretation': 'Recorded acceptance is evidence of an owner decision, not proof of shared understanding, semantic scope coverage, scientific confidence or current remote branch state.'}
        if len(canonical(snapshot).encode()) > MAX_REPORT_BYTES:
            raise RunConflict('El informe completo supera 4 MiB; no se omitió evidencia ni se cerró el proyecto.')
        markdown = self._markdown(snapshot)
        if len(markdown.encode()) + len(canonical(snapshot).encode()) > MAX_REPORT_BYTES:
            raise RunConflict('El informe completo y sus fuentes superan 4 MiB; no se truncó contenido.')
        sha = digest({'snapshot': snapshot, 'report_markdown': markdown})
        old = conn.execute("SELECT result_json FROM runtime_commands WHERE project_id=? AND task_id=? AND json_extract(result_json,'$.kind')='project.completion' AND json_extract(result_json,'$.plan_run_id')=? ORDER BY created_at DESC,rowid DESC LIMIT 1", (project, run['task_id'], plan_run)).fetchone()
        acceptance = json.loads(old[0]) if old else None
        return {'project_id': project, 'task_id': run['task_id'], 'plan_run_id': plan_run, 'report_sha256': sha, 'snapshot': snapshot,
                'report_markdown': markdown, 'blockers': blockers, 'unpublished_attempts': sorted(unpublished),
                'eligible': not blockers and owner_project['status'] != 'completed', 'acceptance': acceptance,
                'acceptance_current': bool(acceptance and acceptance['report_sha256'] == sha and not blockers and owner_project['status'] == 'completed')}

    @staticmethod
    def _markdown(snapshot):
        """Render exact attributed material and concrete interpretation limits; never summarize away source constraints or invent semantic fulfillment."""
        p = snapshot['project']
        original = snapshot['original_plan_input']
        lines = [f'# Informe del proyecto: {p["name"]}', '', 'Este informe reúne decisiones y evidencia guardadas. Que una tarea termine no demuestra que se hayan cumplido todos los objetivos.', '',
                 '## Alcance que se revisa', '', 'Descripción original registrada:', p['original_description'] or 'No registrada; no se reconstruye a partir de la profesión ni de etiquetas.', '',
                 'Descripción actual registrada:', p['description'] or 'No registrada.', '', 'Solicitud original de planificación:', original.get('owner_request') or canonical(original), '',
                 '## Resultados por tarea', '']
        for task in snapshot['tasks']:
            lines += [f'### {task["title"]} · tarea {task["id"]}', '', 'Criterio registrado: '+(task['acceptance_criteria'] or 'No registrado.'), '']
            source = task['evidence']
            if source is None:
                lines += ['Sin resultado aceptado vigente. La etiqueta «'+task['status']+'» no lo sustituye.', '']
            elif source['kind'] == 'accepted_research_reports':
                value = source['snapshot']
                lines += ['Resultado documental aceptado: '+value['summary'], '', 'Limitaciones declaradas: '+canonical(value['limitations']), '']
                for report in value['reports']:
                    lines += ['#### '+report['title'], report['content'], '']
                lines += ['Fuentes, citas y revisiones originales conservadas en la evidencia de este informe.', 'No se infiere confianza científica por haber aceptado un informe.', '']
            elif source['kind'] == 'accepted_code_candidate':
                lines += ['Candidato exacto aceptado: `'+source['snapshot']['head_sha']+'`.', 'Comprobaciones registradas: '+canonical(source['checks']), '', source['publication']['message'], '',
                          'Por ejemplo: aceptar una copia con valor 200 no cambia por sí solo el origen que contiene 137.', '']
            else:
                lines += ['Plan aceptado como propuesta de trabajo; no demuestra por sí solo cobertura de los objetivos.', '']
        lines += ['## Límites y decisión pendiente', '', 'Las fuentes y decisiones completas se incluyen en el snapshot, con sus hashes y versiones. Una publicación registrada describe lo observado entonces; no prueba el estado remoto actual.',
                  'El propietario debe comparar este alcance con su intención, revisar los límites y reconocer cada candidato sin publicación antes de aceptar el cierre.', '']
        lines += ['- '+b['message'] for b in snapshot['blockers']]
        if not snapshot['blockers']:
            lines += ['No hay impedimentos estructurales registrados. Esto no demuestra comprensión compartida ni cumplimiento semántico; falta tu decisión explícita.']
        return '\n'.join(lines)

    def state(self, project, plan_run):
        """Read an exact whole-project report and historical decision without starting work, accepting results or modifying project state."""
        with self.runs._transaction() as conn:
            return self._state(conn, project, plan_run)

    def accept(self, project, plan_run, *, operation_key, report_sha256, acknowledged_unpublished_attempts, statement):
        """Atomically acknowledge the exact full report and explicit owner scope statement; original retries recover history and never reclose changed work."""
        command_key(operation_key)
        text(statement, 'owner scope review', 4000)
        if not isinstance(acknowledged_unpublished_attempts, list) or any(not isinstance(item, str) for item in acknowledged_unpublished_attempts) or len(set(acknowledged_unpublished_attempts)) != len(acknowledged_unpublished_attempts):
            raise ValueError('Use the exact unpublished candidate list from the observed report')
        intent = {'kind': 'project.complete', 'plan_run_id': plan_run, 'report_sha256': report_sha256, 'acknowledged_unpublished_attempts': sorted(acknowledged_unpublished_attempts), 'statement': statement}
        with self.runs._transaction(write=True) as conn:
            run = self.runs._row(conn, project, plan_run)
            old = self.runs._receipt(conn, project, run['task_id'], operation_key, intent)
            if old is not None:
                return old
            state = self._state(conn, project, plan_run)
            if not state['eligible'] or state['report_sha256'] != report_sha256 or state['unpublished_attempts'] != sorted(acknowledged_unpublished_attempts):
                raise RunConflict('El informe cambió, hay trabajo sin aceptar/cerrar o falta reconocer código sin publicar. Consulta el alcance actual.')
            receipt = {'kind': 'project.completion', 'project_id': project, 'task_id': run['task_id'], 'plan_run_id': plan_run, 'operation_key': operation_key,
                       'report_sha256': report_sha256, 'acknowledged_unpublished_attempts': sorted(acknowledged_unpublished_attempts), 'statement': statement,
                       'snapshot': state['snapshot'], 'report_markdown': state['report_markdown'], 'project_status': 'completed', 'publication_performed': False, 'accepted_at': self.runs.clock()}
            self.runs._save_receipt(conn, project, run['task_id'], operation_key, intent, receipt)
            conn.execute("UPDATE projects SET status='completed',completed_at=CURRENT_TIMESTAMP WHERE id=?", (project,))
            self.runs._event(conn, project, run['task_id'], 'project.completed', {'plan_run_id': plan_run, 'operation_key': operation_key, 'report_sha256': report_sha256})
            return receipt
