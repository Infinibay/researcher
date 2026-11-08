"""Build isolated Orca/Xvfb tooling using the already downloaded Node base image and task-local rootless Podman."""
import importlib.util
import json
from pathlib import Path
import subprocess
from datetime import datetime,timezone
ROOT=Path.cwd()
parent=ROOT/'.superpowers/sdd/2026-10-31-actualizacion-proyecto'
spec=importlib.util.spec_from_file_location('container_tools',parent/'container_tools.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
command=json.loads((parent/'container-tools/podman-command.json').read_text())+['build','--pull=never','--network=host','--layers','-t','localhost/researcher:reader-evaluation','-f',str(parent/'reader-tools/Containerfile'),str(parent/'reader-tools')]
receipt={'started_utc':datetime.now(timezone.utc).isoformat(),'scope':'Disposable accessibility tooling, not product packaging or screen-reader acceptance'}
try:
 with (parent/'reader-tools/build.log').open('x') as stream:
  result=subprocess.run(command,env=module.environment(),stdout=stream,stderr=subprocess.STDOUT,timeout=600)
 receipt['exit']=result.returncode
finally:
 receipt['finished_utc']=datetime.now(timezone.utc).isoformat()
 (parent/'reader-tools/build-result.json').write_text(json.dumps(receipt,indent=2)+'\n')
 print(json.dumps(receipt),flush=True)
if result.returncode:raise SystemExit(result.returncode)
