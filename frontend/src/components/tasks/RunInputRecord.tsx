import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { runInput } from '../../api/runtime'

export function RunInputRecord({ projectId, runId }: { projectId: number; runId: string }) {
  const [open, setOpen] = useState(false)
  const query = useQuery({queryKey:['run-input',projectId,runId],queryFn:() => runInput(projectId,runId),enabled:open,retry:false,refetchInterval:open ? 3000 : false})
  const record = query.data
  const input = record?.available ? JSON.parse(record.input_text) : null
  return <details className="space-y-2 rounded-md border border-[var(--work-line)] p-3" onToggle={event => setOpen(event.currentTarget.open)}>
    <summary className="cursor-pointer font-medium text-[var(--work-ink)]">Entrada de esta ejecución</summary>
    {query.isFetching && <p role="status">Recuperando el registro…</p>}
    {query.error && <div role="alert"><p>No se pudo recuperar la entrada.</p><button onClick={() => query.refetch()}>Volver a consultar</button></div>}
    {record && !record.available && <p>No hay un registro de entrada para esta ejecución. No reconstruiremos qué recibió a partir de su resultado.</p>}
    {record?.available && <>
      <p className="text-[var(--work-muted)]">Registro preparado bajo contexto {input.context_version}. Incluye {input.conversation.messages.length} mensajes anteriores de la conversación elegida.</p>
      {input.conversation.other_task_messages_excluded > 0 && <p>Quedaron fuera {input.conversation.other_task_messages_excluded} mensajes de otras tareas.</p>}
      <p>{record.native_start_observed ? 'El motor confirmó el comienzo del turno.' : 'No hay un comienzo confirmado del turno en este registro.'} Esto no confirma que el modelo haya comprendido o aplicado todo el contenido.</p>
      <p>El registro contiene la entrada inicial preparada por Researcher. Los resultados posteriores de herramientas y las instrucciones internas del proveedor tienen otro alcance.</p>
      <details><summary className="cursor-pointer text-[var(--work-accent)]">Ver entrada literal</summary><pre tabIndex={0} className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words text-xs">{record.input_text}</pre></details>
      <details><summary className="cursor-pointer text-[var(--work-accent)]">Instrucciones y catálogo registrados</summary><p>Modelo: {record.model ?? 'Sin registrar'}</p><pre tabIndex={0} className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{record.developer_instructions}</pre><pre tabIndex={0} className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs">{JSON.stringify(record.business_catalog,null,2)}</pre></details>
      <details><summary className="cursor-pointer text-[var(--work-accent)]">Identidad del registro</summary><p className="break-all text-xs">Entrada: {record.input_sha256}</p><p className="break-all text-xs">Instrucciones: {record.instructions_sha256}</p></details>
    </>}
  </details>
}
