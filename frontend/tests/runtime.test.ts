import assert from 'node:assert/strict'
import { test } from 'node:test'

test('an ambiguous instruction retry keeps its original identity, scope and context', async () => {
  const { prepareInstruction, sendInstruction } = await import('../src/api/runtime.ts')
  const sent: { url: string; body: Record<string, unknown> }[] = []
  globalThis.fetch = async (url, options) => {
    sent.push({ url: String(url), body: JSON.parse(String(options?.body)) })
    if (sent.length === 1) throw new TypeError('Connection lost after sending')
    return Response.json({ run: { run_id: 'one-run' }, message: { id: 1 } })
  }
  const intent = prepareInstruction(101, { task_id: 1001, context_version: 2, thread_id: 'thread-a', message: 'Compare the source.' })
  await assert.rejects(sendInstruction(intent), /Connection lost/)
  assert.equal((await sendInstruction(intent)).run.run_id, 'one-run')
  assert.equal(sent[0].url, '/api/chat/101/instructions')
  assert.equal(sent[0].body.operation_key, sent[1].body.operation_key)
  assert.equal(sent[1].body.context_version, 2)
  assert.equal(sent[1].body.task_id, 1001)
  assert.equal(sent[1].body.thread_id, 'thread-a')
  assert.equal(Object.isFrozen(intent.body), true)
})

test('native completion remains a proposal and uncertain work cannot start again', async () => {
  const { presentRun } = await import('../src/api/runtime.ts')
  assert.equal(presentRun('needs_review').canStart, false)
  assert.match(presentRun('needs_review').title, /Propuesta/)
  assert.equal(presentRun('cancelling').canStart, false)
  assert.match(presentRun('cancelling').description, /confirmar/)
  assert.equal(presentRun('reconciling').canStart, false)
  assert.equal(presentRun('unrecognized-new-state').canStart, false)
  assert.equal(presentRun('superseded').canStart, true)
  assert.equal(presentRun(null).canStart, true)
})

test('invalid scope and empty instructions never reach transport', async () => {
  const { prepareInstruction } = await import('../src/api/runtime.ts')
  assert.throws(() => prepareInstruction(101, { task_id: 1001, context_version: 1, thread_id: 'thread-a', message: '   ' }))
  assert.throws(() => prepareInstruction(0, { task_id: 1001, context_version: 1, thread_id: 'thread-a', message: 'Explain' }))
})
