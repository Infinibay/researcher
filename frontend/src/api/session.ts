/** Owner pairing and endpoint-bound browser intent; credentials never enter browser storage. @module */
type SessionStatus = { authenticated: boolean; csrf_token?: string; endpoint_id?: string }
type EndpointChange = {previous:string|null; current:string}
const endpointKey = 'researcher:owner-endpoint:v1'
const archivePrefix = 'researcher:archived-owner-state:v1:'
const listeners = new Set<(ready: boolean) => void>()
let csrfToken: string | null = null
let endpointId: string | null = null
let endpointChange: EndpointChange | null = null
let generation = 0

/** Collect product packets exactly as stored, excluding endpoint metadata and prior archives. */
function pendingEntries() {
  const entries:Record<string,string> = {}
  for (let i=0;i<sessionStorage.length;i++) {
    const key = sessionStorage.key(i)
    if (key?.startsWith('researcher:') && key !== endpointKey && !key.startsWith(archivePrefix)) {
      const value = sessionStorage.getItem(key)
      if (value !== null) entries[key] = value
    }
  }
  return entries
}

/** Expose a correction step without silently assigning previous decisions to a different database. */
export function ownerEndpointChange() { return endpointChange ? {...endpointChange} : null }

/** Produce an inspectable local archive; this does not authorize the new installation. */
export function ownerEndpointArchive(additional:unknown = null) {
  if (!endpointChange || !csrfToken) throw new Error('No hay un cambio de instalación pendiente.')
  return {format:1,...endpointChange,entries:pendingEntries(),additional}
}

/** Archive first, remove only archived active packets, then bind fresh requests after an explicit owner choice. */
export function acceptOwnerEndpointChange(additional:unknown = null) {
  const archive = ownerEndpointArchive(additional)
  const key = archivePrefix + crypto.randomUUID()
  const raw = JSON.stringify(archive)
  sessionStorage.setItem(key,raw)
  if (sessionStorage.getItem(key) !== raw) throw new Error('No se pudo conservar el archivo anterior; la instalación sigue bloqueada.')
  for (const [name,value] of Object.entries(archive.entries)) {
    if (sessionStorage.getItem(name) !== value) throw new Error('Las solicitudes cambiaron; revisa el archivo antes de continuar.')
  }
  for (const name of Object.keys(archive.entries)) sessionStorage.removeItem(name)
  sessionStorage.setItem(endpointKey,archive.current)
  endpointChange = null
  generation++
  listeners.forEach(listener => listener(true))
  return key
}

/** Pair transient credentials with a persisted database identity, retaining prior packets on change. */
function applySession(status: SessionStatus) {
  generation++
  csrfToken = null
  endpointId = null
  endpointChange = null
  if (status.authenticated && status.csrf_token) {
    if (!status.endpoint_id) throw new Error('El servidor no identificó la instalación. Actualiza el servidor antes de continuar.')
    const previous = sessionStorage.getItem(endpointKey)
    endpointId = status.endpoint_id
    if (previous !== endpointId && (previous !== null || Object.keys(pendingEntries()).length > 0)) {
      endpointChange = {previous,current:endpointId}
    } else sessionStorage.setItem(endpointKey,endpointId)
    csrfToken = status.csrf_token
  }
  listeners.forEach((listener) => listener(csrfToken != null && endpointChange === null))
}

/** Subscribe to readiness; endpoint changes keep protected content unmounted until corrected. */
export function subscribeOwnerSession(listener: (ready: boolean) => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

/** Retire transient proof while preserving original endpoint identity and pending owner decisions. */
export function invalidateOwnerSession() {
  applySession({authenticated: false})
}

/** Attach current session and bound endpoint proofs only to local requests; never send stale mutations. */
export async function ownerFetch(path: string, options: RequestInit = {}) {
  if (!path.startsWith('/') || path.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(path)) {
    throw new Error('Owner requests require a path on this server')
  }
  const revision = generation
  const headers = new Headers(options.headers)
  const method = (options.method ?? 'GET').toUpperCase()
  if (endpointChange && path !== '/api/session') throw new Error('La instalación cambió. Conserva y revisa las solicitudes anteriores antes de continuar.')
  if (endpointId && path !== '/api/session') headers.set('X-Researcher-Endpoint',endpointId)
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) {
    headers.set('X-Researcher-CSRF', csrfToken)
  }
  const response = await fetch(path, {...options, headers, credentials: 'same-origin', redirect: 'error'})
  if (response.status === 401 && revision === generation) invalidateOwnerSession()
  if (response.status === 409 && revision === generation) {
    const issue = await response.clone().json().catch(() => null)
    if (issue?.code === 'owner_endpoint_changed') invalidateOwnerSession()
  }
  return response
}

/** Apply only a successful authenticated response with an explicit installation identity. */
async function readStatus(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? 'No se pudo abrir la sesión local.')
  }
  const status: SessionStatus = await response.json()
  applySession(status)
  return status.authenticated && endpointChange === null
}

/** Restore session proof without letting an older response override newer pairing state. */
export async function loadOwnerSession() {
  const revision = generation
  const response = await ownerFetch('/api/session', {cache:'no-store'})
  if (revision !== generation) return csrfToken != null && endpointChange === null
  return readStatus(response)
}

/** Exchange the owner code locally; a different database still requires separate intent archival. */
export async function pairOwner(code: string) {
  return readStatus(await ownerFetch('/api/session', {
    method:'POST',
    headers: {'Content-Type':'application/json', 'X-Researcher-Client':'web'},
    body:JSON.stringify({code}),
  }))
}

/** Close transient owner access without discarding pending decisions or their endpoint binding. */
export async function closeOwnerSession() {
  const response = await ownerFetch('/api/session', {method:'DELETE'})
  if (!response.ok && response.status !== 401) throw new Error('No se pudo cerrar la sesión. Inténtalo de nuevo.')
  invalidateOwnerSession()
}
