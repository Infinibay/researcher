"""Real authenticated HTTP and local workers share persistent project accounting across owner and agent entry points."""

import pytest

from backend.tests.research.test_http import credentials, research_client as research_client
from backend.tests.research.test_acquisition import reference
from backend.runtime.auxiliary_budget import AuxiliaryBudget


def test_owner_preview_and_native_capture_share_one_actual_parser_receipt(research_client,research_store,db_conn,tmp_path,monkeypatch):
    """A completed owner extraction survives a lost response; native capture reuses it without another process, and project scope still gates reads."""
    from backend.research import worker_transport

    _,_,ref=reference(research_store,db_conn,tmp_path,content=b'{"count":137}')
    db_conn.execute("UPDATE reference_files SET file_type='application/json' WHERE id=?",(ref.id,));db_conn.commit()
    first=research_client.get(f'/api/files/{ref.id}/preview',params={'project_id':101})
    assert first.status_code==200,first.text
    budget=AuxiliaryBudget(research_store.database,101)
    state=budget.summary()
    assert state['used_operations']==1 and state['observed_cpu_ms']>0
    def forbidden(*args,**kwargs):
        """A repeated original calculation must recover its bytes instead of creating another process."""
        pytest.fail('worker replay')
    monkeypatch.setattr(worker_transport,'_exchange',forbidden)
    captured=research_client.post('/api/research-tools/sources/reference',headers=credentials(research_store),json={'operation_key':'capture-after-preview','reference_file_id':ref.id})
    assert captured.status_code==200,captured.text
    assert budget.summary()['used_operations']==1
    again=research_client.get(f'/api/files/{ref.id}/preview',params={'project_id':101})
    assert again.status_code==200 and again.json()['content']==first.json()['content']
    foreign=research_client.get(f'/api/files/{ref.id}/preview',params={'project_id':202})
    assert foreign.status_code==404


def test_native_document_capture_is_refused_before_worker_and_source_commit(research_client,research_store,db_conn,tmp_path,monkeypatch):
    """One operation cannot reserve the parser ceiling against an insufficient project CPU allowance."""
    from backend.research import worker_transport

    _,_,ref=reference(research_store,db_conn,tmp_path,content=b'{"count":200}')
    db_conn.execute("UPDATE reference_files SET file_type='application/json' WHERE id=?",(ref.id,))
    db_conn.execute('INSERT INTO runtime_auxiliary_policies VALUES(101,2,1)');db_conn.commit()
    def forbidden(*args,**kwargs):
        """Budget refusal must precede every process and source side effect."""
        pytest.fail('worker before admission')
    monkeypatch.setattr(worker_transport,'_exchange',forbidden)
    response=research_client.post('/api/research-tools/sources/reference',headers=credentials(research_store),json={'operation_key':'too-small','reference_file_id':ref.id})
    assert response.status_code==429,response.text
    assert 'No se inició un proceso' in response.json()['detail']
    assert AuxiliaryBudget(research_store.database,101).summary()['used_operations']==0
    assert db_conn.execute('SELECT count(*) FROM research_sources').fetchone()[0]==0


