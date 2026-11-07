/** Keep an author's diagram, textual alternative and original source together through rendering failures. @module */
import { useEffect, useState } from 'react'
import { renderDiagram } from '../../lib/diagrams'

/** Read Mermaid's accessibility annotations without guessing an explanation from the graph itself. */
export function diagramDescription(source: string) {
  return {
    title: source.match(/^\s*accTitle\s*:\s*(.+)$/m)?.[1]?.trim() || 'Diagrama',
    description: (source.match(/^\s*accDescr\s*:\s*(.+)$/m)?.[1]
      ?? source.match(/^\s*accDescr\s*\{([\s\S]*?)\}/m)?.[1])?.trim() || '',
  }
}

/** Retire late results when a message changes and preserve readable content while loading or after an error. */
export function Diagram({ source }: { source: string }) {
  const { title, description } = diagramDescription(source)
  const [result, setResult] = useState<{ source: string; image?: string; error?: string }>()
  const current = result?.source === source ? result : undefined
  const error = !description ? 'Falta una descripción textual (accDescr) para explicar este diagrama.' : current?.error
  useEffect(() => {
    let active = true
    if (description) void renderDiagram(source).then(
      image => { if (active) setResult({ source, image }) },
      () => { if (active) setResult({ source, error: 'No se pudo dibujar el diagrama. La explicación y el contenido original se conservan.' }) },
    )
    return () => { active = false }
  }, [source, description])
  return <figure className="not-prose my-4 min-w-0 rounded-md border border-[var(--work-line,#475569)] p-4">
    <figcaption className="space-y-2">
      <strong>{title}</strong>
      {description && <p className="whitespace-pre-wrap">{description}</p>}
    </figcaption>
    {error ? <p role="alert" className="my-2">{error}</p>
      : current?.image ? <div className="mt-3 overflow-auto" tabIndex={0} aria-label={`Vista de ${title}`}><img className="max-w-full" src={current.image} alt={title} /></div>
        : <p role="status">Preparando diagrama…</p>}
    <details className="mt-3" open={error ? true : undefined}>
      <summary className="cursor-pointer">Contenido original del diagrama</summary>
      <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words text-sm"><code>{source}</code></pre>
    </details>
  </figure>
}
