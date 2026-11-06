"""Empty remote provisioning with original administrative HTTP ownership and single-write readonly recovery.

No local Git, native task or repository registration exists at this boundary.
Closing a client proves only local closure: the server can finish an issued POST
later. A positive original server marker settles that uncertainty; absence never
authorizes a second POST. The bounded publication transport supplies TLS/JSON
limits, origin-bound credentials, no redirects, no proxies and no HTTP retries.
"""

import asyncio
import hashlib
import os
from dataclasses import asdict
from uuid import uuid4

from backend.git.source_operations import SourceLease, SourceRequest
from backend.knowledge.reviews import canonical
from backend.runtime.contracts import RunConflict
from backend.runtime.forgejo_publication import ForgejoPublicationClient
from backend.runtime.owned_runtime import _settled
from backend.runtime.peer_process import boot_id, observer_namespace, start_ticks
from backend.runtime.remote_publication import RemoteRepository


class RemoteSourceRecords:
    """Reuse bounded source metadata transactions while keeping HTTP clients and issued remote effects separate from Git process grants."""

    def __init__(self, records):
        """Bind the actual source store without creating clients, namespaces or local directories."""
        self.records = records

    @staticmethod
    def _host():
        """Identify this actual host process in its original visible kernel/PID namespace."""
        return {'pid': os.getpid(), 'start_ticks': start_ticks(os.getpid()), 'boot_id': boot_id(), 'observer_namespace': observer_namespace()}

    def _original(self, conn, lease):
        """Require the original HTTP attempt and database even after its owner admission has been withdrawn."""
        metadata, row = self.records._row(conn, lease.project_id, lease.operation_key)
        if row['request']['mode'] != 'create_remote' or (row['attempt_id'], row['fence'], row['owner']['owner_id'], row['database_identity']) != (lease.attempt_id, lease.fence, lease.owner_id, lease.database_identity) or self.records._origin() != lease.database_identity:
            raise RunConflict('El cliente HTTP original cambió; no se eligió otro.')
        return metadata, row

    def _closed(self, row):
        """Prove exact local closure or same-host original process death; neither proves that a remote request stopped."""
        client = row.get('http_client')
        if not client or (client['attempt_id'], client['fence'], client['database_identity']) != (row['attempt_id'], row['fence'], self.records._origin()):
            raise RunConflict('Falta la identidad del cliente HTTP original.')
        if client['state'] == 'closed':
            return
        host = self._host()
        if any(client[k] != host[k] for k in ('boot_id', 'observer_namespace')):
            raise RunConflict('Cambió la visibilidad del host HTTP original.')
        try:
            alive = start_ticks(client['pid']) == client['start_ticks']
        except (FileNotFoundError, ProcessLookupError):
            alive = False
        if alive:
            raise RunConflict('El cliente HTTP original aún no tiene cierre confirmado.')

    def begin(self, project, key, *, observe):
        """Allocate one real HTTP attempt; a fresh observer requires original local closure and never inherits permission to POST."""
        owner = uuid4().hex
        with self.records.runs._transaction(write=True) as conn:
            if not observe:
                lease = self.records._claim(conn, project, key, owner)
            else:
                metadata, row = self.records._row(conn, project, key)
                if row['request']['mode'] != 'create_remote' or row['status'] not in ('running', 'cancelling', 'needs_reconciliation'):
                    raise RunConflict('Esta operación no admite otra observación remota.')
                self._closed(row)
                history = row.setdefault('http_history', [])
                if len(history) >= 8:
                    raise RunConflict('Se alcanzó el límite de observaciones HTTP conservadas.')
                history.append(row['http_client'])
                row.update(status='running', attempt_id=uuid4().hex, fence=row['fence']+1, owner={'owner_id':owner, **self._host()}, observation_only=True, stop_requested=False, issue=None)
                self.records._save(conn, project, metadata)
                lease = SourceLease(project, key, row['attempt_id'], owner, row['fence'], row['database_identity'])
            metadata, row = self.records._owned(conn, lease)
            row['http_client'] = {'attempt_id':lease.attempt_id, 'fence':lease.fence, 'database_identity':lease.database_identity, 'state':'open', **self._host()}
            self.records._save(conn, project, metadata)
        return lease

    def current(self, lease):
        """Check original admission before each HTTP request without granting writes to a readonly observation."""
        with self.records.runs._transaction() as conn:
            return self.records._owned(conn, lease)[1]

    def freeze(self, lease, namespace):
        """Freeze authenticated numeric namespace, explicit visibility and observed name absence before the sole possible creation."""
        with self.records.runs._transaction(write=True) as conn:
            metadata, row = self.records._owned(conn, lease)
            if row.get('observation_only') or row.get('remote_effect'):
                raise RunConflict('El efecto remoto ya tiene identidad; sólo puede observarse.')
            request = SourceRequest(**row['request'])
            marker = 'researcher-source:' + hashlib.sha256(canonical({'operation_id':row['operation_id'], 'request':asdict(request), 'transport':row['remote_identity'], 'namespace':namespace}).encode()).hexdigest()
            endpoint = '/user/repos' if namespace['kind'] == 'user' else '/orgs/'+request.remote_owner+'/repos'
            effect = {'namespace':namespace, 'url':request.remote_server+endpoint, 'payload':{'name':request.name, 'private':request.private, 'auto_init':False, 'description':marker}, 'observed_absent_at':self.records.runs.clock(), 'issued':False}
            row['remote_effect'] = effect
            self.records._save(conn, lease.project_id, metadata)
            return effect

    def issue(self, lease, method, url, payload):
        """Durably issue exactly the original POST before sending bytes; an ambiguous response cannot reset this one-way boundary."""
        with self.records.runs._transaction(write=True) as conn:
            metadata, row = self.records._owned(conn, lease)
            effect = row.get('remote_effect')
            if row.get('observation_only') or not effect or effect['issued'] or method != 'POST' or url != effect['url'] or payload != effect['payload']:
                raise RunConflict('La escritura HTTP no corresponde al único efecto original.')
            effect.update(issued=True, issued_attempt_id=lease.attempt_id, issued_at=self.records.runs.clock())
            self.records._save(conn, lease.project_id, metadata)

    def close(self, lease):
        """Record actual controller closure only for its own original local client, even after Stop withdrew admission."""
        with self.records.runs._transaction(write=True) as conn:
            metadata, row = self._original(conn, lease)
            client = row['http_client']
            if any(client[k] != v for k,v in self._host().items()):
                raise RunConflict('Otro proceso no puede cerrar un cliente HTTP vivo por declaración.')
            client.update(state='closed', closed_at=self.records.runs.clock())
            self.records._save(conn, lease.project_id, metadata)

    def finish(self, lease, remote):
        """Record positive original remote evidence after local closure, preserving uncertainty for missing or foreign results and avoiding a fabricated local registration."""
        with self.records.runs._transaction(write=True) as conn:
            metadata, row = self._original(conn, lease)
            self._closed(row)
            issued = (row.get('remote_effect') or {}).get('issued')
            if remote is not None and issued:
                receipt = {'project_id':lease.project_id, 'operation_key':lease.operation_key, 'operation_id':row['operation_id'], 'remote':remote, 'observed_at':self.records.runs.clock(), 'http_client_closed':True, 'completed_after_withdrawal':bool(row.get('remote_withdrawn'))}
                row.update(status='completed', receipt=receipt, issue=None)
            elif issued:
                row.update(status='needs_reconciliation', issue={'code':'remote_creation_unconfirmed', 'message':'El servidor puede haber recibido la creación. Detener cerró sólo nuestro cliente; observar consulta el resultado original sin volver a crearlo.'})
            else:
                row.update(status='stopped' if row.get('stop_requested') else 'rejected', issue={'code':'remote_creation_not_issued', 'message':'La creación no se envió. Revisa servidor, cuenta, permisos y si el nombre ya existe antes de elegir otra solicitud.'})
            self.records._save(conn, lease.project_id, metadata)


