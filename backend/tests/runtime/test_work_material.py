"""Selective historical context reads preserve exact frozen evidence without requiring recursive native input copies; storage witnesses are synthetic."""

import base64
import hashlib
import json

import pytest

from backend.planning.materials import PredecessorMaterials
from backend.runtime.contracts import RunConflict
from backend.tests.runtime.test_plan_execution import accepted_plan, authorize, reserve_documentary_input
from backend.tests.runtime.test_predecessor_research_material import research_dependency


def decoded(page):
    """Decode one complete selected JSON value; a partial window must never masquerade as the complete document."""
    assert page['complete_material']
    return json.loads(base64.b64decode(page['data_base64'], validate=True))


def large_plan_delivery(service_setup):
    """Build a real accepted plan from a large original project premise and admit its root using original storage decisions."""
    s = service_setup
    original = 'z' * 600000 + '\nOriginal qualification: do not modify the source repository.'
    s.c.conn.execute('UPDATE projects SET description=? WHERE id=101', (original,))
    s.c.conn.commit()
    s, plan, graph = accepted_plan(s)
    executions, authorization = authorize(s, plan)
    spec, binding = executions.prepare(authorization['execution_id'], graph['tasks']['learn'])
    run = s.c.store.admit(spec, binding=binding)
    lease = s.c.store.claim(101, run.run_id, 'bounded-context-reader')
    s.c.store.bind_thread(lease, thread_id='bounded-context-thread')
    frozen = reserve_documentary_input(s, lease)
    return s, run, lease, frozen, original


def test_large_plan_starts_with_reference_and_recovers_original_tail(service_setup):
    """A valid large original plan premise stays outside the native envelope and remains available exactly, including a final restriction."""
    s, run, lease, frozen, original = large_plan_delivery(service_setup)
    assert len(frozen.input_text.encode()) < 25000
    packet = json.loads(frozen.input_text)['work_delivery']
    reference = packet['plan_context']['material_reference']
    assert reference['read_tool'] == 'researcher_work_context' and reference['bytes'] > 1048576
    reader = PredecessorMaterials(s.c.store)
    assert reader.available(lease)
    index = decoded(reader.read_work(lease, 'plan_context', mode='inspect'))
    assert any(item['key'] == 'original_material' for item in index['children'])
    request = decoded(reader.read_work(lease, 'plan_context', path=['original_material', 'owner_request']))
    assert request == 'Investigate the issue and propose a plan.'
    expected = json.dumps(original, ensure_ascii=False, separators=(',', ':')).encode()
    tail = reader.read_work(lease, 'plan_context', path=['original_material', 'project', 'description'], offset=len(expected)-150)
    assert base64.b64decode(tail['data_base64']) == expected[-150:]
    assert tail['sha256'] == hashlib.sha256(expected).hexdigest() and not tail['complete_material']
    assert tail['source']['delivery_packet_sha256'] == packet['delivery_packet_sha256']
    s.c.conn.execute("UPDATE projects SET description='A revised objective' WHERE id=101")
    s.c.conn.commit()
    with pytest.raises(RunConflict):
        reader.read_work(lease, 'plan_context')


def test_selective_research_reads_limitations_and_sources_without_copying_reports(service_setup):
    """The receiving task can inspect a decisive limit, finding and its source in a few bounded calls even when accepted reports exceed one MiB."""
    reports = ['x' * 399800 + '\nDo not infer individual measurements.' for _ in range(3)]
    s, root, _child, lease, _accepted = research_dependency(service_setup, report_contents=reports)
    reader = PredecessorMaterials(s.c.store)
    index = decoded(reader.read_research(lease, root.task_id, mode='inspect'))
    report_index = next(item for item in index['children'] if item['key'] == 'reports')
    assert report_index['bytes'] > 1048576 and index['content_read'] is False
    pages = [reader.read_research(lease, root.task_id, path=path) for path in [['limitations'], ['findings', 0], ['sources', 0]]]
    assert decoded(pages[0]) == ['Measurement not repeated.']
    assert '137 units' in decoded(pages[1])['finding']['content']
    assert '137 units' in decoded(pages[2])['source']['content']
    assert sum(page['total_bytes'] for page in pages) < 8000
    assert all(page['selection']['whole_section_read'] is False for page in pages)
    with pytest.raises(ValueError):reader.read_research(lease, root.task_id, path=['sources', True])
    with pytest.raises(RunConflict):reader.read_research(lease, root.task_id, path=['sources', 5000])
    with pytest.raises(ValueError):reader.read_research(lease, root.task_id, 'author_input', path=['scope'])


