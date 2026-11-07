"""Rehearse legacy SQL/files and real Chroma migration into the installed native product without inference."""

import argparse
from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys

import httpx


CHROMA_FIXTURE = '''import chromadb,json,sys
from chromadb.config import Settings
client=chromadb.PersistentClient(path=sys.argv[1],settings=Settings(anonymized_telemetry=False))
alpha=client.create_collection('historical-alpha',embedding_function=None)
alpha.add(ids=[f'p1-c{i}' for i in range(103)],documents=[f'Fragmento histórico {i}: 137 + 63 = 200.' for i in range(103)],embeddings=[[0.1,0.2,0.3] for _ in range(103)],metadatas=[{'page':1,'chunk_index':i,'source':'original-missing.pdf','project_id':202} for i in range(103)])
alpha.add(ids=['metadata-only'],embeddings=[[0.3,0.2,0.1]],metadatas=[{'source':'missing textual content'}])
beta=client.create_collection('historical-beta',embedding_function=None)
beta.add(ids=['p1-c0'],documents=['Texto de otro proyecto.'],embeddings=[[0.1,0.3,0.2]])
print(json.dumps({'collections':2,'records':105,'embedding_calls':0}))
'''


def isolated(python, root, *args, log_name):
    """Run the pinned legacy reader with no network namespace and writes confined to this fixture root."""
    command=['bwrap','--unshare-net','--die-with-parent','--ro-bind','/','/',
             '--bind',str(root),str(root),'--proc','/proc','--dev','/dev','--chdir',str(root),
             '--',str(python),'-I',*map(str,args)]
    with (root/log_name).open('w') as log:
        result=subprocess.run(command,env={'PATH':os.defpath,'HOME':str(root/'home'),
            'LANG':'C.UTF-8','ANONYMIZED_TELEMETRY':'False','HF_HUB_OFFLINE':'1'},
            stdout=log,stderr=subprocess.STDOUT,timeout=90,check=False)
    if result.returncode:raise RuntimeError(f'Original isolated legacy step failed; inspect {log_name}')


def seed(root):
    """Create an original schema17 database and a report whose body exists only at a mapped host path."""
    import backend.db

    old=root/'old';old.mkdir()
    reports=old/'reports';reports.mkdir()
    (reports/'original.md').write_text('# Informe histórico\n\nContenido conservado exactamente.\n')
    database=old/'legacy.db'
    schema=Path(backend.db.__file__).with_name('schema.sql')
    with closing(sqlite3.connect(database)) as db,db:
        db.executescript(schema.read_text())
        db.execute("INSERT INTO projects(id,name) VALUES(101,'Legacy alpha'),(202,'Legacy beta')")
        db.execute("INSERT INTO tasks(id,project_id,type,title,status) VALUES(1001,101,'research','Retained historical task','in_progress')")
        db.execute("INSERT INTO artifacts(id,project_id,task_id,type,file_path) VALUES(7,101,1001,'report','/artifacts/original.md')")
    return database,{'format':1,'storage':[{'name':'reports','path':str(reports),'stored_prefix':'/artifacts'}],
                     'chroma_exports':[{'path':str(root/'export'),'projects':{'historical-alpha':101,'historical-beta':202}}]}


def inspect_product(root, result):
    """Capture one imported fragment through normal source APIs and verify its preserved identity and text."""
    from backend.research.sqlite_store import SQLiteResearchStore
    from backend.research.acquisition import BoundedReferenceReader
    from backend.research.service import ResearchService

    receipt=result['import']
    manifest=json.loads((root/'imported'/receipt['import_manifest']).read_text())
    fragments=manifest['chroma_chunks']
    assert len(fragments)==105 and sum(row['reference_id'] is None for row in fragments)==1
    fragment=next(row for row in fragments if row['collection']=='historical-alpha' and row['original_id']=='p1-c0')
    store=SQLiteResearchStore(root/'imported/source.db')
    token=store.issue_grant(project_id=101,task_id=1001,agent_id='legacy-evaluator',permissions={'sources.read','sources.capture','reports.read'})
    scope=store.authorize(token)
    service=ResearchService(store,reference_reader=BoundedReferenceReader(root/'imported/uploads'))
    captured=service.capture_reference(scope,'original-imported-fragment-capture',fragment['reference_id'])
    source=store.read_source(scope,captured['source_id'])
    assert source['content']=='Fragmento histórico 0: 137 + 63 = 200.'
    history=source['provenance']['imported_history']
    assert history['original_id']=='p1-c0' and history['metadata']['project_id']==202 and history['project_id']==101
    assert history['complete_original_document'] is False
    report=store.read_report(scope,7)
    assert report['record_origin']=='legacy_unverified' and 'exactamente' in report['content']
    result.update(reference_id=fragment['reference_id'],source_id=captured['source_id'],
                  preserved_fragments=105,text_attachments=104,metadata_only_records=1,
                  exact_capture_and_historical_provenance=True,legacy_report_unverified=True)


