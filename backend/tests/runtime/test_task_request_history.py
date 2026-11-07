"""Verify continuity for direct admissions while retaining deliberate conversation resets and authority boundaries."""

from dataclasses import replace
import hashlib
import json

import pytest

from backend.runtime.contracts import InputTooLarge
from backend.tests.runtime.test_run_input import prepare, reserve


def prior(c, *, key="original", prompt="Explain base 100 and tax 0.21", task=1001, thread=None):
    """Admit and close a historical request without pretending it reached a model."""
    run = c.store.admit(replace(c.spec, operation_key=key, prompt=prompt, task_id=task), conversation_thread=thread)
    c.store.cancel(101, run.run_id)
    return run


def test_corrected_direct_admission_keeps_original_request_with_historical_scope(coordination):
    """An earlier admitted request must be delivered with the correction, never relabeled as current authority."""
    c = coordination
    old = prior(c)
    version = c.store.correct_context(project_id=101, task_id=1001, expected_version=1,
        operation_key="correct", statement="Use base 200 and rate 0.10", source_kind="user_message", source_reference="owner")
    c.spec = replace(c.spec, operation_key="followup", context_version=version, prompt="Explain what changed")
    run, lease = prepare(c, thread=None)
    frozen = reserve(c, lease)
    data = json.loads(frozen.input_text)
    history = data["request_history"]
    assert history["mode"] == "same_task_admissions"
    assert history["cutoff_run_id"] == run.run_id
    assert len(history["requests"]) == 1
    item = history["requests"][0]
    assert item["run_id"] == old.run_id
    assert item["content"] == "Explain base 100 and tax 0.21"
    assert item["content_sha256"] == hashlib.sha256(item["content"].encode()).hexdigest()
    assert item["source_context_version"] == 1
    assert item["same_context_version"] is False
    assert item["current_authorization"] is False
    assert item["kind"] == "recorded_admission"
    assert data["request"] == "Explain what changed"
    assert data["corrections"][0]["statement"] == "Use base 200 and rate 0.10"
    assert c.store.input_record(101, run.run_id)["input_text"] == frozen.input_text


def test_direct_history_excludes_other_tasks_and_future_admissions_despite_clock_changes(coordination):
    """Causal admission order must exclude later records and unrelated task text even if wall time moves back."""
    c = coordination
    old = prior(c)
    prior(c, key="other", prompt="OTHER_TASK_SECRET", task=1002)
    c.now[0] -= 100
    c.spec = replace(c.spec, operation_key="current", prompt="Current request")
    run, lease = prepare(c, thread=None)
    c.conn.execute("""INSERT INTO runtime_runs(id,project_id,task_id,actor_id,context_version,operation_key,prompt,runtime,status,created_at,updated_at)
        VALUES('future',101,1001,'researcher-a',1,'future','FUTURE_REQUEST','codex','cancelled',0,0)""")
    c.conn.commit()
    frozen = reserve(c, lease)
    data = json.loads(frozen.input_text)
    assert [item["run_id"] for item in data["request_history"]["requests"]] == [old.run_id]
    assert "OTHER_TASK_SECRET" not in frozen.input_text and "FUTURE_REQUEST" not in frozen.input_text
    assert data["request_history"]["cutoff_run_id"] == run.run_id


@pytest.mark.parametrize("same_thread", [False, True])
def test_explicit_conversation_uses_only_its_selected_history(coordination, same_thread):
    """Selecting a fresh conversation remains a real reset rather than silently restoring all task requests."""
    c = coordination
    prior(c, prompt="PAST_REQUEST", thread="old-thread")
    c.spec = replace(c.spec, operation_key="current", prompt="Current request")
    _, lease = prepare(c, thread="old-thread" if same_thread else "fresh-thread")
    data = json.loads(reserve(c, lease).input_text)
    assert data["request_history"] == {"mode": "selected_conversation", "requests": []}
    assert ("PAST_REQUEST" in json.dumps(data["conversation"])) is same_thread


def test_oversize_task_history_rolls_back_input_and_inference_budget(coordination, monkeypatch):
    """A complete history that cannot fit must block before dispatch instead of hiding its earliest constraints."""
    from backend.runtime import run_inputs

    c = coordination
    prior(c, prompt="historical constraint " * 250)
    c.spec = replace(c.spec, operation_key="next")
    _, lease = prepare(c, thread=None)
    monkeypatch.setattr(run_inputs, "MAX_INPUT_BYTES", 4096)
    with pytest.raises(InputTooLarge):
        reserve(c, lease)
    for table in ("runtime_input_snapshots", "runtime_inference_dispatches", "runtime_project_budgets"):
        assert c.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0


def test_too_many_task_requests_rejects_without_silently_sampling(coordination, monkeypatch):
    """Request-count limits preserve full-history semantics and never authorize a partial-history turn."""
    from backend.runtime import run_inputs

    c = coordination
    for number in range(3):
        prior(c, key=f"prior-{number}")
    c.spec = replace(c.spec, operation_key="next")
    _, lease = prepare(c, thread=None)
    monkeypatch.setattr(run_inputs, "MAX_HISTORY_MESSAGES", 2)
    with pytest.raises(InputTooLarge):
        reserve(c, lease)
