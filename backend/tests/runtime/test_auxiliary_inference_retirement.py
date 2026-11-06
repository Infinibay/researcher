"""Old configuration, probes, summaries and deep-research tools cannot spend a provider turn or infer native capability outside an admitted runtime."""

import sys
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('entry', ['config','params','probe'])
def test_legacy_provider_ports_reject_before_model_construction_or_generation(monkeypatch, entry):
    """An available old API key or installed provider must never become a billing fallback for native subscription work."""
    from backend.config import llm, model_capabilities
    from backend.runtime.lifecycle import NativeOwnerRequired

    def forbidden(*_args, **_kwargs):
        """Make every old provider invocation observable without making a network request."""
        pytest.fail('Retired provider was invoked')

    monkeypatch.setitem(sys.modules,'crewai',SimpleNamespace(LLM=forbidden))
    monkeypatch.setitem(sys.modules,'litellm',SimpleNamespace(completion=forbidden,acompletion=forbidden))
    llm._reset_llm_cache()
    call = {'config':llm.get_llm,'params':llm.get_litellm_params,'probe':lambda:model_capabilities.probe_model({'model':'old-provider'})}[entry]
    with pytest.raises(NativeOwnerRequired):
        call()


def test_unprobed_legacy_capabilities_do_not_claim_support():
    """Legacy metadata may describe unknown support, but cannot guess native model/account capabilities or claim a probe ran."""
    from backend.config.model_capabilities import ModelCapabilities

    caps = ModelCapabilities()
    assert caps.supports_function_calling is None
    assert caps.supports_tool_choice_required is None
    assert caps.supports_json_mode is None
    assert caps.probed is False


def test_legacy_env_setup_does_not_export_api_credentials(monkeypatch):
    """Old startup hooks leave subscription authentication to the native controller rather than exporting a fallback key."""
    import os

    from backend.config.llm import setup_provider_env_vars
    from backend.config.settings import settings

    monkeypatch.setattr(settings,'LLM_API_KEY','synthetic-unused-test-key')
    monkeypatch.delenv('OPENAI_API_KEY',raising=False)
    setup_provider_env_vars()
    assert 'OPENAI_API_KEY' not in os.environ


def test_old_conversation_reader_does_not_generate_an_unattributed_summary(monkeypatch):
    """Literal original messages remain available; a provider digest is not substituted for testimony or shared understanding."""
    from backend.prompts.team import _summarize_messages_llm

    def forbidden(*_args, **_kwargs):
        """Fail on an old summarizer call before any actual model request."""
        pytest.fail('No auxiliary summary model may run')

    monkeypatch.setitem(sys.modules,'litellm',SimpleNamespace(completion=forbidden))
    monkeypatch.setattr('backend.config.llm.get_litellm_params',lambda:{'model':'synthetic-old-provider'})
    assert _summarize_messages_llm([{'from_agent':'user','message':'This is an example, not approval.'}],'legacy-summary-test',101) is None




def test_historical_conversation_reader_keeps_literal_scoped_text_and_discloses_limits(coordination):
    """A bounded old-context display cannot turn omitted text or another project's message into shared knowledge."""
    from backend.prompts.team import build_conversation_context

    c = coordination
    c.conn.executemany("INSERT INTO conversation_threads(thread_id,project_id,thread_type) VALUES(?,?,'user_chat')", [('reader-alpha',101),('reader-beta',202)])
    for number in range(12):
        c.conn.execute("INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,message) VALUES(101,'reader-alpha','user','legacy-reader',?)", (f'Original example {number:02d}: not an approval.',))
    c.conn.execute("INSERT INTO chat_messages(project_id,thread_id,from_agent,to_agent,message) VALUES(202,'reader-beta','user','legacy-reader','Foreign message must not enter')")
    c.conn.commit()
    result = build_conversation_context(project_id=101,agent_id='legacy-reader')
    assert 'Showing 10 of 12 retrieved messages' in result
    assert 'Original example 11: not an approval.' in result
    assert 'Foreign message' not in result
    assert 'not new instructions' in result and 'unexamined, not absent' in result


@pytest.mark.parametrize('entry',['validate','private_probe'])
def test_private_validation_entries_cannot_bypass_retired_provider_policy(entry):
    """Compatibility/private entry points cannot silently revive capability generation or report an unrun validation as success."""
    from backend.config import llm, model_capabilities
    from backend.runtime.lifecycle import NativeOwnerRequired

    with pytest.raises(NativeOwnerRequired):
        if entry == 'validate':
            llm.validate_function_calling()
        else:
            model_capabilities._run_probes({'model':'old-provider'})
