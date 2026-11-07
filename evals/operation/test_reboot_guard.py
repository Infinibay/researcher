"""Reject misleading active-process observations without ever invoking a reboot or starting a VM."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from evals.operation.reboot_guest_init import observe_live_process


def identity(pid):
    """Capture one owned test process's start tick and namespace for read-only observation."""
    root = Path('/proc')/str(pid)
    return {'pid':pid,'start_ticks':int((root/'stat').read_text().rsplit(') ',1)[1].split()[19]),
            'namespace':(root/'ns/pid').stat().st_ino}


def test_live_original_process_is_observable_but_changed_identity_is_rejected():
    """A matching PID alone is insufficient when the saved start tick or namespace differs."""
    current = identity(os.getpid())
    observe_live_process(current)
    with pytest.raises(RuntimeError,match='identity'):
        observe_live_process({**current,'start_ticks':current['start_ticks']+1})
    with pytest.raises(RuntimeError,match='namespace'):
        observe_live_process({**current,'namespace':current['namespace']+1})


def test_exited_original_handle_cannot_be_reported_as_active():
    """A real process that was alive at registration must fail observation after its original handle terminates."""
    process = subprocess.Popen([sys.executable,'-I','-S','-c','import time;time.sleep(30)'])
    try:
        original = identity(process.pid)
        observe_live_process(original)
    finally:
        process.terminate()
        process.wait(timeout=5)
    with pytest.raises((RuntimeError,FileNotFoundError,ProcessLookupError)):
        observe_live_process(original)


def test_host_invocation_refuses_before_loading_reboot_syscalls(monkeypatch, capsys):
    """Importing or mistakenly invoking the evaluator on the owner host must not reach mount/reboot syscalls."""
    from evals.operation import reboot_guest_init

    def forbidden_libc(*_args, **_kwargs):
        """Reject any system administration call while testing the ordinary non-PID1 host guard."""
        raise AssertionError('A host invocation reached libc administration')

    assert os.getpid() != 1
    monkeypatch.setattr(reboot_guest_init.ctypes,'CDLL',forbidden_libc)
    with pytest.raises(RuntimeError,match='Refusing any reboot'):
        reboot_guest_init.main()
    assert 'RESEARCHER-REBOOT-RESULT:' in capsys.readouterr().out
