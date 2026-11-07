/** Owner budget changes preserve original pending identity and leave execution controls separate. @module */
import {useEffect,useState} from 'react'
import {useMutation,useQueryClient} from '@tanstack/react-query'
import {ApiError} from '../../api/client'
import type {ProjectWorkBudget} from '../../api/history'
import {clearBudgetAction,loadBudgetAction,prepareBudgetChange,readBudgetReceipt,saveBudgetAction,sendBudgetChange,type BudgetAction,type BudgetReceipt} from '../../api/projectBudget'

const button='min-h-11 rounded border border-[var(--work-line)] px-3 py-2 disabled:opacity-50'
const input='min-h-11 w-full rounded border border-[var(--work-line)] bg-[var(--work-paper)] px-3'
/** Edit one project's total allowance with a frozen revision, persistent uncertain decision and read-only recovery. */
export function BudgetPolicyEditor({budget,fresh}:{budget:ProjectWorkBudget;fresh:boolean}){
 const projectId=budget.project_id,client=useQueryClient()
 const [pending,setPending]=useState<BudgetAction|null>(null),[ready,setReady]=useState(false),[editing,setEditing]=useState(false)
 const [turns,setTurns]=useState(''),[tokens,setTokens]=useState(''),[reason,setReason]=useState(''),[revision,setRevision]=useState(0)
 const [local,setLocal]=useState(false),[operations,setOperations]=useState(''),[cpuMs,setCpuMs]=useState('')
 const [notice,setNotice]=useState(''),[localError,setLocalError]=useState('')
 useEffect(()=>{try{setPending(loadBudgetAction(sessionStorage,projectId));setReady(true)}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo recuperar la decisión guardada.')}},[projectId])
 /** Resolve only the packet that produced this receipt and refresh this project's view. */
 function resolved(_receipt:BudgetReceipt,action:BudgetAction){try{clearBudgetAction(sessionStorage,action);setPending(null);setEditing(false);setNotice('Límites guardados. No se inició trabajo ni se cambiaron los límites de intentos ya reservados.');client.invalidateQueries({queryKey:['work-budget',projectId]})}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo cerrar la decisión guardada.')}}
 const save=useMutation({mutationFn:sendBudgetChange,onSuccess:resolved}),recover=useMutation({mutationFn:readBudgetReceipt,onSuccess:resolved})
 const busy=save.isPending||recover.isPending,rejected=save.error instanceof ApiError&&[400,409,422].includes(save.error.status)
 /** Capture the observed version once; background queries cannot silently rebase an open edit. */
 function edit(){setRevision(budget.policy?.revision??0);setTurns(budget.policy?String(budget.policy.turn_limit):'');setTokens(budget.policy?String(budget.policy.token_limit):'');setLocal(!!budget.auxiliary);setOperations(String(budget.auxiliary?.policy.operation_limit??''));setCpuMs(String(budget.auxiliary?.policy.cpu_ms_limit??''));setReason('');setEditing(true);setNotice('');setLocalError('');save.reset();recover.reset()}
 /** Persist the complete original before the first POST; invalid input or failed storage sends nothing. */
 function submit(event:React.FormEvent){event.preventDefault();try{const action=prepareBudgetChange(projectId,revision,Number(turns),Number(tokens),reason,local?{operations:Number(operations),cpuMs:Number(cpuMs)}:undefined);saveBudgetAction(sessionStorage,action);setPending(action);save.mutate(action)}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo guardar la decisión original.')}}
 /** A definitive rejection permits a fresh read and a new explicit decision, never automatic reapplication. */
 async function closeRejected(){if(!pending)return;try{clearBudgetAction(sessionStorage,pending);setPending(null);setEditing(false);save.reset();recover.reset();await client.resetQueries({queryKey:['work-budget',projectId]})}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo cerrar la decisión rechazada.')}}
 return <div className="space-y-3 pt-2">
  {notice&&<p role="status">{notice}</p>}{localError&&<p role="alert">{localError}</p>}
  {pending?<div className="space-y-2 rounded border border-[var(--work-line)] p-3">
   <p>Decisión guardada: límite total de {pending.body.turn_limit} turnos y {pending.body.token_limit} tokens, sobre revisión {pending.body.expected_revision}.</p>
   {pending.body.auxiliary_operation_limit!==undefined&&<p>Procesamiento local: {pending.body.auxiliary_operation_limit} cálculos y {pending.body.auxiliary_cpu_ms_limit} ms de CPU totales.</p>}
   <p>Conservamos esta solicitud hasta comprobar su resultado. Consultar el recibo no vuelve a enviarla.</p>
   {save.error&&<p role="alert">No se confirmó el cambio. {save.error.message}</p>}
   {recover.error&&<p role="alert">No se pudo recuperar el recibo. {recover.error.message}</p>}
   <div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={()=>recover.mutate(pending)}>Consultar recibo original</button>
   {rejected?<button className={button} disabled={busy} onClick={closeRejected}>Cerrar decisión rechazada</button>:<button className={button} disabled={busy} onClick={()=>save.mutate(pending)}>Enviar la misma decisión</button>}</div>
  </div>:editing?<form onSubmit={submit} className="space-y-3 rounded border border-[var(--work-line)] p-4">
   <p>Revisión consultada: {revision}. Los límites son totales del proyecto. El consumo registrado se conserva y los intentos en curso mantienen sus límites.</p>
   <p>Guardar no envía un turno ni reanuda tareas detenidas. El trabajo previamente autorizado puede usar el límite cuando solicite iniciar el siguiente intento.</p>
   <div className="grid gap-3 sm:grid-cols-2"><label>Límite total de turnos<input className={input} type="number" min="1" max={Number.MAX_SAFE_INTEGER} step="1" required value={turns} onChange={e=>setTurns(e.target.value)}/></label>
   <label>Límite total de tokens<input className={input} type="number" min="1" max={Number.MAX_SAFE_INTEGER} step="1" required value={tokens} onChange={e=>setTokens(e.target.value)}/></label></div>
   {local&&<div className="grid gap-3 sm:grid-cols-2"><label>Límite total de cálculos locales<input className={input} type="number" min="1" max={Number.MAX_SAFE_INTEGER} step="1" required value={operations} onChange={e=>setOperations(e.target.value)}/></label><label>Límite total de CPU local (ms)<input className={input} type="number" min="1" max={Number.MAX_SAFE_INTEGER} step="1" required value={cpuMs} onChange={e=>setCpuMs(e.target.value)}/></label></div>}
   <label className="block">Motivo del cambio (opcional)<textarea className={input} rows={2} maxLength={2000} value={reason} onChange={e=>setReason(e.target.value)}/></label>
   <p>Si el total queda por debajo de lo contabilizado, la capacidad restante será cero. El historial conservará el exceso.</p>
   <div className="flex flex-wrap gap-2"><button className={button} type="submit" disabled={!ready||busy}>Guardar límites</button><button className={button} type="button" onClick={()=>setEditing(false)}>Cancelar edición</button></div>
  </form>:<button className={button} disabled={!ready||!fresh} onClick={edit}>Revisar límites</button>}
 </div>
}