def native_http(root, assets, result):
    """Enroll with synthetic account material, start the installed native API and read retained scoped data."""
    from backend.runtime.restored_enrollment import enroll_restored_host

    synthetic=root/'synthetic-account.json'
    synthetic.write_text(json.dumps({'auth_mode':'chatgpt','tokens':{'access_token':'fixture.header.signature','account_id':'fixture'}}))
    synthetic.chmod(0o600)
    selected={**assets,'token_file':str(synthetic),'model':'controlled-no-inference'}
    enrolled=enroll_restored_host(root/'imported',witness_dir=root/'fresh-witness',assets=selected)
    spec=importlib.util.spec_from_file_location('host_smoke',Path(__file__).with_name('host_smoke.py'))
    smoke=importlib.util.module_from_spec(spec);spec.loader.exec_module(smoke)
    with socket.socket() as binding:
        binding.bind(('127.0.0.1',0));port=binding.getsockname()[1]
    process,log=smoke.start(root/'imported',root,port,1)
    try:
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=15) as client:
            smoke.pair(client,root/'imported')
            report=client.get('/api/artifacts/7?project_id=101');report.raise_for_status()
            assert 'exactamente' in report.json()['content']
            attachment=client.get(f'/api/files/{result["reference_id"]}/download?project_id=101')
            attachment.raise_for_status()
            assert attachment.text=='Fragmento histórico 0: 137 + 63 = 200.'
            assert client.get(f'/api/files/{result["reference_id"]}/download?project_id=202').status_code==404
    finally:
        result['service_exit']=smoke.stop(process,log)
    result.update(native_http_read_verified=True,resources=enrolled['resource_observations'])
    with sqlite3.connect(root/'imported/source.db') as db:
        assert db.execute('SELECT count(*) FROM runtime_runs').fetchone()==(0,)
        assert db.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()==(0,)


def main():
    """Run one NEW synthetic compatibility trial with installed backend and an isolated pinned export environment."""
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','legacy-python','assets'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    import backend
    assert Path(backend.__file__).is_relative_to(Path(sys.prefix))
    legacy=args.legacy_python.absolute();assets=json.loads(args.assets.read_text())
    root=args.output.absolute();root.mkdir(mode=0o700);(root/'home').mkdir()
    result={'status':'running','model_turns':0,'embedding_calls':0,'legacy_network_namespace':'none',
            'real_account_copied':False,'installed_backend':True}
    try:
        database,manifest=seed(root)
        before=hashlib.sha256(database.read_bytes()).hexdigest()
        isolated(legacy,root,'-c',CHROMA_FIXTURE,root/'old/chroma',log_name='chroma-fixture.log')
        script=Path(__file__).resolve().parents[2]/'scripts/export_legacy_chroma.py'
        isolated(legacy,root,script,'--source',root/'old/chroma','--output',root/'export',log_name='chroma-export.log')
        mapping=root/'mapping.json';mapping.write_text(json.dumps(manifest))
        completed=subprocess.run([sys.executable,'-I','-m','backend.cli.bootstrap','stage-legacy-host',
            '--database',str(database),'--storage-manifest',str(mapping),'--destination',str(root/'imported')],
            capture_output=True,text=True,timeout=90,check=False)
        (root/'import-cli.log').write_text(completed.stdout+'\n'+completed.stderr)
        if completed.returncode:raise RuntimeError('Original installed import failed; inspect import-cli.log')
        result['import']=json.loads(completed.stdout)
        assert hashlib.sha256(database.read_bytes()).hexdigest()==before
        inspect_product(root,result)
        native_http(root,assets,result)
        result['status']='passed'
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        (root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))


if __name__=='__main__':
    main()
