"""Compare PageDown/Tab timing on the retained synthetic host, without new records or inference."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
ROOT=Path.cwd()
sys.path.insert(0,str(ROOT/'evals/operation'))
from host_smoke import start,stop
from web_workspace import observe
out=ROOT/'.researcher/evaluations/native-zoom-20261108-scroll-probe'
out.mkdir(mode=0o700)
host=ROOT/'.researcher/evaluations/native-zoom-20261108-focus-margin/host'
before=observe(host/'source.db')
project=next(p['id'] for p in before['projects'] if p['name']=='Atlas comprobable')
with socket.socket() as binding:
 binding.bind(('127.0.0.1',0));port=binding.getsockname()[1]
result={'status':'running','scope':'Focused real UI on retained synthetic host; no resource seeds or model requests'}
process=log=None
try:
 process,log=start(host,out,port,1)
 owner,=list((host/'auth').glob('owner-*.key'))
 env={**os.environ,'RESEARCHER_E2E_ORIGIN':f'http://127.0.0.1:{port}','RESEARCHER_E2E_OWNER_FILE':str(owner),'RESEARCHER_E2E_OUTPUT':str(out),'RESEARCHER_PROBE_PROJECT':str(project)}
 node=ROOT/'.superpowers/sdd/2026-10-31-actualizacion-proyecto/toolchains/node-v24.22.2-linux-x64/bin/node'
 with (out/'browser.log').open('x') as stream:
  child=subprocess.run([str(node),str(ROOT/'.superpowers/sdd/2026-10-31-actualizacion-proyecto/zoom-scroll-probe.mjs')],env=env,stdout=stream,stderr=subprocess.STDOUT)
 result['browser_exit']=child.returncode
 assert child.returncode==0
 result['status']='passed'
finally:
 if process is not None:result['service_exit']=stop(process,log)
 after=observe(host/'source.db')
 result['storage_unchanged']=before==after
 result['runs']=after['runs'];result['dispatches']=after['dispatches'];result['integrity']=after['integrity']
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
 print(json.dumps(result))
 assert before==after and after['runs']==after['dispatches']==0 and after['integrity']=='ok'
