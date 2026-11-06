/** Explicit selection and inspection of old file data, with unknown historical context stated before new work. @module */
import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { fileImportSources, previewFileImport, priorPatchText } from '../../api/runtime'
import type { PriorMaterialSelection } from '../../api/runtime'

/** Bind preview results to their actual source/path query; a late response cannot select material for changed input. */
export function FileImportInput({projectId,taskId,selected,locked,configured,onSelect}:{projectId:number;taskId:number;selected:Readonly<PriorMaterialSelection>|null;locked:boolean;configured:boolean;onSelect:(value:Readonly<PriorMaterialSelection>|null)=>void}) {
  const [sourceKey,setSourceKey]=useState('')
  const [pathText,setPathText]=useState('')
  const sources=useQuery({queryKey:['prior-file-sources',projectId,taskId],queryFn:()=>fileImportSources(projectId,taskId),retry:false})
  const source=sources.data?.find(item=>`${item.source_kind}:${item.source_id}`===sourceKey)
  const paths=pathText.split('\n').filter(Boolean)
  const preview=useQuery({queryKey:['prior-files-preview',projectId,taskId,sourceKey,pathText],queryFn:()=>previewFileImport(projectId,taskId,{source_kind:source!.source_kind,source_id:source!.source_id,paths,repository_id:source!.repository_id}),enabled:false,retry:false})
  const packet=preview.data
  if(sources.data?.length===0)return null
  return <section className="space-y-2 rounded-md border border-[var(--work-line)] p-3" aria-label="Importar archivos de trabajo anterior">
    <h4 className="font-medium">Importar archivos de trabajo anterior</h4>
    <p className="text-[var(--work-muted)]">Elige un origen registrado y las rutas que quieres revisar. Por ejemplo, <code>src/calculo.py</code> y <code>tests/test_calculo.py</code>. Los demás archivos quedan fuera de la selección.</p>
    {sources.isPending&&<p role="status">Consultando los orígenes registrados…</p>}
    {sources.error&&<div role="alert"><p>No se pudieron consultar los orígenes anteriores. {sources.error.message}</p><button type="button" onClick={()=>sources.refetch()}>Volver a consultar</button></div>}
    <label className="block">Origen<select className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" disabled={locked} value={sourceKey} onChange={event=>{setSourceKey(event.target.value);onSelect(null)}}>
      <option value="">Elige un origen anterior</option>
      {sources.data?.map(item=><option key={`${item.source_kind}:${item.source_id}`} value={`${item.source_kind}:${item.source_id}`}>{item.source_kind==='legacy_worktree'?'Worktree registrado':'Copia privada'} · {item.label} · repositorio {item.repository_id}</option>)}
    </select></label>
    <label className="block">Rutas relativas, una por línea<textarea className="w-full rounded-md border border-[var(--work-line)] bg-[var(--work-paper)] p-2" rows={3} value={pathText} disabled={locked} onChange={event=>{setPathText(event.target.value);onSelect(null)}}/></label>
    {source?.source_kind==='legacy_worktree'&&<p>El registro pertenece al agente indicado. Eso no demuestra que sus archivos correspondieran a esta tarea: estás eligiendo usarlos aquí.</p>}
    {!configured&&<p>Configura el motor local para comprobar estos archivos. La lista de registros permanece disponible.</p>}
    <button type="button" className="rounded-md border border-[var(--work-line)] px-3 py-2 disabled:opacity-50" disabled={locked||!configured||!source||!paths.length||preview.isFetching} onClick={()=>preview.refetch()}>{preview.isFetching?'Comprobando archivos…':'Inspeccionar archivos seleccionados'}</button>
    {preview.error&&<p role="alert">No se pudo comprobar esta selección. No se iniciará trabajo desde ella. {preview.error.message}</p>}
    {packet&&source&&<>
      <p>{packet.snapshot.original_input_status==='unknown'?'No hay un registro de lo que recibió el autor anterior. Su contexto permanece desconocido.':'Existe una entrada original guardada; se conserva separada de los requisitos actuales.'}</p>
      <p className="text-[var(--work-muted)]">Se capturaron las rutas elegidas. Una ruta ausente no demuestra intención de borrarla; explica qué quieres hacer en la solicitud nueva. No se heredan pruebas ni aprobación.</p>
      {packet.snapshot.files.map(file=><details key={file.path} className="rounded-md border border-[var(--work-line)] p-2"><summary>{file.path} · {file.kind==='missing'?'ausente':file.kind==='symlink'?'enlace sin seguir':`${file.bytes} bytes`}</summary>
        {file.kind==='missing'?<p>Ausencia observada en ese origen; no se atribuye una intención de borrado.</p>:<>
          <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">{priorPatchText(file.content_base64??file.target_base64!)??'Los bytes no se pueden mostrar como UTF-8. Descárgalos para inspeccionarlos completos.'}</pre>
          <p className="break-all text-xs">SHA-256: {file.sha256} · modo {file.git_mode}</p>
          <a download={file.path.split('/').slice(-1)[0]} href={`data:application/octet-stream;base64,${file.content_base64??file.target_base64}`}>Descargar {file.kind==='symlink'?'destino literal del enlace':'bytes originales'}</a>
        </>}
      </details>)}
      {packet.snapshot.original_input&&<details><summary>Entrada original registrada</summary><pre className="max-h-80 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(packet.snapshot.original_input,null,2)}</pre></details>}
      <p>Repositorio del material: {source.repository_id}. Elige el mismo repositorio al iniciar la solicitud.</p>
      <button type="button" className="rounded-md border border-[var(--work-line)] px-3 py-2 disabled:opacity-50" disabled={locked||preview.isFetching||!!preview.error} onClick={()=>onSelect(Object.freeze({source_kind:source.source_kind,source_id:source.source_id,paths:Object.freeze([...paths]),snapshot_sha256:packet.snapshot_sha256}))}>Usar estos archivos en la próxima solicitud</button>
      {selected&&'source_kind'in selected&&<p role="status">Archivos seleccionados como material para el autor nuevo. El inicio necesita la solicitud de abajo.</p>}
    </>}
  </section>
}
