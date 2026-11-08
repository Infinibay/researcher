"""Verify installed graph inspection and original pause recovery without authorizing new native work."""

from contextlib import closing
import hashlib
import json
import sqlite3

from installed_page import run_page


def accepted_plan(runs,binding,title,key):
    """Create a closed synthetic proposal and explicit domain acceptance, with no model or runtime dispatch."""
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.planning.store import ProjectPlans
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers

    request='Documentar el ejemplo y preparar la exportación CSV.'
    task=OwnerPlanningRecords(runs).create_task(project_id=101,title=title,description=request,type='plan',operation_key='fixture-task-'+key)
    context=runs.context_snapshot(101,task['id'])['context_version']
    run=runs.admit(RunSpec(101,task['id'],'project-planner',context,'fixture-plan-'+key,request,'codex'),binding=binding)
    lease,peers=AttemptPeers.claim(runs,101,run.run_id,'synthetic-planner-never-launched')
    try:
        runs.bind_native(lease,thread_id='synthetic-plan-thread-'+key,turn_id='synthetic-plan-turn-'+key)
        packet={'title':title,'rationale':'Primero relacionar los campos del ejemplo; después programar la exportación.','assumptions':['Todavía no se comprobó que los registros reales compartan la estructura del ejemplo.'],'basis':[{'source':'owner_request','quote':'Documentar el ejemplo'}],'epics':[{'key':'csv','title':'Entrada y salida documentadas','description':'Conservar propósito, datos y límites del ejemplo.'}],'tasks':[
            {'key':'learn','epic_key':'csv','type':'research','title':'Documentar una observación de ejemplo','description':'Relacionar id y measurement con la fila CSV, sin presentarla como una medición real.','acceptance_criteria':'Entrada, relación y salida explícitas con sus límites.','priority':2,'depends_on':[]},
            {'key':'export','epic_key':'csv','type':'code','title':'Preparar la exportación CSV','description':'Usar el resultado aceptado y comprobar sus límites antes de programar.','acceptance_criteria':'Prueba del caso ilustrativo y aclaración de datos reales desconocidos.','priority':2,'depends_on':['learn']},
        ]}
        plans=ProjectPlans(runs);proposal=plans.propose(lease,'fixture-proposal-'+key,packet)
        for peer in peers.ids.values():peers.registry.close(peer)
        runs.finish(lease,native_status='completed',summary='Synthetic plan fixture; no model was launched.')
        graph=plans.accept(101,run.run_id,operation_key='fixture-accept-'+key,proposal_sha256=proposal['proposal_sha256'],context_version=context)
    except BaseException:
        for peer in peers.ids.values():peers.registry.close(peer)
        runs.cancel(101,run.run_id);runs.retire_inference(lease,outcome='cancelled');raise
    return {'run':run.run_id,'task':task['id'],'title':title,'learn':graph['tasks']['learn'],'export':graph['tasks']['export']}


def accept_research(runs,research,spec,binding):
    """Record one exact illustrative report under closed logical peers and explicit synthetic owner acceptance."""
    from backend.research.models import RESEARCH_PERMISSIONS,EvidenceReference,FindingDraft,ReportDraft,ResultDraft,SourceDraft
    from backend.runtime.peer_registry import AttemptPeers

    run=runs.admit(spec,binding=binding)
    lease,peers=AttemptPeers.claim(runs,101,run.run_id,'synthetic-research-owner-never-launched')
    try:
        runs.bind_native(lease,thread_id='synthetic-research-thread',turn_id='synthetic-research-turn')
        token=research.issue_grant(project_id=101,task_id=run.task_id,agent_id=lease.actor_id,permissions=set(RESEARCH_PERMISSIONS))
        scope=research.authorize(token);runs.bind_grant(lease,scope.grant_id)
        quote='En el ejemplo sintético, measurement se escribe en la columna value.'
        source=research.capture_source(scope,'fixture-source',SourceDraft('attachment','synthetic:csv-example','Relación ilustrativa',quote),intent={'synthetic_fixture':True})
        finding=research.record_finding(scope,'fixture-finding',FindingDraft('Relación entre entrada y salida',quote,(EvidenceReference(source['source_id'],quote),)))
        report=research.write_report(scope,'fixture-report',ReportDraft('Una observación y su fila CSV','Entrada ilustrativa: {"id":7,"measurement":12}. Salida ilustrativa: columnas id,value y fila7,12. No se comprobó la estructura de los registros reales.',(finding['finding_id'],)))
        research.propose_result(scope,'fixture-delivery',ResultDraft((report['artifact_id'],),'Relación de campos ilustrada.',('El ejemplo no es una medición real.','Falta comprobar los datos reales.')))
        for peer in peers.ids.values():peers.registry.close(peer)
        runs.finish(lease,native_status='completed',summary='Synthetic report fixture; no model was launched.')
        state=runs.result_state(101,run.run_id)
        runs.accept_result(101,run.run_id,operation_key='fixture-research-acceptance',candidate_id=state['candidate']['candidate_id'],candidate_sha256=state['candidate']['candidate_sha256'],context_version=lease.context_version,review_sha256=state['review_sha256'],acknowledge_limits=True,note='Synthetic domain decision, not human or scientific acceptance.')
    except BaseException:
        for peer in peers.ids.values():peers.registry.close(peer)
        runs.cancel(101,run.run_id);runs.retire_inference(lease,outcome='cancelled');raise


