/** Recover original planning intents without overwriting another project, parent or newer request. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Retain exact packets across a simulated browser reload. */
function storage(){const values=new Map<string,string>();return {get length(){return values.size},key:(index:number)=>[...values.keys()][index]??null,getItem:(key:string)=>values.get(key)??null,setItem:(key:string,value:string)=>{values.set(key,value)},removeItem:(key:string)=>{values.delete(key)}}}

test('a pending group keeps its exact intent and key across reload and cannot be overwritten',async()=>{
 const {planningPackets,preparePlanningGroup}=await import('../src/api/planningCommands.ts')
 const retained=storage(),first=preparePlanningGroup(1,'Mediciones','Comparar entrada y salida',2)
 planningPackets.save(retained,first)
 assert.deepEqual(planningPackets.load(retained,'group',1),first)
 assert.throws(()=>planningPackets.save(retained,preparePlanningGroup(1,'Otro objetivo','',1)),/pendiente/)
 assert.deepEqual(planningPackets.load(retained,'group',1),first)
 planningPackets.clear(retained,preparePlanningGroup(1,'Otro objetivo','',1))
 assert.deepEqual(planningPackets.load(retained,'group',1),first)
 planningPackets.clear(retained,first)
 assert.equal(planningPackets.load(retained,'group',1),null)
})

test('milestones in different projects and groups keep independent original requests',async()=>{
 const {planningPackets,preparePlanningMilestone}=await import('../src/api/planningCommands.ts')
 const retained=storage(),a=preparePlanningMilestone(1,12,'Datos'),b=preparePlanningMilestone(2,20,'Datos'),c=preparePlanningMilestone(1,13,'Datos')
 for(const request of [a,b,c])planningPackets.save(retained,request)
 assert.deepEqual(planningPackets.load(retained,'milestone',1,12),a)
 planningPackets.clear(retained,b)
 assert.deepEqual(planningPackets.load(retained,'milestone',1,12),a)
 assert.deepEqual(planningPackets.load(retained,'milestone',1,13),c)
 assert.equal(planningPackets.load(retained,'milestone',2,20),null)
})

test('corrupted or retargeted storage cannot silently become another mutation',async()=>{
 const {planningPackets,preparePlanningGroup}=await import('../src/api/planningCommands.ts')
 const retained=storage(),packet=preparePlanningGroup(1,'Original','',2)
 planningPackets.save(retained,packet)
 const raw=JSON.stringify({...packet,body:{...packet.body,project_id:2}})
 retained.setItem('researcher:planning-create:v1:1:group:0',raw)
 assert.throws(()=>planningPackets.load(retained,'group',1),/recuperar/)
 assert.throws(()=>planningPackets.save(retained,packet),/recuperar/)
})

test('an installation change archives planning requests before permitting fresh owner work',async()=>{
 const {planningPackets,preparePlanningGroup}=await import('../src/api/planningCommands.ts')
 const api=await import('../src/api/session.ts'),retained=storage(),previousFetch=globalThis.fetch,descriptor=Object.getOwnPropertyDescriptor(globalThis,'sessionStorage')
 Object.defineProperty(globalThis,'sessionStorage',{value:retained,configurable:true})
 const requests:string[]=[]
 try{
  globalThis.fetch=async(path)=>{requests.push(String(path));return Response.json({authenticated:true,csrf_token:'first',endpoint_id:'installation-A'})}
  await api.pairOwner('old-owner')
  const packet=preparePlanningGroup(1,'Original de A','',2);planningPackets.save(retained,packet)
  globalThis.fetch=async(path)=>{requests.push(String(path));return Response.json({authenticated:true,csrf_token:'second',endpoint_id:'installation-B'})}
  await api.pairOwner('new-owner')
  await assert.rejects(api.ownerFetch('/api/epics',{method:'POST',body:JSON.stringify(packet.body)}),/instalación cambió/)
  assert.equal(requests.filter(path=>path==='/api/epics').length,0)
  const archiveKey=api.acceptOwnerEndpointChange(),archive=JSON.parse(retained.getItem(archiveKey)!)
  assert.equal(archive.entries['researcher:planning-create:v1:1:group:0'],JSON.stringify(packet))
  assert.equal(planningPackets.load(retained,'group',1),null)
 }finally{globalThis.fetch=previousFetch;if(descriptor)Object.defineProperty(globalThis,'sessionStorage',descriptor);else Reflect.deleteProperty(globalThis,'sessionStorage')}
})
