"""Retired framework adapters cannot reintroduce command owners, generic SQL or hidden document-model calls."""

import importlib.machinery
import importlib.util
from pathlib import Path

import backend


def test_replaced_framework_adapters_are_unavailable():
    """Check installed import locations without loading retired frameworks or web packages."""
    for module in (
        'backend.tools.shell', 'backend.tools.git',
        'backend.tools.rag', 'backend.tools.data', 'backend.tools.web', 'backend.tools.task',
        'backend.tools.communication', 'backend.tools.project', 'backend.tools.knowledge', 'backend.communication.question_registry',
        'backend.communication.response_event_registry',
        'backend.tools._legacy_access', 'backend.tools.base.base_tool',
        'backend.tools.base.dedup', 'backend.tools.base.embeddings',
        'backend.tools.base.permissions',
        'backend.api.routes.internal', 'backend.api.routes.internal_findings',
        'backend.api.routes.internal_tasks',
        'backend.communication.service', 'backend.communication.thread_manager',
        'backend.communication.loop_guard', 'backend.communication.listeners',
        'backend.communication.notifications', 'backend.communication.protocol',
        'backend.communication.brainstorm_coordinator',
        'backend.flows.event_listeners', 'backend.flows.listener_base',
        'backend.flows.helpers', 'backend.flows.flow_helpers',
        'backend.flows.guardrails', 'backend.flows.react_trace',
        'backend.flows.state_models', 'backend.flows.main_project_flow',
        'backend.flows.brainstorming_flow', 'backend.flows.ticket_creation_flow',
        'backend.flows.development_flow', 'backend.flows.code_review_flow',
        'backend.flows.research_flow', 'backend.flows.research_review_flow',
        'backend.flows.investigation_flow',
    ):
        assert importlib.util.find_spec(module) is None, module
    web = Path(backend.__file__).parent / 'tools' / 'web'
    for module in ('code_docs_search', 'crewai_tool_config'):
        assert importlib.machinery.PathFinder.find_spec(module, [str(web)]) is None
