import assert from 'node:assert/strict'
import { test } from 'node:test'

class FakeSocket {
  static CONNECTING = 0
  static OPEN = 1
  static sockets:FakeSocket[] = []
  readyState = 0
  onopen: (() => void)|null = null
  onmessage: ((event:{data:string}) => void)|null = null
  onclose: ((event:{code:number}) => void)|null = null
  onerror: (() => void)|null = null
  closes = 0
  url:string
  constructor(url:string) { this.url=url; FakeSocket.sockets.push(this) }
  close() { this.closes++; this.readyState = 3; this.onclose?.({code:1000}) }
  send(_data:string) {}
}

test('a retired project socket cannot deliver events or close its replacement', async () => {
  Object.defineProperty(globalThis, 'location', {value:new URL('http://localhost:8000'), configurable:true})
  Object.defineProperty(globalThis, 'WebSocket', {value:FakeSocket, configurable:true})
  const { wsManager } = await import('../src/api/websocket.ts')
  const messages:unknown[] = []
  const listener = (event:unknown) => messages.push(event)
  wsManager.subscribe(listener)
  try {
    wsManager.connect(101)
    const first = FakeSocket.sockets.at(-1)!
    wsManager.connect(202)
    const second = FakeSocket.sockets.at(-1)!
    first.onmessage?.({data:JSON.stringify({type:'task_updated', project_id:101})})
    first.onerror?.()
    assert.equal(second.closes, 0, 'Error from project A must not close B')
    assert.deepEqual(messages, [], 'Late events from retired A must not enter B')
    second.onmessage?.({data:JSON.stringify({type:'task_updated', project_id:202})})
    assert.deepEqual(messages, [{type:'task_updated', project_id:202}])
  } finally { wsManager.unsubscribe(listener); wsManager.disconnect() }
})
