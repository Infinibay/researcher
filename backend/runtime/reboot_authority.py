"""Archive verified prior-kernel authority without granting, repairing or replaying its work.

Normal runtime enrollment stays strict. This explicit recovery reader accepts only
a different boot, preserves pending/torn evidence and exposes no mutation API.
"""

from contextlib import contextmanager
from uuid import UUID

from backend.runtime.authority_journal import AuthorityUncertain, WitnessedAuthorityJournal, _apply, _hash
from backend.runtime.peer_process import boot_id, observer_namespace


def validate_reboot_evidence(value):
    """Validate portable historical observations without interpreting them as current execution authority."""
    fields = {'source_boot_id','observed_boot_id','source_observer_namespace','observed_observer_namespace','history','torn_tail'}
    if not isinstance(value,dict) or set(value) != fields:
        raise ValueError('Invalid prior-kernel evidence fields')
    for key in ('source_boot_id','observed_boot_id'):
        if not isinstance(value[key],str) or str(UUID(value[key])) != value[key]:
            raise ValueError('Invalid prior-kernel boot identity')
    if value['source_boot_id'] == value['observed_boot_id']:
        raise ValueError('Reboot evidence must identify a different kernel')
    if any(type(value[key]) is not int or value[key] <= 0 for key in ('source_observer_namespace','observed_observer_namespace')):
        raise ValueError('Invalid prior-kernel observer identity')
    if type(value['torn_tail']) is not bool or value['history'] not in {'committed','prepared_before_database','prepared_after_database'}:
        raise ValueError('Invalid prior-kernel history disposition')
    return dict(value)


def unarchived_peers(db):
    """Read current registrations separately from previously archived copies, including version56 sources."""
    archived = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='runtime_peer_archives'").fetchone()
    exclusion = ' AND NOT EXISTS(SELECT 1 FROM runtime_peer_archives h WHERE h.peer_id=p.id)' if archived else ''
    return db.execute("SELECT p.id,p.boot_id,p.observer_namespace,p.state,p.database_identity FROM runtime_peers p WHERE p.state!='closed'"+exclusion).fetchall()


def prior_kernel_peers(db,evidence):
    """Identify prior-kernel registrations for archival; a different kernel is not global proof of death."""
    verified = validate_reboot_evidence(evidence)
    peers = unarchived_peers(db)
    if any((row[1],row[2]) != (verified['source_boot_id'],verified['source_observer_namespace']) for row in peers):
        raise ValueError('Unclosed peer belongs to another kernel or observer; original recovery evidence is insufficient')
    return [row[0] for row in peers]


def archive_prior_peers(db,peers,*,database,snapshot_id,archived_at):
    """Preserve copied identities and their original states without fabricating native closure receipts."""
    from backend.runtime.peer_registry import PeerRegistry
    from backend.runtime.sqlite_runs import SQLiteRunStore

    current = PeerRegistry(SQLiteRunStore(database))._database_identity()
    for identity in peers:
        row = db.execute('SELECT state,boot_id,observer_namespace,database_identity FROM runtime_peers WHERE id=?',(identity,)).fetchone()
        if row['database_identity'] == current:
            raise ValueError('An original current-database peer cannot be archived as a restored copy')
        db.execute('INSERT INTO runtime_peer_archives VALUES(?,?,?,?,?,?,?)',
                   (identity,snapshot_id,row['state'],row['boot_id'],row['observer_namespace'],row['database_identity'],archived_at))


class _RebootArchive(WitnessedAuthorityJournal):
    """Reuse file/chain/state validation only; neither normal loads nor writes are exposed for old enrollment."""

    def _header(self,payload):
        """Verify original file identities under a different recorded kernel before retaining its provenance."""
        current = boot_id()
        if not isinstance(payload,dict) or payload.get('boot_id') == current:
            raise AuthorityUncertain('Explicit reboot archival requires a different kernel')
        try:
            if str(UUID(payload['boot_id'])) != payload['boot_id'] or str(UUID(current)) != current:
                raise ValueError('Invalid kernel UUID')
        except (ValueError,TypeError,KeyError,AttributeError) as error:
            raise AuthorityUncertain('Invalid prior-kernel enrollment identity') from error
        self._validate_header(payload,expected_boot=payload['boot_id'],expected_observer=payload.get('observer_namespace'))
        self.evidence = {'source_boot_id':payload['boot_id'],'observed_boot_id':current,
                         'source_observer_namespace':payload['observer_namespace'],
                         'observed_observer_namespace':observer_namespace()}

    def load(self):
        """Refuse normal recovery semantics that could repair an old writable authority journal."""
        raise AuthorityUncertain('Prior-kernel authority is archival evidence only')

    def commit(self,*args,**kwargs):
        """Refuse every attempt to mint or mutate old execution authority."""
        raise AuthorityUncertain('Prior-kernel authority cannot authorize new work')

    def _verified(self,conn):
        """Prevent inherited snapshot paths from truncating or applying the historical witness."""
        raise AuthorityUncertain('Use explicit read-only prior-kernel evidence capture')

    @contextmanager
    def frozen_history(self):
        """Hold original locks and attest cross-store agreement without finishing pending journal transitions."""
        failure = None
        with self._operation() as conn:
            conn.execute('BEGIN IMMEDIATE')
            snapshot,transition = self._state(conn)
            history = self._history()
            pending = history.pending
            expected = history.commit if pending is None else pending
            actual = (snapshot.sequence,snapshot.state_hash,transition)
            current = actual == (expected['sequence'],expected['state_hash'],expected['transition_id'])
            previous = pending is not None and actual == (history.commit['sequence'],history.commit['state_hash'],history.commit['transition_id'])
            if not current and not previous:
                raise AuthorityUncertain('Prior-kernel authority restore/rewind or unwitnessed SQL detected')
            if previous and _hash(_apply(snapshot.records,pending['puts'],pending['deletes'])) != pending['state_hash']:
                raise AuthorityUncertain('Prior-kernel prepared delta does not produce its recorded state')
            disposition = 'committed' if pending is None else 'prepared_before_database' if previous else 'prepared_after_database'
            evidence = validate_reboot_evidence({**self.evidence,'history':disposition,'torn_tail':history.torn_tail})
            try:
                yield snapshot,evidence
            except BaseException as error:
                failure = (error,error.__traceback__)
        if failure:
            raise failure[0].with_traceback(failure[1])


@contextmanager
def frozen_reboot_evidence(authority):
    """Expose only a frozen historical snapshot and provenance, never an old authority mutation handle."""
    with _RebootArchive(**authority) as archive, archive.frozen_history() as evidence:
        yield evidence
