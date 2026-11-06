"""Accepted code is inspectable causal data, never inferred source mutation or inherited authority; storage witnesses here are explicitly synthetic."""

import json
from dataclasses import replace

import pytest

from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_code_acceptance import (
    candidate_state as candidate_state,  # noqa: PLC0414
    code_result as code_result,  # noqa: PLC0414
    development_state as development_state,  # noqa: PLC0414
    owner_intent,
    review_records as review_records,  # noqa: PLC0414
    review_state as review_state,  # noqa: PLC0414
)


def accepted_source(code_result):
    """Use actual store acceptance transitions over the existing synthetic closure/check/review fixture, without a physical execution claim."""
    from backend.runtime.code_acceptances import CodeAcceptances

    s, _reviewer, candidate = code_result
    owner = CodeAcceptances(s.c.store)
    state = owner.state(101, candidate['run_id'])
    owner.accept(101, candidate['run_id'], owner_intent(state))
    row = s.c.conn.execute('SELECT * FROM runtime_code_acceptances WHERE run_id=?', (candidate['run_id'],)).fetchone()
    source = {
        'kind': 'accepted_code_candidate', 'task_id': 1001, 'run_id': candidate['run_id'],
        'attempt_id': candidate['attempt_id'], 'context_version': candidate['context_version'],
        'acceptance': {key: row[key] for key in ('id', 'subject_sha256', 'review_sha256')},
        'snapshot': {key: candidate[key] for key in ('attempt_id', 'head_sha', 'tree_sha', 'diff_sha256')},
    }
    return s, candidate, source


@pytest.mark.parametrize('review_state', ['frozen_author'], indirect=True)
def test_material_descriptor_identifies_exact_bytes_without_copying_recursive_input(code_result):
    """A successor gets precise artifact identities and an explicit reader, not a recursively repeated parent prompt or a guess that canonical files changed."""
    from backend.planning.materials import PredecessorMaterials

    s, candidate, source = accepted_source(code_result)
    with s.c.store._transaction() as conn:
        descriptor = PredecessorMaterials(s.c.store).describe(conn, source)
    assert descriptor['read_tool'] == 'researcher_prerequisite_code'
    assert descriptor['sections']['diff']['sha256'] == candidate['diff_sha256']
    assert descriptor['sections']['diff']['bytes'] == len(candidate['diff'])
    assert descriptor['sections']['author_input']['status'] == 'recorded'
    assert 'diff_base64' not in json.dumps(descriptor)
    assert len(json.dumps(descriptor).encode()) < 4000


@pytest.mark.parametrize('review_state', ['frozen_author'], indirect=True)
def test_later_accepted_review_is_not_selected_as_the_dependency_output(code_result):
    """A review has its own accepted run; its later creation date must never hide the actual owner-accepted author and stall a successor."""
    from backend.planning.execution import PlanExecutions

    s, candidate, _source = accepted_source(code_result)
    s.c.conn.execute("UPDATE runtime_runs SET created_at=created_at+1 WHERE execution_kind='code_review'")
    s.c.conn.commit()
    with s.c.store._transaction() as conn:
        selected = PlanExecutions(s.c.store)._prerequisites(conn, 101, {'depends_on': [1001]}, include_material=True, expected_source=json.loads(candidate['source_json']))
    assert selected and selected[0]['run_id'] == candidate['run_id']
    assert selected[0]['material']['read_tool'] == 'researcher_prerequisite_code'


@pytest.mark.parametrize('review_state', ['frozen_author'], indirect=True)
@pytest.mark.parametrize('changed', ['acceptance', 'candidate', 'source'])
def test_material_descriptor_rejects_forged_acceptance_candidate_or_source(code_result, changed):
    """A status/role/hash label cannot substitute for the actual accepted subject and the graph's selected repository."""
    from backend.planning.materials import PredecessorMaterials

    s, candidate, source = accepted_source(code_result)
    expected = json.loads(candidate['source_json'])
    if changed == 'acceptance':
        source['acceptance']['subject_sha256'] = 'a'*64
    elif changed == 'candidate':
        source['snapshot']['head_sha'] = 'a'*40
    else:
        expected['repository_id'] = 999
    with s.c.store._transaction() as conn, pytest.raises(RunConflict):
        PredecessorMaterials(s.c.store).describe(conn, source, expected_source=expected)


