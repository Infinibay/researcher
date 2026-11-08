"""Own a fresh synthetic installed-page evaluation without exposing account credentials or replaying work."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from host_smoke import start, stop

ROOT=Path(__file__).resolve().parents[2]


def run_page(seed,observe,verify,browser_script,description):
    """Prepare one synthetic host, retain before/after observations and always close the original service handle."""
    import backend
    from backend.runtime.host_installation import initialize_host

    parser=argparse.ArgumentParser(description=description)
    parser.add_argument('--assets',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--node',type=Path,required=True)
    args=parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):raise RuntimeError('Use the separately installed product Python')
    output=args.output.resolve();output.mkdir(mode=0o700)
    assets=json.loads(args.assets.read_text());token=output/'synthetic-account.json'
    with token.open('x') as stream:
        os.chmod(token,0o600)
        json.dump({'auth_mode':'chatgpt','tokens':{'access_token':'synthetic.header.signature','account_id':'synthetic-page'}},stream)
    assets.update(token_file=str(token),static_dir=str(ROOT/'frontend/dist'));assets.pop('storage',None)
    host=output/'host';initialize_host(host,witness_dir=output/'witness',assets=assets)
    ids=seed(host);fixture=output/'fixture.json';fixture.write_text(json.dumps(ids,indent=2)+'\n')
    before=observe(host)
    result={'status':'running','synthetic_project_data':True,'actual_model_turns':0,'before':before,'backend':str(Path(backend.__file__).resolve()),'web_index_sha256':hashlib.sha256((ROOT/'frontend/dist/index.html').read_bytes()).hexdigest()}
    with socket.socket() as binding:binding.bind(('127.0.0.1',0));port=binding.getsockname()[1]
    process=log=None
    try:
        process,log=start(host,output,port,1)
        keys=list((host/'auth').glob('owner-*.key'))
        if len(keys)!=1:raise RuntimeError('Expected one private synthetic owner key')
        env={**os.environ,'RESEARCHER_E2E_ORIGIN':f'http://127.0.0.1:{port}','RESEARCHER_E2E_OWNER_FILE':str(keys[0]),'RESEARCHER_E2E_OUTPUT':str(output/'browser'),'RESEARCHER_E2E_FIXTURE':str(fixture)}
        with (output/'browser.log').open('x') as browser_log:
            browser=subprocess.run([str(args.node.resolve(strict=True)),browser_script],cwd=ROOT/'frontend',env=env,stdout=browser_log,stderr=subprocess.STDOUT,check=False,timeout=180)
        result['browser_exit']=browser.returncode
        assert browser.returncode==0,'Inspect original browser log and retained state before continuing'
        evidence=json.loads((output/'browser/evidence.json').read_text());verify(ids,before,observe(host),evidence)
        result['status']='passed'
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__);raise
    finally:
        if process is not None:result['service_exit']=stop(process,log)
        result['after']=observe(host)
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'receipt':str(output/'result.json')}),flush=True)


def resume_page(observe,verify,browser_script,description):
    """Continue an already-verified original effect with reads only; never reseed, retry owner decisions or replace its receipt.

    The caller's domain verifier must prove the retained effect before restart.
    Original before/evidence stay separate from continuation_start/after. The
    browser receives original evidence and must forbid write recovery in this
    mode. Any changed observed business state fails the continuation itself.
    """
    import backend

    parser=argparse.ArgumentParser(description=description)
    parser.add_argument('--original',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--node',type=Path,required=True)
    args=parser.parse_args()
    if not Path(backend.__file__).resolve().is_relative_to(Path(sys.prefix).resolve()):raise RuntimeError('Use the separately installed product Python')
    original=args.original.resolve(strict=True);prior=json.loads((original/'result.json').read_text())
    ids=json.loads((original/'fixture.json').read_text());host=original/'host'
    evidence=json.loads((original/'browser/evidence.json').read_text());current=observe(host)
    assert prior['service_exit']==143 and prior['after']==current
    assert prior['web_index_sha256']==hashlib.sha256((ROOT/'frontend/dist/index.html').read_bytes()).hexdigest()
    verify(ids,prior['before'],current,evidence)
    output=args.output.resolve();output.mkdir(mode=0o700)
    result={'status':'running','original_result':str(original/'result.json'),'before':prior['before'],'continuation_start':current,'scope':'Readonly original-state continuation; original effects are verified before restart, never repeated.'}
    with socket.socket()as binding:binding.bind(('127.0.0.1',0));port=binding.getsockname()[1]
    process=log=None
    try:
        process,log=start(host,output,port,2)
        keys=list((host/'auth').glob('owner-*.key'));assert len(keys)==1
        env={**os.environ,'RESEARCHER_E2E_ORIGIN':f'http://127.0.0.1:{port}','RESEARCHER_E2E_OWNER_FILE':str(keys[0]),'RESEARCHER_E2E_OUTPUT':str(output/'browser'),'RESEARCHER_E2E_FIXTURE':str(original/'fixture.json'),'RESEARCHER_E2E_REVIEW_ORIGINAL':str(original/'browser/evidence.json')}
        with(output/'browser.log').open('x')as stream:
            browser=subprocess.run([str(args.node.resolve(strict=True)),browser_script],cwd=ROOT/'frontend',env=env,stdout=stream,stderr=subprocess.STDOUT,check=False,timeout=120)
        result['browser_exit']=browser.returncode
        assert browser.returncode==0,'Inspect the original continuation state before another action'
        assert observe(host)==current
        verify(ids,prior['before'],current,json.loads((output/'browser/evidence.json').read_text()))
        result['status']='passed'
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__);raise
    finally:
        if process is not None:result['service_exit']=stop(process,log)
        result['after']=observe(host)
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        print(json.dumps({'status':result['status'],'receipt':str(output/'result.json')}),flush=True)
