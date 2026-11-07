"""Check durable once-only evaluation intent and trace evidence without paid model calls."""

import json

import pytest


def test_restored_trial_requires_live_before_creating_data(tmp_path):
    """No implicit model authorization or filesystem preparation occurs without the explicit flag."""
    from evals.operation.restored_host import run

    output = tmp_path/'trial'
    with pytest.raises(ValueError,match='--live'):
        run(output,tmp_path/'absent-assets.json',live=False)
    assert not output.exists()


def test_host_admission_checkpoints_original_key_before_any_http_attempt(tmp_path,monkeypatch):
    """A lost reply cannot erase the identity needed to inspect the original admission without replay."""
    from evals.operation.host_smoke import admit_live
    from backend.runtime.sqlite_runs import SQLiteRunStore

    monkeypatch.setattr(SQLiteRunStore,'context_snapshot',lambda *args:{'context_version':1})
    result = {}
    receipt = tmp_path/'receipt.json'
    class UncertainClient:
        """Fail the single original HTTP request after observing its durable intent."""
        def post(self,path,*,json):
            """Assert persistence precedes sending and emulate an unobserved remote outcome."""
            import json as json_module

            prior = json_module.loads(receipt.read_text())
            assert prior['operation_key'] == json['operation_key']
            assert prior['admissions_sent'] == 1
            raise TimeoutError('original response unknown')
    def checkpoint(value):
        """Capture an exact inspection receipt without recording the model request text."""
        receipt.write_text(json.dumps(value))
    with pytest.raises(TimeoutError,match='original response'):
        admit_live(UncertainClient(),tmp_path,result,checkpoint=checkpoint)
    assert result['admissions_sent'] == 1
    assert 'run_id' not in result


@pytest.mark.parametrize('damage',['no_output','foreign_output','mention_only'])
def test_ken_verifier_rejects_calls_without_correlated_returned_code(damage):
    """A mention, attempted call or another tool's result cannot prove Ken read the restored source."""
    from evals.operation.restored_host import verify_ken

    call = {'type':'custom_tool_call','name':'exec','call_id':'owned','input':'const r=await tools.ken_read({path:"units.py"}); text(r)'}
    output = {'type':'custom_tool_call_output','call_id':'owned','output':'return 137 + 63'}
    rows = [call,output]
    if damage == 'no_output':rows = [call]
    elif damage == 'foreign_output':output['call_id'] = 'other'
    else:call.update(type='message',input='I used ken_read')
    with pytest.raises(AssertionError):verify_ken(rows)


def test_ken_verifier_accepts_correlated_synthetic_source():
    """The controlled trace proves returned fixture code without claiming general JavaScript analysis."""
    from evals.operation.restored_host import verify_ken

    rows = [{'type':'custom_tool_call','name':'exec','call_id':'owned','input':'text(await tools.ken_read({path:"units.py"}))'},
            {'type':'custom_tool_call_output','call_id':'owned','output':'return 137 + 63'}]
    assert verify_ken(rows) == ['ken_read']
