/** Original project policy packets survive uncertainty and cannot adopt another project's receipt. @module */
import test from 'node:test'
import assert from 'node:assert/strict'
import {loadCheckPolicy,prepareCheckPolicy,readCheckPolicyReceipt,saveCheckPolicy,sendCheckPolicy} from '../src/api/projectCheckPolicy.ts'

test('policy storage is scoped and receipt recovery never substitutes current state or a different original request',async()=>{
 const values=new Map<string,string>();const storage={getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v)},removeItem:(k:string)=>{values.delete(k)}}
 const action=prepareCheckPolicy(101,4,'require_tests');saveCheckPolicy(storage,action)
 assert.deepEqual(loadCheckPolicy(storage,101),action);assert.equal(loadCheckPolicy(storage,202),null)
 assert.throws(()=>saveCheckPolicy(storage,prepareCheckPolicy(101,5,'allow_missing')),/pendiente/)
 const original=globalThis.fetch;const calls:{url:string;method:string}[]=[]
 const receipt={...action.body,project_id:101,revision:5,inference_started:false,applies_to:'future_code_acceptances'}
 globalThis.fetch=async(url,options)=>{calls.push({url:String(url),method:options?.method??'GET'});return new Response(JSON.stringify(receipt),{status:200,headers:{'Content-Type':'application/json'}})}
 try{
  assert.deepEqual(await sendCheckPolicy(action),receipt)
  assert.deepEqual(await readCheckPolicyReceipt(action),receipt)
  assert.deepEqual(calls.map(c=>c.method),['POST','GET'])
  globalThis.fetch=async()=>new Response(JSON.stringify({...receipt,project_id:202}))
  await assert.rejects(readCheckPolicyReceipt(action),/no corresponde/)
  globalThis.fetch=async()=>new Response(JSON.stringify({...receipt,mode:'allow_missing'}))
  await assert.rejects(readCheckPolicyReceipt(action),/no corresponde/)
 }finally{globalThis.fetch=original}
})
