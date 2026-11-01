/** Presentation helpers for saved reports; never mutate the persisted body. @module */

/** Hide a duplicate initial Markdown H1 only when it exactly matches the reader title. */
export function reportDocument(content: string, title: string): string {
  const firstBreak = content.indexOf('\n')
  const firstLine = firstBreak < 0 ? content : content.slice(0, firstBreak)
  return firstLine.trim() === `# ${title}` ? (firstBreak < 0 ? '' : content.slice(firstBreak + 1)) : content
}

/**
 * Format persisted dates in explicit UTC, with an honest fallback for absent/invalid dates.
 * Numeric captures use epoch seconds; SQLite timestamps without a zone are UTC.
 */
export function reportTimestamp(value?: string | number | null): { machine?: string; label: string } {
  if (value == null || value === '') return { label: 'Fecha no registrada' }
  let input: string | number = typeof value === 'number' ? value * 1000 : value
  if (typeof input === 'string' && /^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(\.\d+)?$/.test(input)) input = input.replace(' ', 'T') + 'Z'
  const date = new Date(input)
  if (!Number.isFinite(date.getTime())) return { label: 'Fecha no registrada' }
  return { machine: date.toISOString(), label: new Intl.DateTimeFormat('es-AR', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC', hourCycle: 'h23' }).format(date) + ' UTC' }
}

export const artifactTypes: Record<string, string> = { report: 'Informes', code: 'Código', data: 'Datos', diagram: 'Diagramas' }
export const reportStates: Record<string, string> = { draft: 'Borrador · pendiente de revisión', accepted: 'Aceptado', superseded: 'Sustituido' }
