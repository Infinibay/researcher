"""Verify deterministic synthetic author provenance without any model or copied authority."""

import sqlite3


def test_controlled_finding_author_produces_identical_subjects_in_fresh_databases(coordination, tmp_path):
    """Actual writer operations must seal the same claim/source/report while grants close and no inference is reserved."""
    from evals.profile_communication.finding_review import seed_author

    subjects = []
    for name in ['baseline', 'candidate']:
        path = tmp_path / (name + '.db')
        with sqlite3.connect(path) as destination:
            coordination.conn.backup(destination)
        result = seed_author(path)
        assert result['controlled_author_model_turns'] == 0
        assert result['subject']['reviewable'] is True
        assert result['subject']['snapshot']['author']['actor_id'] == 'controlled-author'
        assert result['subject']['snapshot']['finding']['content'] == result['claim']
        subjects.append(result['subject'])
        with sqlite3.connect(path) as db:
            assert db.execute('SELECT COUNT(*) FROM runtime_inference_dispatches').fetchone()[0] == 0
            assert db.execute('SELECT COUNT(*) FROM tool_grants WHERE revoked_at IS NULL').fetchone()[0] == 0
    assert subjects[0] == subjects[1]