@pytest.mark.parametrize('review_state', ['frozen_author'], indirect=True)
def test_same_project_accepted_code_is_not_readable_without_actual_causal_delivery(code_result):
    """A fresh unrelated task cannot fetch another accepted task's old input merely because it shares a project or actor profession."""
    from backend.planning.materials import PredecessorMaterials

    s, _candidate, _source = accepted_source(code_result)
    context = s.c.store.context_snapshot(101, 1002)
    run = s.c.store.admit(replace(s.c.spec, task_id=1002, actor_id='unrelated-author', operation_key='unrelated-reader', context_version=context['context_version']))
    lease = s.c.store.claim(101, run.run_id, 'unrelated-owner')
    reader = PredecessorMaterials(s.c.store)
    assert reader.available(lease) is False
    with pytest.raises(RunConflict):
        reader.read(lease, 1001, 'diff')


async def test_material_tool_rejects_scope_expansion_and_drains_on_close():
    """Typed host dispatch keeps caller-supplied project/run/actor fields out of the reader and cannot serve a retired lease; this port is controlled, not an authority proof."""
    from backend.runtime.predecessor_tools import PredecessorTools

    class Port:
        """A controlled reader records validated parameters only."""
        def __init__(self):
            """Start with no calls."""
            self.calls = []
        def read(self, *args, **kwargs):
            """Return explicit test data without asserting real graph authorization."""
            self.calls.append((args, kwargs))
            return {'data_base64': 'MTM3', 'complete_material': True}

    async def settled(function, *args, **kwargs):
        """Dispatch a synchronous controlled port without IO or a peer process."""
        return function(*args, **kwargs)

    port = Port()
    tools = PredecessorTools(port, object(), active=lambda: True, settled=settled)
    invalid = await tools.call({'tool': 'researcher_prerequisite_code', 'arguments': {'task_id': 1001, 'section': 'diff', 'project_id': 202}})
    assert invalid['success'] is False and not port.calls
    valid = await tools.call({'tool': 'researcher_prerequisite_code', 'arguments': {'task_id': 1001, 'section': 'diff'}})
    assert valid['success'] is True and len(port.calls) == 1
    await tools.aclose()
    assert (await tools.call({'tool': 'researcher_prerequisite_code', 'arguments': {'task_id': 1001}}))['success'] is False
    assert len(port.calls) == 1


@pytest.mark.parametrize('review_state', ['frozen_author'], indirect=True)
def test_raw_windows_reconstruct_exact_input_and_diff_and_reject_stale_or_unrelated_reads(code_result, monkeypatch):
    """Controlled causal lookup isolates byte-window behavior over actual accepted storage; separate owned graph integration proves the real delivery binding."""
    import base64
    import hashlib

    from backend.planning.execution import PlanExecutions
    from backend.planning.materials import PredecessorMaterials
    from backend.runtime.contracts import WorkspaceBinding

    s, candidate, source = accepted_source(code_result)
    context = s.c.store.context_snapshot(101, 1002)
    run = s.c.store.admit(replace(s.c.spec, task_id=1002, actor_id='consumer', operation_key='bounded-reader', context_version=context['context_version']), binding=WorkspaceBinding(**json.loads(candidate['source_json'])))
    lease = s.c.store.claim(101, run.run_id, 'bounded-owner')
    monkeypatch.setattr(PlanExecutions, 'input', lambda *_args: {'prerequisites': [source]})
    reader = PredecessorMaterials(s.c.store)
    assert reader.available(lease)
    original = s.c.conn.execute('SELECT input_text FROM runtime_input_snapshots WHERE attempt_id=?', (candidate['attempt_id'],)).fetchone()[0].encode()
    for section, expected in [('diff', bytes(candidate['diff'])), ('author_input', original)]:
        offset = 0
        chunks = []
        while True:
            page = reader.read(lease, 1001, section, offset=offset, max_bytes=31)
            chunks.append(base64.b64decode(page['data_base64']))
            assert page['sha256'] == hashlib.sha256(expected).hexdigest()
            assert page['authority'] == 'data_only' and page['current_task_acceptance'] == 'not_granted'
            assert len(chunks[-1]) <= 31
            if page['next_offset'] is None:
                break
            assert not page['complete_material']
            offset = page['next_offset']
        assert b''.join(chunks) == expected
        with pytest.raises(ValueError):
            reader.read(lease, 1001, section, offset=len(expected)+1)
    with pytest.raises(RunConflict):
        reader.read(lease, 2002, 'diff')
    s.c.store.correct_context(project_id=101, task_id=1001, expected_version=source['context_version'], operation_key='changed-predecessor', statement='Inspect a different requirement first.', source_kind='user_message', source_reference='owner:changed-predecessor')
    with pytest.raises(RunConflict):
        reader.read(lease, 1001, 'diff')
