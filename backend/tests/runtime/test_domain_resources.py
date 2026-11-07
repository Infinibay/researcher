"""Exercise shared kernel limits, retained exhaustion evidence and owner-facing failures without a model."""

import json
import os
from pathlib import Path
import sys
import time
from uuid import uuid4

import pytest


@pytest.fixture
def resource_cgroup():
    """Allocate only a fresh delegated sibling; never change the controller's own resource policy."""
    relative = Path('/proc/self/cgroup').read_text().strip().split(':', 2)[2]
    parent = (Path('/sys/fs/cgroup') / relative.lstrip('/')).parent
    if not {'cpu', 'memory', 'pids'} <= set((parent / 'cgroup.subtree_control').read_text().split()):
        pytest.skip('Requires delegated CPU, memory and process controllers')
    leaf = parent / ('researcher-resources-' + uuid4().hex)
    leaf.mkdir(mode=0o700)
    try:
        yield leaf
    finally:
        if leaf.exists():
            (leaf / 'cgroup.kill').write_text('1')
            deadline = time.monotonic() + 5
            while 'populated 1' in (leaf / 'cgroup.events').read_text():
                assert time.monotonic() < deadline
                time.sleep(.01)
            leaf.rmdir()


def test_cpu_budget_is_shared_by_forked_workers_and_retained_after_removal(resource_cgroup):
    """Multiple busy descendants must share one bandwidth cap, rather than each receiving a full CPU budget."""
    from backend.runtime.execution_domain import ExecutionDomain

    code = '''import os,time
deadline=time.monotonic()+1.5
children=[]
for _ in range(3):
 pid=os.fork()
 if pid==0:
  while time.monotonic()<deadline: pass
  os._exit(0)
 children.append(pid)
for pid in children:os.waitpid(pid,0)
'''
    with ExecutionDomain.open(resource_cgroup) as domain:
        domain.limit(pids=16, memory_bytes=128*1024**2, cpu_millis=250)
        child = domain.spawn([sys.executable, '-I', '-S', '-c', code])
        try:
            assert child.wait(timeout=6) == 0
            closure = domain.retire()
            assert closure.removed and not resource_cgroup.exists()
            observation = closure.resources
            assert observation['observed'] is True
            assert observation['cpu_throttled_periods'] > 0
            assert 100000 < observation['cpu_usage_usec'] < 1000000
            assert observation['limits']['cpu_max'] == '25000 100000'
        finally:
            child.close_handles()


def test_memory_exhaustion_kills_the_whole_owned_group_and_preserves_evidence(resource_cgroup):
    """An allocating descendant cannot leave a sibling acting after the group exhausts its shared memory budget."""
    from backend.runtime.execution_domain import ExecutionDomain

    code = '''import os,time
if os.fork()==0:
 x=bytearray(96*1024**2)
 for i in range(0,len(x),4096):x[i]=1
 time.sleep(20)
else:time.sleep(20)
'''
    with ExecutionDomain.open(resource_cgroup) as domain:
        domain.limit(pids=16, memory_bytes=64*1024**2, cpu_millis=1000)
        child = domain.spawn([sys.executable, '-I', '-S', '-c', code])
        try:
            assert child.wait(timeout=5) == -9
            closure = domain.retire()
            assert closure.resources['memory_oom_kills'] >= 1
            assert closure.resources['memory_group_oom_kills'] >= 1
            assert closure.resources['limits']['memory_max'] == str(64*1024**2)
        finally:
            child.close_handles()


def test_missing_resource_observation_does_not_delay_physical_stop(resource_cgroup, monkeypatch):
    """Unavailable counters stay unknown while retirement still kills and removes the exact domain."""
    from backend.runtime.execution_domain import ExecutionDomain

    with ExecutionDomain.open(resource_cgroup) as domain:
        domain.limit(pids=16, memory_bytes=128*1024**2)
        read = domain._read

        def unavailable(name):
            """Fail only the telemetry read, leaving real cgroup identity and retirement untouched."""
            if name == 'cpu.stat':
                raise OSError('Counter unavailable')
            return read(name)

        monkeypatch.setattr(domain, '_read', unavailable)
        closure = domain.retire()
        assert closure.removed
        assert closure.resources == {'observed': False}


