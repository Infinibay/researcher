/** Review whole-project scope, evidence and limits before an explicit owner closure; preserve original intent after response loss. @module */
import {useEffect,useState} from 'react'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {ApiError} from '../../api/client'
import {completionActions,completionState,matchesCompletion,prepareCompletion,sendCompletion,type CompletionAction} from '../../api/projectCompletion'
import {MarkdownRenderer} from '../common/MarkdownRenderer'

const button='rounded-md border border-[var(--work-line)] px-3 py-2 text-sm disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[var(--work-accent)]'

/** Distinguish structural readiness, semantic owner review and historical acceptance; viewing the report starts no work. */
export function ProjectCompletion({projectId,taskId,runId,readOnly,onPending,onResolved}:{projectId:number;taskId:number;runId:string;readOnly:boolean;onPending:()=>void;onResolved:()=>void}){
 const client=useQueryClient(),state=useQuery({queryKey:['project-completion',projectId,runId],queryFn:()=>completionState(projectId,taskId,runId),retry:false})
 const [saved,setSaved]=useState<CompletionAction|null>(null),[ready,setReady]=useState(false),[statement,setStatement]=useState(''),[ack,setAck]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
 useEffect(()=>{try{setSaved(completionActions.load(sessionStorage,projectId,taskId,runId));setReady(true)}catch(e){setError(e instanceof Error?e.message:'No se pudo recuperar el cierre original.')}},[projectId,taskId,runId])
 /** Clear only this original request after its exact receipt is known; current validity is queried separately. */
 function resolved(action:CompletionAction){try{completionActions.clear(sessionStorage,action);setSaved(null);onResolved();setNotice('Decisión guardada. El informe conserva el alcance y los límites que revisaste.');state.refetch();client.invalidateQueries({queryKey:['projects']})}catch(e){setError(e instanceof Error?e.message:'No se pudo cerrar la solicitud local.')}}
 const mutation=useMutation({mutationFn:sendCompletion,onSuccess:(_r,a)=>resolved(a)})
 useEffect(()=>{if(saved&&state.data?.acceptance&&matchesCompletion(state.data.acceptance,saved))resolved(saved)},[state.data?.acceptance,saved])
 useEffect(()=>{setAck(false)},[state.data?.report_sha256])
 /** Persist report hash, the owner's own statement and exact unpublished candidates before sending any completion effect. */
 function submit(){try{let action=saved;if(!action){if(!state.data?.eligible||!statement.trim()||(state.data.unpublished_attempts.length&&!ack))throw new Error('Revisa el informe, declara tu decisión y reconoce los candidatos sin publicar.');action=prepareCompletion(projectId,taskId,runId,state.data.report_sha256,state.data.unpublished_attempts,statement);completionActions.save(sessionStorage,action);setSaved(action);onPending()}mutation.mutate(action)}catch(e){setError(e instanceof Error?e.message:'No se pudo guardar la decisión original.')}}
 const data=state.data,rejected=mutation.error instanceof ApiError&&[409,422].includes(mutation.error.status)
 return <section aria-label="Informe y cierre del proyecto" className="space-y-4 border-t border-[var(--work-line)] pt-4 text-sm text-[var(--work-ink)]">
  <h4 className="font-medium">Informe y cierre del proyecto</h4>
  <p className="text-[var(--work-muted)]">Plan aceptado → resultados revisados → tu decisión sobre el proyecto. El informe incluye todas las tareas del proyecto, también las que estén fuera de este plan. No convierte contadores en una prueba de que se cumplió tu intención.</p>
  <button className={button} disabled={state.isFetching} onClick={()=>state.refetch()}>Consultar informe completo</button>
  {state.isPending&&<p role="status">Reuniendo el alcance y la evidencia guardada…</p>}{state.error&&<p role="alert">No se pudo obtener el informe. {state.error.message}</p>}
  {data&&<>
   {data.acceptance&&<p role="status" className="font-medium">{data.acceptance_current?'Cierre aceptado para este alcance y evidencia.':'Hay un cierre histórico; el alcance o la evidencia cambió. La decisión anterior no demuestra un cierre vigente.'}</p>}
   <details><summary className="cursor-pointer font-medium">Leer el informe completo y sus límites</summary><div tabIndex={0} role="region" aria-label="Contenido completo del informe" className="mt-3 max-h-[36rem] overflow-auto rounded-md border border-[var(--work-line)] p-4"><MarkdownRenderer content={data.report_markdown} headingBase={5}/></div></details>
   <details><summary className="cursor-pointer">Fuentes, citas, revisiones y versiones exactas</summary><pre tabIndex={0} aria-label="Evidencia completa del informe" className="mt-2 max-h-96 overflow-auto whitespace-pre-wrap break-words text-xs">{JSON.stringify(data.snapshot,null,2)}</pre></details>
   {!!data.blockers.length&&<div className="space-y-2"><p className="font-medium">Falta resolver antes del cierre</p><ul className="list-disc space-y-1 pl-5">{data.blockers.map((item,i)=><li key={i}>{item.message}{item.task_id&&<> <a className="underline underline-offset-2" href={`/tasks?project=${projectId}&task=${item.task_id}`}>Abrir tarea {item.task_id}</a></>}</li>)}</ul></div>}
   {data.acceptance&&<details><summary className="cursor-pointer">Consultar el informe aceptado originalmente</summary><p className="my-2 whitespace-pre-wrap">Declaración del propietario: {data.acceptance.statement}</p><div tabIndex={0} role="region" aria-label="Informe histórico aceptado" className="max-h-[36rem] overflow-auto"><MarkdownRenderer content={data.acceptance.report_markdown} headingBase={5}/></div></details>}
   {data.eligible&&!saved&&<div className="space-y-3"><p>No hay impedimentos estructurales registrados. Compara el alcance original con lo entregado y explica qué estás aceptando, incluidos sus límites.</p>
    {!!data.unpublished_attempts.length&&<div className="space-y-2 rounded-md border border-[var(--work-line)] p-3"><p>Hay {data.unpublished_attempts.length} candidato(s) aceptado(s) sin publicación confirmada. Por ejemplo, aceptar una copia con valor 200 no cambia el origen que todavía contiene 137.</p><ul className="list-disc pl-5">{data.unpublished_attempts.map(id=><li className="break-all font-mono text-xs" key={id}>{id}</li>)}</ul><label className="flex items-start gap-2"><input type="checkbox" checked={ack} onChange={e=>setAck(e.target.checked)}/><span>Reconozco estos candidatos sin publicar. Cerrar el proyecto no hará merge, push ni publicación.</span></label></div>}
    <label className="block space-y-2"><span className="font-medium">Tu decisión sobre el alcance y los límites</span><textarea className="min-h-24 w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-3" maxLength={4000} value={statement} onChange={e=>setStatement(e.target.value)} placeholder="Explica qué revisaste y por qué aceptas el cierre con los límites descritos."/></label>
    <button className={button} disabled={!ready||readOnly||mutation.isPending||!statement.trim()||(!!data.unpublished_attempts.length&&!ack)} onClick={submit}>Aceptar este informe y cerrar el proyecto</button>
   </div>}
  </>}
  {saved&&<button className={button} disabled={!ready||readOnly||mutation.isPending} onClick={submit}>Recuperar la misma decisión de cierre</button>}
  {mutation.error&&<p role="alert">{rejected?'El servidor rechazó el cierre. Consulta el informe y sus impedimentos actuales.':'No se confirmó el cierre. Conservamos el informe, tu declaración y la solicitud original para recuperar su recibo.'}</p>}
  {rejected&&saved&&<button className={button} onClick={()=>{try{completionActions.clear(sessionStorage,saved);setSaved(null);onResolved();mutation.reset();state.refetch()}catch(e){setError(e instanceof Error?e.message:'No se pudo retirar la solicitud rechazada.')}}}>Descartar cierre rechazado y revisar el informe</button>}
  {error&&<p role="alert">{error}</p>}{notice&&<p role="status">{notice}</p>}
 </section>
}
