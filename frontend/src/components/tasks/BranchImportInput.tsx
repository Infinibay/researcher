/** Explicit owner choice of a recorded branch/immutable commit; original owned preparation must acquire the bytes before any native turn. @module */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { branchInputSources } from '../../api/runtime'
import type { PriorMaterialSelection } from '../../api/runtime'

/** Keep branch identity edits separate from admission and explain the distinction between historical metadata and captured code. */
export function BranchImportInput({projectId,taskId,selected,locked,configured,onSelect}:{projectId:number;taskId:number;selected:Readonly<PriorMaterialSelection>|null;locked:boolean;configured:boolean;onSelect:(value:Readonly<PriorMaterialSelection>|null)=>void}) {
  const [branchId,setBranchId]=useState('')
  const [commit,setCommit]=useState('')
  const sources=useQuery({queryKey:['prior-branch-sources',projectId,taskId],queryFn:()=>branchInputSources(projectId,taskId),retry:false})
  const branch=sources.data?.find(item=>String(item.branch_id)===branchId)
  const valid=/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(commit)
  if(sources.data?.length===0)return null
  return <section className="space-y-2 rounded-md border border-[var(--work-line)] p-3" aria-label="Importar cambios de una rama anterior">
    <h4 className="font-medium">Importar cambios de una rama anterior</h4>
    <p className="text-[var(--work-muted)]">El nombre de una rama es una etiqueta que puede moverse. El commit identifica la versión concreta que quieres entregar al autor nuevo, aunque ya no exista una copia de sus archivos.</p>
    {sources.isPending&&<p role="status">Consultando las ramas registradas…</p>}
    {sources.error&&<div role="alert"><p>No se pudieron consultar los registros. {sources.error.message}</p><button type="button" onClick={()=>sources.refetch()}>Volver a consultar</button></div>}
    <label className="block">Rama registrada<select className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" value={branchId} disabled={locked} onChange={event=>{setBranchId(event.target.value);setCommit('');onSelect(null)}}>
      <option value="">Elige una rama anterior</option>
      {sources.data?.map(item=><option key={item.branch_id} value={item.branch_id}>{item.branch} · repositorio {item.repository_id} · {item.recorded_status}</option>)}
    </select></label>
    {branch?.recorded_commit_sha&&<p className="break-all">El registro histórico conserva este commit: <code>{branch.recorded_commit_sha}</code>. Todavía no se comprobó que siga siendo la punta de la rama.</p>}
    <label className="block">Commit exacto<input className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2 font-mono text-xs" value={commit} disabled={locked||!branch} spellCheck={false} placeholder="SHA completo de 40 o 64 caracteres" onChange={event=>{setCommit(event.target.value.trim());onSelect(null)}}/></label>
    <p>Al iniciar, el motor comprobará ese commit y capturará todos sus cambios respecto de la base actual. Si la rama cambió, falta material o excede los límites, se detendrá antes del modelo. No se aplican automáticamente sus archivos ni se heredan pruebas o aprobación.</p>
    {branch&&<p>Elige el repositorio {branch.repository_id} al iniciar. En la solicitud explica qué conservar o adaptar. Por ejemplo: «Revisa el cambio anterior de unidades y adáptalo a los requisitos actuales».</p>}
    {!configured&&<p>Configura el motor local antes de iniciar la captura. Los registros permanecen disponibles para inspección.</p>}
    <button type="button" className="rounded-md border border-[var(--work-line)] px-3 py-2 disabled:opacity-50" disabled={locked||!configured||!branch||!valid} onClick={()=>onSelect(Object.freeze({source_kind:'legacy_branch',branch_id:branch!.branch_id,commit_sha:commit}))}>Usar este commit como material para el próximo intento</button>
    {selected&&'commit_sha'in selected&&<p role="status">Commit seleccionado; los bytes aún se capturarán al iniciar. Esta selección no inicia trabajo ni acepta o publica cambios.</p>}
  </section>
}
