"""Scientific legacy compatibility preserves historical data and resolves owner actions without model-stage execution or automatic acceptance."""

import pytest

from backend.flows.research_flow import ResearchFlow
from backend.flows.research_review_flow import ResearchReviewFlow
from backend.flows.state_models import ResearchState


def test_historical_research_state_remains_readable():
    """Old hypothesis/confidence fields remain attributed history; loading them starts no stage or validation."""
    state = ResearchState(
        project_id=1,
        task_id=10,
        hypothesis="Algorithm X may be faster.",
        confidence_scores=[0.85, 0.72],
    )
    assert state.hypothesis == "Algorithm X may be faster."
    assert state.confidence_scores == [0.85, 0.72]
    assert ResearchState().findings == []


@pytest.mark.parametrize("entry", [ResearchFlow, ResearchReviewFlow])
def test_public_legacy_scientific_kickoff_is_a_scoped_owner_hint(
    db_conn, executing_project, entry
):
    """Research/review entry reads the real project/task and never claims, revises, reviews or completes from old labels."""
    task = db_conn.execute(
        "SELECT id,status,assigned_to FROM tasks WHERE project_id=? AND type='research'",
        (executing_project,),
    ).fetchone()
    before = tuple(task)
    flow = entry()
    result = flow.kickoff(
        inputs={
            "project_id": executing_project,
            "task_id": task["id"],
            "researcher_id": "old-worker",
            "validated": True,
            "revision_count": 999,
        }
    )
    assert result["delivery"] == "native_owner_handoff"
    assert result["native_runs"] == []
    assert (
        result["event_authorizes_work"] is False
        and result["inference_started_by_handoff"] is False
    )
    assert (
        tuple(
            db_conn.execute(
                "SELECT id,status,assigned_to FROM tasks WHERE id=?", (task["id"],)
            ).fetchone()
        )
        == before
    )
    assert flow.state.task_id == task["id"]


@pytest.mark.parametrize("entry", [ResearchFlow, ResearchReviewFlow])
@pytest.mark.parametrize(
    "project,task", [(999999, 2), (1, 999999), (True, 2), (1, "2")]
)
def test_legacy_scientific_entry_never_guesses_missing_or_foreign_scope(
    db_conn, executing_project, entry, project, task
):
    """Missing, foreign or coerced identifiers cannot select a convenient project or trigger old inference."""
    with pytest.raises(ValueError):
        entry().kickoff(inputs={"project_id": project, "task_id": task})