class SourceRemoteClient(ForgejoPublicationClient):
    """Fixed Forgejo namespace and empty-repository operations over the existing bounded, origin-bound transport."""

    async def namespace(self, username, owner):
        """Resolve selected user or organization by server evidence, never by an org-to-user fallback after an error."""
        user = await self._request('GET', self.api_base+'/user')
        if not isinstance(user,dict) or user.get('login') != username or type(user.get('id')) is not int or user['id'] <= 0:
            raise RunConflict('La cuenta autenticada no coincide con la configuración elegida.')
        if owner == username:
            return {'kind':'user', 'id':user['id'], 'name':owner}
        org = await self._request('GET', self.api_base+'/orgs/'+owner)
        if not isinstance(org,dict) or org.get('name') != owner or type(org.get('id')) is not int or org['id'] <= 0:
            raise RunConflict('La organización elegida no tiene una identidad confirmada.')
        return {'kind':'organization', 'id':org['id'], 'name':owner}

    async def repository(self, request):
        """Read exactly the selected canonical name; only HTTP 404 means absence and no read error grants a POST."""
        return await self._request('GET', self.api_base+'/repos/'+request.remote_owner+'/'+request.name, missing=True)

    @staticmethod
    def matched(request, effect, record):
        """Accept only complete positive server evidence of the issued original marker, namespace, visibility and canonical clone origin."""
        if not effect or not effect.get('issued') or not isinstance(record, dict):
            return None
        owner = record.get('owner')
        if not isinstance(owner,dict) or type(owner.get('id')) is not int or owner['id'] != effect['namespace']['id'] or record.get('full_name') != request.remote_owner+'/'+request.name or type(record.get('private')) is not bool or record['private'] != request.private or record.get('description') != effect['payload']['description']:
            return None
        try:
            remote = RemoteRepository(request.remote_server, record['id'], record['full_name'], record['clone_url'])
        except (KeyError, ValueError, TypeError):
            return None
        return {'id':remote.repository_id, 'full_name':remote.full_name, 'clone_url':remote.clone_url, 'api_base':remote.api_base, 'private':record['private'], 'namespace':effect['namespace'], 'marker':effect['payload']['description']}


