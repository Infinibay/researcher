/** Owner workspace journey against a real disposable product host; no intercepted or fabricated API responses. @module */
import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin = process.env.RESEARCHER_E2E_ORIGIN
const ownerFile = process.env.RESEARCHER_E2E_OWNER_FILE
const output = process.env.RESEARCHER_E2E_OUTPUT
if (!origin || !ownerFile || !output || new URL(origin).hostname !== '127.0.0.1') {
  throw new Error('Use evals/operation/web_workspace.py with a NEW disposable local installation')
}
await fs.mkdir(output, { recursive: false })
const evidence = { status: 'running', scope: 'Real installed HTTP/SQLite; owner forms only; no model requests',
  states: [], writes: [], errors: [], checks: [] }
const browser = await chromium.launch({ headless: true })
let page
try {
  const context = await browser.newContext({ viewport: { width: 1440, height: 1024 } })
  page = await context.newPage()
  page.setDefaultTimeout(10000)
  page.on('pageerror', error => evidence.errors.push(String(error)))
  page.on('response', response => {
    const url = new URL(response.url()), method = response.request().method()
    if (url.pathname.startsWith('/api/') && method !== 'GET' && url.pathname !== '/api/session') {
      evidence.writes.push({ method, path: url.pathname, status: response.status() })
    }
  })
  /** Save an observed state and accessibility results without equating automatic checks with human comprehension. */
  async function capture(name, region, width = 1440) {
    await page.setViewportSize({ width, height: 1024 })
    await page.locator(region).waitFor({ state: 'visible' })
    await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true })
    const axe = await new AxeBuilder({ page }).include(region).analyze()
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
    evidence.states.push({ name, width, fits, violations: axe.violations })
    expect(fits).toBe(true)
  }
  /** Navigate using the currently visible product navigation, including its mobile disclosure. */
  async function navigate(name) {
    const nav = page.getByRole('navigation', { name: 'Navegación principal' })
    if (!(await nav.isVisible())) await page.getByRole('button', { name: 'Menú', exact: true }).click()
    await nav.getByRole('link', { name, exact: true }).click()
  }
  /** Submit one real owner project form and retain the server-assigned identity. */
  async function createProject(name, description) {
    await page.getByRole('button', { name: 'Nuevo proyecto', exact: true }).click()
    await page.getByLabel('Nombre del proyecto', { exact: true }).fill(name)
    await page.getByLabel('Alcance inicial', { exact: true }).fill(description)
    const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/projects' && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Crear proyecto', exact: true }).click()
    const created = await response
    expect(created.status()).toBe(201)
    const value = await created.json()
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
    return value.id
  }
  /** Create a task through its actual form; the dependency choice is an owner decision, not inferred work. */
  async function createTask(title, dependency = null) {
    await page.getByRole('button', { name: 'Nueva tarea', exact: true }).click()
    await page.getByLabel('Título', { exact: true }).fill(title)
    await page.getByLabel('Descripción', { exact: true }).fill('Ensayo sintético: conservar evidencia y revisar el resultado antes de aceptarlo.')
    await page.getByLabel('Épica', { exact: true }).selectOption({ label: 'Reunir evidencia' })
    if (dependency) await page.getByRole('button', { name: `#${dependency} Capturar fuente`, exact: true }).click()
    const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/tasks' && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Crear tarea', exact: true }).click()
    const created = await response
    expect(created.status()).toBe(201)
    const value = await created.json()
    await expect(page.locator(`#task-select-${value.id}`)).toBeVisible()
    return value.id
  }
  await page.goto(origin + '/projects')
  await expect(page.getByRole('heading', { name: 'Abre tu espacio de trabajo' })).toBeVisible()
  await capture('01-local-access', 'main')
  await page.getByLabel('Código de acceso local').fill((await fs.readFile(ownerFile, 'utf8')).trim())
  await page.getByRole('button', { name: 'Abrir espacio', exact: true }).click()
  await expect(page.getByText('No hay proyectos. Crea uno con el alcance que quieras investigar; no iniciará agentes por su cuenta.')).toBeVisible()
  const alpha = await createProject('Atlas comprobable', 'Comparar resultados con fuentes verificables. No presuponer que una propuesta está aceptada.')
  await capture('02-created-project', '.project-workbench')
  const beta = await createProject('Contexto separado', 'No debe heredar las tareas de Atlas.')
  await page.locator(`#project-select-${alpha}`).click()
  await navigate('Planificación')
  await page.getByRole('button', { name: 'Nuevo grupo', exact: true }).click()
  await page.getByLabel('Nombre del grupo').fill('Reunir evidencia')
  await page.getByRole('button', { name: 'Crear grupo', exact: true }).click()
  await expect(page.getByRole('heading', { name: 'Reunir evidencia', exact: true })).toBeVisible()
  await page.getByRole('button', { name: 'Añadir hito', exact: true }).click()
  await page.getByLabel('Nombre del hito').fill('Datos contrastados')
  await page.getByRole('button', { name: 'Guardar hito', exact: true }).click()
  await expect(page.getByText('Datos contrastados', { exact: true })).toBeVisible()
  await capture('03-group-and-milestone', '.planning-workbench')
  await navigate('Tareas')
  const source = await createTask('Capturar fuente')
  const compare = await createTask('Contrastar resultado', source)
  await page.locator(`#task-select-${compare}`).click()
  await expect(page.getByRole('heading', { name: 'Contrastar resultado', exact: true })).toBeVisible()
  await expect(page.getByLabel('Solicitud para esta tarea')).toBeVisible()
  await capture('04-original-task', '.task-workbench')
  await page.getByText('Corregir el contexto', { exact: true }).click()
  await page.getByLabel('Tipo de corrección').selectOption('user_example')
  const correction = 'Ejemplo concreto: dos fuentes con el mismo título pueden describir versiones diferentes. Compara fecha y contenido antes de tratarlas como equivalentes.'
  await page.getByLabel('Qué cambia').fill(correction)
  await page.getByRole('button', { name: 'Guardar corrección', exact: true }).click()
  await expect(page.getByText('Corrección registrada en el contexto 2. Inicia otra ejecución cuando quieras usarla.', { exact: true })).toBeVisible()
  await expect(page.getByText(correction, { exact: true })).toBeVisible()
  await page.getByText(correction, { exact: true }).scrollIntoViewIfNeeded()
  await capture('04b-owner-example-saved', '.task-workbench')
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Contrastar resultado', exact: true })).toBeVisible()
  await expect(page.getByText(correction, { exact: true })).toBeVisible()
  await capture('05-task-after-reload-mobile', '.task-workbench', 390)
  await page.getByRole('button', { name: 'Seleccionar proyecto: Atlas comprobable' }).click()
  await page.getByRole('button', { name: 'Contexto separado', exact: true }).click()
  await expect(page.getByRole('button', { name: 'Seleccionar proyecto: Contexto separado' })).toBeVisible()
  await expect(page.getByText('No hay tareas con estos filtros. Puedes crear una o cambiar los filtros.', { exact: true })).toBeVisible()
  await expect(page.locator(`#task-select-${compare}`)).toHaveCount(0)
  await expect(page.locator('.task-workbench')).not.toContainText('Capturar fuente')
  await expect(page.locator('.task-workbench')).not.toContainText(correction)
  await capture('06-other-project-mobile', '.task-workbench', 390)
  await page.getByRole('button', { name: 'Seleccionar proyecto: Contexto separado' }).click()
  await page.getByRole('button', { name: 'Atlas comprobable', exact: true }).click()
  await navigate('Planificación')
  await page.getByRole('button', { name: /Reunir evidencia/ }).click()
  await page.getByRole('button', { name: 'Ver dependencias: Contrastar resultado' }).click()
  await expect(page.getByRole('region', { name: 'Dependencias de Contrastar resultado' })).toContainText('Capturar fuente')
  await page.getByRole('region', { name: 'Dependencias de Contrastar resultado' }).scrollIntoViewIfNeeded()
  await capture('07-real-dependency-mobile', '.planning-workbench', 390)
  evidence.identities = { alpha, beta, source, compare }
  evidence.checks.push('UI owner pairing', 'two real project creations', 'group and milestone persisted',
    'two tasks with stored dependency', 'explicit user example survives reload', 'selection after reload', 'project isolation', 'no API fixtures')
  if (process.env.RESEARCHER_E2E_NAVIGATION === '1') {
    const { auditNavigation } = await import('./navigation-audit.mjs')
    evidence.navigation = await auditNavigation(page, output)
    // Automatic accessibility findings remain explicit review obligations; they do not erase completed navigation evidence.
    expect(evidence.navigation.failures.filter(item => item.kind !== 'axe')).toEqual([])
  }
  expect(evidence.errors).toEqual([])
  evidence.status = 'passed'
} catch (error) {
  evidence.status = 'failed'
  evidence.error = String(error)
  if (page) {
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {})
    await fs.writeFile(path.join(output, 'failure.txt'), await page.locator('body').innerText()).catch(() => {})
  }
  throw error
} finally {
  await fs.writeFile(path.join(output, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n')
  await browser.close()
}
