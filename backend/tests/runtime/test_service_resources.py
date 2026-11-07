"""Exercise service-wide kernel budgets and original process ownership without model calls."""

import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest


@pytest.fixture
def delegated_service_parent():
    """Use only new owned sibling groups under an already delegated parent; never modify its policy."""
    relative = Path('/proc/self/cgroup').read_text().strip().split(':',2)[2]
    parent = (Path('/sys/fs/cgroup')/relative.lstrip('/')).parent
    if not {'cpu','memory','pids'} <= set((parent/'cgroup.subtree_control').read_text().split()):
        pytest.skip('Requires delegated CPU/memory/PID controllers')
    return parent


def test_service_oom_closes_its_group_and_keeps_observed_reason(tmp_path, delegated_service_parent):
    """An allocating child and its descendants share a real memory ceiling; no successful service exit is invented."""
    from backend.runtime.service_process import run_bounded_services

    state = tmp_path/'service';state.mkdir(mode=0o700)
    command = [sys.executable,'-c','''import os,time
if os.fork()==0:
 data=bytearray(96*1024**2)
 for i in range(0,len(data),4096):data[i]=1
time.sleep(20)
''']
    code = run_bounded_services([('API',command,state)], cgroup_parent=delegated_service_parent,
                               limits={'pids':16,'memory_bytes':64*1024**2,'cpu_millis':500}, state_dir=state, grace=.2)
    assert code == 137
    receipt = json.loads((state/'service-resources.json').read_text())
    assert receipt['status']=='closed' and receipt['domain_removed'] is True
    assert receipt['resources']['memory_oom_kills']>=1
    assert receipt['resources']['limits']['memory_max']==str(64*1024**2)
    assert not Path(receipt['domain_path']).exists()


def test_service_failure_reaps_peers_but_never_signals_unrelated_process(tmp_path, delegated_service_parent):
    """The existing launch contract also holds for an entire bounded service group."""
    from backend.runtime.service_process import run_bounded_services

    state=tmp_path/'service';state.mkdir(mode=0o700)
    marker=state/'pid'
    waiting=[sys.executable,'-c',f'import os,time;open({str(marker)!r},"w").write(str(os.getpid()));time.sleep(30)']
    failure=[sys.executable,'-c','import time;time.sleep(.3);raise SystemExit(7)']
    sentinel=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'])
    try:
        assert run_bounded_services([('API',waiting,state),('other',failure,state)],
            cgroup_parent=delegated_service_parent,limits={'pids':16,'memory_bytes':128*1024**2,'cpu_millis':500},
            state_dir=state,grace=.2)==7
        assert sentinel.poll() is None
        with pytest.raises(ProcessLookupError):os.kill(int(marker.read_text()),0)
        receipt=json.loads((state/'service-resources.json').read_text())
        assert receipt['status']=='closed' and receipt['domain_removed'] is True
    finally:
        sentinel.terminate();sentinel.wait(timeout=5)


def test_launcher_death_closes_forked_service_tree_before_releasing_ownership(tmp_path, delegated_service_parent):
    """A separate guardian survives the launcher's SIGKILL and retires descendants even after setsid()."""
    state=tmp_path/'service';state.mkdir(mode=0o700)
    marker=state/'descendant'
    child_code=f'''import os,time
if os.fork()==0:
 os.setsid();open({str(marker)!r},'w').write(str(os.getpid()))
time.sleep(30)
'''
    program='''import json,sys
from pathlib import Path
from backend.runtime.service_process import run_bounded_services
run_bounded_services([('API',[sys.executable,'-c',sys.argv[3]],Path(sys.argv[1]))],
 cgroup_parent=sys.argv[2],limits={'pids':16,'memory_bytes':128*1024**2,'cpu_millis':500},state_dir=sys.argv[1])
'''
    owner=subprocess.Popen([sys.executable,'-c',program,str(state),str(delegated_service_parent),child_code],
                           stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+8
        while not marker.exists():
            assert owner.poll() is None and time.monotonic()<deadline
            time.sleep(.01)
        owner.kill();owner.wait(timeout=3)
        while time.monotonic()<deadline:
            receipt=json.loads((state/'service-resources.json').read_text())
            if receipt['status']=='closed':break
            time.sleep(.01)
        assert receipt['status']=='closed' and receipt['reason']=='launcher_lost'
        assert not Path(receipt['domain_path']).exists()
        process=Path(f'/proc/{int(marker.read_text())}/stat')
        assert not process.exists() or process.read_text().split(') ',1)[1][0]=='Z'
    finally:
        if owner.poll() is None:owner.kill()
        owner.wait()


def test_configured_launcher_applies_service_limits(tmp_path, delegated_service_parent, monkeypatch):
    """The public launcher enforces configured budgets and records physical closure without a model call."""
    from backend.cli.launcher import run_services

    state = tmp_path/'service';state.mkdir(mode=0o700)
    config = tmp_path/'runtime.json'
    limits = {'pids':16,'memory_bytes':128*1024**2,'cpu_millis':500}
    config.write_text(json.dumps({'cgroup_parent':str(delegated_service_parent),'service_limits':limits}))
    monkeypatch.setenv('INFINIBAY_RUNTIME_CONFIG',str(config))
    assert run_services([('API',[sys.executable,'-c','raise SystemExit(7)'],state)],grace=.2)==7
    receipt = json.loads((state/'service-resources.json').read_text())
    assert receipt['limits']==limits and receipt['domain_removed'] is True
    assert receipt['resources']['limits']['cpu_max']=='50000 100000'


def test_snapshot_ownership_blocks_new_launcher(tmp_path, delegated_service_parent):
    """Holding snapshot ownership prevents a service from starting while offline files are copied."""
    from backend.runtime.service_process import frozen_service_ownership, run_bounded_services

    state=tmp_path/'service';state.mkdir(mode=0o700)
    with frozen_service_ownership(state):
        with pytest.raises(RuntimeError,match='owns'):
            run_bounded_services([('API',[sys.executable,'-c','pass'],state)],
                cgroup_parent=delegated_service_parent,limits={},state_dir=state)
    assert not (state/'service-resources.json').exists()
