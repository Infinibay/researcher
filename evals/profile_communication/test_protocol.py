"""Reject altered evidence, wrong capability injection and accidental replay before subscription work."""

import argparse
import json

import pytest


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
