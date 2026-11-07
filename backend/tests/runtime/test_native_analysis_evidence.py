"""Native analysis evidence must correlate the Ken call with its own returned source."""

import pytest


@pytest.mark.parametrize('missing', [None, 'ken_read', 'researcher_python'])
def test_native_catalog_includes_research_ken_and_analysis(missing):
    """The input snapshot contains all three providers, not only the business MCP catalog."""
    from backend.runtime.business_mediation import RESEARCH_NAMES
    from evals.runtime.run_analysis_inference import verify_native_catalog

    names = set(RESEARCH_NAMES) | {'ken_find', 'ken_read', 'ken_recall', 'ken_related', 'ken_remember',
                                 'researcher_command_start', 'researcher_command_read', 'researcher_command_cancel', 'researcher_python'}
    if missing:
        names.remove(missing)
        with pytest.raises(AssertionError):
            verify_native_catalog(list(names))
    else:
        verify_native_catalog(list(names))


@pytest.mark.parametrize('prefix', ['', 'mcp__researcher_ken__'])
def test_trace_matches_both_native_catalog_spellings(prefix):
    """Recognize current direct names and historical names only when their output contains source."""
    from evals.runtime.run_analysis_inference import verify_ken_reads

    rows = [{'type': 'custom_tool_call', 'name': 'exec', 'call_id': 'read',
             'input': f'text(await tools.{prefix}ken_read({{path:"invoice.py",include:["source"]}}));'},
            {'type': 'custom_tool_call_output', 'call_id': 'read',
             'output': [{'type': 'text', 'text': 'invoice.py: return subtotal + tax_rate'}]}]
    assert verify_ken_reads(rows) == [prefix + 'ken_read']


@pytest.mark.parametrize('output_id,output', [('different', 'return subtotal + tax_rate'), ('read', 'permission denied')])
def test_trace_rejects_unmatched_or_unsuccessful_read(output_id, output):
    """Calling Ken or seeing code in another call is insufficient evidence that this read succeeded."""
    from evals.runtime.run_analysis_inference import verify_ken_reads

    rows = [{'type': 'custom_tool_call', 'name': 'exec', 'call_id': 'read',
             'input': 'text(await tools.ken_read({path:"invoice.py"}));'},
            {'type': 'custom_tool_call_output', 'call_id': output_id, 'output': output}]
    with pytest.raises(AssertionError, match='Ken'):
        verify_ken_reads(rows)
