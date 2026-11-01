"""OS resource, cancellation and cleanup contracts for the trusted PDF worker."""

import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from backend.research.models import ResearchForbidden, SourceTooLarge
from backend.runtime.live_grants import LiveGrants
from backend.tests.research.pdf_fixtures import pdf_bytes


def test_pdf_worker_returns_text_and_observed_hard_limits():
    """Catch extraction falling back to the API process or omitting its OS limits."""
    from backend.research.parser_process import ParserLimits, PDFParser

    text, provenance = PDFParser(
        limits=ParserLimits(cpu_seconds=2, memory_bytes=268435456, wall_seconds=5)
    ).read(pdf_bytes("Tax rates are fractions."))
    assert text == "[Page 1]\nTax rates are fractions."
    assert provenance["execution"]["cpu_limit_seconds"] == 2
    assert provenance["execution"]["address_space_limit_bytes"] == 268435456
    assert provenance["execution"]["worker_closed"] is True


def worker_fault(monkeypatch, tmp_path, body):
    """Inject a parser dependency failure after the real worker has applied OS limits."""
    import backend.research.parser_process as module

    original = module.WORKER
    probe = tmp_path / "dependency_fault.py"
    marker = tmp_path / "running.json"
    probe.write_text(
        """import builtins, json, os, runpy
original_import = builtins.__import__
def substituted_import(name, *args, **kwargs):
    module = original_import(name, *args, **kwargs)
    if name == 'backend.research.pdf_text':
        def dependency(data):
            os.mkdir(MARKER); os.mkdir(MARKER + '/' + str(os.getpid()))
            BODY
        module.extract_pdf = dependency
    return module
builtins.__import__ = substituted_import
runpy.run_path(ORIGINAL, run_name='__main__')
""".replace("MARKER", repr(str(marker)))
        .replace("BODY", body)
        .replace("ORIGINAL", repr(str(original)))
    )
    monkeypatch.setattr(module, "WORKER", probe)
    return marker


@pytest.mark.parametrize(
    "body", ["while True: pass", "return bytearray(1024 * 1024 * 1024)"]
)
def test_worker_cpu_and_memory_exhaustion_are_bounded_failures(
    monkeypatch, tmp_path, body
):
    """Catch missing CPU/AS limits without relying on PDF complexity or timing guesses."""
    from backend.research.parser_process import ParserLimits, PDFParser

    worker_fault(monkeypatch, tmp_path, body)
    with pytest.raises(SourceTooLarge):
        PDFParser(
            limits=ParserLimits(cpu_seconds=1, memory_bytes=134217728, wall_seconds=4)
        ).read(pdf_bytes("Input"))


def test_withdrawal_stops_the_live_worker_and_waits_for_physical_exit(
    monkeypatch, tmp_path
):
    """Catch worker leakage and a false closure acknowledgement after Stop/correction."""
    from backend.research.parser_process import ParserLimits, PDFParser

    marker = worker_fault(monkeypatch, tmp_path, "while True: pass")
    gate = LiveGrants()
    gate.activate("attempt-a")
    parser = PDFParser(
        owner=gate,
        grant_id="attempt-a",
        limits=ParserLimits(cpu_seconds=3, wall_seconds=5),
    )
    with ThreadPoolExecutor() as executor:
        pending = executor.submit(parser.read, pdf_bytes("Input"))
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "worker never reached the actual parser dependency"
        pid = int(next(marker.iterdir()).name)
        gate.withdraw("attempt-a")
        gate.wait_closed("attempt-a", timeout=2)
        with pytest.raises(ResearchForbidden):
            pending.result(timeout=2)
    assert not Path(f"/proc/{pid}").exists(), (
        "withdrawal reported closure while worker still existed"
    )
    with pytest.raises(ResearchForbidden):
        parser.read(pdf_bytes("Must not start after withdrawal"))


def test_wall_deadline_closes_a_parser_that_consumes_no_cpu(monkeypatch, tmp_path):
    """Catch a worker escaping a CPU-only limit by sleeping indefinitely."""
    from backend.research.parser_process import ParserLimits, PDFParser

    marker = worker_fault(monkeypatch, tmp_path, "import time; time.sleep(30)")
    with pytest.raises(SourceTooLarge):
        PDFParser(limits=ParserLimits(wall_seconds=1)).read(pdf_bytes("Input"))
    assert marker.exists()
    assert not Path("/proc/" + next(marker.iterdir()).name).exists()


