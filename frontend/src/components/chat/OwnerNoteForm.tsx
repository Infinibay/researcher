/** Explain and preserve advisory thread notes separately from execution instructions and task corrections. @module */
import {useEffect,useRef,useState} from 'react'
import {useSendMessage} from '../../hooks/useChat'
import {ownerNotePackets,prepareOwnerNote,verifyOwnerNoteReceipt,type OwnerNotePacket} from '../../api/ownerNotes'

/** Restore only the original thread's packet; unreadable storage prevents another note. */
function restored(project:number,thread:string){try{return {packet:typeof window==='undefined'?null:ownerNotePackets.load(window.sessionStorage,project,thread),issue:'',blocked:false}}catch(error){return {packet:null as OwnerNotePacket|null,issue:error instanceof Error?error.message:'No se pudo recuperar la nota.',blocked:true}}}

/** Save before send and recover exact original notes even after navigation or a lost reply. */
export function OwnerNoteForm({projectId,threadId}:{projectId:number;threadId:string}){
 const [saved,setSaved]=useState(()=>restored(projectId,threadId)),[message,setMessage]=useState(()=>saved.packet?.body.message??'')
 const [issue,setIssue]=useState(''),[notice,setNotice]=useState('')
 const send=useSendMessage(),alive=useRef(true)
 useEffect(()=>{alive.current=true;return()=>{alive.current=false}},[])
 /** Deliver only a persisted original; later thread changes cannot acknowledge or retarget it. */
 function submit(){if(saved.blocked)return;try{const packet=saved.packet??prepareOwnerNote(projectId,threadId,message);ownerNotePackets.save(window.sessionStorage,packet);setSaved({packet,issue:'',blocked:false});setIssue('');setNotice('');send.mutate({projectId,...packet.body},{onSuccess:result=>{try{verifyOwnerNoteReceipt(packet,result);ownerNotePackets.clear(window.sessionStorage,packet)}catch(error){if(alive.current)setIssue(error instanceof Error?error.message:'No se confirmó la nota.');return}if(alive.current){setSaved({packet:null,issue:'',blocked:false});setMessage('');setNotice('Nota guardada en este hilo. No se inició ninguna ejecución.')}}})}catch(error){setIssue(error instanceof Error?error.message:'No se guardó la nota; no se envió.')}}
 return <section className="space-y-2 rounded-md border border-[var(--work-line)] p-3" aria-label="Nota para la conversación">
  <h4>Guardar una nota</h4>
  <p>Se guarda en este hilo del proyecto. Si varias tareas comparten el hilo, aparecerá en su historial. No cambia las instrucciones del intento actual ni inicia trabajo; para cambiar una premisa usa «Corregir el contexto».</p>
  <form className="space-y-2" onSubmit={event=>{event.preventDefault();submit()}}>
   <label className="block" htmlFor={`owner-note-${threadId}`}>Nota para este hilo</label><textarea id={`owner-note-${threadId}`} className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" rows={3} maxLength={50000} value={message} readOnly={saved.packet!==null||saved.blocked} onChange={event=>setMessage(event.target.value)}/>
   {saved.packet&&<p role="status">Nota original sin confirmar. Reenviarla conserva el mismo texto, hilo y clave.</p>}
   {(saved.issue||issue||send.error)&&<p role="alert">{saved.issue||issue||`No se confirmó el guardado. ${send.error?.message}`}</p>}
   <button className="task-secondary" disabled={saved.blocked||send.isPending||!message.trim()}>{send.isPending?'Guardando…':saved.packet?'Reenviar la misma nota':'Guardar nota'}</button>
   {saved.packet&&<div><p>Retirar la copia no elimina una nota registrada. Consulta el historial antes de preparar otra.</p><button type="button" className="task-secondary" disabled={send.isPending} onClick={()=>{try{ownerNotePackets.clear(window.sessionStorage,saved.packet!);setSaved({packet:null,issue:'',blocked:false});setMessage('');setIssue('')}catch(error){setIssue(error instanceof Error?error.message:'No se pudo retirar la copia.')}}}>Retirar copia de la nota</button></div>}
  </form>
  {notice&&<p role="status">{notice}</p>}
 </section>
}
