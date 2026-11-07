"""Preserve option identity and readable answers across durable questions, HTTP and context corrections."""
import json

import pytest

from backend.runtime.questions import question_set
from backend.tests.runtime.test_human_questions import setup_question


def choices():
    """Use two distinct questions and labels that cannot be substituted for their option identifiers."""
    return question_set([
        {"id": "unit", "question": "¿Qué unidad tiene el resultado?", "options": [
            {"id": "mass_kg", "label": "Kilogramos"}, {"id": "volume_l", "label": "Litros"}]},
        {"id": "scope", "question": "¿A qué muestra corresponde?", "options": []},
    ])


def test_choices_preserve_ids_without_reinterpreting_free_text_as_an_option():
    """A selected ID and a typed identical string remain different evidence about what the user supplied."""
    draft = choices()
    selected = {"unit": {"option_id": "mass_kg"}, "scope": "Muestra del martes"}
    assert question_set(draft.payload()).payload() == draft.payload()
    assert "Kilogramos" in draft.answered_statement(selected)
    assert "mass_kg" in draft.answered_statement(selected)
    typed = draft.answered_statement({"unit": "mass_kg", "scope": "Muestra del martes"})
    assert "Kilogramos" not in typed
    for bad in [{"option_id": "Kilogramos"}, {"option_id": "absent"}, {"option_id": "mass_kg", "label": "Litros"}]:
        with pytest.raises(ValueError):
            draft.validate_answers({**selected, "unit": bad})


async def test_http_choice_and_free_answer_keep_request_thread_and_snapshot(coordination):
    """One owner answer commits the original question identities and human thread without starting inference."""
    from backend.api.local_access import LocalAccess
    from backend.api.main import create_app
    from backend.api.models.questions import AskUser
    from backend.tests.runtime.test_workspace_delivery import owner_client

    c = coordination
    wire = AskUser.model_validate({"operation_key": "ask-options", "questions": choices().payload()})
    questions, run, lease, _, receipt = setup_question(c, draft=wire.domain())
    questions.park(lease)
    app = create_app(access=LocalAccess(pairing_key="workspace-owner-key-at-least-32-characters"))
    async with app.router.lifespan_context(app), owner_client(app) as client:
        payload = {"operation_key": "answer-options", "expected_version": 1,
                   "answers": {"unit": {"option_id": "mass_kg"}, "scope": "Muestra del martes"}}
        path = f'/api/projects/101/tasks/1001/questions/{receipt["request_id"]}/answers'
        response = await client.post(path, json=payload)
        assert response.status_code == 200, response.text
        assert (await client.post(path, json=payload)).json() == response.json()
    snapshot = c.store.context_snapshot(101, 1001)
    assert snapshot['user_answers'][0]['answers'] == payload['answers']
    assert snapshot['user_answers'][0]['questions'][0]['options'][0] == {"id": "mass_kg", "label": "Kilogramos"}
    saved = c.conn.execute('SELECT response FROM user_requests WHERE id=?', (receipt['request_id'],)).fetchone()[0]
    assert json.loads(saved) == payload['answers']
    messages = c.conn.execute('SELECT thread_id,message FROM chat_messages').fetchall()
    assert {row['thread_id'] for row in messages} == {'human-thread'}
    assert any('Kilogramos' in row['message'] and 'Muestra del martes' in row['message'] for row in messages)
    assert c.conn.execute('SELECT count(*) FROM runtime_runs').fetchone()[0] == 1
    assert c.store.get(101, run.run_id).status == 'superseded'


def test_legacy_text_choices_remain_readable_and_new_ids_must_be_unique():
    """Old persisted string choices keep their shape; new labels cannot conceal repeated identity."""
    old = [{"id": "unit", "question": "¿Unidad?", "why_needed": "", "example": "", "options": ["kg", "l"]}]
    assert question_set(old).payload() == old
    bad = choices().payload()
    bad[0]['options'][1]['id'] = 'mass_kg'
    with pytest.raises(ValueError):
        question_set(bad)
