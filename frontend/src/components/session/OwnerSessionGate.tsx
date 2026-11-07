/** Owner authentication boundary, private query teardown and temporary-draft reload protection. @module */
import { useEffect, useState, type FormEvent, type ReactNode } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { acceptOwnerEndpointChange, loadOwnerSession, ownerEndpointArchive, ownerEndpointChange, pairOwner, subscribeOwnerSession } from '../../api/session'
import { wsManager } from '../../api/websocket'
import { useActivityFeedStore } from '../../stores/activityFeed'
import { useLoopStateStore } from '../../stores/loopState'
import { useWikiDrafts } from '../../stores/wikiDrafts'

/** Keep protected product content locked until owner pairing succeeds; transient expiry preserves drafts. */
export function OwnerSessionGate({children}: {children:ReactNode}) {
  const [state, setState] = useState<'checking'|'locked'|'changed'|'ready'>('checking')
  const [code, setCode] = useState('')
  const [error, setError] = useState('')
  const [pending, setPending] = useState(false)
  const queryClient = useQueryClient()
  const dirtyWiki = useWikiDrafts(state => Object.values(state.drafts).some(draft => draft.dirty))

  /** Protect temporary document text on reload; transient auth loss does not erase a draft. */
  useEffect(() => {
    if (!dirtyWiki) return
    const protect = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = '' }
    window.addEventListener('beforeunload', protect)
    return () => window.removeEventListener('beforeunload', protect)
  }, [dirtyWiki])


  useEffect(() => {
    let live = true
    const unsubscribe = subscribeOwnerSession((ready) => {
      if (!live) return
      if (!ready) {
        wsManager.disconnect()
        queryClient.clear()
        useActivityFeedStore.getState().clearFeed()
        useLoopStateStore.setState({agents: {}})
      }
      setState(ready ? 'ready' : ownerEndpointChange() ? 'changed' : 'locked')
    })
    loadOwnerSession().catch(() => {
      if (live) {
        setState('locked')
        setError('No se pudo conectar con el servidor. Comprueba que esté en marcha e inténtalo de nuevo.')
      }
    })
    return () => { live = false; unsubscribe() }
  }, [queryClient])

  /** Pair with the owner code once and clear the entered credential after the attempt. */
  async function unlock(event:FormEvent) {
    event.preventDefault()
    setPending(true)
    setError('')
    try { await pairOwner(code.trim()) }
    catch (failure) { setError(failure instanceof Error ? failure.message : 'No se pudo abrir la sesión.') }
    finally { setCode(''); setPending(false) }
  }

  /** Preserve unsent document text alongside exact pending packets before entering another installation. */
  function enterRestored() {
    try {
      acceptOwnerEndpointChange({wikiDrafts:useWikiDrafts.getState().drafts})
      useWikiDrafts.getState().clear()
      setError('')
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'No se pudo conservar el archivo anterior.') }
  }

  /** Download an inspectable local copy without transmitting drafts or enabling old requests. */
  function downloadPrevious() {
    try {
      const data = ownerEndpointArchive({wikiDrafts:useWikiDrafts.getState().drafts})
      const url = URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}))
      const link = document.createElement('a')
      link.href = url; link.download = 'researcher-solicitudes-anteriores.json'; link.click()
      setTimeout(() => URL.revokeObjectURL(url),1000)
    } catch (failure) { setError(failure instanceof Error ? failure.message : 'No se pudo preparar la descarga.') }
  }

  if (state === 'ready') return children
  return (
    <main className="flex min-h-screen items-center justify-center bg-surface-950 p-6 text-slate-100">
      <section className="w-full max-w-md rounded-xl border border-surface-700 bg-surface-900 p-8" aria-labelledby="owner-title">
        <p className="mb-3 text-xs font-medium uppercase tracking-widest text-slate-400">Researcher · acceso local</p>
        <h1 id="owner-title" className="text-2xl font-semibold">{state === 'changed' ? 'Esta instalación cambió' : 'Abre tu espacio de trabajo'}</h1>
        {state === 'changed' ? <div className="mt-5 space-y-4 text-sm leading-6">
          <p>La base que responde ahora es distinta de la que usaste antes, o tus solicitudes guardadas todavía no identifican su instalación. Conservamos esas solicitudes y los borradores; no los enviaremos aquí.</p>
          <p>Por ejemplo, una publicación pendiente en la instalación anterior podría haber terminado allí aunque esta copia aún no lo muestre. Revisa su historial antes de pedir otra.</p>
          <button onClick={downloadPrevious} className="w-full rounded-md border border-surface-600 px-4 py-2 focus-visible:ring-2 focus-visible:ring-sky-400">Descargar solicitudes y borradores anteriores</button>
          <p>Al continuar, quedarán archivados en esta pestaña y abrirás la instalación actual para preparar solicitudes nuevas.</p>
          <button onClick={enterRestored} className="w-full rounded-md bg-slate-100 px-4 py-2 font-medium text-slate-950 focus-visible:ring-2 focus-visible:ring-sky-400">Archivar anteriores y abrir esta instalación</button>
          {error && <p role="alert" className="text-red-300">{error}</p>}
        </div> : state === 'checking' ? <p className="mt-4" role="status">Comprobando la sesión…</p> : (
          <form onSubmit={unlock} className="mt-5 space-y-4">
            <p className="text-sm leading-6 text-slate-300">Introduce el código del archivo privado cuya ruta indica el servidor al arrancar. Este acceso es independiente de tu cuenta de OpenAI.</p>
            <div>
              <label htmlFor="owner-code" className="mb-2 block text-sm font-medium">Código de acceso local</label>
              <input id="owner-code" type="password" autoComplete="off" value={code} onChange={(event) => setCode(event.target.value)} required maxLength={256} disabled={pending} aria-describedby="owner-hint" className="w-full rounded-md border border-surface-600 bg-surface-950 px-3 py-2 outline-hidden focus-visible:ring-2 focus-visible:ring-sky-400" />
              <p id="owner-hint" className="mt-2 text-xs text-slate-400">El código cambia al reiniciar el servidor. No uses una clave de API.</p>
            </div>
            {error && <p role="alert" className="text-sm text-red-300">{error}</p>}
            <button type="submit" disabled={pending || !code.trim()} className="w-full rounded-md bg-slate-100 px-4 py-2 font-medium text-slate-950 focus-visible:ring-2 focus-visible:ring-sky-400 disabled:opacity-50">{pending ? 'Abriendo…' : 'Abrir espacio'}</button>
          </form>
        )}
      </section>
    </main>
  )
}
