/** Inspect real installed findings/reports and their stored citations; history is a synthetic domain fixture. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
const ids=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use evidence_pages.py with a fresh synthetic host')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Installed owner reads of synthetic documentary domain history, no generative model',pageStatus:{reports:'running',findings:'pending'},states:[],checks:[],faults:[],writes:[],errors:[],semantic:null}
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 page.on('response',response=>{const p=new URL(response.url()).pathname,m=response.request().method();if(p.startsWith('/api/')&&m!=='GET'&&p!=='/api/session')evidence.writes.push({method:m,path:p,status:response.status()})})
 const failed=new Set()
 let delayPath=null,started,release,delivered
 /** Fault only actual reads; late report bytes remain the original service response. */
 await page.route('**/api/**',async route=>{
  const p=new URL(route.request().url()).pathname
  if(route.request().method()!=='GET')return route.continue()
  if(failed.has(p)){evidence.faults.push({path:p,kind:'abort-read'});return route.abort('failed')}
  if(delayPath===p){
   delayPath=null;const response=await route.fetch();started()
   await new Promise(resolve=>{release=resolve})
   await route.fulfill({response});delivered();evidence.faults.push({path:p,kind:'late-original-alpha-report'});return
  }
  return route.continue()
 })
 /** Capture the actual selected workbench and bounded accessibility/geometry checks. */
 async function capture(name,region,width=1440,scrollTo=null){
  await page.setViewportSize({width,height:1024})
  if(scrollTo)await page.locator(scrollTo).scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true})
  const axe=await new AxeBuilder({page}).include(region).analyze()
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)
  evidence.states.push({name,width,region,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])
 }
 /** Choose the visible project without rewriting deep-link identities. */
 async function project(from,to){
  await page.getByRole('button',{name:`Seleccionar proyecto: ${from}`}).click()
  await page.getByRole('button',{name:to,exact:true}).click()
  await expect(page.getByRole('button',{name:`Seleccionar proyecto: ${to}`})).toBeVisible()
 }
 /** Open an original report using its actual indexed identity. */
 async function report(id){
  await page.locator(`#report-select-${id}`).focus();await page.keyboard.press('Enter')
  await expect(page.locator('.report-heading h1')).toBeFocused()
 }
 await page.goto(origin+'/reports')
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Elige un proyecto para consultar sus informes'})).toBeVisible()
 await capture('01-reports-no-selection','.report-workbench')
 await project('Elegir proyecto…','Inventario documentado')
 await expect(page.locator('[id^="report-select-"]')).toHaveCount(50)
 await page.getByRole('button',{name:'Mostrar más archivos',exact:true}).click()
 await expect(page.locator('[id^="report-select-"]')).toHaveCount(53)
 await report(ids.draft.report)
 await expect(page.locator('.report-heading')).toContainText('Borrador · pendiente de revisión')
 await expect(page.locator('.report-document')).toContainText('Entrada: un inventario documental sintético')
 await expect(page.locator('.report-document')).toContainText('No se contaron las piezas físicamente')
 await expect(page.locator('.report-evidence')).toContainText(ids.draft.quote)
 await expect(page.getByRole('heading',{name:'Resumen del inventario documental',exact:true})).toHaveCount(1)
 await page.getByRole('link',{name:'Ver tarea y corregir contexto'}).first().waitFor({state:'attached'})
 for(const link of await page.getByRole('link',{name:'Ver tarea y corregir contexto'}).all())await expect(link).toHaveAttribute('href',`/tasks?project=101&task=1001&fromArtifact=${ids.draft.report}`)
 await capture('02-report-desktop-citations','.report-workbench')
 await capture('03-report-mobile-body','.report-workbench',390,'.report-heading')
 await page.getByText('Datos de captura',{exact:true}).click()
 await expect(page.locator('.report-citations')).toContainText('https://example.org/synthetic-inventory')
 await page.getByText('Identidad del informe guardado',{exact:true}).click()
 await expect(page.locator('.report-hash code')).toHaveText(/^[a-f0-9]{64}$/)
 await capture('04-report-mobile-provenance','.report-workbench',390,'.report-evidence')
 await page.getByRole('link',{name:'Ver tarea y corregir contexto'}).last().click()
 await expect(page).toHaveURL(new RegExp(`task=1001&fromArtifact=${ids.draft.report}`))
 await expect(page.getByRole('heading',{name:'Examinar el inventario documental',exact:true})).toBeVisible()
 await page.goto(origin+'/reports');await page.setViewportSize({width:1440,height:1024})
 await page.locator('.report-index select').selectOption('accepted')
 await expect(page.locator('[id^="report-select-"]')).toHaveCount(1)
 await report(ids.accepted.report)
 await expect(page.locator('.report-heading')).toContainText('Aceptación guardada · vigencia por comprobar')
 await expect(page.getByRole('region',{name:'Aceptación del resultado'})).toContainText('Estado del documento original: Borrador')
 await expect(page.getByRole('link',{name:'Ver aceptación en la tarea original'})).toHaveAttribute('href',`/tasks?project=101&task=${ids.accepted.task}&fromArtifact=${ids.accepted.report}`)
 await expect(page.locator('.report-evidence')).toContainText(ids.accepted.quote)
 await capture('05-accepted-documentary-fixture','.report-workbench')
 await page.getByRole('button',{name:'Todos los informes',exact:true}).click()
 await expect(page.locator(`#report-select-${ids.accepted.report}`)).toBeFocused()
 await page.locator('.report-index select').selectOption('')
 await page.getByRole('group',{name:'Tipo de archivo'}).getByRole('button',{name:'Código',exact:true}).click()
 await expect(page.locator('[id^="report-select-"]')).toHaveCount(1)
 await report(ids.legacyArtifact)
 await expect(page.locator('.report-document')).toContainText('print(20)')
 await expect(page.locator('.report-heading')).toContainText('Sin revisión registrada')
 await page.goto(origin+'/reports')
 await page.getByLabel('Buscar en informes',{exact:true}).fill('Apunte de inventario 07')
 await expect(page.locator('[id^="report-select-"]')).toHaveCount(1)
 await expect(page.locator('.report-list')).toContainText('Apunte de inventario 07')
 await page.getByLabel('Buscar en informes',{exact:true}).fill('Registro inexistente para este ensayo')
 await expect(page.getByText('No hay archivos con estos filtros. Puedes cambiar el tipo, el estado o la búsqueda.',{exact:true})).toBeVisible()
 await page.getByLabel('Buscar en informes',{exact:true}).fill('')
 await expect(page.locator('[id^="report-select-"]')).toHaveCount(50)
 evidence.checks.push('reports-pagination-50-plus-3','saved-markdown-title-not-duplicated','captured-citation-hash-and-limits','original-correction-task-link','accepted-documentary-state-filter','legacy-code-not-accepted-report','report-keyboard-return','report-query-and-known-no-results')
 failed.add('/api/artifacts')
 await page.reload()
 await expect(page.getByText('No se pudo consultar la lista.',{exact:true})).toBeVisible()
 await expect(page.getByText('No hay archivos con estos filtros. Puedes cambiar el tipo, el estado o la búsqueda.',{exact:true})).toHaveCount(0)
 await capture('06-report-list-failed','.report-workbench')
 failed.clear();await page.getByRole('button',{name:'Volver a consultar',exact:true}).click()
 await expect(page.locator('[id^="report-select-"]')).toHaveCount(50)
 await page.goto(origin+`/reports?project=101&artifact=${ids.draft.report}`)
 failed.add(`/api/artifacts/${ids.draft.report}/evidence`)
 await page.reload()
 await expect(page.getByText('No se pudieron consultar las fuentes.',{exact:true})).toBeVisible()
 await expect(page.getByText('No hay citas registradas para este archivo. Las menciones en el texto no equivalen a procedencia verificada.',{exact:true})).toHaveCount(0)
 await capture('07-report-citations-failed','.report-workbench',390,'.report-evidence')
 failed.clear();await page.getByRole('button',{name:'Volver a consultar fuentes',exact:true}).click()
 await expect(page.locator('.report-evidence')).toContainText(ids.draft.quote)
 delayPath=`/api/artifacts/${ids.draft.report}`
 const began=new Promise(resolve=>{started=resolve}),arrived=new Promise(resolve=>{delivered=resolve})
 await page.reload();await began
 await project('Inventario documentado','Archivo separado')
 release();await arrived
 await expect(page.locator('.report-workbench')).not.toContainText('Entrada: un inventario documental sintético')
 await expect(page.locator('.report-link-warning')).toContainText('Este enlace corresponde a otro proyecto')
 await page.goto(origin+'/reports')
 await expect(page.getByText('No hay archivos con estos filtros. Puedes cambiar el tipo, el estado o la búsqueda.',{exact:true})).toBeVisible()
 await expect(page.locator('[id^="report-select-"]')).toHaveCount(0)
 await capture('08-empty-beta-no-alpha-report','.report-workbench',390)
 await project('Archivo separado','Inventario documentado')
 await page.goto(origin+`/reports?project=101&artifact=${ids.draft.report}`)
 await expect(page.locator('.report-document')).toContainText('Entrada: un inventario documental sintético')
 evidence.checks.push('report-list-failure-not-empty','citation-failure-not-no-sources','read-only-recovery','late-original-report-project-isolation','foreign-link-not-retargeted','report-reload-alpha-beta-alpha')
 evidence.pageStatus.reports='passed';evidence.pageStatus.findings='running'
 await page.goto(origin+'/findings');await page.setViewportSize({width:1440,height:1024})
 await expect(page.locator('[id^="finding-select-"]')).toHaveCount(50)
 await page.getByRole('button',{name:'Mostrar más hallazgos',exact:true}).click()
 await expect(page.locator('[id^="finding-select-"]')).toHaveCount(53)
 await page.locator(`#finding-select-101-${ids.draft.finding}`).click()
 await expect(page.locator('.findings-reader h1')).toBeFocused()
 await expect(page.locator('.findings-reader')).toContainText('Sin revisión independiente registrada')
 await expect(page.locator('.findings-evidence')).toContainText(ids.draft.quote)
 await capture('09-finding-desktop-evidence','.findings-workbench')
 await page.getByRole('button',{name:'Siguiente fragmento',exact:true}).click()
 await expect(page).toHaveURL(/offset=12000/)
 await expect(page.locator('.findings-body')).toContainText('Detalle de lectura del inventario')
 await page.getByRole('button',{name:'Ver cita',exact:true}).click()
 await expect(page.getByRole('region',{name:'Captura citada'})).toContainText(ids.draft.quote)
 await expect(page.locator('.findings-source mark')).toHaveText(ids.draft.quote)
 await page.getByText('Identidad de la captura',{exact:true}).click()
 await expect(page.locator('.findings-source code')).toHaveText(/^[a-f0-9]{64}$/)
 await capture('10-finding-mobile-captured-quote','.findings-workbench',390,'.findings-source')
 await page.getByRole('button',{name:'‹ Volver al hallazgo',exact:true}).click()
 await expect(page.getByRole('button',{name:'Ver cita',exact:true})).toBeFocused()
 await page.getByRole('button',{name:'‹ Volver a hallazgos',exact:true}).click()
 await page.locator(`#finding-select-101-${ids.legacyFinding}`).click()
 await page.getByText('Ver evaluación declarada · registro heredado',{exact:true}).click()
 await expect(page.locator('details.findings-assessment')).toContainText('Confianza declarada: 0,9')
 await expect(page.locator('.findings-reader')).not.toContainText('90% de certeza')
 await capture('11-legacy-declaration-not-review','.findings-workbench',390,'details.findings-assessment')
 await page.goto(origin+'/findings');await page.setViewportSize({width:1440,height:1024})
 await page.getByLabel('Tipo',{exact:true}).selectOption('conclusion')
 await expect(page.locator('[id^="finding-select-"]')).toHaveCount(1)
 await page.getByLabel('Tipo',{exact:true}).selectOption('')
 await page.getByLabel('Buscar hallazgos',{exact:true}).fill('inventario')
 await page.getByRole('button',{name:'Buscar',exact:true}).click()
 await expect(page.locator(`#finding-select-101-${ids.draft.finding}`)).toBeVisible()
 await page.getByLabel('Buscar por',{exact:true}).selectOption('semantic')
 await page.getByLabel('Buscar hallazgos',{exact:true}).fill('recuento físico de las piezas del inventario')
 const semantic=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/findings-query')
 await page.getByRole('button',{name:'Buscar',exact:true}).click()
 const response=await semantic,body=await response.json()
 evidence.semantic={status:response.status(),search_kind:body.search_kind??null,full_coverage:body.full_coverage??null,scientific_confidence:body.scientific_confidence??null,corpus_count:body.corpus_count??null,corpus_sha256:body.corpus_sha256??null,record_set_sha256:body.record_set_sha256??null,execution:body.execution??null}
 if(process.env.RESEARCHER_E2E_EXPECT_SEMANTIC==='1')expect(response.status()).toBe(200)
 if(response.status()===200){
  expect(body.scientific_confidence).toBe(null);expect(body.full_coverage).toBe(true)
  expect(body.corpus_count).toBe(53);expect(new Set(body.finding_ids).size).toBe(53)
  expect(body.corpus_sha256).toMatch(/^[a-f0-9]{64}$/);expect(body.record_set_sha256).toMatch(/^[a-f0-9]{64}$/)
  await expect(page.locator('.findings-count')).toContainText('53 registros completos')
  await expect(page.locator('[id^="finding-select-"]')).toHaveCount(new Set(body.matches.map(match=>match.finding_id)).size)
  expect(body.next_rank).not.toBe(null)
  const continuation=page.waitForResponse(r=>{const u=new URL(r.url());return u.pathname==='/api/findings-query'&&u.searchParams.get('after_rank')===String(body.next_rank)})
  await page.getByRole('button',{name:'Mostrar más coincidencias',exact:true}).click()
  const next=await continuation,nextBody=await next.json()
  expect(next.status()).toBe(200)
  expect(nextBody.corpus_sha256).toBe(body.corpus_sha256);expect(nextBody.record_set_sha256).toBe(body.record_set_sha256)
  expect(nextBody.full_coverage).toBe(true);expect(nextBody.scientific_confidence).toBe(null)
  await expect(page.locator('[id^="finding-select-"]')).toHaveCount(new Set([...body.matches,...nextBody.matches].map(match=>match.finding_id)).size)
  evidence.semantic.continuation={status:next.status(),matches:nextBody.matches.length,next_rank:nextBody.next_rank,execution:nextBody.execution??null}
 }else{
  await expect(page.getByRole('alert')).toContainText('No se pudo completar la búsqueda por significado')
  await expect(page.locator('[id^="finding-select-"]')).toHaveCount(0)
 }
 await capture('12-actual-semantic-availability','.findings-workbench')
 evidence.checks.push('findings-pagination-50-plus-3','original-body-window','captured-source-quote-highlight-and-hash','citation-focus-return','legacy-confidence-not-scientific-certainty','combined-type-and-word-filter','actual-semantic-availability-no-lexical-fallback')
 evidence.pageStatus.findings='readers-passed-review-admission-and-semantic-acceptance-separate'
 expect(evidence.writes).toEqual([]);expect(evidence.errors).toEqual([])
 evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}
