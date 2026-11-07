"""Research predecessors retain full evidence behind bounded reads; synthetic storage witnesses are not live agent comprehension evidence."""

import base64
import hashlib
import json

import pytest

from backend.planning.materials import PredecessorMaterials
from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_plan_execution import accepted_plan, authorize, accept_documentary_result, reserve_documentary_input


def research_dependency(service_setup, *, report_contents=None):
    """Accept actual stored reports and bind their successor through the real plan delivery, using synthetic peer closure witnesses."""
    state, plan, graph = accepted_plan(service_setup, research_only=True)
    executions, receipt = authorize(state, plan)
    spec, binding = executions.prepare(receipt['execution_id'], graph['tasks']['learn'])
    root = state.c.store.admit(spec, binding=binding)
    accepted = accept_documentary_result(state, root, report_contents=report_contents, freeze_author=True)
    spec, binding = executions.prepare(receipt['execution_id'], graph['tasks']['change'])
    child = state.c.store.admit(spec, binding=binding)
    lease = state.c.store.claim(101, child.run_id, 'documentary-reader')
    state.c.store.bind_thread(lease, thread_id='child-reader')
    reserve_documentary_input(state, lease)
    return state, root, child, lease, accepted


def test_large_research_dependency_starts_without_inlining_reports_and_recovers_exact_tail(service_setup):
    """More than one MiB of accepted reports must not block successor admission; exact windows preserve decisive final text and unread coverage."""
    reports = ['x' * 399800 + f'\nFinal qualification {i}: do not infer individual measurements. 137 units.' for i in range(3)]
    s, root, child, lease, accepted = research_dependency(service_setup, report_contents=reports)
    frozen = s.c.conn.execute('SELECT input_text FROM runtime_input_snapshots WHERE attempt_id=?', (lease.attempt_id,)).fetchone()[0]
    assert len(frozen.encode()) < 25000
    material = json.loads(frozen)['work_delivery']['prerequisites'][0]['material']
    assert material['read_tool'] == 'researcher_prerequisite_research'
    assert material['sections']['packet']['bytes'] > 1048576
    assert 'snapshot' not in json.loads(frozen)['work_delivery']['prerequisites'][0]
    reader = PredecessorMaterials(s.c.store)
    assert reader.available(lease)
    for descriptor, expected in zip(material['reports'], reports, strict=True):
        expected = '# Count report\n\n' + expected
        chunks, offset = [], 0
        while True:
            page = reader.read_research(lease, root.task_id, 'report', report_id=descriptor['artifact_id'], offset=offset)
            chunks.append(base64.b64decode(page['data_base64'], validate=True))
            assert page['authority'] == 'data_only' and page['sha256'] == hashlib.sha256(expected.encode()).hexdigest()
            if page['next_offset'] is None:
                assert not page['complete_material']
                break
            offset = page['next_offset']
        assert b''.join(chunks) == expected.encode()
    packet = reader.read_research(lease, root.task_id, 'packet')
    assert packet['sha256'] == accepted['candidate_sha256']
    assert packet['next_offset'] == 16384 and not packet['complete_material']


@pytest.mark.parametrize('changed', ['source', 'context'])
def test_research_material_rejects_changed_accepted_evidence(service_setup, changed):
    """Old acceptance cannot authorize reading a now-unverifiable prerequisite after its data or context changes."""
    s, root, child, lease, accepted = research_dependency(service_setup)
    reader = PredecessorMaterials(s.c.store)
    assert reader.read_research(lease, root.task_id)['source']['run_id'] == root.run_id
    if changed == 'source':
        s.c.conn.execute("UPDATE research_sources SET content='Changed source' WHERE task_id=?", (root.task_id,))
        s.c.conn.commit()
    else:
        s.c.store.correct_context(project_id=101, task_id=root.task_id, expected_version=root.context_version,
            operation_key='new-premise', statement='Use a different measurement.', source_kind='user_message', source_reference='owner:correction')
    with pytest.raises(RunConflict):
        reader.read_research(lease, root.task_id)


def test_research_material_scope_and_sections_do_not_widen_the_delivery(service_setup):
    """A task identifier, report identifier or section name cannot grant access to unrelated accepted material or nonexistent original input."""
    s, root, child, lease, accepted = research_dependency(service_setup)
    reader = PredecessorMaterials(s.c.store)
    with pytest.raises(RunConflict):reader.read_research(lease, 2002)
    with pytest.raises(RunConflict):reader.read_research(lease, root.task_id, 'report', report_id=99999)
    with pytest.raises(ValueError):reader.read_research(lease, root.task_id, 'diff')
    with pytest.raises(ValueError):reader.read_research(lease, root.task_id, max_bytes=16385)
    original = reader.read_research(lease, root.task_id, 'author_input')
    assert json.loads(base64.b64decode(original['data_base64']))['scope']['task_id'] == root.task_id


async def test_research_tool_dispatch_preserves_scope_windows_and_retirement(service_setup):
    """The actual tool dispatches a bounded stored report, rejects expanded arguments and stops reading after retirement."""
    from backend.runtime.predecessor_tools import PredecessorTools

    s, root, _child, lease, _accepted = research_dependency(service_setup)

    async def settled(function, *args, **kwargs):
        """Execute storage in this controlled test; the owned runtime separately proves its real draining executor."""
        return function(*args, **kwargs)

    port = PredecessorTools(PredecessorMaterials(s.c.store), lease, active=lambda: True, settled=settled)
    request = {'tool': 'researcher_prerequisite_research', 'arguments': {'task_id': root.task_id, 'max_bytes': 31}}
    response = await port.call(request)
    assert response['success']
    window = json.loads(response['contentItems'][0]['text'])
    assert window['next_offset'] == 31 and not window['complete_material']
    assert not (await port.call({**request, 'arguments': {**request['arguments'], 'project_id': 202}}))['success']
    assert not (await port.call({**request, 'arguments': {**request['arguments'], 'section': 'diff'}}))['success']
    await port.aclose()
    assert not (await port.call(request))['success']
