import assert from 'node:assert/strict'
import { test } from 'node:test'

test('prior code selection is copied into the original instruction and cannot drift after a lost response', async () => {
  const { prepareInstruction, sendInstruction } = await import('../src/api/runtime.ts')
  const selection = {attempt_id:'previous-attempt',snapshot_sha256:'a'.repeat(64)}
  const intent = prepareInstruction(101,{task_id:1001,context_version:3,thread_id:'reuse',message:'Adapt the earlier change.',repository_id:11,prior_code:selection})
  selection.snapshot_sha256='b'.repeat(64)
  const sent:unknown[]=[]
  const original=globalThis.fetch
  try {
    globalThis.fetch=async (_url,options)=>{sent.push(JSON.parse(String(options?.body)));if(sent.length===1)throw new TypeError('Lost response');return Response.json({})}
    await assert.rejects(sendInstruction(intent));await sendInstruction(intent)
    assert.deepEqual(sent[0],sent[1])
    assert.deepEqual((sent[1] as {prior_code:unknown}).prior_code,{attempt_id:'previous-attempt',snapshot_sha256:'a'.repeat(64)})
    assert.equal(Object.isFrozen(intent.body.prior_code),true)
    assert.throws(()=>prepareInstruction(101,{task_id:1001,context_version:3,thread_id:'reuse',message:'Adapt',prior_code:{attempt_id:'previous-attempt',snapshot_sha256:'guessed'}}))
  } finally {globalThis.fetch=original}
})

test('prior code inspection keeps exact task scope and decodes a binary patch without inventing text', async () => {
  const {priorCodeInput,priorPatchText}=await import('../src/api/runtime.ts')
  const original=globalThis.fetch;const requests:string[]=[]
  try {
    globalThis.fetch=async url=>{requests.push(String(url));return Response.json({})}
    await priorCodeInput(101,1001,'attempt:a')
    assert.deepEqual(requests,['/api/projects/101/tasks/1001/prior-code/attempt%3Aa'])
    assert.equal(priorPatchText('ZGlmZiBmaXh0dXJlCg=='),'diff fixture\n')
    assert.equal(priorPatchText('/w=='),null)
  } finally {globalThis.fetch=original}
})

test('owner command readers preserve run scope and byte offsets using GET only', async () => {
  const { commandList, commandOutput } = await import('../src/api/runtime.ts')
  const sent: { url: string; method: string; body: unknown; credentials: RequestCredentials | undefined }[] = []
  const original = globalThis.fetch
  try {
    globalThis.fetch = async (url, options) => {
      sent.push({url:String(url),method:options?.method ?? 'GET',body:options?.body,credentials:options?.credentials})
      return Response.json({items:[],total:0,next_after_seq:null})
    }
    await commandList(101, 'run:a', '9007199254740993')
    await commandOutput(101, 'run:a', 'job/b', {stdoutOffset:8192,stderrOffset:4,maxBytes:2})
    assert.equal(sent[0].url, '/api/projects/101/runs/run%3Aa/jobs?after_seq=9007199254740993&limit=25')
    assert.equal(sent[1].url, '/api/projects/101/runs/run%3Aa/jobs/job%2Fb?stdout_offset=8192&stderr_offset=4&max_bytes=2')
    assert.deepEqual(sent.map(request => [request.method,request.body,request.credentials]), [['GET',undefined,'same-origin'],['GET',undefined,'same-origin']])
  } finally { globalThis.fetch = original }
})

test('queued-start retry preserves its original run, fence and context after a lost response', async () => {
  const { prepareStartRetry, sendStartRetry } = await import('../src/api/runtime.ts')
  const sent: {url: string; body: Record<string, unknown>}[] = []
  globalThis.fetch = async (url, options) => {
    sent.push({url: String(url), body: JSON.parse(String(options?.body))})
    if (sent.length === 1) throw new TypeError('Receipt lost')
    return Response.json({run_id: 'original-run', status: 'queued'})
  }
  const intent = prepareStartRetry(101, 1001, 'original-run', 0, 1)
  await assert.rejects(sendStartRetry(intent), /Receipt lost/)
  await sendStartRetry(intent)
  assert.deepEqual(sent[0], sent[1])
  assert.equal(sent[0].url, '/api/projects/101/runs/original-run/retry-start')
  assert.equal(sent[0].body.expected_fence, 0)
  assert.equal(sent[0].body.context_version, 1)
  assert.equal('repository_id' in sent[0].body, false)
  assert.equal('request' in sent[0].body, false)
  assert.equal(Object.isFrozen(intent.body), true)
})

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

test('answer retries retain the question, original context and literal answers without starting work', async () => {
  const { prepareAnswer, sendAnswer, presentRun } = await import('../src/api/runtime.ts')
  const sent: { url: string; body: Record<string, unknown> }[] = []
  globalThis.fetch = async (url, options) => {
    sent.push({ url: String(url), body: JSON.parse(String(options?.body)) })
    if (sent.length === 1) throw new TypeError('Lost answer receipt')
    return Response.json({ context_version: 3, application: 'recorded_for_next_run', inference_started: false })
  }
  const answers = { base: '200' }
  const intent = prepareAnswer(101, 1001, 7, 2, answers)
  answers.base = '100'
  await assert.rejects(sendAnswer(intent), /Lost answer receipt/)
  assert.equal((await sendAnswer(intent)).inference_started, false)
  assert.equal(sent[0].url, '/api/projects/101/tasks/1001/questions/7/answers')
  assert.deepEqual(sent[0], sent[1])
  assert.deepEqual(sent[1].body.answers, { base: '200' })
  assert.equal(sent[1].body.expected_version, 2)
  assert.equal(Object.isFrozen(intent.body.answers), true)
  assert.equal(presentRun('waiting_input').canStart, false)
  assert.match(presentRun('waiting_input').title, /respuesta/)
})

test('recovery retries keep the original attempt and fence without replaying a prompt', async () => {
  const { prepareRecovery, sendRecovery } = await import('../src/api/runtime.ts')
  const sent: { url: string; body: Record<string, unknown> }[] = []
  globalThis.fetch = async (url, options) => {
    sent.push({ url: String(url), body: JSON.parse(String(options?.body)) })
    if (sent.length === 1) throw new TypeError('Recovery receipt lost')
    return Response.json({ status: 'failed', local_execution_closed: true, inference_started: false, task_accepted: false })
  }
  const intent = prepareRecovery(101, 1001, 'run-original', 'attempt-original', 4)
  await assert.rejects(sendRecovery(intent), /receipt lost/)
  assert.equal((await sendRecovery(intent)).inference_started, false)
  assert.deepEqual(sent[0], sent[1])
  assert.equal(sent[1].url, '/api/projects/101/runs/run-original/recovery')
  assert.equal(sent[1].body.expected_fence, 4)
  assert.equal(sent[1].body.attempt_id, 'attempt-original')
  assert.equal('request' in sent[1].body, false)
})
