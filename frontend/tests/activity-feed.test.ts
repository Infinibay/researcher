/** Preserve every applied cursor while displaying a bounded recent project feed. @module */
import assert from 'node:assert/strict'
import {test} from 'node:test'
import {useActivityFeedStore} from '../src/stores/activityFeed.ts'

/** Build a saved observation without invented provider activity. */
function event(id:number){return {id:String(id),type:'run.observed',timestamp:'2026-11-07 00:00:00',content:`Observation ${id}`}}

test('a bounded feed deduplicates older replay even after its visible rows were discarded',()=>{
 const store=useActivityFeedStore.getState(),generation=store.selectProject(101)
 for(let id=1;id<=305;id++)store.addEvent(101,generation,event(id))
 for(let id=1;id<=305;id++)store.addEvent(101,generation,event(id))
 assert.equal(useActivityFeedStore.getState().receivedCount,305)
 assert.equal(useActivityFeedStore.getState().events.length,100)
 assert.equal(useActivityFeedStore.getState().events.at(-1)?.id,'206')
 store.clearFeed();store.addEvent(101,generation,event(305));store.addEvent(101,generation,event(306))
 assert.deepEqual(useActivityFeedStore.getState().events.map(event=>event.id),['306'])
})

test('A to B to A rejects retired generations and retains a retention warning after catch-up',()=>{
 const store=useActivityFeedStore.getState(),first=store.selectProject(101)
 const other=store.selectProject(202)
 store.addEvent(101,first,event(1));store.addEvent(202,other,event(2))
 const current=store.selectProject(101)
 store.addEvent(101,first,event(3));store.setConnection(202,other,'live')
 assert.deepEqual(useActivityFeedStore.getState().events,[])
 assert.equal(useActivityFeedStore.getState().connection,'connecting')
 store.setConnection(101,current,'reset_required');store.setConnection(101,current,'live')
 assert.equal(useActivityFeedStore.getState().gap,true)
 store.addEvent(101,current,event(4))
 assert.equal(useActivityFeedStore.getState().events[0].id,'4')
})
