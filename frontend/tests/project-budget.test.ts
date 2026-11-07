/** Preserve original budget identity, exact receipts and damaged local state without silently authorizing another decision. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {loadBudgetAction,prepareBudgetChange,readBudgetReceipt,saveBudgetAction,sendBudgetChange} from '../src/api/projectBudget.ts'

test('budget action recovery validates original project, version, limits and non-dispatch receipt',async()=>{
 const action=prepareBudgetChange(101,2,20,5000,'More research'),original=globalThis.fetch,sent:any[]=[]
 const valid={project_id:101,...action.body,revision:3,inference_started:false}
 try{
  globalThis.fetch=async(url,options)=>{sent.push({url:String(url),body:options?.body?JSON.parse(String(options.body)):null});return Response.json(valid)}
  assert.deepEqual(await sendBudgetChange(action),valid);assert.deepEqual(await readBudgetReceipt(action),valid)
  assert.deepEqual(sent[0].body,action.body);assert.equal(sent[1].body,null);assert.ok(sent[1].url.endsWith('/changes/'+action.body.operation_key))
  for(const invalid of [{project_id:202},{token_limit:5001},{revision:4},{inference_started:true},{reason:'Changed'}]){
   globalThis.fetch=async()=>Response.json({...valid,...invalid});await assert.rejects(readBudgetReceipt(action),/original/)
  }
 }finally{globalThis.fetch=original}
})

test('budget storage rejects replaced or corrupt pending actions and scopes project state',()=>{
 const values=new Map<string,string>(),storage={getItem:(k:string)=>values.get(k)??null,setItem:(k:string,v:string)=>{values.set(k,v)},removeItem:(k:string)=>{values.delete(k)}}
 const action=prepareBudgetChange(101,0,2,200,'');saveBudgetAction(storage,action)
 assert.deepEqual(loadBudgetAction(storage,101),action);assert.equal(loadBudgetAction(storage,202),null)
 assert.throws(()=>saveBudgetAction(storage,prepareBudgetChange(101,1,4,400,'')),/pendiente/)
 const key=[...values.keys()][0];values.set(key,JSON.stringify({...action,body:{...action.body,expected_revision:0.1}}));assert.throws(()=>loadBudgetAction(storage,101),/original/)
 assert.throws(()=>prepareBudgetChange(101,0,2,Number.MAX_SAFE_INTEGER+1,''),/original/)
})
