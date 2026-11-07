/** Explain and record project-level evidence requirements for future code acceptance. @module */
import {useEffect,useState} from 'react'
import {useMutation,useQueryClient} from '@tanstack/react-query'
import {ApiError} from '../../api/client'
import {clearCheckPolicy,loadCheckPolicy,prepareCheckPolicy,readCheckPolicyReceipt,saveCheckPolicy,sendCheckPolicy,type CheckPolicy,type CheckPolicyAction,type CheckPolicyMode,type CheckPolicyReceipt} from '../../api/projectCheckPolicy'

const button='min-h-11 rounded border border-[var(--work-line)] px-3 py-2 disabled:opacity-50'
/** Keep a pending decision tied to one project, even while candidate evidence refreshes. */
export function CheckPolicyEditor({projectId,policy,readOnly=false}:{projectId:number;policy:CheckPolicy;readOnly?:boolean}){
 const client=useQueryClient()
 const [pending,setPending]=useState<CheckPolicyAction|null>(null),[ready,setReady]=useState(false),[editing,setEditing]=useState(false)
 const [revision,setRevision]=useState(0),[mode,setMode]=useState<CheckPolicyMode>('require_tests')
 const [notice,setNotice]=useState(''),[localError,setLocalError]=useState('')
 useEffect(()=>{try{setPending(loadCheckPolicy(sessionStorage,projectId));setReady(true)}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo recuperar la decisión.')}},[projectId])
 /** Resolve the original packet and refresh evidence without starting checks or acceptance. */
 function resolved(_receipt:CheckPolicyReceipt,action:CheckPolicyAction){try{clearCheckPolicy(sessionStorage,action);setPending(null);setEditing(false);setNotice('Política guardada para aceptaciones nuevas. No se ejecutaron pruebas ni se aceptó código.');client.invalidateQueries({queryKey:['code-result',projectId]})}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo cerrar la decisión local.')}}
 const save=useMutation({mutationFn:sendCheckPolicy,onSuccess:resolved}),recover=useMutation({mutationFn:readCheckPolicyReceipt,onSuccess:resolved})
 const busy=save.isPending||recover.isPending,rejected=save.error instanceof ApiError&&[400,409,422].includes(save.error.status)
 /** Capture the displayed revision once; refreshed policy cannot silently rebase this edit. */
 function edit(){setRevision(policy.revision);setMode(policy.mode??'require_tests');setEditing(true);setNotice('');save.reset();recover.reset()}
 /** Save the complete decision before making the only initial POST. */
 function submit(event:React.FormEvent){event.preventDefault();try{const action=prepareCheckPolicy(projectId,revision,mode);saveCheckPolicy(sessionStorage,action);setPending(action);save.mutate(action)}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo guardar la decisión.')}}
 /** A definite refusal can be closed before a new, freshly observed owner choice. */
 async function closeRejected(){if(!pending)return;try{clearCheckPolicy(sessionStorage,pending);setPending(null);setEditing(false);save.reset();recover.reset();await client.resetQueries({queryKey:['code-result',projectId]})}catch(e){setLocalError(e instanceof Error?e.message:'No se pudo cerrar la decisión rechazada.')}}
 return <section className="space-y-2 rounded border border-[var(--work-line)] p-3 text-sm" aria-label="Política de comprobaciones del proyecto">
  <h4 className="font-medium">Qué pruebas exige este proyecto</h4>
  <p>{policy.mode==='require_tests'?'Se exigen pruebas ejecutadas y satisfactorias, sin omisiones.':policy.mode==='allow_missing'?'Se permite aceptar con pruebas ausentes u omitidas, reconociendo ese límite en cada entrega.':'Todavía no elegiste una política para aceptar código en este proyecto.'}</p>
  <p>Un fallo o una revisión rechazada siempre bloquea la aceptación. Cambiar esta política conserva las decisiones históricas.</p>
  {notice&&<p role="status">{notice}</p>}{localError&&<p role="alert">{localError}</p>}
  {pending?<div className="space-y-2">
   <p>Decisión pendiente sobre revisión {pending.body.expected_revision}: {pending.body.mode==='require_tests'?'exigir pruebas':'permitir límites reconocidos'}. Conservamos la solicitud original.</p>
   {save.error&&<p role="alert">No se confirmó el cambio. {save.error.message}</p>}{recover.error&&<p role="alert">No se pudo recuperar el recibo. {recover.error.message}</p>}
   <div className="flex flex-wrap gap-2"><button className={button} disabled={busy} onClick={()=>recover.mutate(pending)}>Consultar recibo de la política</button>{rejected?<button className={button} disabled={busy||readOnly} onClick={closeRejected}>Cerrar decisión rechazada</button>:<button className={button} disabled={busy||readOnly} onClick={()=>save.mutate(pending)}>Enviar la misma política</button>}</div>
  </div>:editing?<form className="space-y-2" onSubmit={submit}>
   <label className="block">Requisito para nuevas aceptaciones<select className="mt-1 min-h-11 w-full rounded border border-[var(--work-line)] bg-[var(--work-paper)] px-2" value={mode} onChange={e=>setMode(e.target.value as CheckPolicyMode)}><option value="require_tests">Exigir pruebas ejecutadas, sin fallos ni omisiones</option><option value="allow_missing">Permitir ausencia u omisiones con reconocimiento explícito</option></select></label>
   <p>Por ejemplo, «el comando terminó bien» no demuestra que se ejecutaran pruebas. Con la primera opción, esa entrega sigue bloqueada.</p>
   <p>Revisión consultada: {revision}. Guardar sólo cambia el requisito del proyecto.</p>
   <div className="flex flex-wrap gap-2"><button className={button} disabled={!ready||busy||readOnly}>Guardar política</button><button type="button" className={button} onClick={()=>setEditing(false)}>Cancelar edición</button></div>
  </form>:<button className={button} disabled={!ready||readOnly} onClick={edit}>Elegir política de pruebas</button>}
 </section>
}
