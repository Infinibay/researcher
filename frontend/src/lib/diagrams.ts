/** Render bounded Mermaid explanations with site-owned configuration and inert image delivery. @module */
let renderer: Promise<typeof import('mermaid')['default']> | undefined
let sequence = 0

/** Load the renderer only for diagrams; document directives cannot replace the application policy. */
async function library() {
  renderer ??= import('mermaid').then(({ default: mermaid }) => {
    mermaid.initialize({
      startOnLoad: false, securityLevel: 'strict', suppressErrorRendering: true,
      maxTextSize: 12000, maxEdges: 100, htmlLabels: false, theme: 'neutral',
      flowchart: { htmlLabels: false, useMaxWidth: false },
      secure: ['securityLevel', 'startOnLoad', 'maxTextSize', 'maxEdges', 'suppressErrorRendering', 'htmlLabels', 'flowchart'],
    })
    return mermaid
  })
  return renderer
}

/** Reject active styling/configuration and external resources before Mermaid touches a temporary layout container. */
export function validateDiagram(source: string) {
  if (source.length > 12000) throw new Error('El diagrama supera el límite de 12.000 caracteres.')
  if (/^\s*---|%%\s*\{|@\s*\{|\b(?:click|link|style|classDef)\b|(?:https?:|data:|javascript:|url\s*\()/im.test(source)) {
    throw new Error('El diagrama contiene configuración, estilos o recursos externos no admitidos.')
  }
}

/** Render real Mermaid syntax, remove temporary DOM on either outcome, and never mount author SVG as active document HTML. */
export async function renderDiagram(source: string): Promise<string> {
  validateDiagram(source)
  const mermaid = await library()
  const container = document.createElement('div')
  container.setAttribute('aria-hidden', 'true')
  Object.assign(container.style, { position: 'absolute', left: '-100000px', width: '1200px' })
  document.body.append(container)
  try {
    const { svg } = await mermaid.render(`researcher-diagram-${++sequence}`, source, container)
    return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  } finally {
    container.remove()
  }
}
