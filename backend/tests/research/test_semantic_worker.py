"""Semantic capacity, process ownership and post-work authority are independently verifiable."""

import hashlib
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from backend.research.models import ResearchForbidden, SourceTooLarge
from backend.research.retrieval_assets import RetrievalBusy, RetrievalUnavailable
from backend.tests.research.test_semantic_retrieval import assets


def source():
    """Provide one fixed authorized-text revision for process tests, without database setup."""
    return {
        "id": 1,
        "content": "Evidence",
        "sha256": hashlib.sha256(b"Evidence").hexdigest(),
        "provenance": {},
    }


def fixed_fault(monkeypatch, tmp_path, body):
    """Change only the host-fixed test entry point; retain real limits, pipes, pidfd and reaping."""
    import backend.research.semantic as module

    marker = tmp_path / "worker"
    program = tmp_path / "fault.py"
    program.write_text(
        """import json,sys,os,time
options=json.loads(sys.argv[1]);sys.path.insert(0,options['package_root'])
os.mkdir(MARKER);os.mkdir(MARKER+'/'+str(os.getpid()))
from backend.research.worker_limits import apply_limits
apply_limits(options)
BODY
""".replace("MARKER", repr(str(marker))).replace("BODY", body)
    )
    monkeypatch.setattr(module, "WORKER", program)
    return marker


def test_semantic_withdrawal_reaps_worker_before_releasing_capacity(
    monkeypatch, tmp_path
):
    """Stop must close the real child; busy is not a second worker and capacity recovers afterwards."""
    import backend.research.semantic as module
    from backend.research.semantic import SemanticLimits, SemanticRetriever
    from backend.runtime.live_grants import LiveGrants

    original_worker = module.WORKER
    marker = fixed_fault(monkeypatch, tmp_path, "while True: time.sleep(0.01)")
    engine = SemanticRetriever(assets(), limits=SemanticLimits(wall_seconds=5))
    owner = LiveGrants()
    owner.activate("semantic-a")

    def execute():
        """Keep the same operation registered through CPU work and physical cleanup."""
        with owner.operation("semantic-a") as cancelled:
            return engine.query(source(), "meaning", cancelled=cancelled)

    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(execute)
        deadline = time.monotonic() + 3
        while not marker.exists() and time.monotonic() < deadline:
            time.sleep(0.01)
        assert marker.exists(), "Fixed worker was not admitted"
        pid = next(marker.iterdir()).name
        with pytest.raises(RetrievalBusy):
            engine.query(source(), "another query")
        owner.withdraw("semantic-a")
        with pytest.raises(ResearchForbidden):
            future.result(timeout=3)
    assert not Path("/proc/" + pid).exists()
    monkeypatch.setattr(module, "WORKER", original_worker)
    recovered = engine.query(source(), "meaning")
    assert recovered["matches"][0]["excerpt"] == "Evidence"


@pytest.mark.parametrize(
    "body,limits",
    [
        ("while True: pass", {"cpu_seconds": 1, "wall_seconds": 4}),
        ("os.write(1,b'X'*4096)", {"max_output_bytes": 64}),
    ],
)
def test_semantic_cpu_or_output_exhaustion_never_returns_partial_results(
    monkeypatch, tmp_path, body, limits
):
    """Real resource fuses terminate and reap faulty workers, retaining the complete-result contract."""
    from backend.research.semantic import SemanticLimits, SemanticRetriever

    marker = fixed_fault(monkeypatch, tmp_path, body)
    with pytest.raises(SourceTooLarge):
        SemanticRetriever(assets(), limits=SemanticLimits(**limits)).query(
            source(), "meaning"
        )
    assert marker.exists() and not Path("/proc/" + next(marker.iterdir()).name).exists()


def test_semantic_missing_interpreter_is_an_explicit_availability_failure(monkeypatch):
    """A failed OS launch is not malformed source evidence or a leaked API exception."""
    import backend.research.worker_transport as transport
    from backend.research.semantic import SemanticRetriever

    directory = assets()

    def unavailable(*args, **kwargs):
        """Represent a launch failure before any owned child exists."""
        raise FileNotFoundError("interpreter unavailable")

    monkeypatch.setattr(transport.subprocess, "Popen", unavailable)
    with pytest.raises(RetrievalUnavailable):
        SemanticRetriever(directory).query(source(), "meaning")