def seed(host):
    """Prepare accepted, unauthorized and stale graphs; pause every authorization before the service can dispatch anything."""
    from backend.db.connection import connect
    from backend.planning.execution import PlanExecutions
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    folder=host/'sources'/'observations';folder.mkdir()
    (folder/'observations.py').write_text('"""Synthetic fixture; no actual observations were supplied."""\nobservations = []\n')
    with closing(connect(host/'source.db')) as db,db:
        db.execute("INSERT INTO projects(id,name,description) VALUES(101,'Cuaderno de observaciones','Documentar el ejemplo y preparar la exportación CSV.'),(202,'Proyecto separado','Sin los planes del cuaderno.')")
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'observaciones',?)",(str(folder),))
    runs=SQLiteRunStore(host/'source.db');research=SQLiteResearchStore(host/'source.db');binding=WorkspaceRegistry(host/'source.db',host/'sources').bind(101,11);executions=PlanExecutions(runs)
    main=accepted_plan(runs,binding,'Plan de exportación CSV','main')
    preview=executions.state(101,main['run']);authorization=executions.authorize(101,main['run'],operation_key='fixture-authorize-main',manifest_sha256=preview['manifest_sha256'])
    spec,source=executions.prepare(authorization['execution_id'],main['learn']);accept_research(runs,research,spec,source)
    assert executions.prepare(authorization['execution_id'],main['export']) is not None
    pause_body={'operation_key':'fixture-original-pause','manifest_sha256':authorization['manifest_sha256'],'status':'paused'}
    receipt=executions.control(101,authorization['execution_id'],**pause_body)
    main.update(execution=authorization['execution_id'],packet={'schema':1,'kind':'plan-execution','projectId':101,'taskId':main['task'],'runId':main['run'],'executionId':authorization['execution_id'],'body':pause_body},receipt=receipt)
    fresh=accepted_plan(runs,binding,'Plan aceptado sin autorización','fresh')
    stale=accepted_plan(runs,binding,'Plan conservado con contexto anterior','stale')
    preview=executions.state(101,stale['run']);old=executions.authorize(101,stale['run'],operation_key='fixture-authorize-stale',manifest_sha256=preview['manifest_sha256'])
    executions.control(101,old['execution_id'],operation_key='fixture-pause-stale',manifest_sha256=old['manifest_sha256'],status='paused')
    with closing(connect(host/'source.db')) as db,db:db.execute("UPDATE tasks SET description='Cambió el alcance del plan; conservar su historia.' WHERE id=?",(stale['task'],))
    assert not executions.pending() and not executions.state(101,stale['run'])['execution']['current']
    return {'alpha':101,'beta':202,'main':main,'fresh':fresh,'stale':stale}


def observe(host):
    """Bind graph/receipt/delivery bytes and scoped state independently of the frontend's labels."""
    from backend.db.connection import connect

    with closing(connect(host/'source.db')) as db:
        names=('projects','tasks','task_dependencies','task_contexts','runtime_runs','runtime_attempts','runtime_peers','runtime_commands','runtime_plan_executions','runtime_plan_deliveries','runtime_plan_handoffs','runtime_context_causes','runtime_context_affected','runtime_context_revisions','tool_grants','research_reports','artifacts','events_log','runtime_inference_dispatches')
        digest={name:hashlib.sha256(json.dumps(sorted([dict(row)for row in db.execute(f'SELECT * FROM {name}')],key=lambda row:json.dumps(row,sort_keys=True,default=str)),sort_keys=True,ensure_ascii=False,default=str).encode()).hexdigest()for name in names}
        return {'table_sha256':digest,'source_sha256':hashlib.sha256((host/'sources/observations/observations.py').read_bytes()).hexdigest(),'runs':[dict(row)for row in db.execute('SELECT id,status FROM runtime_runs ORDER BY id')],'peers':[dict(row)for row in db.execute('SELECT kind,state FROM runtime_peers ORDER BY id')],'dispatches':db.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0],'synthetic_bound_turn_ids':db.execute('SELECT count(*) FROM runtime_attempts WHERE turn_id IS NOT NULL').fetchone()[0],'integrity':db.execute('PRAGMA integrity_check').fetchone()[0],'foreign_keys':[tuple(row)for row in db.execute('PRAGMA foreign_key_check')]}


def verify(ids,before,after,evidence):
    """Original pause receipt recovery must preserve every observed business row and create no dispatch or native attempt."""
    assert before==after and after['dispatches']==0 and after['synthetic_bound_turn_ids']==4
    assert all(peer['state']=='closed'for peer in after['peers'])
    assert len(evidence['controls'])==2
    assert all(item['body']==ids['main']['packet']['body'] and item['receipt']==ids['main']['receipt']for item in evidence['controls'])


if __name__=='__main__':run_page(seed,observe,verify,'tests/execution-page.e2e.mjs',__doc__)
