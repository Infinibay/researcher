/** Check exact continuation receipts and pending project identity independently of rendering. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {loadLocalAction,prepareLocalContinuation,readLocalContinuation,saveLocalAction,sendLocalContinuation} from '../src/api/localWork.ts'

test('receipt recovery validates original project and source and never sends a second write',async()=>{
 const action=prepareLocalContinuation(101,'a'.repeat(64),'Repeat this calculation'),original=globalThis.fetch,sent:any[]=[]
 const valid={project_id:101,...action.body,successor_operation_id:'b'.repeat(64),generation:1,work_started:false}
 try{
  globalThis.fetch=async(url,options)=>{sent.push({url:String(url),body:options?.body?JSON.parse(String(options.body)):null});return Response.json(valid)}
  assert.deepEqual(await sendLocalContinuation(action),valid);assert.deepEqual(await readLocalContinuation(action),valid)
  assert.deepEqual(sent[0].body,action.body);assert.equal(sent[1].body,null)
  for(const invalid of [{project_id:202},{source_operation_id:'c'.repeat(64)},{work_started:true},{generation:0},{reason:'Changed'},{successor_operation_id:'bad'}]){
   globalThis.fetch=async()=>Response.json({...valid,...invalid});await assert.rejects(readLocalContinuation(action),/original/)
  }
 }finally{globalThis.fetch=original}
})

test('pending continuation cannot be replaced, crossed into another project or silently repaired',()=>{
 const values=new Map<string,string>(),storage={getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v)},removeItem:(k:string)=>{values.delete(k)}}
 const action=prepareLocalContinuation(101,'a'.repeat(64),'');saveLocalAction(storage,action)
 assert.deepEqual(loadLocalAction(storage,101),action);assert.equal(loadLocalAction(storage,202),null)
 assert.throws(()=>saveLocalAction(storage,prepareLocalContinuation(101,'b'.repeat(64),'')),/pendiente/)
 values.set([...values.keys()][0],JSON.stringify({...action,body:{...action.body,source_operation_id:'invalid'}}))
 assert.throws(()=>loadLocalAction(storage,101),/original/)
})
