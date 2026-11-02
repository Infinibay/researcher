/** Independent review requests retain the owner's exact observed candidate across reload and lost responses. @module */
import assert from 'node:assert/strict'
import { test } from 'node:test'

test('review retry restores exact candidate, context, request and operation without starting a second review',async()=>{
  const {prepareCodeReview,codeReviewActions,sendCodeReview}=await import('../src/api/codeReviews.ts')
  const values=new Map<string,string>()
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}
  const action=prepareCodeReview(101,24,'author:a',{attemptId:'attempt:a',contextVersion:3,subjectSha:'a'.repeat(64),request:'Comprueba el ejemplo 100 × 1,2 = 120.'})
  codeReviewActions.save(storage,action)
  assert.equal(codeReviewActions.pendingRun(storage,101,24),'author:a')
  const restored=codeReviewActions.load(storage,101,24,'author:a')!
  assert.deepEqual(restored,action)
  const sent:unknown[]=[]
  const original=globalThis.fetch
  try {
    globalThis.fetch=async(url,options)=>{sent.push([String(url),JSON.parse(String(options?.body))]);if(sent.length===1) throw new TypeError('response lost');return Response.json({project_id:101,task_id:24,operation_key:action.body.operation_key,context_version:3,prompt:action.body.request,execution_kind:'code_review',run_id:'review:a'})}
    await assert.rejects(sendCodeReview(restored),/response lost/)
    await sendCodeReview(codeReviewActions.load(storage,101,24,'author:a')!)
    assert.deepEqual(sent[0],sent[1])
    assert.equal((sent[0] as unknown[])[0],'/api/projects/101/tasks/24/code-reviews')
    codeReviewActions.clear(storage,action)
    assert.equal(codeReviewActions.pendingRun(storage,101,24),null)
  } finally {globalThis.fetch=original}
})

test('review requests reject corrupt packets, changed receipt scope and replacement of an unresolved request',async()=>{
  const {prepareCodeReview,codeReviewActions,sendCodeReview}=await import('../src/api/codeReviews.ts')
  assert.throws(()=>codeReviewActions.load({getItem:()=>'{broken'},101,24,'author:a'),/recuperar/)
  assert.throws(()=>prepareCodeReview(101,24,'author:a',{attemptId:'a',contextVersion:3,subjectSha:'a'.repeat(64),request:'  '}))
  const values=new Map<string,string>()
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}
  const observed={attemptId:'a',contextVersion:3,subjectSha:'a'.repeat(64),request:'Revisa esta versión.'}
  const action=prepareCodeReview(101,24,'author:a',observed)
  codeReviewActions.save(storage,action)
  assert.throws(()=>codeReviewActions.save(storage,prepareCodeReview(101,24,'author:b',observed)),/pendiente/)
  const original=globalThis.fetch
  try {
    globalThis.fetch=async()=>Response.json({project_id:202,task_id:24,operation_key:action.body.operation_key,context_version:3,prompt:action.body.request,execution_kind:'code_review',run_id:'foreign'})
    await assert.rejects(sendCodeReview(action),/recibo/)
    assert.deepEqual(codeReviewActions.load(storage,101,24,'author:a'),action)
  } finally {globalThis.fetch=original}
})
