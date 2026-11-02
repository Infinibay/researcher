/** Result owner actions preserve observed versions across lost responses and reloads. @module */
import assert from 'node:assert/strict'
import { test } from 'node:test'

 test('acceptance retry reloads exactly the original project, candidate, review and nonce', async () => {
  const { prepareAcceptance, saveResultAction, loadResultAction, sendResultAction } = await import('../src/api/results.ts')
  const values = new Map<string,string>()
  const storage = {getItem:(key:string)=>values.get(key) ?? null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}
  const action = prepareAcceptance(101, 24, 'run:a', {candidateId:7,candidateSha:'a'.repeat(64),contextVersion:3,reviewSha:'b'.repeat(64),acknowledgeLimits:true,note:'Documentary use only.'})
  saveResultAction(storage, action)
  const restored = loadResultAction(storage,101,24,'run:a')
  assert.deepEqual(restored, action)
  assert.equal(loadResultAction(storage,202,24,'run:a'), null)
  const sent: {url:string;body:unknown}[]=[]
  const original = globalThis.fetch
  try {
   globalThis.fetch=async (url,options)=>{sent.push({url:String(url),body:JSON.parse(String(options?.body))});if(sent.length===1) throw new TypeError('response lost');return Response.json({task_accepted:true})}
   await assert.rejects(sendResultAction(restored!),/response lost/)
   await sendResultAction(loadResultAction(storage,101,24,'run:a')!)
   assert.deepEqual(sent[0],sent[1])
   assert.equal(sent[0].url,'/api/projects/101/runs/run%3Aa/result/accept')
   assert.deepEqual(sent[0].body,action.body)
  } finally {globalThis.fetch=original}
 })

 test('a corrupt saved result action cannot silently become a new decision', async () => {
  const { loadResultAction } = await import('../src/api/results.ts')
  assert.throws(()=>loadResultAction({getItem:()=>'{broken'},101,24,'run:a'),/recuperar/)
 })

 test('result changes preserve correction evidence and never start a model turn', async () => {
  const { prepareResultChange, sendResultAction } = await import('../src/api/results.ts')
  const action=prepareResultChange(101,24,'run:a',3,'Compare an independent source.')
  const original=globalThis.fetch
  try {
   globalThis.fetch=async(url,options)=>{assert.equal(String(url),'/api/projects/101/tasks/24/context-corrections');assert.deepEqual(JSON.parse(String(options?.body)),action.body);return Response.json({context_version:4,inference_started:false})}
   await sendResultAction(action)
   assert.equal(action.body.source_kind,'user_message')
   assert.equal(action.body.expected_version,3)
  } finally {globalThis.fetch=original}
 })

 test('a pending decision stays discoverable when a newer author run becomes visible',async()=>{
  const { prepareResultChange, saveResultAction, pendingResultRun, clearResultAction }=await import('../src/api/results.ts')
  const values=new Map<string,string>()
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}
  const old=prepareResultChange(101,24,'old-author',3,'Compare another source.')
  saveResultAction(storage,old)
  assert.equal(pendingResultRun(storage,101,24),'old-author')
  assert.equal(pendingResultRun(storage,202,24),null)
  assert.throws(()=>saveResultAction(storage,prepareResultChange(101,24,'new-author',4,'Another request.')),/pendiente/)
  clearResultAction(storage,old)
  assert.equal(pendingResultRun(storage,101,24),null)
 })
