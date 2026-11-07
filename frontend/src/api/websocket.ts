/** Resume committed project observations with generation checks and exact last-applied cursors. @module */
import {invalidateOwnerSession} from './session.ts'
import {applyEventPage} from './events.ts'
import type {DurableEvent} from './events.ts'

/** Connection state is transport evidence, never execution or task completion. */
export type StreamStatus='connecting'|'catching_up'|'live'|'reconnecting'|'reset_required'|'unavailable'
type Callback=(event:DurableEvent)=>void
type StatusCallback=(status:StreamStatus,projectId:number)=>void

/** Own one selected project's connection; retired sockets cannot mutate its replacement. */
export class WebSocketManager {
 private ws:WebSocket|null=null
 private listeners=new Set<Callback>()
 private statusListeners=new Set<StatusCallback>()
 private projectId:number|null=null
 private cursor='0'
 private reconnectTimer:ReturnType<typeof setTimeout>|null=null
 private pingTimer:ReturnType<typeof setInterval>|null=null
 private backoff:number
 private initialBackoff:number
 private intentionalClose=false

 /** Allow a short retry delay in deterministic transport tests without changing production bounds. */
 constructor(initialBackoff=1000){this.initialBackoff=initialBackoff;this.backoff=initialBackoff}

 /** Reset the cursor only on explicit scope change; reconnects retain the last fully applied page. */
 connect(projectId:number){
  if(this.projectId===projectId&&this.ws&&(this.ws.readyState===WebSocket.OPEN||this.ws.readyState===WebSocket.CONNECTING))return
  this.disconnect();this.projectId=projectId;this.intentionalClose=false;this.openConnection()
 }
 /** Retire this exact socket and its timers before another project can subscribe. */
 disconnect(){this.intentionalClose=true;this.clearTimers();const socket=this.ws;this.ws=null;socket?.close();this.projectId=null;this.cursor='0';this.backoff=this.initialBackoff}
 /** Subscribe to validated committed observations. */
 subscribe(callback:Callback){this.listeners.add(callback)}
 /** Remove the original observation callback during scope cleanup. */
 unsubscribe(callback:Callback){this.listeners.delete(callback)}
 /** Observe transport and retention state separately from activity payloads. */
 subscribeStatus(callback:StatusCallback){this.statusListeners.add(callback)}
 /** Remove the original status callback during scope cleanup. */
 unsubscribeStatus(callback:StatusCallback){this.statusListeners.delete(callback)}
 /** Notify only the currently selected project's status observers. */
 private status(status:StreamStatus){if(this.projectId!=null)this.statusListeners.forEach(callback=>callback(status,this.projectId!))}

 /** Open a new generation from the last applied durable ID without issuing execution commands. */
 private openConnection(){
  if(this.projectId==null)return
  const project=this.projectId
  const protocol=location.protocol==='https:'?'wss:':'ws:'
  const socket=new WebSocket(`${protocol}//${location.host}/ws?project_id=${project}&after_id=${this.cursor}`)
  this.ws=socket;this.status('connecting')
  socket.onopen=()=>{if(this.ws!==socket)return;this.status('catching_up');this.pingTimer=setInterval(()=>{if(this.ws===socket&&socket.readyState===WebSocket.OPEN)socket.send('ping')},30000)}
  socket.onmessage=message=>{
   if(this.ws!==socket||this.projectId!==project)return
   try{
    const raw=JSON.parse(message.data)
    if(raw?.type==='pong')return
    const page=applyEventPage(raw,project,this.cursor)
    if(page.reset)this.status('reset_required')
    for(const event of page.events)this.listeners.forEach(callback=>callback(event))
    this.cursor=page.cursor
    if(!page.reset){this.status(page.hasMore?'catching_up':'live');this.backoff=this.initialBackoff}
   }catch{this.status('unavailable');socket.close(1002,'Invalid event page')}
  }
  socket.onclose=event=>{
   if(this.ws!==socket)return
   this.clearTimers()
   if(event.code===1008){this.intentionalClose=true;this.status('unavailable');invalidateOwnerSession()}
   if(!this.intentionalClose){this.status('reconnecting');const delay=this.backoff;this.backoff=Math.min(this.backoff*2,30000);this.reconnectTimer=setTimeout(()=>{this.reconnectTimer=null;this.openConnection()},delay)}
  }
  socket.onerror=()=>{if(this.ws===socket)socket.close()}
 }
 /** Cancel only timers owned by the current generation. */
 private clearTimers(){if(this.reconnectTimer){clearTimeout(this.reconnectTimer);this.reconnectTimer=null}if(this.pingTimer){clearInterval(this.pingTimer);this.pingTimer=null}}
}

export const wsManager=new WebSocketManager()
