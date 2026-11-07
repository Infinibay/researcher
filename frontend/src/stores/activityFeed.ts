/** Bounded recent owner activity with exact IDs, scope generations and explicit transport gaps. @module */
import {create} from 'zustand'
import type {AgentActivityEvent} from '../types/api'
import type {StreamStatus} from '../api/websocket'

const MAX_EVENTS=100
/** Scope and transport evidence remain independent from whether the recent feed has rows. */
interface ActivityFeedStore {
 projectId:number|null;generation:number;lastEventId:string;receivedCount:number
 events:AgentActivityEvent[];unreadCount:number;feedOpen:boolean;connection:StreamStatus;gap:boolean
 selectProject:(projectId:number|null)=>number
 addEvent:(projectId:number,generation:number,event:AgentActivityEvent)=>void
 setConnection:(projectId:number,generation:number,status:StreamStatus)=>void
 clearFeed:()=>void;toggleFeed:()=>void
}

export const useActivityFeedStore=create<ActivityFeedStore>()((set,get)=>({
 projectId:null,generation:0,lastEventId:'0',receivedCount:0,events:[],unreadCount:0,feedOpen:false,connection:'connecting',gap:false,
 /** Start a new scope generation so a late A response cannot enter a later visit to A. */
 selectProject(projectId){const generation=get().generation+1;set({projectId,generation,lastEventId:'0',receivedCount:0,events:[],unreadCount:0,connection:'connecting',gap:false});return generation},
 /** Apply a committed ascending ID only once, including replay after a partially applied page. */
 addEvent(projectId,generation,event){set(state=>{
  if(state.projectId!==projectId||state.generation!==generation||BigInt(event.id)<=BigInt(state.lastEventId))return state
  return {events:[event,...state.events].slice(0,MAX_EVENTS),lastEventId:event.id,receivedCount:state.receivedCount+1,unreadCount:state.feedOpen?state.unreadCount:state.unreadCount+1}
 })},
 /** Preserve a visible gap warning after catch-up finishes instead of implying complete history. */
 setConnection(projectId,generation,connection){set(state=>state.projectId!==projectId||state.generation!==generation?state:connection==='reset_required'?{connection,gap:true,events:[],lastEventId:'0',unreadCount:0,receivedCount:0}:{connection})},
 /** Clear presentation only; transport cursors and deduplication survive clearing the visible list. */
 clearFeed(){set({events:[],unreadCount:0})},
 /** Mark the current visible notification batch read when the drawer opens. */
 toggleFeed(){const feedOpen=!get().feedOpen;set({feedOpen,...(feedOpen?{unreadCount:0}:{})})},
}))
