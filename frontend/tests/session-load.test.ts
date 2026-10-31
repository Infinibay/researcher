import assert from 'node:assert/strict'
import { test } from 'node:test'

test('a delayed initial status response cannot lock a session paired afterwards', async () => {
  const { loadOwnerSession, pairOwner, ownerFetch } = await import('../src/api/session.ts')
  let settle!: (response:Response) => void
  globalThis.fetch = () => new Promise(resolve => {settle = resolve})
  const loading = loadOwnerSession()
  globalThis.fetch = async () => Response.json({authenticated:true, csrf_token:'new-session'})
  await pairOwner('new-owner-code')
  settle(Response.json({authenticated:false}))
  assert.equal(await loading, true)
  let proof: string|null = null
  globalThis.fetch = async (_, options) => {proof = new Headers(options?.headers).get('X-Researcher-CSRF'); return new Response('')}
  await ownerFetch('/api/projects', {method:'POST'})
  assert.equal(proof, 'new-session')
})
