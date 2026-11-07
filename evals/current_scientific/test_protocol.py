"""Check frozen source/policy integrity and no-replay admission before using a subscription."""
import asyncio
import json

import pytest

from evals.context_alignment.protocol import load_registered
from evals.current_scientific.run import execute, register


def prepare(tmp_path):
    """Use resource-free test assets so these checks cannot create an actual inference installation."""
    assets = tmp_path/'assets.json'
    assets.write_text(json.dumps({'limits': {'max_tool_calls': 7, 'max_observed_tokens': 40000}}))
    root = tmp_path/'trial'
    register(root, assets)
    return root, assets


def test_current_policy_receives_operator_limits_and_modified_evidence_is_refused(tmp_path):
    """The model sees the lower operator ceilings, and source edits cannot silently change the registered problem."""
    root, _ = prepare(tmp_path)
    protocol = load_registered(root)
    policy = (root/'candidate.txt').read_text()
    limits = json.loads(policy.split('RESEARCHER_INITIAL_BUDGET\n')[1])
    assert limits['max_tool_calls'] == 7 and limits['max_observed_tokens'] == 40000
    assert limits == protocol['limits']
    assert protocol['maximum_model_turns'] == 1
    (root/'reference.md').write_text('Different evidence')
    with pytest.raises(ValueError, match='Registered input changed'):
        load_registered(root)


def test_changed_assets_prevent_admission(tmp_path):
    """A resource change after freezing fails before the shared native harness may open an installation."""
    root, assets = prepare(tmp_path)
    assets.write_text('{}')
    with pytest.raises(ValueError, match='Host assets changed'):
        asyncio.run(execute(root, assets))
    assert not (root/'primary_abstract_rates-candidate').exists()


def test_existing_arm_and_registration_are_not_overwritten(tmp_path):
    """An uncertain prior arm cannot be rerun, even when its folder has no final receipt."""
    root, assets = prepare(tmp_path)
    arm = root/'primary_abstract_rates-candidate'
    arm.mkdir()
    with pytest.raises(FileExistsError, match='Arm already exists'):
        asyncio.run(execute(root, assets))
    with pytest.raises(FileExistsError):
        register(root, assets)