def test_capsule_cannot_change_scheduler_to_escape_cpu_accounting(broker_setup):
    """Even an otherwise permitted normal scheduling change is denied by the payload's inherited filter."""
    _s, registry, peer, broker, journal, _path = broker_setup
    code = '''import os,json
try:
 os.sched_setscheduler(0,os.SCHED_OTHER,os.sched_param(0));error=0
except OSError as e:error=e.errno
print(json.dumps({'scheduler':os.sched_getscheduler(0),'error':error}))
'''
    started = broker.run_peer(registry, peer, operation_key='scheduler-boundary', code=code)
    try:
        assert started.child.wait(timeout=5) == 0
        assert json.loads(started.child.stdout.read()) == {'scheduler': 0, 'error': 1}
    finally:
        started.child.close_handles()
    grant = broker.revoke()
    assert grant['resource_observation']['observed'] is True
    assert grant['limits']['cpu_millis'] == 2000
    assert journal.load().records['broker:grant:' + broker.grant_id]['resource_observation'] == grant['resource_observation']


async def test_owner_sees_observed_memory_exhaustion_without_invented_native_completion(service_setup):
    """A failed turn exposes scoped kernel observations and preserved-work guidance through the actual run record."""
    from backend.tests.runtime.test_runtime_service import ControlledInference, coordinator

    class ExhaustedInference(ControlledInference):
        """Supply the runtime's observed resource boundary while retaining the real coordinator and SQLite policy."""

        async def run(self, prompt, *, on_started, on_event):
            """Record native admission, then emulate loss of its connection after a kernel exhaustion event."""
            await on_started(self.thread_id, 'turn-a')
            raise RuntimeError('Native peer connection closed')

        def consume_resources(self, lease):
            """Return observations only for the attempt whose tools this controlled runtime owns."""
            assert lease.project_id == 101 and lease.task_id == 1001
            return {'observed': True, 'memory_oom_kills': 1, 'memory_group_oom_kills': 1, 'pids_denied': 0, 'cpu_usage_usec': 12000, 'cpu_throttled_periods': 0, 'limits': {'memory_max': '67108864', 'pids_max': '16', 'cpu_max': '100000 100000'}}

    s = service_setup
    async with coordinator(s, ExhaustedInference(s)) as runtime:
        run = await runtime.submit(s.c.spec)
        await runtime.wait(run.run_id)
        saved = s.c.store.get(101, run.run_id)
        assert saved.status == 'failed'
        assert saved.issue['code'] == 'resource_exhaustion'
        assert 'memoria' in saved.issue['message']
        assert saved.issue['resource_observation']['memory_oom_kills'] == 1
        assert s.c.conn.execute('SELECT native_result_json FROM runtime_attempts WHERE id=?', (saved.attempt_id,)).fetchone()[0] is None


def test_process_budget_counts_descendants_and_records_denied_births(resource_cgroup):
    """A bounded set of fork attempts cannot multiply the shared process allowance."""
    from backend.runtime.execution_domain import ExecutionDomain

    code = '''import os,time
children=[]
for _ in range(12):
 try:pid=os.fork()
 except BlockingIOError:continue
 if pid==0:
  time.sleep(.4);os._exit(0)
 children.append(pid)
for pid in children:os.waitpid(pid,0)
print(len(children),flush=True)
'''
    with ExecutionDomain.open(resource_cgroup) as domain:
        domain.limit(pids=4, memory_bytes=128*1024**2)
        child = domain.spawn([sys.executable, '-I', '-S', '-c', code])
        try:
            assert child.wait(timeout=5) == 0
            assert int(child.stdout.read()) == 3
            assert domain.retire().resources['pids_denied'] == 9
        finally:
            child.close_handles()


@pytest.mark.parametrize('cpu_millis', [0, -1, 99, 8001, True, 1.5, '2000'])
def test_invalid_cpu_policy_cannot_become_a_broker_reservation(cpu_millis):
    """Host configuration must choose a bounded exact integer rather than an unlimited or coerced policy."""
    from backend.runtime.peer_broker import BrokerLimits

    with pytest.raises(ValueError):
        BrokerLimits(cpu_millis=cpu_millis)


def test_realtime_controller_cannot_birth_a_payload_outside_bandwidth_accounting(resource_cgroup, monkeypatch):
    """An incompatible inherited scheduling class is rejected before creating any child."""
    from backend.runtime.execution_domain import DomainUncertain, ExecutionDomain

    monkeypatch.setattr(os, 'sched_getscheduler', lambda _pid: os.SCHED_FIFO)
    with ExecutionDomain.open(resource_cgroup) as domain:
        with pytest.raises(DomainUncertain, match='scheduler'):
            domain.spawn([sys.executable, '-c', 'pass'])
        assert 'populated 0' in (resource_cgroup / 'cgroup.events').read_text()
        domain.retire()
