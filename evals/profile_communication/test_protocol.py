"""Reject altered evidence, wrong capability injection and accidental replay before subscription work."""

import argparse
import json

import pytest


def test_controlled_code_author_transport_is_deterministic_and_scoped(tmp_path):
    """The account-free author fixture changes only its declared protocol branch and model advertisement."""
    from evals.profile_communication.code_review import build_controlled_asset

    first, second = tmp_path / 'first', tmp_path / 'second'
    source = '"""Controlled bad candidate."""\ndef mean_observations(records):\n    return 10\n'
    build_controlled_asset(first, 'gpt-6.1-sol', source)
    build_controlled_asset(second, 'gpt-6.1-sol', source)
    assert first.read_bytes() == second.read_bytes()
    assert first.stat().st_mode & 0o777 == 0o700
    compile(first.read_text(), str(first), 'exec')
    assert 'Controlled author transport; no generative model ran.' in first.read_text()


def test_controlled_author_accepts_actual_ken_source_text_without_json_decoding(tmp_path):
    """Ken source prose is a successful tool result; only command receipts carry the JSON used for job control."""
    import ast
    from evals.profile_communication.code_review import build_controlled_asset

    path = tmp_path / 'controlled'
    build_controlled_asset(path, 'gpt-6.1-sol', '"""Candidate."""\n')
    function = next(n for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'next_development_tool')
    calls = []
    scope = {'steps': 1, 'job': None, 'json': json, 'call': lambda name, args: calls.append((name, args))}
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), scope)
    scope['next_development_tool']({'success': True, 'contentItems': [{'text': 'evidence.py:1-5\n1 | def list_observations(records):'}]})
    assert calls[0][0] == 'researcher_python'
    assert calls[0][1]['operation_key'] == 'controlled-write'


def test_code_review_registration_discloses_controlled_reservation_without_more_generative_turns(tmp_path):
    """A native author fixture reservation must remain distinct from the original one-model-turn reviewer ceiling."""
    from evals.profile_communication.code_review import register
    from evals.context_alignment.protocol import load_registered

    assets = tmp_path / 'assets.json'
    assets.write_text(json.dumps({'model': 'gpt-6.1-sol', 'project_turn_limit': 1,
                                 'project_token_limit': 100000, 'limits': {'max_tool_calls': 12}}))
    root = tmp_path / 'study'
    register(root, assets)
    p = load_registered(root)
    assert p['maximum_generative_turns'] == 2
    assert p['controlled_author_generative_turns'] == 0
    assert p['controlled_author_reservations_per_arm'] == 1
    assert p['reviewer_limits']['max_observed_tokens'] == 100000
    assert p['reviewer_limits']['max_tool_calls'] == 12
    assert p['human_comprehension'] is None
    (root / 'controlled-native').write_text('Changed after freezing.')
    with pytest.raises(ValueError, match='Registered input changed'):
        load_registered(root)


def test_code_review_controls_allow_only_verified_capture_head_variation():
    """Commit time may change the head, never the tree/diff, owner request, author input or a foreign head reference."""
    from backend.knowledge.reviews import digest as subject_digest
    from evals.context_alignment.protocol import digest
    from evals.profile_communication.code_review import compare_code_pair

    def result(head, run):
        """Construct independent identities over otherwise identical substantive candidate evidence."""
        text = '{"request":"Zeros count as observations"}'
        snapshot = {'candidate': {'head_sha': head, 'base_sha': 'base', 'tree_sha': 'tree', 'diff_sha256': 'diff'},
                    'author_input': {'input_sha256': digest(text.encode()), 'bytes': len(text)},
                    'author_request': {'text': 'Zeros count as observations'}, 'checks': []}
        sha = subject_digest(snapshot)
        return {'controlled_author': {'packet': {'snapshot': snapshot, 'subject_sha256': sha},
                                     'input_text': text, 'candidate': {'head_sha': head}},
                'attempts': [{'input': {'scope': {'run_id': run, 'attempt_id': run + '-attempt'},
                    'execution': {'head_sha': head, 'subject_sha256': sha},
                    'review': {'run_id': run, 'subject_sha256': sha}},
                    'catalog_hash': 'same-tools', 'model_control': {'model': 'fixed'}, 'comparable_input_sha256': 'unused'}]}

    left, right = result('a' * 40, 'one'), result('b' * 40, 'two')
    assert compare_code_pair(left, right)['controls_matched']
    right['attempts'][0]['input']['execution']['head_sha'] = 'foreign'
    with pytest.raises(ValueError, match='head'):
        compare_code_pair(left, right)
    right = result('b' * 40, 'two')
    right['controlled_author']['packet']['snapshot']['candidate']['tree_sha'] = 'different'
    with pytest.raises(ValueError, match='subject|packet'):
        compare_code_pair(left, right)
    right = result('b' * 40, 'two')
    right['controlled_author']['input_text'] = '{"request":"Zeros are missing"}'
    with pytest.raises(ValueError, match='input'):
        compare_code_pair(left, right)


