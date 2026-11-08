"""Verify current installed bytes and selected behavior without importing the source checkout."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

root = Path.cwd()
scratch = root/'.superpowers/sdd/2026-10-31-actualizacion-proyecto'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--python',type=Path,default=scratch/'native-runtime-env/bin/python')
parser.add_argument('--subdir',default='')
options=parser.parse_args()
out=scratch/'documentation-final'/options.subdir
if options.subdir:out.mkdir()
python=options.python.absolute()
paths = ['backend/tests/research/test_http_client.py', 'backend/tests/research/test_async_http_client.py', 'backend/tests/research/test_web_fetcher.py', 'backend/tests/tools/test_db_layer.py', 'backend/tests/runtime/test_host_business.py', 'backend/tests/runtime/test_business_mediation.py', 'backend/tests/runtime/test_code_mode_host.py', 'backend/tests/runtime/test_broker_native.py', 'backend/tests/runtime/test_runtime_profile.py', 'backend/tests/runtime/test_ken_mediation.py', 'backend/tests/runtime/test_host_installation.py::test_prepared_semantic_assets_reach_reopened_host_and_launcher', 'backend/tests/runtime/test_owner_history.py::test_archive_requires_the_actual_project_and_preserves_native_receipts', 'backend/tests/runtime/test_workspace_delivery.py::test_owner_can_inspect_sources_and_closed_task_runs_without_runtime_config']
worker = r'''
import hashlib,importlib.metadata as metadata,json,sys,xml.etree.ElementTree as ET
from pathlib import Path
import pytest
project=metadata.distribution('researcher')
assert not json.loads(project.read_text('direct_url.json') or '{}').get('dir_info',{}).get('editable',False)
expected=json.loads(Path(sys.argv[3]).read_text())['files']
backend=Path(project.locate_file('backend'))
actual={str(p.relative_to(backend.parent)) for p in backend.rglob('*') if p.is_file() and p.suffix in {'.py','.sql'}}
assert actual==set(expected), {'extra':sorted(actual-set(expected)),'missing':sorted(set(expected)-actual)}
assert all(hashlib.sha256(Path(project.locate_file(name)).read_bytes()).hexdigest()==digest for name,digest in expected.items())
root=Path(sys.argv[1]);ini=root/'pytest.ini'
ini.write_text('[pytest]\nasyncio_mode=auto\nasyncio_default_fixture_loop_scope=function\n')
paths=json.loads(sys.argv[2]);resolved=[str(project.locate_file(p.partition('::')[0]))+('::'+p.partition('::')[2] if '::' in p else '') for p in paths]
status=pytest.main(['-q','-c',str(ini),'-m','not live','--disable-socket','--allow-unix-socket','--timeout=60','--junitxml='+str(root/'results.xml'),*resolved])
modules={name:module.__file__ for name,module in sys.modules.items() if (name=='backend' or name.startswith('backend.')) and getattr(module,'__file__',None)}
assert modules and all(Path(p).resolve().is_relative_to(Path(sys.prefix).resolve()) for p in modules.values()),modules
cases=ET.parse(root/'results.xml').findall('.//testcase')
observed={'cases':len(cases),'passed':sum(not any(c.find(t)is not None for t in ['failure','error','skipped']) for c in cases),'failed':sum(any(c.find(t)is not None for t in ['failure','error']) for c in cases),'skipped':sum(c.find('skipped')is not None for c in cases),'backend_modules':len(modules),'all_backend_imports_installed':True,'installed_bytes_match':len(expected),'seconds':float(ET.parse(root/'results.xml').find('.//testsuite').get('time')),'exit_code':int(status)}
print('DOCUMENTATION-INSTALLED:'+json.dumps(observed))
raise SystemExit(status)
'''
env = {k:v for k,v in os.environ.items() if 'API_KEY' not in k and k not in {'PYTHONPATH','INFINIBAY_RUNTIME_CONFIG','INFINIBAY_RETRIEVAL_ASSET_DIR'}}
env['RESEARCHER_TEST_RETRIEVAL_ASSETS']=str(scratch/'retrieval-assets/prepared')
with tempfile.TemporaryDirectory(prefix='researcher-documentation-installed-') as directory:
    temporary=Path(directory);env['INFINIBAY_DB']=str(temporary/'not-created.sqlite')
    result=subprocess.run([str(python),'-I','-c',worker,str(temporary),json.dumps(paths),str(scratch/'documentation-final/package-bytes.json')],cwd=temporary,env=env,capture_output=True,text=True,timeout=900)
    (out/'installed-tests.log').write_text(result.stdout+'\n'+result.stderr)
    if (temporary/'results.xml').exists():(out/'installed-tests.xml').write_bytes((temporary/'results.xml').read_bytes())
    lines=[line for line in result.stdout.splitlines() if line.startswith('DOCUMENTATION-INSTALLED:')]
    receipt={'scope':'Selected actual installed tests and complete byte membership, not installed global suite','paths':paths,'process_exit':result.returncode,'observed':json.loads(lines[-1].split(':',1)[1]) if lines else None,'real_model_turns_requested':0}
    (out/'installed-tests.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps(receipt.get('observed') or {'exit':result.returncode,'inspect':'installed-tests.log'}))
    assert result.returncode==0 and receipt['observed']['skipped']==0
