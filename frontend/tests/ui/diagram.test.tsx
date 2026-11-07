/** Preserve a readable explanation across diagram rendering, failure and retired async work. @module */
import { render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MarkdownRenderer } from '../../src/components/common/MarkdownRenderer'

const renderer = vi.hoisted(() => ({ render: vi.fn() }))
vi.mock('../../src/lib/diagrams', () => ({ renderDiagram: renderer.render }))

/** Supply meaningful author text rather than treating the diagram's syntax as its accessible description. */
function diagram(label = 'Comparar versiones') {
  return `\`\`\`mermaid\nflowchart LR\naccTitle: ${label}\naccDescr: La fuente anterior conserva 137; la nueva registra 200. Comparar las versiones no demuestra la causa.\nA[137] --> B[200]\n\`\`\``
}

describe('correctable diagrams in saved Markdown', () => {
  it('keeps a visible textual alternative and presents the rendered diagram as an inert image', async () => {
    renderer.render.mockResolvedValue('data:image/svg+xml,diagram')
    render(<MarkdownRenderer content={diagram()} />)
    expect(screen.getByText(/La fuente anterior conserva 137;/, { selector: 'p' })).toBeVisible()
    expect(await screen.findByRole('img', { name: 'Comparar versiones' })).toHaveAttribute('src', 'data:image/svg+xml,diagram')
  })

  it('retains the explanation and original code when rendering fails', async () => {
    renderer.render.mockRejectedValue(new Error('invalid diagram'))
    render(<MarkdownRenderer content={diagram()} />)
    expect(await screen.findByRole('alert')).toHaveTextContent('No se pudo dibujar')
    expect(screen.getByText(/La fuente anterior conserva 137;/, { selector: 'p' })).toBeVisible()
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.getByText(/A\[137\] --> B\[200\]/)).toBeVisible()
  })

  it('does not invent a textual description for an unexplained diagram', async () => {
    renderer.render.mockClear()
    render(<MarkdownRenderer content={'```mermaid\nflowchart LR\nA --> B\n```'} />)
    expect(screen.getByRole('alert')).toHaveTextContent('descripción textual')
    expect(renderer.render).not.toHaveBeenCalled()
  })

  it('cannot replace a new explanation with a late result from an old message', async () => {
    let finishOld!: (value: string) => void
    renderer.render.mockReturnValueOnce(new Promise<string>(resolve => { finishOld = resolve }))
      .mockResolvedValueOnce('data:image/svg+xml,new')
    const view = render(<MarkdownRenderer content={diagram('Anterior')} />)
    await waitFor(() => expect(renderer.render).toHaveBeenCalled())
    view.rerender(<MarkdownRenderer content={diagram('Actual')} />)
    expect(await screen.findByRole('img', { name: 'Actual' })).toHaveAttribute('src', 'data:image/svg+xml,new')
    finishOld('data:image/svg+xml,old')
    await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'data:image/svg+xml,new'))
  })
})
