/** Global project controls use native observations and persist exact original owner requests. @module */
import { useCallback, useEffect, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { projectWorkspace, projectPackets, prepareProjectStop, sendProjectStop, type ProjectStopAction } from '../../api/projectWorkspace'
import { useStartProject } from '../../hooks/useProjects'

/** Keep pending controls scoped to one selected project; metadata labels never establish worker activity. */
export function ProjectExecutionControls({ projectId }: { projectId: number }) {
  const client = useQueryClient()
  const workspace = useQuery({ queryKey: ['project-workspace', projectId], queryFn: () => projectWorkspace(projectId), refetchInterval: 3000, retry: false })
  const start = useStartProject()
  const [savedStop, setSavedStop] = useState<ProjectStopAction | null>(null)
  const [savedStart, setSavedStart] = useState(false)
  const [storageReady, setStorageReady] = useState(false)
  const [storageError, setStorageError] = useState('')
  const [notice, setNotice] = useState('')

  /** Reconcile the shared dossier's original packet without creating or replaying an action. */
  const restorePending = useCallback(() => {
    try {
      setSavedStop(projectPackets.load(sessionStorage, 'stop', projectId))
      setSavedStart(sessionStorage.getItem(`researcher:project-plan-start:v1:${projectId}`) !== null)
      setStorageReady(true)
      setStorageError('')
    } catch (error) {
      setStorageReady(false)
      setStorageError(error instanceof Error ? error.message : 'No se pudieron recuperar las solicitudes originales.')
    }
  }, [projectId])
  useEffect(restorePending, [restorePending, workspace.dataUpdatedAt])

  /** Refresh only observations; an uncertain request is retried exclusively by explicit owner action. */
  function refresh() {
    restorePending()
    void client.invalidateQueries({ queryKey: ['project-workspace', projectId] })
    void client.invalidateQueries({ queryKey: ['task-workspace', projectId] })
    void client.invalidateQueries({ queryKey: ['agent-runs', projectId] })
  }

  const stop = useMutation({
    mutationFn: sendProjectStop,
    retry: false,
    onSuccess: (_receipt, packet) => {
      try {
        projectPackets.clear(sessionStorage, packet)
        setNotice('Detención original registrada. El cierre de los intentos aún debe comprobarse.')
      } catch (error) {
        setStorageError(error instanceof Error ? error.message : 'El recibo llegó, pero no pudimos actualizar su copia local.')
      }
      refresh()
    },
  })

  const observed = !workspace.isError ? workspace.data : undefined
  const known = !!observed
  const blocked = !storageReady || !!storageError
  const rejected = stop.error instanceof ApiError && [409, 422].includes(stop.error.status)
  const canDiscard = rejected && !!savedStop && JSON.stringify(stop.variables) === JSON.stringify(savedStop)
  const showStop = !!savedStop || (!observed?.legacy_registered && (!!observed?.stop || !known))

  /** Persist the displayed target scope, or recover the original packet even if newer work exists. */
  function requestStop() {
    setNotice('')
    try {
      let packet = projectPackets.load(sessionStorage, 'stop', projectId)
      if (!packet) {
        if (!observed?.stop || observed.legacy_registered) throw new Error('Actualiza la actividad antes de preparar una detención.')
        packet = prepareProjectStop(projectId, observed.stop)
        projectPackets.save(sessionStorage, packet)
      }
      setSavedStop(packet)
      stop.mutate(packet)
    } catch (error) {
      setStorageError(error instanceof Error ? error.message : 'No se pudo guardar la detención original.')
    }
  }

  /** Discard only a packet explicitly rejected by the server, never one with an uncertain response. */
  function discardRejectedStop() {
    if (!savedStop || !canDiscard) return
    try {
      projectPackets.clear(sessionStorage, savedStop)
      stop.reset()
      refresh()
    } catch (error) {
      setStorageError(error instanceof Error ? error.message : 'No se pudo retirar la solicitud rechazada.')
    }
  }

  /** Retain original planning input on failure; the hook guards navigation against a changed project. */
  function requestPlan() {
    setNotice('')
    start.mutate(projectId, { onSettled: refresh })
  }

  return <section className="project-execution-controls" aria-label="Control de ejecución del proyecto">
    <div className="project-execution-actions">
      <span className="project-execution-observation">{workspace.isPending ? 'Consultando actividad…' : !known ? 'Actividad no disponible' : observed.legacy_registered ? 'Controlador anterior registrado' : observed.stop ? 'Trabajo activo registrado' : 'Sin trabajo activo registrado'}</span>
      <button onClick={refresh} disabled={workspace.isFetching}>Actualizar actividad</button>
      {showStop && <button className="project-execution-stop" onClick={requestStop} disabled={blocked || stop.isPending || (!savedStop && !observed?.stop)}>{savedStop ? 'Recuperar la misma detención' : 'Detener trabajo observado'}</button>}
      <button onClick={requestPlan} disabled={blocked || start.isPending || !observed?.runtime_available || observed.legacy_registered}>{savedStart ? 'Reenviar el mismo inicio' : 'Planificar proyecto'}</button>
      {observed?.legacy_registered && <Link to="/projects">Revisar controlador anterior</Link>}
    </div>
    {workspace.isError && <p role="alert">No pudimos consultar la actividad. Actualiza antes de iniciar o detener trabajo nuevo.</p>}
    {known && !observed.runtime_available && <p>Configura la ejecución nativa para preparar un plan.</p>}
    {stop.error && <p role="alert">{rejected ? 'La detención fue rechazada. Actualiza la actividad antes de preparar otra.' : 'No se confirmó la detención. Conservamos la solicitud original; recuperarla no detendrá trabajo nuevo.'}</p>}
    {canDiscard && <button onClick={discardRejectedStop}>Descartar detención rechazada</button>}
    {start.error && <p role="alert">No se confirmó la planificación. Conservamos la solicitud original. {start.error.message}</p>}
    {storageError && <p role="alert">{storageError}</p>}
    {notice && <p role="status">{notice}</p>}
  </section>
}
