/** Owner inspection and explicit selection of exact earlier code as data for the next request. @module */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { priorCodeInput, priorPatchText } from '../../api/runtime'
import type { PriorMaterialSelection, RuntimeRun } from '../../api/runtime'

/** Keep prior input visible and correctable without treating old requirements or checks as current authority. */
export function PriorCodeInput({projectId,taskId,runs,selected,locked,onSelect}:{projectId:number;taskId:number;runs:RuntimeRun[];selected:Readonly<PriorMaterialSelection>|null;locked:boolean;onSelect:(target:Readonly<PriorMaterialSelection>|null)=>void}) {
  const [attemptId,setAttemptId]=useState('')
  const previous=runs.filter(run=>run.execution_kind==='development'&&run.attempt_id)
  const preview=useQuery({queryKey:['prior-code',projectId,taskId,attemptId],queryFn:()=>priorCodeInput(projectId,taskId,attemptId),enabled:!!attemptId,retry:false})
  if(!previous.length)return null
  const packet=preview.data
  const patch=packet?priorPatchText(packet.snapshot.diff_base64):null
  return <section className="space-y-2 rounded-md border border-[var(--work-line)] p-3" aria-label="Reutilizar cambios anteriores">
    <h4 className="font-medium">Reutilizar cambios anteriores</h4>
    <p className="text-[var(--work-muted)]">Puedes tomar un candidato anterior como punto de partida. Por ejemplo, conservar su implementación y adaptarla a una corrección nueva. Sus pruebas y su aprobación no se trasladan.</p>
    <label className="block">Cambios guardados<select className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" value={attemptId} disabled={locked} onChange={event=>{setAttemptId(event.target.value);onSelect(null)}}>
      <option value="">Iniciar sin seleccionar cambios anteriores</option>
      {previous.map(run=><option key={run.run_id} value={run.attempt_id!}>Contexto {run.context_version} · {run.prompt.slice(0,90)} · {run.run_id.slice(0,8)}</option>)}
    </select></label>
    {attemptId&&preview.isPending&&<p role="status">Recuperando los cambios y su entrada original…</p>}
    {attemptId&&preview.error&&<div role="alert"><p>No se pudieron comprobar estos cambios. No se seleccionaron para la solicitud. {preview.error.message}</p><button type="button" onClick={()=>preview.refetch()}>Volver a consultar</button></div>}
    {attemptId&&packet&&<>
      <p>Contexto original {packet.snapshot.origin.context_version} · {packet.snapshot.diff_bytes} bytes de diff · repositorio {packet.snapshot.origin.repository_id}</p>
      <p className="text-[var(--work-muted)]">La solicitud y la base Git anteriores pueden diferir de las actuales. Revisa qué quieres conservar en la solicitud nueva. Si hay trabajo activo, detén esa ejecución antes de iniciar otra.</p>
      <details><summary>Solicitud, base y cambios originales</summary>
        <p className="whitespace-pre-wrap">{packet.snapshot.original_input.request}</p>
        <p className="break-all">Base original: {packet.snapshot.candidate.base_sha}</p>
        {patch===null?<p>El diff contiene bytes que no se pueden mostrar como UTF-8. Descárgalo para inspeccionarlo completo.</p>:<pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{patch}</pre>}
        <a download={`cambios-${attemptId}.patch`} href={`data:application/octet-stream;base64,${packet.snapshot.diff_base64}`}>Descargar los bytes originales del diff</a>
        <details><summary>Contexto completo que recibió el autor anterior</summary><pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(packet.snapshot.original_input,null,2)}</pre></details>
      </details>
      <button type="button" disabled={locked} className="rounded-md border border-[var(--work-line)] px-3 py-2 disabled:opacity-50" onClick={()=>onSelect(Object.freeze({attempt_id:attemptId,snapshot_sha256:packet.snapshot_sha256}))}>Usar estos cambios en la próxima solicitud</button>
      {selected&&'attempt_id'in selected&&<p role="status">Cambios seleccionados. Se entregarán como material al autor nuevo; el inicio necesita la solicitud de abajo.</p>}
    </>}
  </section>
}
