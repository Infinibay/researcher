"""Run compiled-browser recovery against an installed owner server and synthetic committed events."""

import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.request


def main():
    """Own a temporary database, listener and server; verify browser replay and always close the child."""
    repo = Path(__file__).resolve().parents[2]
    scratch = repo / '.superpowers/sdd/2026-10-31-actualizacion-proyecto'
    node = scratch / 'toolchains/node-v24.22.2-linux-x64/bin/node'
    out = repo / 'docs/design/audits/2026-11-07-durable-events'
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='researcher-event-browser-') as directory:
        root = Path(directory)
        database = root / 'events.db'
        init = "from backend.tools.base.db import ensure_migrations;import sys,sqlite3;ensure_migrations(sys.argv[1]);db=sqlite3.connect(sys.argv[1]);db.execute(\"INSERT INTO projects(id,name) VALUES(1,'Eventos controlados'),(2,'Otro proyecto')\");db.commit();db.close()"
        subprocess.run([sys.executable,'-I','-c',init,str(database)],cwd=root,check=True,capture_output=True)
        with socket.socket() as listener, (out/'server.log').open('w') as log:
            listener.bind(('127.0.0.1',0));listener.listen(32)
            origin = 'http://127.0.0.1:'+str(listener.getsockname()[1])
            env = {key:value for key,value in os.environ.items() if key not in {'INFINIBAY_RUNTIME_CONFIG','PYTHONPATH'} and not any(part in key for part in ('API_KEY','TOKEN','SECRET'))}
            env.update(INFINIBAY_DB=str(database),INFINIBAY_DATA=str(root/'data'),INFINIBAY_AUTH_DIR=str(root/'auth'),INFINIBAY_STATIC_DIR=str(repo/'frontend/dist'),OTEL_SDK_DISABLED='true',DO_NOT_TRACK='1')
            program = "import sys,uvicorn;from backend.api.main import create_app;from backend.api.local_access import LocalAccess;uvicorn.run(create_app(access=LocalAccess(pairing_key='event-browser-fixture-code-at-least-32-characters')),fd=int(sys.argv[1]),access_log=False,log_level='warning')"
            server = subprocess.Popen([sys.executable,'-I','-c',program,str(listener.fileno())],cwd=root,env=env,pass_fds=(listener.fileno(),),stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+15
                while True:
                    if server.poll() is not None:
                        raise RuntimeError('Owned event server exited before readiness')
                    try:
                        with urllib.request.urlopen(origin+'/api/session',timeout=0.25) as response:
                            if response.status==200:break
                    except OSError:
                        if time.monotonic()>=deadline:raise
                        time.sleep(0.05)
                browser_env={**env,'EVENT_ORIGIN':origin,'EVENT_DATABASE':str(database),'EVENT_PYTHON':sys.executable,'EVENT_ARTIFACT_DIR':str(out)}
                trial=subprocess.run([str(node),'tests/events.browser.mjs'],cwd=repo/'frontend',env=browser_env,capture_output=True,text=True,timeout=120)
                (out/'browser.log').write_text(trial.stdout+'\n'+trial.stderr)
                with sqlite3.connect(database) as db:
                    counts={table:db.execute('SELECT count(*) FROM '+table).fetchone()[0] for table in ('runtime_runs','runtime_inference_dispatches')}
                assert counts=={'runtime_runs':0,'runtime_inference_dispatches':0},counts
                assert trial.returncode==0,trial.stderr[-4000:]
            finally:
                server.terminate()
                try:server.wait(timeout=10)
                except subprocess.TimeoutExpired:server.kill();server.wait(timeout=5)
                (out/'server-exit.json').write_text(json.dumps({'pid':server.pid,'returncode':server.returncode})+'\n')
            result={'scope':'Installed Python application and compiled frontend over real loopback HTTP/WebSocket; synthetic data only','server_returncode':server.returncode,'counts':counts,'model_turns':0,'owner_processes_closed':server.poll() is not None,'browser_receipt':str(out.relative_to(repo)/'evidence.json')}
            (out/'operation.json').write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps(result))


if __name__=='__main__':
    main()
