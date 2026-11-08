"""Run registered policy pairs through fresh installed Codex/Ken hosts, preserving original attempts and anonymous review material."""

import argparse
import asyncio
import json
import os
import secrets
import sqlite3
import subprocess
import sys
import time
from contextlib import closing
from functools import partial
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from evals.context_alignment.protocol import comparable_input, comparable_model, digest, load_registered, register, review_item
from evals.runtime.native_trial import backend, prepare


def save(path, value):
    """Write synthetic evaluation evidence without recording authentication headers or account resources."""
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def start_policy(root, output, port, ordinal, *, policy, expected_hash, gate, task_type='investigation', execution_kind='research'):
    """Start one installed evaluation worker and keep its original process handle until actual closure."""
    import httpx
    from evals.operation.host_smoke import stop

    log=(output/'service.log').open('w')
    command=[sys.executable,'-I',str(Path(__file__).with_name('worker.py')),'--installation',str(root),
             '--policy',str(policy),'--sha256',expected_hash,'--port',str(port),'--task-type',task_type,
             '--execution-kind',execution_kind]
    if gate:command.append('--gate')
    env={k:v for k,v in os.environ.items() if not k.startswith('INFINIBAY_') and not any(p in k for p in ('API_KEY','TOKEN','SECRET')) and k not in ('PYTHONPATH','CODEX_HOME')}
    process=subprocess.Popen(command,cwd=root/'service',env=env,stdout=log,stderr=subprocess.STDOUT)
    try:
        deadline=time.monotonic()+30
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=1) as client:
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('Evaluation worker exited; inspect its retained log')
                try:
                    if client.get('/api/health/ready').json()=={'ready':True}:return process,log
                except (httpx.TransportError,ValueError):pass
                time.sleep(.1)
        raise TimeoutError('Evaluation worker not ready')
    except BaseException:
        stop(process,log)
        raise


async def terminal(owner, run_id, *, timeout=300):
    """Observe one original run without resubmitting admission, including context-correction closure."""
    async with asyncio.timeout(timeout):
        while True:
            response=await owner.get('/api/projects/101/runs/'+run_id)
            response.raise_for_status();run=response.json()
            if run['status'] not in ('queued','running','cancelling','reconciling'):
                return run
            await asyncio.sleep(.2)


def observations(trial):
    """Extract complete synthetic inputs, answers, model choices, usage and closure without host secrets."""
    with closing(sqlite3.connect(trial.database)) as db:
        db.row_factory=sqlite3.Row
        attempts=[]
        for row in db.execute('SELECT a.id,a.native_result_json,s.*,d.observed_tokens,d.status AS dispatch_status,d.catalog_hash,d.model,m.selection_json FROM runtime_attempts a JOIN runtime_input_snapshots s ON s.attempt_id=a.id JOIN runtime_inference_dispatches d ON d.attempt_id=a.id JOIN runtime_attempt_models m ON m.attempt_id=a.id ORDER BY a.started_at'):
            item=dict(row)
            item['input']=json.loads(item.pop('input_text'))
            item['native_result']=json.loads(item.pop('native_result_json') or 'null')
            item['model_selection']=json.loads(item.pop('selection_json'))
            item['model_control']=comparable_model(item['model_selection'])
            item['catalog']=json.loads(item.pop('business_catalog_json'))
            item['comparable_input_sha256']=digest(comparable_input(item['input']))
            attempts.append(item)
        result={'attempts':attempts,'peers':[dict(row) for row in db.execute('SELECT kind,state FROM runtime_peers')],
                'task_status':db.execute('SELECT status FROM tasks WHERE id=1001').fetchone()[0],
                'questions':[dict(row) for row in db.execute("SELECT title,body,options_json FROM user_requests WHERE project_id=101 ORDER BY id")],
                'unrevoked_grants':db.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0]}
    tool_path=trial.root/'tools.jsonl'
    result['tools']=[json.loads(line) for line in tool_path.read_text().splitlines()] if tool_path.exists() else []
    return result


