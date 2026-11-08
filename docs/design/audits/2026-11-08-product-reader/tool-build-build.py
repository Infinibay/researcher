"""Build current isolated reader tooling while retaining original build handles and package-version receipts."""
import importlib.util
import json
from pathlib import Path
import subprocess
from datetime import datetime,timezone
ROOT=Path.cwd();parent=ROOT/'.superpowers/sdd/2026-10-31-actualizacion-proyecto'
spec=importlib.util.spec_from_file_location('container_tools',parent/'container_tools.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
command=json.loads((parent/'container-tools/podman-command.json').read_text())+['build','--pull=missing','--network=host','--layers','-t','localhost/researcher:reader-current','-f',str(parent/'reader-current/Containerfile'),str(parent/'reader-current')]
receipt={'started_utc':datetime.now(timezone.utc).isoformat(),'scope':'Current isolated accessibility tooling; not product packaging or reader acceptance'}
try:
 with (parent/'reader-current/build.log').open('x') as stream:
  result=subprocess.run(command,env=module.environment(),stdout=stream,stderr=subprocess.STDOUT,timeout=600)
 receipt['exit']=result.returncode
finally:
 receipt['finished_utc']=datetime.now(timezone.utc).isoformat();(parent/'reader-current/build-result.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt),flush=True)
if result.returncode:raise SystemExit(result.returncode)
