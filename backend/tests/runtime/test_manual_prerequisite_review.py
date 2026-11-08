"""Independent code reviewers inherit the exact author's causal evidence without acquiring author authority."""

from dataclasses import replace
import json

import pytest

from backend.tests.runtime.test_code_review_state import (
    candidate_state as candidate_state,
    development_state as development_state,
    review_state as review_state,
    review_request,
)


@pytest.fixture
def service_setup(service_setup):
    """Accept a real documentary prerequisite before the existing independent development/review fixtures admit work."""
    from backend.tests.runtime.test_plan_execution import accept_documentary_result

    s=service_setup
    parent=s.c.store.admit(replace(s.c.spec,task_id=1002,operation_key='research-prerequisite'))
    accept_documentary_result(s,parent)
    s.c.conn.execute("INSERT INTO task_dependencies(task_id,depends_on_task_id,dependency_type) VALUES(1001,1002,'blocks')")
    s.c.conn.commit()
    return s


@pytest.mark.parametrize('review_state',['frozen_author'],indirect=True)
def test_reviewer_can_claim_freeze_input_and_read_original_author_prerequisites(review_state):
    """Review admission uses its exact original author packet; it must not demand a fabricated reviewer-owned delivery."""
    from backend.planning.materials import PredecessorMaterials
    from backend.runtime.run_inputs import freeze_input

    s,author,_candidate,reviews=review_state
    spec,target=review_request(review_state)
    run=reviews.admit_once(spec,target)[0]
    lease=s.c.store.claim(101,run.run_id,'synthetic-independent-review-owner')
    context=s.c.store.context_snapshot(101,run.task_id)
    with s.c.store._transaction() as conn:
        frozen=freeze_input(conn,s.c.store._row(conn,101,run.run_id),context)
    value=json.loads(frozen.input_text)
    assert value['scope']['run_id']==run.run_id
    assert value['prerequisite_material']['run_id']==author.run_id
    assert value['prerequisite_material']['prerequisites'][0]['task_id']==1002
    reader=PredecessorMaterials(s.c.store)
    assert reader.available(lease)
    assert reader.read_research(lease,1002)['source']['task_id']==1002
    assert s.c.conn.execute('SELECT count(*) FROM runtime_manual_prerequisites WHERE run_id=?',(run.run_id,)).fetchone()[0]==0
