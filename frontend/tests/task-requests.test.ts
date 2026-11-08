/** Durable request packets preserve pre-admission identity and selected data across reload and installation changes. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {prepareInstruction} from '../src/api/runtime.ts'
import {instructionPacket,prepareTaskCorrection,taskRequestPackets} from '../src/api/taskRequests.ts'

/** Keep exact local bytes and permit the existing installation archive to enumerate them. */
function storage(){const values=new Map<string,string>();return {get length(){return values.size},key:(index:number)=>[...values.keys()][index]??null,getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}}

test('stored requests retain original material and separate task, project and correction scopes',()=>{
 const saved=storage(),paths=['observations.py']
 const intent=instructionPacket(prepareInstruction(101,{task_id:1001,context_version:1,thread_id:'original-thread',message:'Comprobar la entrada.',repository_id:11,prior_code:{source_kind:'legacy_worktree',source_id:'7',paths,snapshot_sha256:'a'.repeat(64)}}))
 paths.push('unselected.py');taskRequestPackets.save(saved,intent)
 const loaded=taskRequestPackets.load(saved,'instruction',101,1001)!
 assert.deepEqual(loaded,intent);assert.deepEqual((loaded.body.prior_code as {paths:readonly string[]}).paths,['observations.py'])
 assert(Object.isFrozen((loaded.body.prior_code as {paths:readonly string[]}).paths))
 const correction=prepareTaskCorrection(101,1001,{expected_version:1,statement:'Ejemplo original.',source_kind:'user_example'})
 taskRequestPackets.save(saved,correction);taskRequestPackets.clear(saved,correction)
 assert.deepEqual(taskRequestPackets.load(saved,'instruction',101,1001),intent)
 assert.equal(taskRequestPackets.load(saved,'instruction',202,1001),null)
 assert.equal(taskRequestPackets.load(saved,'instruction',101,1002),null)
})

test('a different pending body and a stale acknowledgement cannot replace or clear the original request',()=>{
 const saved=storage(),first=instructionPacket(prepareInstruction(101,{task_id:1001,context_version:1,thread_id:'first',message:'Original'})),other=instructionPacket(prepareInstruction(101,{task_id:1001,context_version:2,thread_id:'other',message:'Changed'}))
 taskRequestPackets.save(saved,first)
 assert.throws(()=>taskRequestPackets.save(saved,other),/pendiente/)
 taskRequestPackets.clear(saved,other)
 assert.deepEqual(taskRequestPackets.load(saved,'instruction',101,1001),first)
 saved.setItem('researcher:task-instruction:v1:101:1001',JSON.stringify({...first,body:{...first.body,task_id:1002}}))
 assert.throws(()=>taskRequestPackets.load(saved,'instruction',101,1001),/recuperar/)
})

test('installation change archives an original task instruction before any transport can target the new host',async()=>{
 const api=await import('../src/api/session.ts'),saved=storage(),previousFetch=globalThis.fetch,descriptor=Object.getOwnPropertyDescriptor(globalThis,'sessionStorage')
 Object.defineProperty(globalThis,'sessionStorage',{value:saved,configurable:true})
 const requests:string[]=[]
 try{
  globalThis.fetch=async path=>{requests.push(String(path));return Response.json({authenticated:true,csrf_token:'first',endpoint_id:'original-A'})}
  await api.pairOwner('synthetic-original-owner')
  const packet=instructionPacket(prepareInstruction(101,{task_id:1001,context_version:1,thread_id:'original',message:'Original instruction'}));taskRequestPackets.save(saved,packet)
  globalThis.fetch=async path=>{requests.push(String(path));return Response.json({authenticated:true,csrf_token:'second',endpoint_id:'different-B'})}
  await api.pairOwner('synthetic-next-owner')
  await assert.rejects(api.ownerFetch('/api/chat/101/instructions',{method:'POST',body:JSON.stringify(packet.body)}),/instalación cambió/)
  assert.equal(requests.filter(path=>path==='/api/chat/101/instructions').length,0)
  const archive=JSON.parse(saved.getItem(api.acceptOwnerEndpointChange())!)
  assert.equal(archive.entries['researcher:task-instruction:v1:101:1001'],JSON.stringify(packet))
  assert.equal(taskRequestPackets.load(saved,'instruction',101,1001),null)
 }finally{globalThis.fetch=previousFetch;if(descriptor)Object.defineProperty(globalThis,'sessionStorage',descriptor);else Reflect.deleteProperty(globalThis,'sessionStorage')}
})
