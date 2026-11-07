"""Verify administrative process budgets and bounded traversal through observable failures."""

import json
import os
from pathlib import Path
import time
import subprocess
import sys

import pytest


def test_inventory_refuses_while_reading_instead_of_materializing_directory(tmp_path, monkeypatch):
    """The entry budget stops traversal before the remaining directory entries are consumed."""
    from backend.runtime import snapshot_files

    for name in ('one', 'two', 'three'):
        (tmp_path / name).write_text(name)
    original = snapshot_files.os.scandir
    consumed = []

    def bounded_listing(fd):
        """Expose real directory entries but fail if the reader asks past the rejection boundary."""
        with original(fd) as entries:
            for entry in entries:
                consumed.append(entry.name)
                if len(consumed) > 2:
                    raise AssertionError('Directory was accumulated before applying the entry budget')
                yield entry

    monkeypatch.setattr(snapshot_files.os, 'scandir', bounded_listing)
    with pytest.raises(ValueError, match='budget'):
        snapshot_files.inventory(tmp_path, snapshot_files.CopyBudget(max_files=1))
    assert len(consumed) == 2


def test_administrative_child_has_real_memory_ceiling(tmp_path, monkeypatch, capfd):
    """A fixed test child fails an oversized allocation under the same kernel setup used by actual commands."""
    from backend.runtime import administration_process as processes

    worker = tmp_path / 'memory.py'
    worker.write_text('''import json, sys
options=json.loads(sys.argv[1]);sys.path.insert(0,options['package_root'])
from backend.runtime.administration_process import apply_limits, observed_limits
apply_limits(options)
try:
    bytearray(2*1024**3)
except MemoryError:
    print(json.dumps({'allocation_refused':True, 'limits':observed_limits()}))
else:
    raise AssertionError('Memory ceiling was not enforced')
''')
    monkeypatch.setattr(processes, 'WORKER', worker)
    assert processes.run_administration({'command':'verify-backup', 'backup':str(tmp_path),
                                        'max_bytes':1024, 'max_files':10, 'timeout':5}) == 0
    receipt = json.loads(capfd.readouterr().out)
    assert receipt['allocation_refused'] is True
    assert receipt['limits']['address_space_bytes'] == 1024**3


def test_administrative_timeout_reaps_original_child_and_preserves_partial_files(tmp_path, monkeypatch, capfd):
    """A blocked operation cannot exceed its deadline or cause automatic replay or deletion of partial output."""
    from backend.runtime import administration_process as processes

    worker = tmp_path / 'blocked.py'
    partial = tmp_path / 'partial-evidence'
    worker.write_text('''import json, os, sys, time
options=json.loads(sys.argv[1]);sys.path.insert(0,options['package_root'])
from backend.runtime.administration_process import apply_limits
apply_limits(options)
from pathlib import Path
Path(options['operation']['backup']).write_text(str(os.getpid()))
time.sleep(30)
''')
    monkeypatch.setattr(processes, 'WORKER', worker)
    started = time.monotonic()
    assert processes.run_administration({'command':'verify-backup', 'backup':str(partial),
                                        'max_bytes':1024, 'max_files':10, 'timeout':1}) == 124
    assert time.monotonic() - started < 5
    pid = int(partial.read_text())
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)
    assert 'partial' in capfd.readouterr().err.lower()


def test_parent_death_ends_administrative_child_without_replaying_it(tmp_path):
    """Killing the CLI parent also ends its sleeping child, while its original evidence remains readable."""
    from backend.runtime import administration_process as processes

    marker = tmp_path / 'child-pid'
    worker = tmp_path / 'owned-child.py'
    worker.write_text('''import json, os, sys, time
options=json.loads(sys.argv[1]);sys.path.insert(0,options['package_root'])
from backend.runtime.administration_process import apply_limits
apply_limits(options)
from pathlib import Path
Path(options['operation']['backup']).write_text(str(os.getpid()))
time.sleep(30)
''')
    parent = subprocess.Popen([sys.executable, '-c', '''import sys
from pathlib import Path
from backend.runtime import administration_process as processes
processes.WORKER=Path(sys.argv[1])
processes.run_administration({'command':'verify-backup','backup':sys.argv[2],
 'max_bytes':1024,'max_files':10,'timeout':20})
''', str(worker), str(marker)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + 5
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(.01)
        assert marker.exists()
        pid = int(marker.read_text())
        parent.kill()
        parent.wait(timeout=3)
        state = Path(f'/proc/{pid}/stat')
        while state.exists() and state.read_text().split(') ', 1)[1][0] != 'Z' and time.monotonic() < deadline:
            time.sleep(.01)
        assert not state.exists() or state.read_text().split(') ', 1)[1][0] == 'Z'
        assert marker.read_text() == str(pid)
    finally:
        if parent.poll() is None:
            parent.kill()
        parent.wait()
