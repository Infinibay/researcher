"""The native product has no importable old inference loop; project policy guards remain independent of the retired engine."""

import importlib.util
import threading

import pytest


def test_old_inference_modules_are_not_importable():
    """Removed factories, pseudo-tool dispatch and auxiliary provider loops cannot become a competing execution path."""
    for name in (
        "base", "loop_engine", "llm_client", "loop_context", "loop_models",
        "loop_tools", "tool_executor", "tool_call_parser", "summarizer",
        "file_change_tracker", "engine_logging",
    ):
        try:
            found = importlib.util.find_spec(f"backend.engine.{name}")
        except ModuleNotFoundError as error:
            assert error.name in ("backend.engine", f"backend.engine.{name}")
        else:
            assert found is None, f"Retired execution module is still available: {name}"




def test_legacy_project_guards_remain_before_and_after_native_admission(coordination):
    """Removing the model loop does not authorize its retained reporting helpers or manufacture native work for old project data."""
    from backend.runtime.lifecycle import NativeOwnerRequired, require_legacy_execution_project

    c = coordination
    for project in (101, 202):
        with pytest.raises(NativeOwnerRequired):
            require_legacy_execution_project(project)
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 0
    run = c.store.admit(c.spec)
    with pytest.raises(NativeOwnerRequired):
        require_legacy_execution_project(101)
    assert c.store.get(101, run.run_id).status == "queued"
    assert c.conn.execute("SELECT count(*) FROM runtime_runs").fetchone()[0] == 1
