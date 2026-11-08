/** Read bounded command receipts and paginate retained bytes without executing commands. @module */
import { useEffect, useId, useRef, useState } from 'react'
import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { commandList, commandOutput } from '../../api/runtime'
import type { CommandSummary, CommandWindow } from '../../api/runtime'

const buttonClass = 'rounded-md border border-[var(--work-line)] px-3 py-2 text-sm text-[var(--work-ink)] hover:bg-[var(--work-wash)] disabled:opacity-50'
const blockClass = 'max-h-72 overflow-auto whitespace-pre-wrap break-words rounded-md bg-[var(--work-wash)] p-3 text-xs text-[var(--work-ink)]'
const windowBytes = 8192

/** Expose terminal and bidirectional controls without changing the original retained bytes. */
function visibleText(text: string) {
  // Preserve original bytes in the receipt; do not let terminal/bidi controls
  // visually rewrite a read-only explanation. HTML remains React-escaped text.
  return text.replace(/[\u0000-\u0008\u000b-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/g,
    value => `\\u${value.charCodeAt(0).toString(16).padStart(4, '0')}`)
}

/** Distinguish the process result, local closure evidence and historical attempt scope. */
function CommandState({command}: {command: CommandSummary}) {
  return <div className="space-y-1 text-[var(--work-muted)]">
    <p>{command.status === 'dispatching' ? 'En ejecución' : command.status === 'cancelling' ? 'Cancelación solicitada' : command.exit_code == null ? 'Resultado desconocido' : `Código de salida ${command.exit_code}`}</p>
    <p>{command.local_execution_closed ? 'Cierre local registrado' : 'Cierre sin comprobar'}</p>
    {!command.is_current_attempt && <p>Registro de un intento anterior.</p>}
  </div>
}

/** Show one retained byte window with named navigation and original-byte access. */
function OutputStream({label, window, busy, change}: {label: string; window: CommandWindow; busy: boolean; change: (offset: number) => void}) {
  return <section className="space-y-2" aria-label={label} aria-busy={busy}>
    <h5 className="font-medium text-[var(--work-ink)]">{label}</h5>
    <p className="text-xs text-[var(--work-muted)]">{window.next_offset > window.offset
      ? `Bytes ${window.offset + 1}–${window.next_offset} de ${window.total_bytes} guardados`
      : `Sin bytes en esta ventana · ${window.total_bytes} guardados`}</p>
    {window.text && <pre tabIndex={0} aria-label={`Texto de ${label.toLowerCase()}`} className={blockClass}>{visibleText(window.text)}</pre>}
    {window.utf8_lossy && <p className="text-[var(--work-caution)]">La vista UTF-8 incluye reemplazos: puede haber bytes no válidos o un carácter cortado entre ventanas. El base64 conserva los bytes originales.</p>}
    {window.has_more && <p className="text-[var(--work-muted)]">Hay más bytes guardados para consultar.</p>}
    {window.total_bytes > 0 && <details><summary className="cursor-pointer text-[var(--work-accent)]">Bytes originales de esta ventana (base64)</summary><pre tabIndex={0} className={blockClass}>{window.base64}</pre></details>}
    <div className="flex flex-wrap gap-2">
      <button type="button" className={buttonClass} disabled={busy || window.offset === 0} aria-label={`Inicio de ${label.toLowerCase()}`} onClick={() => change(0)}>Inicio</button>
      <button type="button" className={buttonClass} disabled={busy || window.offset === 0} aria-label={`Anterior: bytes de ${label.toLowerCase()}`} onClick={() => change(Math.max(0, window.offset - windowBytes))}>Anterior</button>
      <button type="button" className={buttonClass} disabled={busy || !window.has_more} aria-label={`Siguiente: bytes de ${label.toLowerCase()}`} onClick={() => change(window.next_offset)}>Siguiente</button>
      <button type="button" className={buttonClass} disabled={busy || !window.has_more} aria-label={`Últimos bytes de ${label.toLowerCase()}`} onClick={() => change(Math.max(0, window.total_bytes - windowBytes))}>Últimos bytes</button>
    </div>
  </section>
}

type ReceiptProps = {projectId:number;runId:string;jobId:string;enabled?:boolean}

/** Reset receipt presentation whenever project, run or command ownership changes. */
export function CommandReceipt(props: ReceiptProps) {
  // Reset offsets and placeholder data when changing owner scope or job.
  return <ReceiptScope key={`${props.projectId}:${props.runId}:${props.jobId}`} {...props} />
}

/** Fetch owner-scoped output windows and retain explicit read-error and capture-loss states. */
function ReceiptScope({projectId,runId,jobId,enabled = true}: ReceiptProps) {
  const [stdoutOffset,setStdoutOffset] = useState(0)
  const [stderrOffset,setStderrOffset] = useState(0)
  const query = useQuery({
    queryKey:['command-output',projectId,runId,jobId,stdoutOffset,stderrOffset],
    queryFn:() => commandOutput(projectId,runId,jobId,{stdoutOffset,stderrOffset}),
    enabled,retry:false,placeholderData:keepPreviousData,
    refetchInterval:state => enabled && state.state.error == null && !state.state.data?.local_execution_closed ? 3000 : false,
  })
  const data=query.data
  return <section className="space-y-3 rounded-md border border-[var(--work-line)] p-3" aria-label="Recibo del comando">
    {query.isPending && <p role="status">Consultando la salida guardada…</p>}
    {query.error && <div role="alert"><p>No se pudo consultar esta ventana. Los datos que se conserven en pantalla son los últimos recuperados.</p><button type="button" className={buttonClass} onClick={() => query.refetch()}>Volver a consultar salida</button></div>}
    {query.isPlaceholderData && <p role="status">Consultando otra ventana; los bytes mostrados todavía corresponden a la anterior.</p>}
    {data && <>
      <h4 className="font-medium text-[var(--work-ink)]">{data.executable} · contexto {data.context_version}</h4>
      <CommandState command={data} />
      <p className="text-[var(--work-muted)]">El código de salida y el cierre registrado son hechos distintos. No confirman la validez del análisis ni la aceptación de la tarea.</p>
      <p className="text-[var(--work-muted)]">La salida se guarda al terminar o perder seguimiento del comando. Mientras trabaja puede estar vacía. Consultarla no repite el comando.</p>
      {data.output_limited && <p className="text-[var(--work-caution)]">Se alcanzó el límite de captura. El resto no quedó guardado; recorrer estas ventanas sólo recupera los bytes conservados.</p>}
      <details><summary className="cursor-pointer text-[var(--work-accent)]">Argumentos y límites registrados</summary><p className="mt-2 text-[var(--work-muted)]">Carpeta relativa: {visibleText(data.cwd)} · máximo {data.timeout_seconds} segundos · {data.output_bytes} bytes por salida</p><pre tabIndex={0} className={blockClass}>{JSON.stringify(data.argv,null,2)}</pre><p className="break-all text-xs text-[var(--work-muted)]">Operación: {data.operation_key} · comando: {data.job_id}</p></details>
      <OutputStream label="Salida estándar" window={data.stdout} busy={query.isPlaceholderData} change={setStdoutOffset} />
      <OutputStream label="Salida de errores" window={data.stderr} busy={query.isPlaceholderData} change={setStderrOffset} />
      <button type="button" className={buttonClass} disabled={query.isFetching} onClick={() => query.refetch()}>Consultar recibo</button>
    </>}
  </section>
}

/** Reset the command catalog when its project or run changes. */
export function RunCommands(props: {projectId:number;runId:string}) {
  return <RunCommandsScope key={`${props.projectId}:${props.runId}`} {...props} />
}

/** Browse the bounded retained command catalog and open a read-only receipt. */
function RunCommandsScope({projectId,runId}: {projectId:number;runId:string}) {
  const [open,setOpen] = useState(false)
  const [cursors,setCursors] = useState(['0'])
  const [selected,setSelected] = useState<string | null>(null)
  const region = useRef<HTMLDivElement>(null)
  const receiptId = useId()
  const afterSeq=cursors[cursors.length - 1]
  const query=useQuery({queryKey:['run-commands',projectId,runId,afterSeq],queryFn:() => commandList(projectId,runId,afterSeq),
    enabled:open,retry:false,placeholderData:keepPreviousData,
    refetchInterval:state => open && state.state.error == null ? 3000 : false})
  const data=query.data
  useEffect(() => {if (selected) region.current?.focus()},[selected])
  return <details className="space-y-3 rounded-md border border-[var(--work-line)] p-3" onToggle={event => {
    if (event.target === event.currentTarget) setOpen(event.currentTarget.open)
  }}>
    <summary className="cursor-pointer font-medium text-[var(--work-ink)]">Comandos y resultados guardados</summary>
    <p className="text-[var(--work-muted)]">Esta consulta conserva los recibos y no repite comandos. Está disponible aunque la ejecución se haya detenido.</p>
    {open && query.isPending && <p role="status">Consultando comandos…</p>}
    {query.error && <div role="alert"><p>No se pudo consultar la lista.</p><button type="button" className={buttonClass} onClick={() => query.refetch()}>Volver a consultar comandos</button></div>}
    {query.isPlaceholderData && <p role="status">Consultando otra página; se conserva la anterior mientras llega.</p>}
    {data && <>
      <p className="text-[var(--work-muted)]">{data.total} comandos registrados</p>
      {data.total === 0 && <p className="text-[var(--work-muted)]">Esta ejecución no tiene recibos de comandos.</p>}
      <ul className="space-y-2">{data.items.map(command => <li key={command.job_id} className="space-y-1 border-t border-[var(--work-line)] pt-2">
        <p className="font-medium text-[var(--work-ink)]">{visibleText(command.executable)} · contexto {command.context_version}</p>
        <CommandState command={command} />
        <p className="text-xs text-[var(--work-muted)]">{command.stdout_bytes} bytes de salida · {command.stderr_bytes} de errores</p>
        <button type="button" className={buttonClass} aria-expanded={selected === command.job_id} aria-controls={selected === command.job_id ? receiptId : undefined}
          onClick={() => setSelected(selected === command.job_id ? null : command.job_id)}>{selected === command.job_id ? 'Cerrar salida' : 'Ver salida'}</button>
      </li>)}</ul>
      <div className="flex flex-wrap gap-2">
        <button type="button" className={buttonClass} disabled={cursors.length < 2 || query.isPlaceholderData} onClick={() => {setSelected(null);setCursors(cursors.slice(0,-1))}}>Comandos anteriores</button>
        <button type="button" className={buttonClass} disabled={data.next_after_seq == null || query.isPlaceholderData} onClick={() => {
          if (data.next_after_seq != null) {setSelected(null);setCursors([...cursors,data.next_after_seq])}
        }}>Siguientes comandos</button>
        <button type="button" className={buttonClass} disabled={query.isFetching} onClick={() => query.refetch()}>Consultar lista</button>
      </div>
    </>}
    {selected && <div id={receiptId} ref={region} tabIndex={-1} role="region" aria-label="Salida del comando seleccionado"><CommandReceipt projectId={projectId} runId={runId} jobId={selected} enabled={open} /></div>}
  </details>
}
