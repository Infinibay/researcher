/** Successor permission retains exact owner-observed history across transport loss. @module */
import test from 'node:test'
import assert from 'node:assert/strict'

/** In-memory storage port exercises the same persisted-packet implementation as the browser. */
function storage(){const items=new Map<string,string>();return {getItem:(key:string)=>items.get(key)??null,setItem:(key:string,value:string)=>{items.set(key,value)},removeItem:(key:string)=>{items.delete(key)}}}

test('continuation reload resends original evidence and refuses a foreign successor receipt',async()=>{
 const api=await import('../src/api/planContinuations.ts'),saved=storage(),previous=globalThis.fetch,sent:unknown[]=[]
 try{
  const action=api.prepareContinuationAction(101,42,'plan:a','execution:a','delivery:a','old:a','a'.repeat(64))
  api.continuationActions.save(saved,action)
  globalThis.fetch=async(url,options)=>{const body=JSON.parse(String(options?.body));sent.push([String(url),body]);if(sent.length===1)throw new TypeError('lost response');return Response.json({project_id:101,plan_run_id:'plan:a',execution_id:'execution:a',predecessor_delivery_id:'delivery:a',previous_run_id:'old:a',delivery_id:'delivery:b',inference_started:false,...body})}
  await assert.rejects(api.sendContinuationAction(action),/lost response/)
  const restored=api.continuationActions.load(saved,101,42,'plan:a')!
  const receipt=await api.sendContinuationAction(restored)
  assert.equal(receipt.delivery_id,'delivery:b');assert.deepEqual(sent[0],sent[1])
  globalThis.fetch=async()=>Response.json({...receipt,previous_run_id:'unrelated:a'})
  await assert.rejects(api.sendContinuationAction(restored),/recibo/)
  assert.notEqual(api.continuationActions.load(saved,101,42,'plan:a'),null)
  api.continuationActions.clear(saved,restored)
  assert.equal(api.continuationActions.pendingRun(saved,101,42),null)
 }finally{globalThis.fetch=previous}
})

test('continuation refuses damaged packets and unrelated preview scope',async()=>{
 const api=await import('../src/api/planContinuations.ts'),saved=storage(),previous=globalThis.fetch
 const action=api.prepareContinuationAction(101,42,'plan:a','execution:a','delivery:a','old:a','a'.repeat(64))
 api.continuationActions.save(saved,action)
 saved.setItem('researcher:plan-continuation-action:v1:101:42:plan%3Aa',JSON.stringify({...action,body:{...action.body,prompt:'injected'}}))
 assert.throws(()=>api.continuationActions.load(saved,101,42,'plan:a'))
 try{
  globalThis.fetch=async()=>Response.json({project_id:101,execution_id:'execution:foreign',delivery_id:'delivery:a',eligible:true,snapshot_sha256:'a'.repeat(64)})
  await assert.rejects(api.continuationState(101,'execution:a','delivery:a'),/entrega/)
 }finally{globalThis.fetch=previous}
})