def test_review_input_normalizes_only_its_own_run_alias():
    """A fresh review UUID may alias scope; a foreign review reference is a substantive mismatch."""
    from evals.context_alignment.protocol import comparable_input

    first = {'scope': {'run_id': 'one', 'attempt_id': 'a'},
             'review': {'run_id': 'one', 'subject_sha256': 'same', 'author_run_id': 'author'}}
    second = {'scope': {'run_id': 'two', 'attempt_id': 'b'},
              'review': {'run_id': 'two', 'subject_sha256': 'same', 'author_run_id': 'author'}}
    assert comparable_input(first) == comparable_input(second)
    second['review']['run_id'] = 'foreign'
    assert comparable_input(first) != comparable_input(second)
    second['review']['run_id'] = 'two'
    second['review']['author_run_id'] = 'different-author'
    assert comparable_input(first) != comparable_input(second)


def test_finding_review_registration_freezes_author_material_and_real_review_capability(tmp_path):
    """Review comparison fixes the controlled author's evidence/claim and rejects changed policy before dispatch."""
    from evals.profile_communication.finding_review import register
    from evals.context_alignment.protocol import load_registered

    assets = tmp_path / 'assets.json'
    assets.write_text(json.dumps({'limits': {'max_tool_calls': 12}, 'project_token_limit': 100000}))
    root = tmp_path / 'study'
    register(root, assets)
    p = load_registered(root)
    assert p['execution_kind'] == 'finding_review'
    assert p['maximum_model_turns'] == 2 and p['controlled_author_model_turns'] == 0
    assert p['limits']['max_tool_calls'] == 12 and p['limits']['max_observed_tokens'] == 100000
    assert p['human_comprehension'] is None
    (root / 'reference.md').write_text('Different evidence.')
    with pytest.raises(ValueError, match='Registered input changed'):
        load_registered(root)


async def test_review_execution_preserves_a_lower_operator_limit_after_registration(tmp_path, monkeypatch):
    """Frozen experiment ceilings never override a tighter current operator budget before installation or inference."""
    from evals.profile_communication import finding_review as review

    assets = tmp_path / 'assets.json'
    assets.write_text('{}')
    root = tmp_path / 'study'
    protocol = review.register(root, assets)
    assets.write_text(json.dumps({'limits': {'max_tool_calls': 7, 'max_observed_tokens': 50000}}))
    observed = {}

    def stopped_prepare(folder, private, **kwargs):
        """Read the derived resource plan, then stop without a host or model."""
        observed.update(json.loads(private.read_text()))
        raise RuntimeError('Stopped before installation')

    monkeypatch.setattr(review, 'prepare', stopped_prepare)
    with pytest.raises(RuntimeError, match='Stopped before installation'):
        await review.run_review_arm(root, protocol, 'candidate', assets)
    assert observed['limits']['max_tool_calls'] == 7
    assert observed['limits']['max_observed_tokens'] == 50000


def test_development_registration_freezes_source_tests_and_lower_operator_limits(tmp_path):
    """A development comparison must freeze its input/output contract without raising account or execution ceilings."""
    from evals.profile_communication.development import register
    from evals.context_alignment.protocol import load_registered

    assets = tmp_path / 'assets.json'
    assets.write_text(json.dumps({'limits': {'wall_seconds': 100, 'max_tool_calls': 12},
                                 'project_token_limit': 100000}))
    root = tmp_path / 'development'
    register(root, assets)
    frozen = load_registered(root)
    assert frozen['execution_kind'] == 'development'
    assert frozen['task_type'] == 'code'
    assert frozen['maximum_model_turns'] == 2
    assert frozen['workspace_files'] == ['evidence.py', 'test_evidence.py']
    assert frozen['limits']['wall_seconds'] == 100
    assert frozen['limits']['max_tool_calls'] == 12
    assert frozen['limits']['max_observed_tokens'] == 100000
    assert frozen['human_comprehension'] is None
    assert frozen['human_effort_seconds'] is None
    (root / 'test_evidence.py').write_text('Changed after registration.')
    with pytest.raises(ValueError, match='Registered input changed'):
        load_registered(root)


