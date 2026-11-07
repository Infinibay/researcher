/** Real installed storage journey: late upload receipt, CSV extraction and independent local/global documents. @module */
import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
import { createHash } from 'node:crypto'

const origin = process.env.RESEARCHER_E2E_ORIGIN
const ownerFile = process.env.RESEARCHER_E2E_OWNER_FILE
const output = process.env.RESEARCHER_E2E_OUTPUT
if (!origin || !ownerFile || !output || new URL(origin).hostname !== '127.0.0.1') {
  throw new Error('Run the knowledge journey through evals/operation/web_workspace.py on NEW disposable storage')
}
await fs.mkdir(output, { recursive: false })
const evidence = { status: 'running', scope: 'Real HTTP/SQLite/files; only one actual upload response is held after server commit',
  states: [], writes: [], errors: [], checks: [], attachments: {}, documents: {} }
const browser = await chromium.launch({ headless: true })
let page, releaseUpload
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
  /** Capture current visible evidence and collect regional accessibility observations without claiming full compliance. */
  async function capture(name, region, width = 1440) {
    await page.setViewportSize({ width, height: 1024 })
    await page.locator(region).waitFor({ state: 'visible' })
    await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true })
    const axe = await new AxeBuilder({ page }).include(region).analyze()
    const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)
    evidence.states.push({ name, width, fits, violations: axe.violations })
    expect(fits).toBe(true)
  }
  /** Follow visible product navigation, opening its mobile disclosure only when required. */
  async function navigate(name) {
    const nav = page.getByRole('navigation', { name: 'Navegación principal' })
    if (!(await nav.isVisible())) await page.getByRole('button', { name: 'Menú', exact: true }).click()
    await nav.getByRole('link', { name, exact: true }).click()
  }
  /** Create a new project solely through its owner form and retain its real server identity. */
  async function createProject(name) {
    await page.getByRole('button', { name: 'Nuevo proyecto', exact: true }).click()
    await page.getByLabel('Nombre del proyecto', { exact: true }).fill(name)
    await page.getByLabel('Alcance inicial', { exact: true }).fill('Ensayo de archivos y notas con alcance explícito.')
    const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/projects' && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Crear proyecto', exact: true }).click()
    const created = await response
    expect(created.status()).toBe(201)
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
    return (await created.json()).id
  }
  /** Switch the visible owner scope without assuming that pending responses have already completed. */
  async function selectProject(current, next) {
    await page.getByRole('button', { name: `Seleccionar proyecto: ${current}` }).click()
    await page.getByRole('button', { name: next, exact: true }).click()
    await expect(page.getByRole('button', { name: `Seleccionar proyecto: ${next}` })).toBeVisible()
  }
  /** Set a real multipart file using synthetic bytes; submitting remains a separate user action. */
  async function chooseCsv(content) {
    await page.getByLabel('Seleccionar archivo', { exact: true }).setInputFiles({ name: 'muestra.csv', mimeType: 'text/csv', buffer: Buffer.from(content) })
    await page.getByLabel('Descripción (opcional)').fill('Mismo nombre, contenido propio de este proyecto.')
  }
  /** Confirm extracted values and download the exact original rather than treating a preview as a saved source. */
  async function inspectFile(projectId, fileId, content, marker, screenshot) {
    await expect(page.getByRole('heading', { name: 'muestra.csv', exact: true })).toBeVisible()
    const response = page.waitForResponse(r => new URL(r.url()).pathname === `/api/files/${fileId}/preview`)
    await page.getByRole('button', { name: 'Extraer previa', exact: true }).click()
    const preview = await response
    expect(preview.status()).toBe(200)
    const extraction = await preview.json()
    expect(extraction.project_id).toBe(projectId)
    expect(extraction.persisted_source).toBe(false)
    expect(extraction.provenance.format).toBe('csv')
    await expect(page.getByLabel('Texto extraído del adjunto')).toContainText(marker)
    await expect(page.getByText('La primera fila se conserva y se interpreta como encabezados: es una suposición. Se distinguen las celdas vacías de los valores que faltan.', { exact: true })).toBeVisible()
    const downloaded = page.waitForEvent('download')
    await page.getByRole('button', { name: 'Descargar original', exact: true }).click()
    const file = await downloaded
    expect(file.suggestedFilename()).toBe('muestra.csv')
    const chunks = []
    for await (const chunk of await file.createReadStream()) chunks.push(chunk)
    const bytes = Buffer.concat(chunks)
    expect(bytes.equals(Buffer.from(content))).toBe(true)
    const sha256 = createHash('sha256').update(bytes).digest('hex')
    evidence.attachments[String(projectId)] = { id: fileId, sha256, extraction_sha256: extraction.content_sha256,
      format: extraction.provenance.format, persisted_source: extraction.persisted_source }
    await page.getByLabel('Texto extraído del adjunto').scrollIntoViewIfNeeded()
    await capture(screenshot, '.files-workbench', 390)
  }
  /** Create the same logical document path in the selected explicit namespace, retaining its actual receipt. */
  async function createDocument(scope, content) {
    await page.getByRole('button', { name: 'Nueva página' }).click()
    await page.getByLabel('Ruta, por ejemplo arquitectura/contexto', { exact: true }).fill('overview')
    await page.getByLabel('Título', { exact: true }).fill('Resumen de evidencia')
    await page.getByLabel('Texto en Markdown').fill(content)
    const response = page.waitForResponse(r => new URL(r.url()).pathname === '/api/wiki' && r.request().method() === 'POST')
    await page.getByRole('button', { name: 'Guardar página', exact: true }).click()
    const saved = await response
    expect(saved.status()).toBe(201)
    const value = await saved.json()
    await expect(page.getByRole('heading', { name: 'Resumen de evidencia', exact: true })).toBeVisible()
    await expect(page.locator('.wiki-document')).toContainText(content)
    evidence.documents[String(scope)] = { id: value.id, content, revision: value.revision }
  }
  await page.goto(origin + '/projects')
  await page.getByLabel('Código de acceso local').fill((await fs.readFile(ownerFile, 'utf8')).trim())
  await page.getByRole('button', { name: 'Abrir espacio', exact: true }).click()
  const alpha = await createProject('Archivo Atlas')
  const beta = await createProject('Archivo Beta')
  await page.locator(`#project-select-${alpha}`).click()
  await navigate('Archivos')
  const alphaCsv = 'origen,valor\nAtlas,137\n'
  const betaCsv = 'origen,valor\nBeta,63\n'
  let confirmCommit, firstUpload = true
  const committed = new Promise(resolve => { confirmCommit = resolve })
  await page.route('**/api/files?*', async route => {
    if (!firstUpload || route.request().method() !== 'POST') return route.continue()
    firstUpload = false
    const response = await route.fetch()
    expect(response.status()).toBe(201)
    const value = await response.json()
    const wait = new Promise(resolve => { releaseUpload = resolve })
    confirmCommit(value)
    await wait
    await route.fulfill({ response })
  })
  await chooseCsv(alphaCsv)
  const originalResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/files' && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Subir archivo', exact: true }).click()
  const alphaFile = await committed
  await selectProject('Archivo Atlas', 'Archivo Beta')
  await expect(page.getByText('Todavía no hay adjuntos. Puedes subir el primero desde el formulario.', { exact: true })).toBeVisible()
  releaseUpload()
  await (await originalResponse).finished()
  await expect(page.getByRole('button', { name: 'Seleccionar proyecto: Archivo Beta' })).toBeVisible()
  await expect(page.locator(`#file-select-${alphaFile.id}`)).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'muestra.csv', exact: true })).toHaveCount(0)
  await capture('01-late-upload-keeps-current-project', '.files-workbench')
  await chooseCsv(betaCsv)
  const betaResponse = page.waitForResponse(r => new URL(r.url()).pathname === '/api/files' && r.request().method() === 'POST')
  await page.getByRole('button', { name: 'Subir archivo', exact: true }).click()
  const betaFile = await (await betaResponse).json()
  await inspectFile(beta, betaFile.id, betaCsv, 'Beta', '02-beta-csv-preview')
  await selectProject('Archivo Beta', 'Archivo Atlas')
  await page.locator(`#file-select-${alphaFile.id}`).click()
  await inspectFile(alpha, alphaFile.id, alphaCsv, 'Atlas', '03-alpha-same-name-preview')
  await navigate('Documentos')
  await createDocument(alpha, 'Atlas: 137 unidades observadas en el archivo. La nota conserva contexto; la extracción no valida el resultado.')
  await page.getByRole('button', { name: 'Editar', exact: true }).click()
  const revised = 'Atlas: 137 unidades. Ejemplo del usuario: un título igual no demuestra que dos fuentes sean la misma versión.'
  await page.getByLabel('Texto en Markdown').fill(revised)
  const updated = page.waitForResponse(r => r.request().method() === 'PUT' && new URL(r.url()).pathname.startsWith('/api/wiki/'))
  await page.getByRole('button', { name: 'Guardar página', exact: true }).click()
  const revision = await (await updated).json()
  expect(revision.revision).toBe(2)
  evidence.documents[String(alpha)] = { id: revision.id, content: revised, revision: 2 }
  await expect(page.locator('.wiki-document')).toContainText(revised)
  await page.reload()
  await expect(page.locator('.wiki-document')).toContainText(revised)
  await capture('04-document-revision-after-reload', '.wiki-workbench', 390)
  await page.getByRole('button', { name: '‹ Volver a documentos', exact: true }).click()
  await page.getByLabel('Mostrar páginas de').selectOption('global')
  await createDocument('global', 'Biblioteca global: las notas de cada proyecto permanecen separadas de esta explicación compartida.')
  await selectProject('Archivo Atlas', 'Archivo Beta')
  await page.getByRole('button', { name: 'Documentos del proyecto actual', exact: true }).click()
  await createDocument(beta, 'Beta: 63 unidades. Este documento tiene la misma ruta overview y no reemplaza el documento de Atlas.')
  await capture('05-beta-same-path-document', '.wiki-workbench', 390)
  await expect(page.locator('.wiki-document')).not.toContainText('137')
  await page.getByRole('button', { name: '‹ Volver a documentos', exact: true }).click()
  await page.getByLabel('Mostrar páginas de').selectOption('global')
  await page.getByRole('button', { name: /Resumen de evidencia.*overview/ }).click()
  await expect(page.getByText('Este documento es global y está disponible desde otros proyectos. Una edición aquí cambia esa página global.', { exact: true })).toBeVisible()
  await expect(page.locator('.wiki-document')).toContainText(evidence.documents.global.content)
  await capture('06-explicit-global-library', '.wiki-workbench', 1440)
  evidence.identities = { alpha, beta }
  evidence.checks.push('late actual upload receipt does not change selected project', 'same-name files retain distinct bytes',
    'real isolated CSV previews expose header assumption', 'downloads match original bytes',
    'edited wiki survives reload', 'same-path project documents remain independent', 'global namespace explicitly selected')
  expect(evidence.errors).toEqual([])
  evidence.status = 'passed'
} catch (error) {
  evidence.status = 'failed'; evidence.error = String(error)
  if (page) {
    await page.screenshot({ path: path.join(output, 'failure.png'), fullPage: true }).catch(() => {})
    await fs.writeFile(path.join(output, 'failure.txt'), await page.locator('body').innerText()).catch(() => {})
  }
  throw error
} finally {
  if (releaseUpload) releaseUpload()
  await fs.writeFile(path.join(output, 'evidence.json'), JSON.stringify(evidence, null, 2) + '\n')
  await browser.close()
}