@pytest.mark.parametrize('section', ['plan_context', 'continuation', 'reauthorization'])
def test_projection_keeps_large_context_exact_and_historical_schema_unchanged(section):
    """Pure projection covers all context kinds without claiming a synthetic packet grants actual runtime authority."""
    from backend.planning.material_views import project_delivery

    packet = {'schema_version': 5, 'delivery_id': 'synthetic', 'instruction': 'Current task only.', section: {'important_tail': 'x' * 1100000 + 'NO REPLAY'}}
    projected = project_delivery(packet)
    assert len(json.dumps(projected)) < 2000 and projected['instruction'] == packet['instruction']
    assert packet[section]['important_tail'].endswith('NO REPLAY')
    for version in (2, 3, 4):
        old = {**packet, 'schema_version': version}
        assert project_delivery(old) == old


def test_work_reader_rejects_unknown_sections_paths_and_unbound_attempts(service_setup):
    """Selectors navigate only admitted immutable context; they are not filesystem paths, project selectors or a grant to inspect other work."""
    s, _run, lease, _frozen, _original = large_plan_delivery(service_setup)
    reader = PredecessorMaterials(s.c.store)
    with pytest.raises(ValueError):reader.read_work(lease, '/etc/passwd')
    with pytest.raises(RunConflict):reader.read_work(lease, 'continuation')
    with pytest.raises(RunConflict):reader.read_work(lease, 'plan_context', path=['__dict__'])
    with pytest.raises(ValueError):reader.read_work(lease, 'plan_context', path=['a'] * 17)
    from dataclasses import replace
    other = s.c.store.admit(replace(s.c.spec, task_id=1002, operation_key='unrelated-material-reader'))
    other_lease = s.c.store.claim(101, other.run_id, 'unrelated-owner')
    with pytest.raises(RunConflict):reader.read_work(other_lease, 'plan_context')


def test_selective_continuation_preserves_original_identity_and_cancel_withdraws_access(service_setup):
    """An actual owner-authorized successor reads its predecessor history, and its live lease remains mandatory for later reads."""
    from backend.tests.runtime.test_plan_continuation import interrupted_delivery

    s, _plan, executions, eid, original, previous, _lease, _peers = interrupted_delivery(service_setup)
    preview = executions.continuation_state(101, eid, original['delivery_id'])
    executions.continue_delivery(101, eid, original['delivery_id'], operation_key='selective-continuation', snapshot_sha256=preview['snapshot_sha256'])
    spec, binding = executions.prepare(eid, previous.task_id)
    current = s.c.store.admit(spec, binding=binding)
    lease = s.c.store.claim(101, current.run_id, 'successor-reader')
    reader = PredecessorMaterials(s.c.store)
    assert decoded(reader.read_work(lease, 'continuation', path=['previous_run', 'run_id'])) == previous.run_id
    assert decoded(reader.read_work(lease, 'continuation', path=['limitations'])) == preview['snapshot']['limitations']
    s.c.store.cancel(101, current.run_id)
    with pytest.raises(RunConflict):reader.read_work(lease, 'continuation')


def test_inspection_pages_child_descriptors_without_revealing_or_claiming_body_reads():
    """A broad evidence collection yields explicit child-index continuation and hashes, keeping content undisclosed until a separate selected read."""
    from backend.planning.material_views import select_material

    value = {f'item-{i:03d}': 'Important content ' * 1000 for i in range(61)}
    first = json.loads(select_material(value, mode='inspect'))
    assert len(first['children']) == 25 and first['next_child_offset'] == 25
    assert first['content_read'] is False and 'Important content' not in json.dumps(first)
    second = json.loads(select_material(value, mode='inspect', child_offset=25))
    last = json.loads(select_material(value, mode='inspect', child_offset=second['next_child_offset']))
    keys = [v['key'] for p in (first, second, last) for v in p['children']]
    assert keys == sorted(value) and last['next_child_offset'] is None