def test_development_fixture_has_identical_git_base_and_preserves_registered_bytes(tmp_path):
    """Fresh arm directories must not introduce different Git bases or accidentally retain the invoice challenge."""
    from types import SimpleNamespace
    from evals.profile_communication.development import prepare_workspace, register

    assets = tmp_path / 'assets.json'
    assets.write_text('{}')
    root = tmp_path / 'study'
    protocol = register(root, assets)
    bases = []
    for name in ['baseline', 'candidate']:
        workspace = tmp_path / name
        workspace.mkdir()
        for file in ['invoice.py', 'test_invoice.py']:
            (workspace / file).write_text('Original native_trial fixture.')
        bases.append(prepare_workspace(SimpleNamespace(workspace=workspace), root, protocol))
        assert (workspace / 'evidence.py').read_bytes() == (root / 'evidence.py').read_bytes()
        assert (workspace / 'test_evidence.py').read_bytes() == (root / 'test_evidence.py').read_bytes()
        assert not (workspace / 'test_invoice.py').exists()
    assert bases[0] == bases[1]
    with pytest.raises(FileExistsError, match='fresh'):
        prepare_workspace(SimpleNamespace(workspace=workspace), root, protocol)


async def test_started_development_comparison_cannot_replay_even_before_reading_assets(tmp_path):
    """A retained first arm, including a partial failed one, blocks all new admissions under that registration."""
    from evals.profile_communication.development import register, run

    assets = tmp_path / 'assets.json'
    assets.write_text('{}')
    root = tmp_path / 'study'
    register(root, assets)
    (root / 'development_csv-baseline').mkdir()
    assets.unlink()
    with pytest.raises(FileExistsError, match='original receipts'):
        await run(root, assets)


@pytest.mark.parametrize('kind,task', [
    ('development', 'code'), ('code_review', 'code'), ('finding_review', 'research'),
])
def test_frozen_policy_is_bound_to_one_explicit_native_capability(kind, task):
    """A paired native evaluation cannot inject another role's instructions into a differently authorized turn."""
    from evals.context_alignment.worker import bind_policy

    bound = bind_policy(b'Frozen capability policy.', task, execution_kind=kind)
    assert bound(kind, task) == 'Frozen capability policy.'
    for other_kind, other_task in [
        ('research', 'research'), ('development', 'code'), ('code_review', 'code'),
        ('finding_review', 'research'), ('remote_publication', 'code'),
    ]:
        if (other_kind, other_task) != (kind, task):
            with pytest.raises(ValueError, match='another capability'):
                bound(other_kind, other_task)
    with pytest.raises(ValueError, match='Unsupported'):
        bind_policy(b'Invalid pairing.', 'plan', execution_kind=kind)


def test_budget_regression_selection_freezes_only_one_attempt_and_honors_lower_operator_limits(tmp_path):
    """A targeted planning regression cannot silently run other profiles or enlarge the operator's limits."""
    from evals.profile_communication.delivery_budget import register
    from evals.context_alignment.protocol import load_registered

    assets = tmp_path / 'assets.json'
    assets.write_text(json.dumps({'limits': {'wall_seconds': 100, 'max_tool_calls': 12},
                                 'project_token_limit': 100000}))
    root = tmp_path / 'single-case'
    register(root, assets, case_ids=['plan_dependencies'])
    manifest = json.loads((root / 'registration.json').read_text())
    assert manifest['maximum_model_turns'] == 1
    assert [c['id'] for c in manifest['cases']] == ['plan_dependencies']
    protocol = load_registered(root / 'plan_dependencies')
    assert protocol['limits']['max_observed_tokens'] == 100000
    assert protocol['limits']['max_tool_calls'] == 12
    assert protocol['limits']['wall_seconds'] == 100
    assert protocol['maximum_model_turns'] == 1
    assert protocol['human_comprehension'] is None
    assert not (root / 'skipped_checks').exists()


@pytest.mark.parametrize('task_type', ['investigation', 'research', 'plan', 'review'])
def test_policy_override_is_bound_to_its_original_capability(task_type):
    """An evaluation policy cannot override another task profile or a development/publication turn."""
    from evals.context_alignment.worker import bind_policy

    policy = bind_policy(b'Exact original policy.\n', task_type)
    assert policy('research', task_type) == 'Exact original policy.\n'
    assert policy('research', task_type, limits=object()) == 'Exact original policy.\n'
    for kind, task in [('development', task_type), ('remote_publication', task_type), ('research', 'unknown')]:
        with pytest.raises(ValueError, match='another capability'):
            policy(kind, task)
    with pytest.raises(ValueError, match='Unsupported'):
        bind_policy(b'bad', 'unknown')


@pytest.mark.parametrize('file', ['candidate.txt', 'reference.md', 'evidence.py', 'case.json'])
def test_registration_rejects_changed_policy_source_and_rubric(tmp_path, file):
    """All outcome-relevant inputs are frozen, including held-out cases, before live execution."""
    from evals.profile_communication.run import register, registered

    root = tmp_path / 'study'
    register(root)
    before = registered(root)
    assert len(before['cases']) == 4 and before['maximum_model_turns'] == 8
    (root / 'selective_outcomes' / file).write_text('Changed after seeing a response.')
    with pytest.raises(ValueError, match='changed'):
        registered(root)


