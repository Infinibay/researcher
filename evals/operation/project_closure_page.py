"""Exercise a nonempty installed documentary project closure and its original overview link without generation."""

from contextlib import closing

from execution_page import accept_research, observe as observe_execution
from installed_page import resume_page, run_page


def seed(host):
    """Accept a synthetic documentary graph and both actual scoped reports; pause before serving to admit no native work."""
    from backend.db.connection import connect
    from backend.planning.completion import ProjectCompletion
    from backend.planning.execution import PlanExecutions
    from backend.planning.owner_records import OwnerPlanningRecords
    from backend.planning.store import ProjectPlans
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.runtime.contracts import RunSpec
    from backend.runtime.peer_registry import AttemptPeers
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.workspaces import WorkspaceRegistry

    request='Documentar el ejemplo y explicar su fila CSV y sus límites; no programar un exportador.'
    folder=host/'sources/observations';folder.mkdir()
    (folder/'observations.py').write_text('"""Synthetic fixture; actual observations were not supplied."""\nobservations = []\n')
    with closing(connect(host/'source.db'))as db,db:
        db.execute('INSERT INTO projects(id,name,description,original_description) VALUES(101,?,?,?)',('Relación ilustrativa de datos',request,request))
        db.execute("INSERT INTO projects(id,name,description) VALUES(202,'Proyecto separado','Sin informe aceptado.')")
        db.execute("INSERT INTO repositories(id,project_id,name,local_path) VALUES(11,101,'observaciones',?)",(str(folder),))
    runs=SQLiteRunStore(host/'source.db');binding=WorkspaceRegistry(host/'source.db',host/'sources').bind(101,11)
    task=OwnerPlanningRecords(runs).create_task(project_id=101,title='Documentar la relación ilustrativa',type='plan',description=request,operation_key='fixture-plan-task')
    version=runs.context_snapshot(101,task['id'])['context_version']
    run=runs.admit(RunSpec(101,task['id'],'project-planner',version,'fixture-plan',request,'codex'),binding=binding)
    lease,peers=AttemptPeers.claim(runs,101,run.run_id,'synthetic-closure-planner-never-launched')
    try:
        runs.bind_native(lease,thread_id='synthetic-closure-plan-thread',turn_id='synthetic-closure-plan-turn')
        packet={'title':'Documentar la relación ilustrativa','rationale':'Describir la entrada y después explicar su relación con la salida y los límites.','basis':[{'source':'owner_request','quote':'Documentar el ejemplo'}],'assumptions':['La estructura de los datos reales aún no está comprobada.'],'epics':[{'key':'docs','title':'Entrada y salida del ejemplo','description':'Documentación del ejemplo, sin implementación ni mediciones.'}],'tasks':[
            {'key':'learn','epic_key':'docs','type':'research','title':'Documentar una observación ilustrativa','description':'Explicar id y measurement como datos inventados.','acceptance_criteria':'Entrada y su procedencia ilustrativa explícitas.','priority':2,'depends_on':[]},
            {'key':'explain','epic_key':'docs','type':'research','title':'Explicar la fila CSV y sus límites','description':'Relacionar la entrada documentada con id,value y distinguirla de datos reales.','acceptance_criteria':'Salida relacionada con entrada y límites explícitos.','priority':2,'depends_on':['learn']}]}
        plans=ProjectPlans(runs);proposal=plans.propose(lease,'fixture-closure-proposal',packet)
        for peer in peers.ids.values():peers.registry.close(peer)
        runs.finish(lease,native_status='completed',summary='Synthetic proposal, not a model output or semantic owner evaluation.')
        graph=plans.accept(101,run.run_id,operation_key='fixture-plan-acceptance',proposal_sha256=proposal['proposal_sha256'],context_version=version)
    except BaseException:
        for peer in peers.ids.values():peers.registry.close(peer)
        runs.cancel(101,run.run_id);runs.retire_inference(lease,outcome='cancelled');raise
    executions=PlanExecutions(runs);preview=executions.state(101,run.run_id)
    execution=executions.authorize(101,run.run_id,operation_key='fixture-authorize-documentation',manifest_sha256=preview['manifest_sha256'])
    research=SQLiteResearchStore(host/'source.db')
    for key in ('learn','explain'):
        spec,source=executions.prepare(execution['execution_id'],graph['tasks'][key]);accept_research(runs,research,spec,source,fixture_key="closure-"+key)
    executions.control(101,execution['execution_id'],operation_key='fixture-pause-completed-deliveries',manifest_sha256=execution['manifest_sha256'],status='paused')
    assert not executions.pending()
    state=ProjectCompletion(runs,legacy_active=lambda _:False).state(101,run.run_id)
    assert state['eligible'] and len(state['snapshot']['tasks'])==3 and len(state['snapshot']['deliveries'])==2
    assert all(item['evidence']is not None for item in state['snapshot']['tasks'])
    return {'alpha':101,'beta':202,'task':task['id'],'run':run.run_id,'report_sha256':state['report_sha256'],'report_markdown':state['report_markdown']}


def observe(host):
    """Observe exact report/receipt and closure deltas independently of the owner's rendered labels."""
    from backend.db.connection import connect

    state=observe_execution(host)
    with closing(connect(host/'source.db'))as db:
        state.update(project_status=db.execute('SELECT status FROM projects WHERE id=101').fetchone()[0],completion_events=db.execute("SELECT count(*) FROM events_log WHERE event_type='project.completed'").fetchone()[0],completion_receipts=db.execute("SELECT count(*) FROM runtime_commands WHERE json_extract(result_json,'$.kind')='project.completion'").fetchone()[0])
    return state


def verify(ids,before,after,evidence):
    """One reviewed documentary report creates one closure decision, preserving every original task/run and zero dispatches."""
    allowed={'projects','runtime_commands','events_log'}
    assert all(after['table_sha256'][name]==value for name,value in before['table_sha256'].items()if name not in allowed)
    assert before['completion_events']==before['completion_receipts']==0 and after['completion_events']==after['completion_receipts']==1
    assert after['project_status']=='completed' and after['dispatches']==0 and after['synthetic_bound_turn_ids']==3
    assert all(peer['state']=='closed'for peer in after['peers'])and before['source_sha256']==after['source_sha256']
    assert len(evidence['decisions'])==1
    receipt=evidence['decisions'][0]['receipt']
    assert receipt['report_sha256']==ids['report_sha256'] and receipt['report_markdown']==ids['report_markdown']
    assert receipt['publication_performed']is False and len(receipt['snapshot']['tasks'])==3
    assert any(item['acceptance']==receipt and item['acceptance_current']for item in evidence['completion_reads'])


if __name__=='__main__':
    import sys

    if '--resume' in sys.argv:
        sys.argv.remove('--resume');resume_page(observe,verify,'tests/project-closure.e2e.mjs',__doc__)
    else:run_page(seed,observe,verify,'tests/project-closure.e2e.mjs',__doc__)
