"""The native product has no importable old inference loop, while retained controller cancellation remains scoped and observable."""

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


def test_registered_controller_stop_remains_scoped_after_engine_removal():
    """A stopped original controller cannot continue effects or lend its signal to another project; leaving the scope restores its predecessor."""
    from backend.runtime.legacy_scope import (
        LegacyControllerStopped,
        check_legacy_stop,
        legacy_stop_scope,
    )

    original, other = threading.Event(), threading.Event()
    with legacy_stop_scope(101, original):
        check_legacy_stop(101)
        with pytest.raises(ValueError, match="mismatch"):
            check_legacy_stop(202)
        original.set()
        with pytest.raises(LegacyControllerStopped):
            check_legacy_stop(101)
        with legacy_stop_scope(202, other):
            check_legacy_stop(202)
        with pytest.raises(LegacyControllerStopped):
            check_legacy_stop(101)
    check_legacy_stop(101)


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
