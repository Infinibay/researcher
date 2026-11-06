"""History reuse must reduce repeated parsing without trusting file metadata or stale enrollment."""

import os

import pytest

from backend.tests.runtime.authority_fixture import journal, provisioned


def test_verified_history_parses_each_appended_prepare_once(tmp_path, monkeypatch):
    """Repeated reads and commits reuse only byte-identical prefixes, including an append from a second journal handle."""
    c = provisioned(tmp_path)
    with journal(c) as owner:
        parsed = []
        prepare = owner._prepare

        def observed(payload, commit):
            """Count actual semantic validations instead of asserting a machine-specific time threshold."""
            parsed.append(payload['transition_id'])
            return prepare(payload, commit)

        monkeypatch.setattr(owner, '_prepare', observed)
        for index in range(6):
            owner.commit(owner.load(), transition_id=f'edit-{index}', puts={'measure': index})
            assert owner.load().records == {'measure': index}
        for _ in range(5):
            assert owner.load().records == {'measure': 5}
        assert parsed == [f'edit-{index}' for index in range(6)]
        with journal(c) as other:
            other.commit(other.load(), transition_id='external-edit', puts={'measure': 6})
        assert owner.load().records == {'measure': 6}
        assert parsed[-1] == 'external-edit' and len(parsed) == 7


def test_same_length_witness_tampering_is_detected_after_reuse(tmp_path):
    """Restoring timestamps cannot let changed bytes borrow validation from an earlier read."""
    from backend.runtime.authority_journal import AuthorityUncertain

    c = provisioned(tmp_path)
    with journal(c) as owner:
        owner.commit(owner.load(), transition_id='original', puts={'measure': 1})
        assert owner.load().records == {'measure': 1}
        before = c.witness.stat()
        original = c.witness.read_bytes()
        changed = original.replace(b'"measure":1', b'"measure":2')
        assert changed != original and len(changed) == len(original)
        c.witness.write_bytes(changed)
        os.utime(c.witness, ns=(before.st_atime_ns, before.st_mtime_ns))
        with pytest.raises(AuthorityUncertain, match='corrupt|inconsistent'):
            owner.load()
        assert c.witness.read_bytes() == changed


def test_reused_history_still_checks_live_observer_enrollment(tmp_path, monkeypatch):
    """An unchanged prefix cannot authorize the same handle after its observer namespace changes."""
    from backend.runtime import authority_journal

    c = provisioned(tmp_path)
    with journal(c) as owner:
        owner.load()
        previous = authority_journal.observer_namespace()
        monkeypatch.setattr(authority_journal, 'observer_namespace', lambda: previous + 1)
        with pytest.raises(authority_journal.AuthorityUncertain, match='enrollment'):
            owner.load()


def test_large_history_uses_bounded_streaming_validation(tmp_path, monkeypatch):
    """The optional reuse buffer has a separate bound and does not change the durable journal capacity."""
    from backend.runtime import authority_journal

    monkeypatch.setattr(authority_journal, 'MAX_HISTORY_CACHE_BYTES', 32)
    c = provisioned(tmp_path)
    with journal(c) as owner:
        owner.commit(owner.load(), transition_id='streamed', puts={'measure': 1})
        assert owner.load().records == {'measure': 1}
        assert owner._history_cache is None
