"""Native policy selection and provenance remain explicit across capability profiles; historical direct-provider prompt paths cannot execute."""
import hashlib
import pytest

from backend.tests.runtime.test_owned_factory import owned_config as owned_config


@pytest.mark.parametrize('kind,task,profile',[
    ('research','research','scientific_research'),('research','review','code_audit'),
    ('research','investigation','investigation'),('research','plan','planning'),
    ('development','code','development'),('code_review','code','code_review'),
    ('finding_review','research','finding_review'),
])
def test_every_native_profile_has_one_shared_policy_and_exact_versioned_identity(kind,task,profile):
    """Selecting a real capability includes common correction/communication policy exactly once and a hash of the complete actual instructions."""
    from backend.prompts.native import build_instructions,instruction_identity,COMMON_INSTRUCTIONS
    value=build_instructions(kind,task)
    assert value.count(COMMON_INSTRUCTIONS)==1
    assert instruction_identity(value)=={'catalog_version':3,'profile':profile,'sha256':hashlib.sha256(value.encode()).hexdigest()}
    assert 'Evidence and shared context' in value and 'Correctable explanation' in value
    assert 'Ken' in value and 'operation_key' in value
    assert 'profession' in value and 'chain of thought' in value


def test_catalog_does_not_relabel_old_instructions_or_admit_host_publication_as_inference():
    """Unknown historic text retains unknown catalog provenance; host-only publication never acquires a generative profile."""
    from backend.prompts.native import build_instructions,instruction_identity
    assert instruction_identity('old research instructions') is None
    with pytest.raises(ValueError):build_instructions('remote_publication','code')
    with pytest.raises(ValueError):build_instructions('research','unknown')


def test_recorded_catalog_two_identity_survives_new_policy_without_relabeling():
    """A stored older header retains its original version and exact hash after the current catalog advances."""
    from backend.prompts.native import instruction_identity

    recorded = 'RESEARCHER_POLICY 2 investigation\n\nEarlier recorded policy.'
    assert instruction_identity(recorded) == {
        'catalog_version': 2, 'profile': 'investigation',
        'sha256': hashlib.sha256(recorded.encode()).hexdigest(),
    }
    assert instruction_identity(recorded.replace('POLICY 2', 'POLICY 999')) is None


def test_warmup_compatibility_entry_refuses_before_http_or_prompt_rendering(monkeypatch):
    """The historical warmup helper cannot send even a one-token request to another provider or URL."""
    from backend.scripts.warmup_prefix_cache import _warmup_one
    from backend.runtime.lifecycle import NativeOwnerRequired
    with pytest.raises(NativeOwnerRequired):_warmup_one('researcher','ignored','https://unapproved.example','other-model')


async def test_actual_owned_turn_records_the_exact_versioned_policy_sent_to_native(owned_config):
    """The real owner/store/broker/Ken path sends catalog policy and freezes its exact bytes; a simulated native answer is not evidence of human comprehension."""
    import json
    from backend.prompts.native import instruction_identity
    from backend.tests.runtime.test_source_repair import app_for_sources
    c=owned_config;app,runtime=app_for_sources()
    async with runtime:
        run=await runtime.submit(c.s.c.spec,repository_id=11);await runtime.wait(run.run_id)
        view=runtime.store.get(101,run.run_id);assert view.status=='needs_review',view
        record=runtime.store.input_record(101,run.run_id);assert record['native_start_observed']
        thread=json.loads(next(c.s.control.glob('native-state/*/home/fixture-thread.json')).read_text())
        assert thread['developer_instructions']==record['developer_instructions']
        policy=instruction_identity(record['developer_instructions'])
        assert policy['profile']=='scientific_research' and policy['catalog_version']==3
        assert policy['sha256']==record['instructions_sha256']
