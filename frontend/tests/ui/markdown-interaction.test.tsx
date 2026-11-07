/** Exercise readable evidence and hostile document input through the real Markdown plugin stack. @module */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { MarkdownRenderer } from '../../src/components/common/MarkdownRenderer'

describe('document reading after dependency migration', () => {
  it('keeps nested headings and a keyboard-accessible external source', async () => {
    const user = userEvent.setup()
    render(<MarkdownRenderer headingBase={3} content={'# Resultado\n\nLa suma es 200. [Consultar fuente](https://example.org/evidence)\n\n## Límites\n\nEs un ejemplo sintético.'} />)
    expect(screen.getByRole('heading', { level: 3, name: 'Resultado' })).toBeVisible()
    expect(screen.getByRole('heading', { level: 4, name: 'Límites' })).toBeVisible()
    const source = screen.getByRole('link', { name: 'Consultar fuente' })
    expect(source).toHaveAttribute('href', 'https://example.org/evidence')
    expect(source).toHaveAttribute('rel', 'noopener noreferrer')
    await user.tab()
    expect(source).toHaveFocus()
  })

  it('renders formulas, code and read-only task lists without interpreting document HTML', () => {
    const { container } = render(<MarkdownRenderer content={'La fórmula es $x = 137 + 63$.\n\n```python\nprint(137 + 63)\n```\n\n- [x] Cálculo observado\n\n<img src=x onerror="alert(1)"><script>alert(2)</script>'} />)
    expect(container.querySelector('math')).not.toBeNull()
    expect(container.querySelector('pre code')).toHaveTextContent('print(137 + 63)')
    expect(screen.getByRole('checkbox')).toBeChecked()
    expect(screen.getByRole('checkbox')).toBeDisabled()
    expect(container.querySelector('script, img[onerror]')).toBeNull()
  })

  it('rejects executable links in Markdown and untrusted math commands', () => {
    const { container } = render(<MarkdownRenderer content={'[Documento](javascript:alert%281%29)\n\n$\\href{javascript:alert(2)}{enlace}$\n\n<iframe src="https://example.org"></iframe>'} />)
    expect(container.querySelector('iframe')).toBeNull()
    for (const link of container.querySelectorAll('a')) {
      expect(link.getAttribute('href') ?? '').not.toMatch(/^\s*(?:javascript|data|vbscript):/i)
    }
  })
})
