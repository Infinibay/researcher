/** Explain local calculation uncertainty and preserve explicit owner continuation intent. @module */
import {useEffect,useState} from 'react'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {ApiError} from '../../api/client'
import {clearLocalAction,loadLocalAction,localWork,prepareLocalContinuation,readLocalContinuation,saveLocalAction,sendLocalContinuation,type LocalAction,type LocalCalculation,type LocalReceipt} from '../../api/localWork'

const button='min-h-11 rounded border border-[var(--work-line)] px-3 py-2 disabled:opacity-50'
/** Show original calculations on demand, with scoped pending receipts and a separate explicit permission step. */
export function LocalWork({projectId}:{projectId:number}){
 const client=useQueryClient(),[open,setOpen]=useState(false),[before,setBefore]=useState<number|null>(null)
 const [selected,setSelected]=useState<LocalCalculation|null>(null),[reason,setReason]=useState('')
 const [pending,setPending]=useState<LocalAction|null>(null),[ready,setReady]=useState(false),[localError,setLocalError]=useState(''),[notice,setNotice]=useState('')
 useEffect(()=>{try{setPending(loadLocalAction(sessionStorage,projectId));setReady(true)}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo recuperar la autorización original.')}},[projectId])
 const query=useQuery({queryKey:['local-work',projectId,before],queryFn:()=>localWork(projectId,before),enabled:open,retry:false})
 const page=query.data?.project_id===projectId?query.data:undefined
 /** Resolve only the original decision and refresh its project without dispatching a calculation. */
 function resolved(receipt:LocalReceipt,action:LocalAction){try{clearLocalAction(sessionStorage,action);setPending(null);setSelected(null);setNotice(receipt.authorization_scope==='historical_installation'?'Recibo histórico recuperado. Esta decisión no autoriza trabajo en esta instalación. Revisa el cálculo y, si corresponde, guarda una autorización nueva.':'Autorización guardada. No se inició un cálculo. La próxima solicitud idéntica podrá usar una nueva reserva; el consumo anterior se conserva.');if(receipt.authorization_scope==='historical_installation')setOpen(true);client.invalidateQueries({queryKey:['local-work',projectId]})}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo cerrar la autorización guardada.')}}
 const save=useMutation({mutationFn:sendLocalContinuation,onSuccess:resolved}),recover=useMutation({mutationFn:readLocalContinuation,onSuccess:resolved})
 const busy=save.isPending||recover.isPending,rejected=save.error instanceof ApiError&&[400,409,422].includes(save.error.status)
 /** Capture the observed original operation; refreshed history cannot silently select a different one. */
 function choose(row:LocalCalculation){setSelected(row);setReason('');setNotice('');setLocalError('');save.reset();recover.reset()}
 /** Save before POST so response loss cannot cause an untracked duplicate continuation command. */
 function submit(event:React.FormEvent){event.preventDefault();if(!selected)return;try{const action=prepareLocalContinuation(projectId,selected.operation_id,reason);saveLocalAction(sessionStorage,action);setPending(action);save.mutate(action)}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo guardar la decisión original.')}}
 /** Discard only a definitively rejected write and require a fresh observation before another decision. */
 async function closeRejected(){if(!pending)return;try{clearLocalAction(sessionStorage,pending);setPending(null);setSelected(null);save.reset();recover.reset();await client.resetQueries({queryKey:['local-work',projectId]})}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo cerrar la decisión rechazada.')}}
 return <section className="space-y-3 pt-3" aria-label="Historial de cálculos locales">
  <button className={button} onClick={()=>setOpen(!open)} aria-expanded={open}>{open?'Ocultar cálculos locales':'Revisar cálculos locales'}</button>
  {notice&&<p role="status">{notice}</p>}{localError&&<p role="alert">{localError}</p>}
  {pending?<div className="space-y-2 rounded border border-[var(--work-line)] p-3">
   <p>Autorización pendiente de comprobar para el cálculo <span className="break-all">{pending.body.source_operation_id}</span>.</p>
   {(save.error||recover.error)&&<p role="alert">No se confirmó la autorización. {save.error?.message??recover.error?.message} Conservamos su identidad original.</p>}
   <div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={()=>recover.mutate(pending)}>Consultar autorización original</button><button className={button} disabled={busy||rejected} onClick={()=>save.mutate(pending)}>Reenviar la misma autorización</button>{rejected&&<button className={button} disabled={busy} onClick={closeRejected}>Cerrar rechazo y actualizar</button>}</div>
  </div>:selected?<form onSubmit={submit} className="space-y-3 rounded border border-[var(--work-line)] p-3">
   <h4 className="font-semibold">Autorizar una sucesora del cálculo seleccionado</h4><p className="break-all">Original: {selected.operation_id}</p>
   {selected.diagnosis.code==='restored_history'&&<p>Trabajarás sobre la copia restaurada, con permisos nuevos en esta instalación. El estado actual del host original no se comprobó. Su historial y consumo se conservan.</p>}
   <p>La próxima solicitud idéntica del usuario o de un agente con permisos vigentes podrá realizar un nuevo cálculo. Guardar esta autorización no lo inicia ni reanuda un intento detenido.</p>
   <p>La reserva anterior de {selected.cpu_ceiling_ms.toLocaleString()} ms se conserva. Por ejemplo: si quedó una reserva desconocida de 3.000 ms, otra de 3.000 ms necesitará capacidad adicional; no sustituye la primera.</p>
   <p>Para usarla, vuelve a solicitar la misma búsqueda o vista previa con el mismo contenido. Si cambian los datos o el procesador, será un cálculo distinto.</p>
   <label className="block">Motivo de la continuación (opcional)<textarea className="min-h-20 w-full rounded border border-[var(--work-line)] bg-[var(--work-paper)] p-2" maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
   <div className="flex gap-2"><button className={button} disabled={!ready||busy||!!query.error} type="submit">Guardar autorización</button><button className={button} type="button" onClick={()=>setSelected(null)}>Cancelar</button></div>
  </form>:null}
  {open&&<>
   <p>Consulta qué se guardó y si el proceso anterior terminó. Las observaciones pueden cambiar; el servidor vuelve a comprobar el cierre al autorizar.</p>
   <button className={button} onClick={()=>query.refetch()}>Actualizar cálculos</button>
   {query.isPending&&<p role="status">Consultando cálculos…</p>}{query.error&&<p role="alert">No se pudo consultar el historial. {query.error.message}</p>}
   {page&&<>{page.items.length===0&&<p>Todavía no hay cálculos locales registrados.</p>}<ol className="space-y-3">{page.items.map(row=><li key={row.operation_id} className="space-y-2 border-t border-[var(--work-line)] pt-3">
    <h4 className="font-semibold">{row.kind==='semantic'?'Búsqueda local':`Procesamiento ${row.kind}`} · {new Date(row.created_at*1000).toLocaleString()}</h4>
    <p className="break-all">Cálculo: {row.operation_id}</p><p>{row.input_bytes.toLocaleString()} bytes de entrada. CPU: {row.observed_cpu_ms==null?`desconocida; reserva de ${row.cpu_ceiling_ms.toLocaleString()} ms`:`${row.observed_cpu_ms.toLocaleString()} ms observados`}.</p>
    <p>{row.diagnosis.message}</p>{row.diagnosis.can_continue&&!pending&&!selected&&<button className={button} disabled={!ready||!!query.error} onClick={()=>choose(row)}>Autorizar un nuevo cálculo</button>}
   </li>)}</ol><div className="flex gap-2">{before!==null&&<button className={button} onClick={()=>setBefore(null)}>Volver a los recientes</button>}{page.next_before!==null&&<button className={button} onClick={()=>setBefore(page.next_before)}>Ver cálculos anteriores</button>}</div></>}
  </>}
 </section>
}
