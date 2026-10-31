/** Owner credentials live in an HttpOnly cookie; only the CSRF proof is JS state. */
type SessionStatus = { authenticated: boolean; csrf_token?: string }
const listeners = new Set<(ready: boolean) => void>()
let csrfToken: string | null = null
let generation = 0

function applySession(status: SessionStatus) {
  generation++
  csrfToken = status.authenticated && status.csrf_token ? status.csrf_token : null
  listeners.forEach((listener) => listener(csrfToken != null))
}

export function subscribeOwnerSession(listener: (ready: boolean) => void) {
  listeners.add(listener)
  return () => { listeners.delete(listener) }
}

export function invalidateOwnerSession() {
  applySession({authenticated: false})
}

export async function ownerFetch(path: string, options: RequestInit = {}) {
  if (!path.startsWith('/') || path.startsWith('//') || /[\\\u0000-\u0020\u007f]/.test(path)) {
    throw new Error('Owner requests require a path on this server')
  }
  const revision = generation
  const headers = new Headers(options.headers)
  const method = (options.method ?? 'GET').toUpperCase()
  if (!['GET', 'HEAD', 'OPTIONS'].includes(method) && csrfToken) {
    headers.set('X-Researcher-CSRF', csrfToken)
  }
  const response = await fetch(path, {...options, headers, credentials: 'same-origin', redirect: 'error'})
  if (response.status === 401 && revision === generation) invalidateOwnerSession()
  return response
}

async function readStatus(response: Response) {
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail ?? 'No se pudo abrir la sesión local.')
  }
  const status: SessionStatus = await response.json()
  applySession(status)
  return status.authenticated
}

export async function loadOwnerSession() {
  const revision = generation
  const response = await ownerFetch('/api/session', {cache:'no-store'})
  if (revision !== generation) return csrfToken != null
  return readStatus(response)
}

export async function pairOwner(code: string) {
  return readStatus(await ownerFetch('/api/session', {
    method:'POST',
    headers: {'Content-Type':'application/json', 'X-Researcher-Client':'web'},
    body:JSON.stringify({code}),
  }))
}

export async function closeOwnerSession() {
  const response = await ownerFetch('/api/session', {method:'DELETE'})
  if (!response.ok && response.status !== 401) throw new Error('No se pudo cerrar la sesión. Inténtalo de nuevo.')
  invalidateOwnerSession()
}
