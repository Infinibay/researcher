/** Check compiled Tailwind layout and keyboard focus at the owner boundary without pairing or backend access. @module */
import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin = process.env.ACCESS_ORIGIN ?? 'http://127.0.0.1:5179'
const out = path.resolve(process.env.BROWSER_AUDIT_OUT ?? '../docs/design/audits/frontend-dependencies/access')
await fs.mkdir(out, { recursive: true })
const evidence = { scope: 'Compiled web with a locked session fixture; no pairing, backend or model calls.', states: [], errors: [], writes: [] }
const browser = await chromium.launch({ headless: true })
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1024 } })
  const page = await context.newPage()
  page.on('pageerror', error => evidence.errors.push(String(error)))
  await page.route('**/api/**', async route => {
    const request = route.request()
    if (request.method() !== 'GET') evidence.writes.push(request.method())
    if (new URL(request.url()).pathname === '/api/session') {
      return route.fulfill({ status: 200, json: { authenticated: false } })
    }
    return route.fulfill({ status: 404, json: { detail: 'Unexpected fixture request' } })
  })
  await page.goto(origin)
  const input = page.getByLabel('Código de acceso local')
  await expect(input).toBeVisible()
  await expect(page.getByRole('button', { name: 'Abrir espacio' })).toBeDisabled()
  await page.keyboard.press('Tab')
  await expect(input).toBeFocused()

  for (const [name, width, forcedColors] of [
    ['desktop-focus', 1440, 'none'],
    ['mobile-focus', 390, 'none'],
    ['mobile-forced-colors', 390, 'active'],
  ]) {
    await page.setViewportSize({ width, height: 1024 })
    await page.emulateMedia({ forcedColors })
    await expect(input).toBeFocused()
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true)
    const style = await input.evaluate(node => {
      const css = getComputedStyle(node)
      return { outline: css.outlineStyle, width: css.outlineWidth, color: css.outlineColor, shadow: css.boxShadow }
    })
    if (forcedColors === 'active') {
      expect(style.outline).toBe('solid')
      expect(style.width).toBe('2px')
      expect(style.color).not.toBe('rgba(0, 0, 0, 0)')
    } else {
      expect(style.shadow).not.toBe('none')
    }
    await page.screenshot({ path: path.join(out, `${name}.png`), fullPage: true })
    const axe = await new AxeBuilder({ page }).include('main').analyze()
    evidence.states.push({ name, width, forcedColors, style, axe_violations: axe.violations.length, violations: axe.violations })
    expect(axe.violations).toEqual([])
  }
  expect(evidence.errors).toEqual([])
  expect(evidence.writes).toEqual([])
} finally {
  await fs.writeFile(path.join(out, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n')
  await browser.close()
}