class SourceHTTPControl:
    """Own the real original HTTP client and immediate local withdrawal, independently of SQLite completion or a nonexistent Git domain."""

    def __init__(self, lease, operation_id):
        """Capture immutable original lease identity before any network request; attach only this controller's real transport."""
        self.lease, self.operation_id = lease, operation_id
        self.owner = self
        self.client = None
        self.withdrawn = False
        self._closing = None

    def withdraw(self):
        """Synchronously deny later requests and start closing actual local sockets before Stop waits on metadata."""
        self.withdrawn = True
        if self._closing is None and self.client is not None:
            self._closing = asyncio.create_task(self.client._client.aclose())
        return self._closing

    async def close(self):
        """Drain the original local transport once; server-side work is deliberately outside this closure claim."""
        self.withdraw()
        if self._closing is not None:
            await asyncio.shield(self._closing)


async def execute_remote_source(records, project, key, transport, *, observe=False, on_owner=None):
    """Create at most once or observe only, under original source lease and actual HTTP lifetime, retaining issued-write uncertainty after every interruption."""
    row = await _settled(records.read, project, key)
    request = SourceRequest(**row['request'])
    if transport is None or transport.identity != row['remote_identity'] or transport.api_base != request.remote_server:
        raise RunConflict('El servidor o la configuración remota original cambió; no se envió otra creación.')
    remote_records = RemoteSourceRecords(records)
    lease, control, observed = None, None, None
    handoff = asyncio.create_task(asyncio.to_thread(remote_records.begin, project, key, observe=observe))
    try:
        try:
            lease = await asyncio.shield(handoff)
        except asyncio.CancelledError:
            lease = await handoff
            raise
        control = SourceHTTPControl(lease, row['operation_id'])
        async def before_request():
            """Recheck original admission, then the synchronous local Stop fuse immediately before sending any request."""
            await _settled(remote_records.current, lease)
            if control.withdrawn:
                raise asyncio.CancelledError

        async def before_write(method, url, payload):
            """Persist exact write issuance and refuse late Stop before transport release; this boundary can never authorize replay."""
            await _settled(remote_records.issue, lease, method, url, payload)
            if control.withdrawn:
                raise asyncio.CancelledError

        control.client = SourceRemoteClient(transport.api_base, transport.token(), verify=transport.ssl_context(), before_request=before_request, before_write=before_write)
        if on_owner:
            on_owner(control)
        if observe:
            effect = row.get('remote_effect')
            record = await control.client.repository(request)
            observed = control.client.matched(request, effect, record)
        else:
            namespace = await control.client.namespace(transport.username, request.remote_owner)
            if await control.client.repository(request) is not None:
                raise RunConflict('El nombre remoto ya existe y no demuestra una creación original nuestra.')
            effect = await _settled(remote_records.freeze, lease, namespace)
            record = await control.client._request('POST', effect['url'], payload=effect['payload'])
            effect['issued'] = True
            observed = control.client.matched(request, effect, record)
    finally:
        if lease is not None:
            if control is not None:
                await control.close()
            await _settled(remote_records.close, lease)
            await _settled(remote_records.finish, lease, observed)