async def test_existing_pair_refuses_before_reading_or_starting_another_arm(tmp_path):
    """A prior failed/partial arm cannot silently be replaced under the same experiment identity."""
    from evals.profile_communication.run import register, run

    root = tmp_path / 'study'
    register(root)
    (root / 'plan_dependencies' / 'plan_dependencies-baseline').mkdir()
    assets = tmp_path / 'assets.json'
    assets.write_text('{}')
    args = argparse.Namespace(output=root, assets=assets, split='development', case='plan_dependencies')
    with pytest.raises(FileExistsError, match='original receipts'):
        await run(args)


def test_full_source_check_rejects_outline_or_same_text_from_other_file():
    """Required code must be returned by successful reads of the actual registered source, not merely guessed symbols."""
    from evals.context_alignment.run import verify_ken

    source = 'def calculate():\n    return 137 + 63\n'
    records = [{'tool': 'ken_find', 'response': {'success': True}},
               {'tool': 'ken_read', 'arguments': {'path': 'elsewhere.py'},
                'response': {'success': True, 'contentItems': [{'text': source}]}}]
    with pytest.raises(RuntimeError, match='registered source'):
        verify_ken(records, required_source=source)
    records[1]['arguments']['path'] = 'evidence.py'
    verify_ken(records, required_source=source)
    records[1]['response']['contentItems'][0]['text'] = 'def calculate'
    with pytest.raises(RuntimeError, match='registered source'):
        verify_ken(records, required_source=source)


async def test_case_budget_cannot_raise_the_original_operator_ceiling(tmp_path, monkeypatch):
    """A wider registered experiment still obeys a tighter actual host budget before inference."""
    from evals.context_alignment import run as shared

    assets = tmp_path / 'operator.json'
    assets.write_text(json.dumps({'limits': {'max_observed_tokens': 90000, 'max_tool_calls': 8},
                                 'project_token_limit': 80000, 'project_turn_limit': 1}))
    observed = {}

    def stopped_prepare(folder, private_assets, **kwargs):
        """Inspect derived synthetic resources, then stop before creating any host or native process."""
        observed.update(json.loads(private_assets.read_text()))
        raise RuntimeError('stop before installation')

    monkeypatch.setattr(shared, 'prepare', stopped_prepare)
    protocol = {'limits': {'max_observed_tokens': 350000, 'max_tool_calls': 20}}
    with pytest.raises(RuntimeError, match='stop before installation'):
        await shared.run_arm(tmp_path, protocol, {'id': 'budget'}, 'candidate', assets)
    assert observed['limits']['max_observed_tokens'] == 90000
    assert observed['limits']['max_tool_calls'] == 8
    assert observed['project_token_limit'] == 80000
    assert json.loads(assets.read_text())['limits']['max_observed_tokens'] == 90000


def test_history_cutoff_alias_normalization_preserves_history_and_foreign_identity():
    """The current cutoff may alias a fresh run UUID; prior request text or a foreign cutoff cannot be ignored."""
    from evals.context_alignment.protocol import comparable_input

    first = {'scope': {'run_id': 'one', 'attempt_id': 'a', 'task_id': 1},
             'request_history': {'mode': 'same_task_admissions', 'cutoff_run_id': 'one', 'requests': []}}
    second = {'scope': {'run_id': 'two', 'attempt_id': 'b', 'task_id': 1},
              'request_history': {'mode': 'same_task_admissions', 'cutoff_run_id': 'two', 'requests': []}}
    assert comparable_input(first) == comparable_input(second)
    second['request_history']['cutoff_run_id'] = 'foreign'
    assert comparable_input(first) != comparable_input(second)
    second['request_history']['cutoff_run_id'] = 'two'
    second['request_history']['requests'].append({'content': 'Different original request', 'current_authorization': False})
    assert comparable_input(first) != comparable_input(second)
    assert first['request_history']['cutoff_run_id'] == 'one'


def test_pair_recomputes_original_input_instead_of_trusting_a_copied_digest():
    """Copied digest metadata cannot hide a semantic difference in actually delivered owner context."""
    from evals.context_alignment.run import compare_pair

    row = {'comparable_input_sha256': 'copied', 'catalog_hash': 'tools', 'model_control': {'model': 'fixed'},
           'input': {'scope': {'run_id': 'one', 'attempt_id': 'a'}, 'request': 'first'}}
    changed = json.loads(json.dumps(row))
    changed['input']['request'] = 'different'
    with pytest.raises(ValueError, match='comparable_input_sha256'):
        compare_pair({'attempts': [row]}, {'attempts': [changed]})
