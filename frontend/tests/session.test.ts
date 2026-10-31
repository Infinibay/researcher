import assert from 'node:assert/strict'
import { test } from 'node:test'

test('owner transport keeps CSRF in memory and sends it only to this server', async () => {
  const { pairOwner, ownerFetch, invalidateOwnerSession } = await import('../src/api/session.ts')
  const requests: {path: string, options: RequestInit}[] = []
  globalThis.fetch = async (path, options = {}) => {
    requests.push({path: String(path), options})
    return Response.json({authenticated: true, csrf_token: 'fixture-csrf'})
  }
  await pairOwner('fixture-owner-code')
  assert.equal(requests[0].path, '/api/session')
  assert.equal(requests[0].options.body, JSON.stringify({code:'fixture-owner-code'}))
  assert.equal(new Headers(requests[0].options.headers).get('X-Researcher-Client'), 'web')
  await ownerFetch('/api/projects', {method:'POST', body:'{}'})
  assert.equal(new Headers(requests[1].options.headers).get('X-Researcher-CSRF'), 'fixture-csrf')
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
  globalThis.fetch = async () => Response.json({authenticated: true, csrf_token:'first'})
  await pairOwner('first-code')
  let settle!: (response:Response) => void
  globalThis.fetch = () => new Promise(resolve => {settle = resolve})
  const stale = ownerFetch('/api/projects')
  globalThis.fetch = async () => Response.json({authenticated:true, csrf_token:'second'})
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
