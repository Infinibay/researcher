/** Code decisions preserve exact owner observations and reuse durable action storage. @module */
import assert from 'node:assert/strict'
import { test } from 'node:test'

test('code acceptance survives lost responses without borrowing a research action or refreshed version', async () => {
  const { prepareCodeAcceptance, codeActions, sendCodeAcceptance } = await import('../src/api/codeResults.ts')
  const { prepareAcceptance, saveResultAction } = await import('../src/api/results.ts')
  const values = new Map<string,string>()
  const storage = {getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}
  const action = prepareCodeAcceptance(101,24,'code:a',{attemptId:'author-a',contextVersion:3,subjectSha:'a'.repeat(64),reviewSha:'b'.repeat(64),acknowledgeLimits:true,note:'Con límites visibles.'})
  codeActions.save(storage,action)
  saveResultAction(storage,prepareAcceptance(101,24,'research:a',{candidateId:7,candidateSha:'c'.repeat(64),contextVersion:3,reviewSha:'d'.repeat(64),acknowledgeLimits:true,note:null}))
  assert.equal(codeActions.pendingRun(storage,101,24),'code:a')
  assert.deepEqual(codeActions.load(storage,101,24,'code:a'),action)
  assert.equal(codeActions.load(storage,202,24,'code:a'),null)
  const original=globalThis.fetch
  const sent: {url:string;body:unknown}[]=[]
  try {
    globalThis.fetch=async(url,options)=>{sent.push({url:String(url),body:JSON.parse(String(options?.body))});if(sent.length===1) throw new TypeError('response lost');return Response.json({project_id:101,task_id:24,run_id:'code:a',...action.body,task_accepted:true,publication_performed:false})}
    await assert.rejects(sendCodeAcceptance(action),/response lost/)
    await sendCodeAcceptance(codeActions.load(storage,101,24,'code:a')!)
    assert.deepEqual(sent[0],sent[1])
    assert.equal(sent[0].url,'/api/projects/101/runs/code%3Aa/code-result/accept')
    codeActions.clear(storage,action)
    assert.equal(codeActions.pendingRun(storage,101,24),null)
  } finally {globalThis.fetch=original}
})

test('invalid and conflicting stored code decisions never silently become another action', async () => {
  const { prepareCodeAcceptance, codeActions } = await import('../src/api/codeResults.ts')
  assert.throws(()=>codeActions.load({getItem:()=>'{broken'},101,24,'code:a'),/No se pudo/)
  assert.throws(()=>prepareCodeAcceptance(101,24,'code:a',{attemptId:'author',contextVersion:3,subjectSha:'bad',reviewSha:'b'.repeat(64),acknowledgeLimits:true,note:null}))
  const values=new Map<string,string>()
  const storage={getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}
  const observed={attemptId:'author',contextVersion:3,subjectSha:'a'.repeat(64),reviewSha:'b'.repeat(64),acknowledgeLimits:true,note:null}
  codeActions.save(storage,prepareCodeAcceptance(101,24,'code:a',observed))
  assert.throws(()=>codeActions.save(storage,prepareCodeAcceptance(101,24,'code:b',observed)),/pendiente/)
})