async def run_arm(root, protocol, case, arm, assets_path):
    """Admit each planned turn once in a fresh installation; retain failed trials rather than replaying them."""
    folder=root/(case['id']+'-'+arm)
    if folder.exists():raise FileExistsError('Arm already exists; inspect its original receipt instead of replaying')
    execution_kind=protocol.get('execution_kind','research')
    if execution_kind not in ('research','development'):
        raise ValueError('This runner requires research or development admission; reviewers need exact subjects')
    turns=2 if case.get('live_correction') else 1
    assets=json.loads(assets_path.read_text())
    ceilings={key:min(assets.get('limits',{}).get(key,cap),cap) for key,cap in protocol['limits'].items()}
    assets['limits']={**assets.get('limits',{}),**ceilings}
    assets['project_turn_limit']=turns
    assets['project_token_limit']=min(assets.get('project_token_limit',350000),ceilings['max_observed_tokens']*turns)
    if execution_kind=='development':
        assets['development_checks']=[]  # The registered comparison discloses ad hoc checks only.
    private_assets=root/(case['id']+'-'+arm+'-assets.json')
    fd=os.open(private_assets,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as out:json.dump(assets,out)
    task_type=protocol.get('task_type','investigation')
    trial=prepare(folder,private_assets,live=True,turns=turns,
                  task_type=task_type,task_title=protocol.get('task_title','Context alignment'),task_context=case.get('context',{}))
    (trial.workspace/'evidence.py').write_bytes((root/'evidence.py').read_bytes())
    if execution_kind=='development':
        from evals.profile_communication.development import prepare_workspace
        prepare_workspace(trial,root,protocol)
    if protocol.get('reference_file'):
        data=(root/protocol['reference_file']).read_bytes()
        with closing(sqlite3.connect(trial.database)) as db, db:
            reference=db.execute('SELECT id,file_path FROM reference_files WHERE project_id=101').fetchone()
            Path(reference[1]).write_bytes(data)
            db.execute('UPDATE reference_files SET file_size=? WHERE id=?',(len(data),reference[0]))
    evidence={'case_id':case['id'],'arm':arm,'status':'running','runs':[],'model_turn_budget':turns,'admissions_sent':0}
    save(folder/'result.json',evidence)
    started=time.monotonic()
    starter=partial(start_policy,policy=root/(arm+'.txt'),expected_hash=protocol['files'][arm+'.txt'],gate=bool(case.get('live_correction')),task_type=task_type,execution_kind=execution_kind)
    try:
        async with backend(trial,evidence,starter=starter) as (_store,owner,_api,_database):
            async def correct(statement,key):
                """Submit one actual owner correction; a successful HTTP receipt is not itself proof of model comprehension."""
                response=await owner.post('/api/projects/101/tasks/1001/context-corrections',json={'operation_key':key,'expected_version':1,'statement':statement,'source_kind':'user_message'})
                response.raise_for_status()
                evidence['correction']=response.json()
                return response.json()['context_version']

            version=await correct(case['correction'],'registered-correction') if case.get('correction') else 1

            async def admit(request,version,key):
                """Persist intent before one POST so lost replies cannot trigger an automatic second admission."""
                evidence['admissions_sent']+=1
                save(folder/'result.json',evidence)
                body={'operation_key':key,'context_version':version,'request':protocol['request_prefix']+request}
                if execution_kind=='development':body['repository_id']=protocol['repository_id']
                response=await owner.post('/api/projects/101/tasks/1001/runs',json=body)
                evidence.setdefault('admission_receipts',[]).append({'status':response.status_code,'body':response.json()})
                save(folder/'result.json',evidence)
                response.raise_for_status()
                return response.json()['run_id']

            run_id=await admit(case['request'],version,'registered-first')
            if case.get('live_correction'):
                async with asyncio.timeout(180):
                    while not (folder/'correction-ready').exists():await asyncio.sleep(.05)
                before=await owner.get('/api/projects/101/runs/'+run_id);before.raise_for_status()
                if before.json()['status']!='running':raise RuntimeError('Correction did not reach an active attempt')
                try:version=await correct(case['live_correction'],'registered-live-correction')
                finally:(folder/'correction-release').write_text('Owner correction submitted; release only original held response.\n')
                previous=await terminal(owner,run_id)
                evidence['runs'].append(previous)
                if previous['status']!='superseded':raise RuntimeError('Old corrected attempt did not reach superseded')
                run_id=await admit(case['followup'],version,'registered-corrected')
            evidence['runs'].append(await terminal(owner,run_id))
            evidence.update(observations(trial))
            if execution_kind=='development':
                response=await owner.get('/api/projects/101/runs/'+run_id+'/code-result')
                response.raise_for_status()
                evidence['code_result']=response.json()
                evidence['original_source_unchanged']=all((trial.workspace/name).read_bytes()==(root/name).read_bytes() for name in protocol['workspace_files'])
                if not evidence['original_source_unchanged']:
                    raise RuntimeError('Development changed the registered original source')
            if evidence['runs'][-1]['status'] not in ('needs_review','waiting_input'):
                raise RuntimeError('No complete explanation or material question; preserve this arm as failed')
            if evidence['unrevoked_grants'] or any(row['state']!='closed' for row in evidence['peers']):
                raise RuntimeError('Original model/tool peers not closed')
            verify_ken(evidence['tools'],required_source=(root/'evidence.py').read_text() if protocol.get('require_complete_source') else None)
            evidence['status']='observed'
    except BaseException as error:
        evidence.update(status='failed',error_type=type(error).__name__,error=str(error))
        raise
    finally:
        evidence['seconds']=round(time.monotonic()-started,3)
        save(folder/'result.json',evidence)
        print(case['id'],arm,evidence['status'],flush=True)
    return evidence


def verify_ken(records, *, required_source=None):
    """Require successful real Ken calls and returned fixture code, not merely attempted tool names."""
    successful=[row for row in records if row['response'].get('success') is True]
    if not {'ken_find','ken_read'} <= {row['tool'] for row in successful}:
        raise RuntimeError('Required successful actual Ken calls absent')
    reads='\n'.join(item.get('text','') for row in successful if row['tool']=='ken_read'
                    and (required_source is None or row.get('arguments',{}).get('path')=='evidence.py')
                    for item in row['response'].get('contentItems',[]))
    required=tuple(line for line in required_source.splitlines() if line.strip()) if required_source is not None else ('timeout_seconds','tax_amount','CorrectionReceipt')
    if not all(symbol in reads for symbol in required):
        raise RuntimeError('Ken did not return the registered source needed for these cases')


def compare_pair(first,second):
    """Accept only paired model/tool/input controls; do not turn matched controls into a quality score."""
    if len(first['attempts'])!=len(second['attempts']):raise ValueError('Unequal turn counts')
    for a,b in zip(first['attempts'],second['attempts']):
        for key in ('comparable_input_sha256','catalog_hash','model_control'):
            left,right=a[key],b[key]
            if key=='comparable_input_sha256' and 'input' in a and 'input' in b:
                left,right=digest(comparable_input(a['input'])),digest(comparable_input(b['input']))
            if key=='model_control' and isinstance(left,dict) and isinstance(right,dict):
                left,right=comparable_model(left),comparable_model(right)
            if left!=right:raise ValueError('Paired control differs: '+key)
    return {'controls_matched':True,'quality_review':'pending','human_observation':'pending',
            'model_receipt_identity_variation':['run_id','attempt_id','selected_at']}


def export_review(root, case, pair):
    """Randomize visible labels after collection and keep the unblinding key outside the review packet."""
    arms=['baseline','candidate']
    if secrets.randbelow(2):arms.reverse()
    items=[]
    for label,arm in zip(('A','B'),arms):
        final=pair[arm]['attempts'][-1]['native_result'] or {}
        response=final.get('summary',final.get('text',''))
        if not response and pair[arm]['questions']:
            response=json.dumps(pair[arm]['questions'],ensure_ascii=False,indent=2)
        items.append(review_item(case['id'],label,response))
    save(root/(case['id']+'-review.json'),{'request':case['request'],
         'correction':case.get('correction') or case.get('live_correction'),
         'followup':case.get('followup'),'responses':items,
         'questions':['¿Cuál es la conclusión?','¿Qué todavía no está demostrado?','¿Cómo corregirías una premisa?']})
    save(root/(case['id']+'-key.json'),dict(zip(('A','B'),arms)))


async def run(args):
    """Run only unstarted registered arms in the chosen split, stopping on invalid trials or mismatched controls."""
    protocol=load_registered(args.output)
    if args.case and not any(case['id']==args.case and case['split']==args.split for case in protocol['cases']):
        raise ValueError('Unknown case in requested split')
    for index,case in enumerate(protocol['cases']):
        if case['split']!=args.split or (args.case and case['id']!=args.case):continue
        order=('baseline','candidate') if index%2==0 else ('candidate','baseline')
        pair={}
        for arm in order:
            load_registered(args.output)
            pair[arm]=await run_arm(args.output,protocol,case,arm,args.assets)
        comparison=compare_pair(pair['baseline'],pair['candidate'])
        comparison['analysis_amendment_sha256']=protocol.get('analysis_amendment_sha256')
        save(args.output/(case['id']+'-comparison.json'),comparison)
        export_review(args.output,case,pair)
        print('Pair controls verified',case['id'],flush=True)


def main():
    """Keep preparation account-free and require explicit live opt-in before any model admission."""
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--prepare',action='store_true')
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--assets',type=Path)
    parser.add_argument('--split',choices=('development','reserved'),default='development')
    parser.add_argument('--case')
    args=parser.parse_args();args.output=args.output.resolve()
    if args.prepare:
        register(args.output);print('Registered',args.output);return
    if not args.live or args.assets is None:parser.error('--live and --assets are required for model work')
    asyncio.run(run(args))


if __name__=='__main__':main()