def test_owner_and_agent_semantic_queries_share_actual_encoder_receipt(research_client,research_store,db_conn,monkeypatch):
    """The pinned offline encoder runs once for the exact corpus/query; another authorized actor recovers it after the first response is lost."""
    from backend.tests.research.test_finding_registry import legacy_finding
    from backend.tests.research.test_semantic_retrieval import assets
    from backend.research.semantic import SemanticRetriever
    from backend.research import worker_transport

    legacy_finding(db_conn,content='The sample contains137units.')
    research_client.app.state.retrieval=SemanticRetriever(assets())
    first=research_client.get('/api/findings-query',params={'project_id':101,'query':'sample size'})
    assert first.status_code==200,first.text
    budget=AuxiliaryBudget(research_store.database,101)
    assert budget.summary()['used_operations']==1 and budget.summary()['observed_cpu_ms']>0
    def forbidden(*args,**kwargs):
        """The saved exact result must avoid all encoder process work."""
        pytest.fail('encoder replay')
    monkeypatch.setattr(worker_transport,'_exchange',forbidden)
    second=research_client.get('/api/research-tools/findings-query',headers=credentials(research_store),params={'query':'sample size'})
    assert second.status_code==200,second.text
    assert first.json()['local_accounting']['reused'] is False
    assert second.json()['local_accounting']['reused'] is True
    assert second.json()['local_accounting']['operation_id']==first.json()['local_accounting']['operation_id']
    assert second.json()['local_accounting']['measurement_origin']=='original_worker'
    assert second.json()['matches']==first.json()['matches']
    assert budget.summary()['used_operations']==1


def test_source_query_uses_actual_local_budget_and_rejects_next_calculation(research_client,research_store,research_scope,db_conn,monkeypatch):
    """Source-query accounting reaches the same real worker and refuses a different request before encoding when the project slot is spent."""
    from backend.tests.research.test_semantic_retrieval import assets
    from backend.research.semantic import SemanticRetriever
    from backend.research.models import SourceDraft
    from backend.research import worker_transport

    saved=research_store.capture_source(research_scope,'local-source',SourceDraft('web','https://example.org','Trial','The trial found no improvement.'),intent={'source':'fixture'})
    research_client.app.state.retrieval=SemanticRetriever(assets())
    db_conn.execute('INSERT INTO runtime_auxiliary_policies VALUES(101,1,600000)');db_conn.commit()
    path=f"/api/research-tools/sources/{saved['source_id']}/query";headers=credentials(research_store)
    first=research_client.get(path,headers=headers,params={'query':'treatment outcomes'})
    assert first.status_code==200,first.text
    def forbidden(*args,**kwargs):
        """A different query needs new capacity before invoking the encoder."""
        pytest.fail('encoder after cap')
    monkeypatch.setattr(worker_transport,'_exchange',forbidden)
    second=research_client.get(path,headers=headers,params={'query':'a different question'})
    assert second.status_code==429,second.text
    assert AuxiliaryBudget(research_store.database,101).summary()['used_operations']==1


def test_cancelled_owned_parser_closes_physically_and_keeps_unknown_cpu(research_store,monkeypatch,tmp_path):
    """Stop joins the actual busy child while its durable allowance remains held without a fabricated CPU measurement."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    from pathlib import Path
    from backend.research.models import ResearchForbidden
    from backend.research.parser_process import PDFParser, ParserLimits
    from backend.runtime.live_grants import LiveGrants
    from backend.tests.research.test_parser_process import worker_fault
    from backend.tests.research.pdf_fixtures import pdf_bytes

    marker=worker_fault(monkeypatch,tmp_path,'while True: pass')
    gate=LiveGrants();gate.activate('local-cancel')
    budget=AuxiliaryBudget(research_store.database,101)
    parser=PDFParser(owner=gate,grant_id='local-cancel',limits=ParserLimits(cpu_seconds=3,wall_seconds=5),accounting=budget)
    with ThreadPoolExecutor() as pool:
        pending=pool.submit(parser.read,pdf_bytes('Bounded operation'))
        deadline=time.monotonic()+3
        while not marker.exists() and time.monotonic()<deadline:time.sleep(.01)
        assert marker.exists()
        pid=int(next(marker.iterdir()).name)
        assert budget.summary()['pending_operations']==1
        gate.withdraw('local-cancel');gate.wait_closed('local-cancel',timeout=2)
        with pytest.raises(ResearchForbidden):pending.result(timeout=2)
    assert not Path(f'/proc/{pid}').exists()
    state=budget.summary()
    assert state['observed_cpu_ms'] is None and state['held_cpu_ms']==4000 and state['unknown_operations']==1
