"""Own an isolated rootless Orca/Xvfb capability container and retain its terminal result."""
import importlib.util,json,subprocess,shutil
from pathlib import Path
ROOT=Path.cwd();parent=ROOT/'.superpowers/sdd/2026-10-31-actualizacion-proyecto'
spec=importlib.util.spec_from_file_location('container_tools',parent/'container_tools.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
out=ROOT/'.researcher/evaluations/reader-capability-20261108-speech-complete';out.mkdir(mode=0o700)
for name in ['probe.py','probe.mjs','run-probe.py']:shutil.copy2(parent/'reader-tools'/name,out/name)
command=json.loads((parent/'container-tools/podman-command.json').read_text())+['run','--rm','--name','researcher-reader-capability','--network=none','--shm-size=512m','--mount',f'type=bind,source={parent}/reader-tools,destination=/opt/audit,ro','--mount',f'type=bind,source={ROOT}/frontend/node_modules,destination=/opt/frontend/node_modules,ro','--mount','type=bind,source=/home/andres/.cache/ms-playwright/chromium-1248/chrome-linux64,destination=/opt/chromium,ro','--mount',f'type=bind,source={out},destination=/out','localhost/researcher:reader-evaluation','dbus-run-session','--','python3','/opt/audit/probe.py']
with (out/'container.log').open('x') as log:r=subprocess.run(command,env=module.environment(),stdout=log,stderr=subprocess.STDOUT,timeout=120)
(out/'container-result.json').write_text(json.dumps({'exit':r.returncode,'scope':'Tool capability, not product screen-reader acceptance'})+'\n');print('container exit',r.returncode,flush=True)
raise SystemExit(r.returncode)