def test_worker_does_not_inherit_credentials_or_open_host_descriptors(
    monkeypatch, tmp_path
):
    """Catch accidental inheritance of an API secret or an explicitly inheritable host FD."""
    import fcntl
    import json
    import os

    from backend.research.parser_process import PDFParser

    monkeypatch.setenv("OPENAI_API_KEY", "fixture-secret-never-for-worker")
    with (tmp_path / "private").open("w") as private:
        descriptor = fcntl.fcntl(private.fileno(), fcntl.F_DUPFD, 256)
        os.set_inheritable(descriptor, True)
        try:
            worker_fault(
                monkeypatch,
                tmp_path,
                "return (__import__('json').dumps({'secret':os.environ.get('OPENAI_API_KEY'),'host_fd':os.path.exists('/proc/self/fd/"
                + str(descriptor)
                + "')}), {})",
            )
            text, _ = PDFParser().read(pdf_bytes("Input"))
        finally:
            os.close(descriptor)
    assert json.loads(text) == {"secret": None, "host_fd": False}


def test_excess_output_is_killed_without_buffering_an_unbounded_receipt(
    monkeypatch, tmp_path
):
    """Catch an IPC writer exceeding its budget before JSON validation can run."""
    from backend.research.parser_process import ParserLimits, PDFParser

    marker = worker_fault(
        monkeypatch, tmp_path, "os.write(1,b'X'*4096); return ('ignored',{})"
    )
    with pytest.raises(SourceTooLarge):
        PDFParser(limits=ParserLimits(max_output_bytes=256)).read(pdf_bytes("Input"))
    assert not Path("/proc/" + next(marker.iterdir()).name).exists()


def test_worker_launch_failure_is_a_source_error(monkeypatch):
    """Catch an unavailable trusted interpreter leaking an unhandled API exception."""
    import backend.research.parser_process as module
    from backend.research.models import SourceUnavailable

    def unavailable(*args, **kwargs):
        """Represent a failed OS process launch, before there is any child to own."""
        raise FileNotFoundError("injected unavailable interpreter")

    monkeypatch.setattr(module.subprocess, "Popen", unavailable)
    with pytest.raises(SourceUnavailable):
        module.PDFParser().read(pdf_bytes("Input"))


def test_worker_exits_when_its_api_owner_process_is_killed(monkeypatch, tmp_path):
    """Prove parent-death cleanup with a real sleeping worker and its pinned pidfd."""
    import os
    import select
    import subprocess
    import sys

    import backend.research.parser_process as module
    from backend.runtime.peer_process import _pidfd, _signal

    marker = worker_fault(monkeypatch, tmp_path, "import time; time.sleep(30)")
    code = (
        "from pathlib import Path\nimport backend.research.parser_process as p\np.WORKER=Path("
        + repr(str(module.WORKER))
        + ")\np.PDFParser().read("
        + repr(pdf_bytes("Input"))
        + ")"
    )
    launcher = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=Path(__file__).parents[3],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    pidfd = None
    try:
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "worker did not enter the parser"
        pidfd = _pidfd(int(next(marker.iterdir()).name))
        launcher.kill()
        launcher.wait(timeout=2)
        poller = select.poll()
        poller.register(pidfd, select.POLLIN)
        assert poller.poll(2000), "worker remained alive after API owner died"
    finally:
        if launcher.poll() is None:
            launcher.kill()
            launcher.wait(timeout=2)
        if pidfd is not None:
            _signal(pidfd)
            os.close(pidfd)


def test_callers_remaining_deadline_restricts_the_worker_budget(monkeypatch, tmp_path):
    """Catch a PDF parser ignoring time already spent downloading its input."""
    from backend.research.parser_process import PDFParser

    worker_fault(monkeypatch, tmp_path, "import time; time.sleep(30)")
    started = time.monotonic()
    with pytest.raises(SourceTooLarge):
        PDFParser().read(pdf_bytes("Input"), max_wall_seconds=0.25)
    assert time.monotonic() - started < 2
