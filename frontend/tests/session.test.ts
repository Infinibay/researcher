import assert from 'node:assert/strict'
import { test } from 'node:test'

/** Isolate browser persistence without storing credentials in the fixture. */
class MemoryStorage implements Storage {
  values = new Map<string,string>()
  get length() { return this.values.size }
  clear() { this.values.clear() }
  getItem(key:string) { return this.values.get(key) ?? null }
  key(index:number) { return [...this.values.keys()][index] ?? null }
  removeItem(key:string) { this.values.delete(key) }
  setItem(key:string,value:string) { this.values.set(key,value) }
}
Object.defineProperty(globalThis,'sessionStorage',{value:new MemoryStorage(),configurable:true})

test('owner transport keeps CSRF in memory and sends it only to this server', async () => {
  const { pairOwner, ownerFetch, invalidateOwnerSession } = await import('../src/api/session.ts')
  const requests: {path: string, options: RequestInit}[] = []
  globalThis.fetch = async (path, options = {}) => {
    requests.push({path: String(path), options})
    return Response.json({authenticated: true, csrf_token: 'fixture-csrf',endpoint_id:'endpoint-original'})
  }
  await pairOwner('fixture-owner-code')
  assert.equal(requests[0].path, '/api/session')
  assert.equal(requests[0].options.body, JSON.stringify({code:'fixture-owner-code'}))
  assert.equal(new Headers(requests[0].options.headers).get('X-Researcher-Client'), 'web')
  await ownerFetch('/api/projects', {method:'POST', body:'{}'})
  assert.equal(new Headers(requests[1].options.headers).get('X-Researcher-CSRF'), 'fixture-csrf')
  assert.equal(new Headers(requests[1].options.headers).get('X-Researcher-Endpoint'), 'endpoint-original')
  assert.equal(requests[1].options.credentials, 'same-origin')
  assert.equal(requests[1].options.redirect, 'error')
  for (const path of ['https://hostile.example/api', '//hostile.example/api', '/\\hostile.example/api', '/\t/hostile.example/api']) {
    await assert.rejects(() => ownerFetch(path, {method:'POST'}))
  }
  assert.equal(requests.length, 2, 'No outbound request may carry owner state')
  invalidateOwnerSession()
  await ownerFetch('/api/projects', {method:'POST'})
  assert.equal(new Headers(requests[2].options.headers).get('X-Researcher-CSRF'), null)
})

test('401 retires owner state, but a stale request cannot retire a freshly paired session', async () => {
  const { pairOwner, ownerFetch, subscribeOwnerSession, invalidateOwnerSession } = await import('../src/api/session.ts')
  let retirements = 0
  const unsubscribe = subscribeOwnerSession((ready) => {if (!ready) retirements++})
  globalThis.fetch = async () => Response.json({authenticated: true, csrf_token:'first',endpoint_id:'endpoint-original'})
  await pairOwner('first-code')
  let settle!: (response:Response) => void
  globalThis.fetch = () => new Promise(resolve => {settle = resolve})
  const stale = ownerFetch('/api/projects')
  globalThis.fetch = async () => Response.json({authenticated:true, csrf_token:'second',endpoint_id:'endpoint-original'})
  await pairOwner('second-code')
  settle(new Response('',{status:401}))
  await stale
  assert.equal(retirements, 0)
  globalThis.fetch = async () => new Response('',{status:401})
  await ownerFetch('/api/projects')
  assert.equal(retirements, 1)
  unsubscribe()
  invalidateOwnerSession()
})

test('restored endpoint cannot reuse old pending requests until their original bytes are archived', async () => {
  const api = await import('../src/api/session.ts')
  sessionStorage.setItem('researcher:source-setup:v1:101','{"original":"unchanged"}')
  sessionStorage.setItem('unrelated','keep')
  let requests = 0
  globalThis.fetch = async () => {requests++; return Response.json({authenticated:true,csrf_token:'new',endpoint_id:'endpoint-restored'})}
  await api.pairOwner('new-code')
  assert.equal(api.ownerEndpointChange()?.previous,'endpoint-original')
  await assert.rejects(() => api.ownerFetch('/api/projects',{method:'POST',body:'{}'}),/instalación/)
  assert.equal(requests,1,'old mutation never reaches the restored installation')
  assert.equal(sessionStorage.getItem('researcher:source-setup:v1:101'),'{"original":"unchanged"}')
  const archiveKey = api.acceptOwnerEndpointChange({wikiDrafts:{draft:'retained'}})
  const archive = JSON.parse(sessionStorage.getItem(archiveKey)!)
  assert.equal(archive.entries['researcher:source-setup:v1:101'],'{"original":"unchanged"}')
  assert.equal(archive.previous,'endpoint-original')
  assert.equal(archive.current,'endpoint-restored')
  assert.deepEqual(archive.additional,{wikiDrafts:{draft:'retained'}})
  assert.equal(sessionStorage.getItem('researcher:source-setup:v1:101'),null)
  assert.equal(sessionStorage.getItem('unrelated'),'keep')
  assert.equal(api.ownerEndpointChange(),null)
  await api.ownerFetch('/api/projects',{method:'POST',body:'{}'})
  assert.equal(requests,2)
  api.invalidateOwnerSession()
})

test('archive quota failure preserves old packets and keeps restored mutations blocked', async () => {
  const api = await import('../src/api/session.ts')
  sessionStorage.setItem('researcher:project-plan-start:v1:101','original plan')
  globalThis.fetch = async () => Response.json({authenticated:true,csrf_token:'third',endpoint_id:'endpoint-third'})
  await api.pairOwner('code')
  const storage = sessionStorage
  const set = storage.setItem
  storage.setItem = () => {throw new Error('quota')}
  assert.throws(() => api.acceptOwnerEndpointChange(),/quota/)
  storage.setItem = set
  assert.equal(storage.getItem('researcher:project-plan-start:v1:101'),'original plan')
  await assert.rejects(() => api.ownerFetch('/api/projects',{method:'POST'}),/instalación/)
  api.invalidateOwnerSession()
})

test('legacy pending packets without a stored endpoint require an explicit correction step', async () => {
  const api = await import('../src/api/session.ts')
  sessionStorage.clear()
  sessionStorage.setItem('researcher:result-action:v1:101:1:run','original decision')
  globalThis.fetch = async () => Response.json({authenticated:true,csrf_token:'legacy',endpoint_id:'endpoint-current'})
  await api.pairOwner('code')
  assert.equal(api.ownerEndpointChange()?.previous,null)
  await assert.rejects(() => api.ownerFetch('/api/projects',{method:'POST'}),/instalación/)
  api.acceptOwnerEndpointChange()
  api.invalidateOwnerSession()
})
