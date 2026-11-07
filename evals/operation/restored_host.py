"""Run one explicit subscription/Ken turn after restoring synthetic data to another host root.

The original pending request is retained, never replayed. Installed execution uses
``python -I``; this harness loads its sibling without adding the checkout to sys.path.
"""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import socket
import sqlite3
import sys
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

import httpx


def _host():
    """Reuse operational start/pair/admit/stop helpers without overriding installed backend imports."""
    spec = importlib.util.spec_from_file_location('researcher_host_smoke',Path(__file__).with_name('host_smoke.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def checkpoint(path, value):
    """Durably replace a private evaluation receipt without copying credentials or prompt bodies."""
    from backend.runtime.bootstrap import _sync_directory

    pending = path.with_suffix('.pending')
    fd = os.open(pending,os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as stream:
        json.dump(value,stream,indent=2)
        stream.write('\n');stream.flush();os.fsync(stream.fileno())
    os.replace(pending,path)
    _sync_directory(path.parent)


def verify_ken(rows):
    """Correlate this synthetic source-read call with its returned code, not a model's self-report.

This bounded fixture check does not evaluate arbitrary JavaScript or establish
general attribution for adversarial traces containing fabricated output strings.
"""
    calls = []
    for row in rows:
        if row.get('type') == 'custom_tool_call' and row.get('name') == 'exec':
            names = re.findall(r'tools\.((?:mcp__researcher_ken__)?ken_read)\s*\(',row.get('input',''))
            kind = 'custom_tool_call_output'
        elif row.get('type') == 'function_call':
            names = [row['name']] if row.get('name') in {'ken_read','mcp__researcher_ken__ken_read'} else []
            kind = 'function_call_output'
        else:
            continue
        outputs = [item for item in rows if item.get('type') == kind and item.get('call_id') == row.get('call_id')]
        if names and len(outputs) == 1 and 'return 137 + 63' in str(outputs[0].get('output','')):
            calls.extend(names)
    assert calls,'Ken read must return the restored synthetic source under the same call identity'
    return calls


def verify(root):
    """Inspect original terminal data and its exact native trace; this path never starts a service or model."""
    root = Path(root).resolve(strict=True)
    receipt = json.loads((root/'result.json').read_text())
    restored = root/'restored'
    result = {'status':'checking','generations_started_by_verification':0}
    with closing(sqlite3.connect((restored/'source.db').as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory = sqlite3.Row
        assert db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'
        assert not db.execute('PRAGMA foreign_key_check').fetchall()
        runs = [dict(row) for row in db.execute('SELECT id,status,current_attempt_id FROM runtime_runs ORDER BY rowid')]
        assert len(runs) == 2 and runs[0] == {'id':receipt['original_run_id'],'status':'superseded','current_attempt_id':None}
        assert runs[1]['id'] == receipt['run_id'] and runs[1]['status'] == 'needs_review'
        result['runs'] = runs
        dispatch = [dict(row) for row in db.execute('SELECT model,status,native_status,observed_tokens FROM runtime_inference_dispatches')]
        assert len(dispatch) == 1 and dispatch[0]['status'] == 'settled' and dispatch[0]['native_status'] == 'completed'
        result['dispatches'] = dispatch
        peers = [dict(row) for row in db.execute('SELECT kind,state FROM runtime_peers ORDER BY rowid')]
        assert all(row['state'] == 'closed' for row in peers)
        assert {'business','native','ken','command'} <= {row['kind'] for row in peers}
        result['peers'] = peers
        jobs = [dict(row) for row in db.execute('SELECT operation_key,status,exit_code,stdout,stderr,output_limited FROM runtime_jobs')]
        assert len(jobs) == 1 and jobs[0]['status'] == 'exited' and jobs[0]['exit_code'] == 0
        assert jobs[0]['stdout'].decode().strip() == '200' and not jobs[0]['output_limited']
        result['jobs'] = [{**row,'stdout':row['stdout'].decode(),'stderr':row['stderr'].decode()} for row in jobs]
        reports = [dict(row) for row in db.execute('SELECT artifact_id,status,content_sha256 FROM research_reports')]
        assert len(reports) == 1 and reports[0]['status'] == 'draft'
        assert db.execute('SELECT count(*) FROM findings').fetchone()[0] == 1
        assert db.execute('SELECT count(*) FROM report_findings').fetchone()[0] == 1
        citations = db.execute('SELECT f.quote,s.content FROM finding_sources f JOIN research_sources s ON s.id=f.source_id').fetchall()
        assert citations and all(row['quote'] and row['quote'] in row['content'] for row in citations)
        result['reports'] = reports
        result['citations_verified'] = len(citations)
        assert db.execute('SELECT count(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0] == 0
        thread = db.execute('SELECT thread_id FROM runtime_attempts').fetchone()[0]
    matches = list((restored/'control/native-state').rglob('*'+thread+'*.jsonl'))
    assert len(matches) == 1,'Inspect the exact original native thread, never a replacement turn'
    raw = matches[0].read_bytes()
    rows = [json.loads(line).get('payload',{}) for line in raw.splitlines()]
    result['ken_reads'] = verify_ken(rows)
    result['native_trace_sha256'] = hashlib.sha256(raw).hexdigest()
    for relative in ('sources/host-smoke/units.py','uploads/101/uploads/units.txt'):
        assert (root/'original'/relative).read_bytes() == (restored/relative).read_bytes()
    with closing(sqlite3.connect((root/'original/source.db').as_uri()+'?mode=ro',uri=True)) as db:
        assert db.execute('SELECT id,status,current_attempt_id FROM runtime_runs').fetchall() == [(receipt['original_run_id'],'queued',None)]
        assert db.execute('SELECT count(*) FROM runtime_attempts').fetchone()[0] == 0
    result.update(status='passed',original_unchanged=True,source_files_unchanged=True)
    checkpoint(root/'verification.json',result)
    return result


def run(output,assets_path,*,live=False):
    """Create new synthetic original/copy/restored roots and issue exactly one new subscription request."""
    if not live:
        raise ValueError('Only --live authorizes the restored-host subscription evaluation')
    from backend.runtime.host_installation import initialize_host, _read_json, inspect_host
    from backend.runtime.installation_backup import backup_installation, verify_backup
    from backend.runtime.installation_restore import restore_installation
    from backend.runtime.restored_enrollment import enroll_restored_host
    from backend.runtime.sqlite_runs import SQLiteRunStore
    from backend.runtime.contracts import RunSpec
    from backend.api.owner_endpoint import endpoint_identity

    assets = _read_json(assets_path)
    if assets.get('project_turn_limit') != 1 or assets.get('limits',{}).get('max_turns') != 1:
        raise ValueError('Provide explicit one-turn host and project limits')
    root = Path(output).absolute()
    root.mkdir(mode=0o700)
    original, restored = root/'original',root/'restored'
    host = _host()
    result = {'status':'preparing','admissions_sent':0,'service_exits':[],'model':assets['model'],'original_host_run_replayed':False}
    process = log = None
    try:
        checkpoint(root/'result.json',result)
        prepared = initialize_host(original,witness_dir=root/'original-witness',assets=assets)
        host.seed(original)
        store = SQLiteRunStore(original/'source.db')
        old = store.admit(RunSpec(101,1001,'synthetic-original',1,'original-pending-intent','Keep this original request pending; never replay it in the restored installation.','codex'))
        result['original_run_id'] = old.run_id
        request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(runtime_service=SimpleNamespace(store=store))))
        result['original_endpoint'] = endpoint_identity(request)
        backup_installation(original,root/'backup')
        result['snapshot_id'] = verify_backup(root/'backup')['snapshot_id']
        restore_installation(root/'backup',restored)
        enrollment = enroll_restored_host(restored,witness_dir=root/'restored-witness',assets=assets)
        assert enrollment['authority_id'] != prepared['authority_id']
        result['fresh_authority'] = True
        result['kernel_probe'] = inspect_host(restored,probe=True)['kernel_probe']
        with socket.socket() as binding:
            binding.bind(('127.0.0.1',0))
            port = binding.getsockname()[1]
        result['status'] = 'serving_restored'
        checkpoint(root/'result.json',result)
        process,log = host.start(restored,root,port,1)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=15) as client:
            host.pair(client,restored)
            assert client.headers['X-Researcher-Endpoint'] != result['original_endpoint']
            result['restored_endpoint'] = client.headers['X-Researcher-Endpoint']
            file = client.get('/api/files/7/download?project_id=101')
            assert file.status_code == 200 and file.content == (original/'uploads/101/uploads/units.txt').read_bytes()
            host.admit_live(client,restored,result,checkpoint=lambda value:checkpoint(root/'result.json',value))
            report = client.get('/api/artifacts/1?project_id=101')
            assert report.status_code == 200 and '200' in report.json()['content']
        result['service_exits'].append(host.stop(process,log));process=log=None
        checkpoint(root/'result.json',result)
        result['verification'] = verify(root)
        process,log = host.start(restored,root,port,2)
        with httpx.Client(base_url=f'http://127.0.0.1:{port}',trust_env=False,timeout=15) as client:
            host.pair(client,restored)
            assert client.headers['X-Researcher-Endpoint'] == result['restored_endpoint']
            result['after_restart'] = host.snapshot(restored/'source.db')
            assert result['after_restart'] == result['before_restart']
            assert client.get('/api/artifacts/1?project_id=101').status_code == 200
        result['status'] = 'passed'
    except BaseException as error:
        result.update(status='failed',error_type=type(error).__name__)
        raise
    finally:
        try:
            if process is not None:result['service_exits'].append(host.stop(process,log))
        finally:
            paths = [module.__file__ for name,module in sys.modules.items() if name.startswith('backend') and getattr(module,'__file__',None)]
            result['all_backend_imports_installed'] = bool(paths) and all(Path(p).is_relative_to(Path(sys.prefix)) for p in paths)
            checkpoint(root/'result.json',result)
    return result


def main():
    """Choose explicit new execution or read-only inspection of the original retained outcome."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true')
    parser.add_argument('--assets',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--verify-root',type=Path)
    args = parser.parse_args()
    if args.verify_root:
        result = verify(args.verify_root)
    else:
        if not args.output or not args.assets:parser.error('--output and --assets are required for a new run')
        result = run(args.output,args.assets,live=args.live)
    print(json.dumps({'status':result['status'],'admissions_sent':result.get('admissions_sent',0)}))


if __name__ == '__main__':
    main()
