/** Project source and Stop requests preserve original scope after uncertain replies; metadata never becomes native activity. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Isolate exact persisted resource requests without a browser storage dependency. */
function storage(){const m=new Map<string,string>();return {getItem:(k:string)=>m.get(k)??null,setItem:(k:string,v:string)=>{m.set(k,v)},removeItem:(k:string)=>{m.delete(k)}}}

test('project Stop reload retries only its exact observed work and preserves an uncertain receipt',async()=>{
 const {prepareProjectStop,projectPackets,sendProjectStop}=await import('../src/api/projectWorkspace.ts')
 const a=prepareProjectStop(101,{task_id:42,scope_sha256:'a'.repeat(64)}),s=storage(),old=globalThis.fetch,sent:unknown[]=[]
 projectPackets.save(s,a)
 try{globalThis.fetch=async(url,options)=>{sent.push([String(url),JSON.parse(String(options?.body))]);if(sent.length===1)throw new TypeError('lost');return Response.json({kind:'project.stop',project_id:101,...a.body,run_ids:['original'],execution_ids:[],status:'requested',closure:'unconfirmed'})}
  await assert.rejects(sendProjectStop(a),/lost/);await sendProjectStop(projectPackets.load(s,'stop',101)!);assert.deepEqual(sent[0],sent[1])
  globalThis.fetch=async()=>Response.json({kind:'project.stop',project_id:101,...a.body,scope_sha256:'b'.repeat(64),closure:'unconfirmed',status:'requested'})
  await assert.rejects(sendProjectStop(a),/recibo/)
 }finally{globalThis.fetch=old}
})

test('source registration keeps its original directory and never adds Git or remote effects after reload',async()=>{
 const {prepareProjectSource,projectPackets,sendProjectSource}=await import('../src/api/projectWorkspace.ts')
 const a=prepareProjectSource(202,'beta','/managed/beta'),s=storage(),old=globalThis.fetch
 projectPackets.save(s,a)
 try{globalThis.fetch=async()=>Response.json({project_id:202,name:'beta',path:'/managed/beta',repository_id:12,filesystem_changed:false,remote_changed:false});assert.equal((await sendProjectSource(projectPackets.load(s,'source',202)!)).repository_id,12)
  globalThis.fetch=async()=>Response.json({project_id:202,name:'beta',path:'/other',repository_id:12,filesystem_changed:false,remote_changed:true});await assert.rejects(sendProjectSource(a),/recibo/)
 }finally{globalThis.fetch=old}
 assert.throws(()=>prepareProjectSource(202,'beta','relative/path'),/absoluta/)
})

test('project creation accepts only its exact original resource receipt independent of JSON key order',async()=>{
 const {prepareProjectCreate,projectPackets,sendProjectCreate}=await import('../src/api/projectWorkspace.ts')
 const a=prepareProjectCreate('Gamma','New scope'),s=storage(),old=globalThis.fetch
 projectPackets.save(s,a)
 try{globalThis.fetch=async()=>Response.json({id:203,name:'Renamed later',status:'new',creation:{project_id:203,request:{description:a.body.description,name:a.body.name,operation_key:a.body.operation_key}}});assert.equal((await sendProjectCreate(projectPackets.load(s,'create',0)!)).id,203)}finally{globalThis.fetch=old}
})
