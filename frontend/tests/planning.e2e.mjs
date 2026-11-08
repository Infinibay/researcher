/** Real installed Planning reads/deletions with synthetic domain history and actual delivery faults. @module */
import {chromium, expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN, output=process.env.RESEARCHER_E2E_OUTPUT
const fixture=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use planning_page.py with a fresh synthetic installation')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',syntheticDomainHistory:true,modelTurns:0,states:[],checks:[],writes:[],faults:[],errors:[]}
const browser=await chromium.launch({headless:true})
let page
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0})))
 page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 page.on('response',response=>{const p=new URL(response.url()).pathname,m=response.request().method();if(p.startsWith('/api/')&&m!=='GET'&&p!=='/api/session')evidence.writes.push({path:p,method:m,status:response.status()})})
 const failed=new Set()
 let delayNextGroups=false,releaseDelayed,delayedStarted,delayedDelivered
 /** Only drop/delay actual reads; never fabricate proposal, task, or success bodies. */
 await page.route('**/api/**',async route=>{
  const request=route.request(),u=new URL(request.url())
  if(request.method()!=='GET')return route.continue()
  if(failed.has(u.pathname)){evidence.faults.push({path:u.pathname,kind:'abort-read'});return route.abort('failed')}
  if(delayNextGroups&&u.pathname==='/api/epics'&&u.searchParams.get('project_id')==='101'){
   delayNextGroups=false
   const response=await route.fetch()
   delayedStarted()
   await new Promise(resolve=>{releaseDelayed=resolve})
   evidence.faults.push({path:u.pathname,kind:'late-original-alpha-read'})
   await route.fulfill({response})
   delayedDelivered()
   return
  }
  return route.continue()
 })
 /** Save visible evidence, bounded accessibility analysis and actual horizontal geometry. */
 async function capture(name,width=1440,region='.planning-workbench'){
  await page.setViewportSize({width,height:1024})
  await page.locator(region).waitFor()
  await page.screenshot({path:path.join(output,`${name}.png`),fullPage:true})
  const axe=await new AxeBuilder({page}).include(region).analyze()
  const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)
  evidence.states.push({name,width,fits,violations:axe.violations})
  expect(fits).toBe(true);expect(axe.violations).toEqual([])
 }
 /** Switch scope using the actual global project selector. */
 async function project(from,to){
  await page.getByRole('button',{name:`Seleccionar proyecto: ${from}`}).click()
  await page.getByRole('button',{name:to,exact:true}).click()
  await expect(page.getByRole('button',{name:`Seleccionar proyecto: ${to}`})).toBeVisible()
 }
 /** Open a concrete original group and verify keyboard focus enters its reading pane. */
 async function group(id){
  await page.locator(`#planning-group-${id}`).click()
  await expect(page.locator('#planning-reading')).toBeFocused()
 }
 await page.goto(origin+'/epics')
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Planificación',exact:true})).toBeVisible()
 await expect(page.locator('[id^="planning-group-"]')).toHaveCount(19)
 await group(fixture.manual)
 await page.getByRole('button',{name:'Ver dependencias: Exportar columnas comprobadas'}).click()
 await expect(page.getByRole('region',{name:'Dependencias de Exportar columnas comprobadas'})).toContainText('Leer una observación de ejemplo')
 await capture('01-desktop-group-dependency')
 await capture('02-mobile-group-dependency',390)
 await page.getByRole('button',{name:'Volver al índice'}).click()
 await expect(page.locator(`#planning-group-${fixture.manual}`)).toBeFocused()
 await page.locator(`#planning-plan-${fixture.proposal.run}`).focus()
 await page.keyboard.press('Enter')
 await expect(page.locator('#planning-reading')).toBeFocused()
 await expect(page.getByRole('heading',{name:'Lo que se está suponiendo'})).toBeVisible()
 await expect(page.locator('.planning-detail')).toContainText('Entrada ilustrativa: una lista de observaciones')
 await expect(page.locator('.planning-detail')).toContainText('Salida deseada: un CSV')
 await expect(page.locator('.planning-detail')).toContainText('Depende de: Comprobar una entrada real')
 const decision=page.getByRole('link',{name:'Revisar y decidir en la tarea original'})
 await expect(decision).toHaveAttribute('href',`/tasks?project=101&task=${fixture.proposal.task}&planRun=${fixture.proposal.run}`)
 await capture('03-mobile-proposal',390)
 await decision.scrollIntoViewIfNeeded();await capture('04-mobile-original-decision',390)
 await decision.click()
 await expect(page).toHaveURL(new RegExp(`task=${fixture.proposal.task}&planRun=${fixture.proposal.run}`))
 await expect(page.getByRole('heading',{name:'Plan sintético pendiente de revisión',exact:true})).toBeVisible()
 evidence.checks.push('actual-dependency-read','keyboard-selection-and-return','illustrative-input-output-not-observed-data','original-task-run-link')
 await page.goto(origin+'/epics');await page.setViewportSize({width:1440,height:1024})
 await page.locator(`#planning-plan-${fixture.accepted.run}`).click()
 await expect(page.locator('.planning-notice')).toContainText('La aceptación está registrada para este contexto')
 await capture('05-desktop-accepted-history')
 await group(fixture.accepted.acceptance.epics.export)
 await page.getByRole('button',{name:'Eliminar grupo',exact:true}).click()
 await expect(page.getByRole('button',{name:'Conservar grupo'})).toBeFocused()
 await page.getByRole('button',{name:'Eliminar este grupo'}).click()
 await expect(page.getByRole('dialog').getByRole('alert')).toContainText('No se confirmó la eliminación')
 await capture('06-accepted-history-delete-refused',1440,'.planning-delete')
 await page.getByRole('button',{name:'Conservar grupo'}).click()
 await group(fixture.native)
 await page.getByRole('button',{name:'Eliminar grupo',exact:true}).click()
 await page.getByRole('button',{name:'Eliminar este grupo'}).click()
 await expect(page.getByRole('dialog').getByRole('alert')).toContainText('historia nativa protegida')
 await page.getByRole('button',{name:'Conservar grupo'}).click()
 evidence.checks.push('accepted-plan-group-delete-refused','native-history-group-delete-refused')
 failed.add('/api/milestones');failed.add('/api/tasks')
 await page.reload();await group(fixture.manual)
 await expect(page.getByText('No pudimos consultar los hitos.',{exact:true})).toBeVisible()
 await expect(page.getByText('No pudimos consultar las tareas del grupo.',{exact:true})).toBeVisible()
 await expect(page.getByText('Este grupo no tiene hitos registrados.',{exact:true})).toHaveCount(0)
 await expect(page.getByText('No hay tareas asociadas a este grupo.',{exact:true})).toHaveCount(0)
 await capture('07-partial-reads-failed')
 failed.clear()
 await page.getByRole('button',{name:'Volver a consultar hitos'}).click()
 await expect(page.getByText('Muestra documentada',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Actualizar planificación'}).click()
 await expect(page.getByRole('link',{name:'Exportar columnas comprobadas',exact:true})).toBeVisible()
 const workspacePath='/api/projects/101/workspace'
 failed.add(workspacePath)
 await page.reload()
 await expect(page.getByText('No pudimos consultar las propuestas. La lista visible conserva la última consulta correcta.',{exact:true})).toBeVisible()
 await expect(page.getByText('No hay planes nativos guardados.',{exact:true})).toHaveCount(0)
 await capture('08-proposal-list-read-failed')
 failed.clear();await page.getByRole('button',{name:'Actualizar planificación'}).click()
 await expect(page.locator(`#planning-plan-${fixture.proposal.run}`)).toBeVisible()
 await page.locator(`#planning-plan-${fixture.proposal.run}`).click()
 const planPath=`/api/projects/101/runs/${fixture.proposal.run}/project-plan`
 failed.add(planPath)
 await page.getByRole('button',{name:'Actualizar propuesta'}).click()
 await expect(page.getByRole('alert')).toContainText('No pudimos consultar la propuesta.')
 await capture('09-original-proposal-read-failed')
 failed.clear();await page.getByRole('button',{name:'Actualizar propuesta'}).click()
 await expect(page.getByRole('alert')).toHaveCount(0)
 evidence.checks.push('partial-task-and-milestone-failure-not-empty','milestone-and-task-explicit-recovery','proposal-list-failure-not-empty','original-proposal-refresh-recovery')
 delayNextGroups=true
 const started=new Promise(resolve=>{delayedStarted=resolve})
 const delivered=new Promise(resolve=>{delayedDelivered=resolve})
 await page.reload();await started
 await project('Atlas de observaciones','Proyecto separado')
 await expect(page.getByText('Todavía no hay grupos en este proyecto.',{exact:true})).toBeVisible()
 releaseDelayed()
 await delivered
 await expect(page.getByRole('button',{name:'Seleccionar proyecto: Proyecto separado'})).toBeVisible()
 await expect(page.locator('[id^="planning-group-"]')).toHaveCount(0)
 await expect(page.locator('[id^="planning-plan-"]')).toHaveCount(0)
 await capture('10-late-alpha-response-in-beta',390)
 await project('Proyecto separado','Atlas de observaciones')
 await expect(page.locator('[id^="planning-group-"]')).toHaveCount(19)
 const last=page.locator('[id^="planning-group-"]').last()
 await last.click();await expect(page.locator('.planning-description')).toContainText('Descripción sintética extensa')
 await expect(page.getByText('Este grupo no tiene hitos registrados.',{exact:true})).toBeVisible()
 await expect(page.getByText('No hay tareas asociadas a este grupo.',{exact:true})).toBeVisible()
 await capture('11-long-group-mobile',390)
 await capture('12-long-group-desktop')
 evidence.checks.push('late-original-read-project-isolation','alpha-beta-alpha','nineteen-groups-and-long-description')
 await group(fixture.manual)
 await page.getByRole('button',{name:'Eliminar grupo',exact:true}).click()
 await expect(page.getByRole('button',{name:'Conservar grupo'})).toBeFocused()
 await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).toHaveCount(0)
 await page.getByRole('button',{name:'Eliminar grupo',exact:true}).click()
 await capture('13-manual-delete-dialog',1440,'.planning-delete')
 const deletion=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/epics/${fixture.manual}`&&r.request().method()==='DELETE')
 await page.getByRole('button',{name:'Eliminar este grupo'}).click()
 expect((await deletion).status()).toBe(204)
 await expect(page.locator(`#planning-group-${fixture.manual}`)).toHaveCount(0)
 await page.reload()
 await expect(page.locator('[id^="planning-group-"]')).toHaveCount(18)
 await capture('14-deletion-after-reload')
 evidence.checks.push('manual-delete-dialog-safe-default-and-escape','manual-deletion-durable')
 expect(evidence.writes.every(w=>w.method==='DELETE'&&w.path.startsWith('/api/epics/'))).toBe(true)
 expect(evidence.writes.filter(w=>w.status===409)).toHaveLength(2)
 expect(evidence.writes.filter(w=>w.status===204)).toHaveLength(1)
 expect(evidence.errors).toEqual([])
 evidence.status='passed'
}finally{
 if(page)await page.screenshot({path:path.join(output,'final.png'),fullPage:true}).catch(()=>{})
 await browser.close()
 await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}
