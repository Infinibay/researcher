/** Exercise reconnect cursor ownership and retired browser generations without a live server. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'

/** Record generation callbacks while allowing deliberate stale and duplicate deliveries. */
class FakeSocket {
 static CONNECTING=0
 static OPEN=1
 static sockets:FakeSocket[]=[]
 readyState=0
 onopen:(()=>void)|null=null
 onmessage:((event:{data:string})=>void)|null=null
 onclose:((event:{code:number})=>void)|null=null
 onerror:(()=>void)|null=null
 closes=0
 url:string
 /** Capture the exact reconnect URL used by the production manager. */
 constructor(url:string){this.url=url;FakeSocket.sockets.push(this)}
 /** Retire this fake socket and dispatch the close callback synchronously. */
 close(code=1000){this.closes++;this.readyState=3;this.onclose?.({code})}
 /** Keep pings inert because these tests exercise history rather than socket I/O. */
 send(_data:string){}
}

/** Produce a valid durable page with the original project and decimal cursor. */
function page(project:number,ids:string[],after='0'){
 return {type:'events.page',project_id:project,after_id:after,next_after_id:ids.at(-1)??after,has_more:false,reset_required:false,resume_after_id:null,events:ids.map(id=>({event_id:id,type:'task_updated',project_id:project,data:{}}))}
}
/** Install a fresh browser transport surface for one independent manager test. */
function browser(){
 Object.defineProperty(globalThis,'location',{value:new URL('http://localhost:8000'),configurable:true})
 Object.defineProperty(globalThis,'WebSocket',{value:FakeSocket,configurable:true})
 FakeSocket.sockets=[]
}

test('a retired project socket cannot deliver events or close its replacement',async()=>{
 browser()
 const {WebSocketManager}=await import('../src/api/websocket.ts')
 const manager=new WebSocketManager()
 const messages:unknown[]=[]
 manager.subscribe(event=>messages.push(event))
 try{
  manager.connect(101);const first=FakeSocket.sockets.at(-1)!
  manager.connect(202);const second=FakeSocket.sockets.at(-1)!
  first.onmessage?.({data:JSON.stringify(page(101,['1']))});first.onerror?.()
  assert.equal(second.closes,0)
  assert.deepEqual(messages,[])
  second.onmessage?.({data:JSON.stringify(page(202,['2']))})
  assert.deepEqual(messages,page(202,['2']).events)
  manager.connect(101);const third=FakeSocket.sockets.at(-1)!
  first.onmessage?.({data:JSON.stringify(page(101,['3'],'1'))})
  assert.equal(messages.length,1,'Earlier A generation must not enter a later A visit')
  assert.match(third.url,/after_id=0$/)
 }finally{manager.disconnect()}
})

test('reconnect resumes the applied cursor and deduplicates overlapping server pages',async()=>{
 browser()
 const {WebSocketManager}=await import('../src/api/websocket.ts')
 const manager=new WebSocketManager(1)
 const ids:string[]=[]
 manager.subscribe(event=>ids.push(event.event_id))
 try{
  manager.connect(101);const first=FakeSocket.sockets.at(-1)!
  first.onmessage?.({data:JSON.stringify(page(101,['1','2']))})
  first.close(1006)
  await new Promise(resolve=>setTimeout(resolve,15))
  const resumed=FakeSocket.sockets.at(-1)!
  assert.notEqual(first,resumed)
  assert.match(resumed.url,/after_id=2$/)
  first.onmessage?.({data:JSON.stringify(page(101,['3'],'2'))})
  resumed.onmessage?.({data:JSON.stringify(page(101,['2','3','4'],'1'))})
  resumed.onmessage?.({data:JSON.stringify(page(101,['3','4'],'2'))})
  assert.deepEqual(ids,['1','2','3','4'])
  resumed.onmessage?.({data:JSON.stringify(page(101,['6'],'5'))})
  assert.equal(resumed.closes,1,'A skipped page must reconnect rather than advance the cursor')
  assert.deepEqual(ids,['1','2','3','4'])
 }finally{manager.disconnect()}
})
