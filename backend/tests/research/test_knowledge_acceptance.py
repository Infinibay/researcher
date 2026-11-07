"""Accept real source transactions and immutable captured revisions through owner and agent HTTP boundaries with controlled web acquisition."""

from starlette.testclient import TestClient

from backend.research.models import EvidenceReference, FindingDraft, SourceDraft
from backend.tests.research.test_http import credentials, research_client

__all__ = ['research_client']


def test_failed_capture_cannot_claim_saved_evidence_and_original_retry_can_succeed(
    research_client, research_store, db_conn, monkeypatch,
):
    """A real receipt-transaction failure returns HTTP failure with no source; retrying the same intent after recovery commits exactly one source and receipt."""
    monkeypatch.setattr('backend.research.web_fetcher.PublicWebFetcher.fetch',
                        lambda self, url: SourceDraft('web', url, 'Sample', 'Observed 137 units.'))
    headers = credentials(research_store)
    body = {'operation_key':'original-capture', 'url':'https://example.org/sample'}
    db_conn.execute("CREATE TRIGGER reject_capture_receipt BEFORE INSERT ON tool_operations BEGIN SELECT RAISE(ABORT,'controlled storage failure'); END")
    db_conn.commit()
    with TestClient(research_client.app, base_url='http://localhost', raise_server_exceptions=False) as client:
        failed = client.post('/api/research-tools/sources/web', json=body, headers=headers)
        assert failed.status_code == 500
        assert db_conn.execute('SELECT count(*) FROM research_sources').fetchone()[0] == 0
        assert db_conn.execute('SELECT count(*) FROM tool_operations').fetchone()[0] == 0
        db_conn.execute('DROP TRIGGER reject_capture_receipt')
        db_conn.commit()
        saved = client.post('/api/research-tools/sources/web', json=body, headers=headers)
        assert saved.status_code == 200, saved.text
        repeated = client.post('/api/research-tools/sources/web', json=body, headers=headers)
        assert repeated.status_code == 200 and repeated.json() == saved.json()
        assert db_conn.execute('SELECT count(*) FROM research_sources').fetchone()[0] == 1
        assert db_conn.execute('SELECT count(*) FROM tool_operations').fetchone()[0] == 1


def test_changed_web_page_keeps_old_quote_and_superseded_claim_attributed_to_its_capture(
    research_client, research_store, db_conn, monkeypatch,
):
    """Two versions of one URL retain distinct hashes and exact original quotes; an owner sees the older superseded claim as captured history, not current web evidence."""
    current = ['Observed 137 units.']

    def fetch(self, url):
        """Change only the external document bytes while production HTTP authorization and SQLite persistence stay real."""
        return SourceDraft('web', url, 'Sample', current[0], provenance={'requested_url':url, 'etag':current[0]})

    monkeypatch.setattr('backend.research.web_fetcher.PublicWebFetcher.fetch', fetch)
    headers = credentials(research_store)
    path = '/api/research-tools/sources/web'
    first_body = {'operation_key':'original-capture', 'url':'https://example.org/sample'}
    first = research_client.post(path, json=first_body, headers=headers)
    assert first.status_code == 200, first.text
    old = first.json()
    scope = research_store.authorize(headers['Authorization'].split()[1])
    claim = research_store.record_finding(scope, 'original-claim', FindingDraft('Sample', current[0], (EvidenceReference(old['source_id'], current[0]),)))['finding_id']
    current[0] = 'Observed 200 units.'
    repeated = research_client.post(path, json=first_body, headers=headers)
    assert repeated.json() == old
    fresh = research_client.post(path, json={**first_body, 'operation_key':'new-capture'}, headers=headers)
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()['source_id'] != old['source_id'] and fresh.json()['sha256'] != old['sha256']
    db_conn.execute("UPDATE findings SET status='superseded' WHERE id=?", (claim,))
    db_conn.commit()
    finding = research_client.get(f'/api/findings/{claim}?project_id=101')
    assert finding.status_code == 200 and finding.json()['status'] == 'superseded'
    assert finding.json()['scientific_confidence'] is None
    capture = research_client.get(f"/api/findings/{claim}/sources/{old['source_id']}?project_id=101")
    assert capture.status_code == 200, capture.text
    assert capture.json()['content'] == 'Observed 137 units.' and capture.json()['sha256'] == old['sha256']
    assert capture.json()['captured_at']
    assert research_store.read_source(scope, fresh.json()['source_id'])['content'] == 'Observed 200 units.'
