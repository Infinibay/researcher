/** Verify actual restored-history messaging, old receipt scope and fresh owner permission on the installed API. */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const base='http://127.0.0.1:5296',out=path.resolve('../docs/design/audits/2026-11-07-local-restoration')
const fixture=JSON.parse(await fs.readFile('../.superpowers/sdd/2026-10-31-actualizacion-proyecto/auxiliary-restoration-web/fixture.json','utf8'))
await fs.mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true}),report={states:[],writes:[],checks:[],errors:[]}
try{
 const context=await browser.newContext({viewport:{width:1440,height:2200}})
 expect((await context.request.post(base+'/api/session',{data:{code:'restoration-browser-fixture-owner-32-characters'},headers:{'X-Researcher-Client':'web'}})).status()).toBe(200)
 await context.addInitScript(action=>{localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0}));if(!sessionStorage.getItem('restoration-fixture-seeded')){sessionStorage.setItem('researcher:local-continuation:v1:101',JSON.stringify(action));sessionStorage.setItem('restoration-fixture-seeded','1')}},fixture.action)
 const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>report.errors.push(String(error)))
 await page.route('**/api/projects/101/local-work/continuations',async route=>{
  if(route.request().method()!=='POST')return route.continue()
  const response=await route.fetch();expect(response.status()).toBe(200)
  report.writes.push({request:route.request().postDataJSON(),receipt:await response.json()})
  return route.abort('failed')
 })
 await page.goto(base+'/agents')
 const local=page.getByRole('region',{name:'Historial de cálculos locales'})
 /** Capture the actual component after its final state is visible, checking scoped accessibility and document overflow. */
 async function capture(name,width){await page.setViewportSize({width,height:2200});await local.scrollIntoViewIfNeeded();await local.screenshot({path:path.join(out,name+'.png')});const axe=await new AxeBuilder({page}).include('[aria-label="Historial de cálculos locales"]').analyze();expect(axe.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);report.states.push({name,width,height:2200,axe_violations:0})}
 await expect(page.getByRole('heading',{name:'Esta instalación cambió'})).toBeVisible()
 expect(report.writes).toHaveLength(0)
 await page.screenshot({path:path.join(out,'00-owner-installation-barrier.png'),fullPage:true})
 report.states.push({name:'00-owner-installation-barrier',width:1440,height:2200,scope:'full-page'})
 await page.getByRole('button',{name:'Archivar anteriores y abrir esta instalación'}).click()
 const archives=await page.evaluate(()=>Object.keys(sessionStorage).filter(key=>key.startsWith('researcher:archived-owner-state:v1:')).map(key=>JSON.parse(sessionStorage.getItem(key))))
 expect(archives).toHaveLength(1);expect(archives[0].entries['researcher:local-continuation:v1:101']).toBe(JSON.stringify(fixture.action))
 await local.getByRole('button',{name:'Revisar cálculos locales'}).click()
 await expect(local).toContainText('No se comprobó el cierre del host original.')
 expect(report.writes).toHaveLength(0)
 await capture('01-historical-receipt-desktop',1440)
 await local.getByRole('button',{name:'Autorizar un nuevo cálculo'}).click()
 await expect(local).toContainText('Trabajarás sobre la copia restaurada, con permisos nuevos en esta instalación.')
 await local.getByLabel('Motivo de la continuación (opcional)').fill('Calcular de nuevo sobre esta copia restaurada.')
 await capture('02-fresh-decision-mobile',390)
 await local.getByRole('button',{name:'Guardar autorización'}).click();await expect(local).toContainText('No se confirmó la autorización')
 await page.reload();await local.getByRole('button',{name:'Consultar autorización original'}).click()
 await expect(local).toContainText('Autorización guardada. No se inició un cálculo.')
 await local.getByRole('button',{name:'Revisar cálculos locales'}).click();await expect(local).toContainText('Ya autorizaste una sucesora.')
 await capture('03-current-permission-recovered',1440)
 expect(report.writes).toHaveLength(1);expect(report.writes[0].receipt.authorization_scope).toBe('current_installation')
 expect(report.writes[0].request.operation_key).not.toBe(fixture.action.body.operation_key)
 const old=await context.request.get(base+'/api/projects/101/local-work/continuations/'+fixture.action.body.operation_key)
 report.original_receipt=await old.json();expect(report.original_receipt.authorization_scope).toBe('historical_installation')
 const budget=await context.request.get(base+'/api/projects/101/work-budget');report.budget=await budget.json()
 expect(report.budget.auxiliary.used_operations).toBe(1);expect(report.budget.auxiliary.held_cpu_ms).toBe(3000)
 expect(report.errors).toEqual([])
 report.checks.push('verified-restore-before-serving','owner-installation-barrier-preserved','original-pending-packet-archived-before-entry','old-receipt-remains-historical','original-host-closure-not-claimed','new-explicit-decision','lost-reply-recovered-without-second-post','unknown-consumption-preserved','no-calculation-started')
}finally{await browser.close();await fs.writeFile(path.join(out,'browser-evidence.json'),JSON.stringify(report,null,2)+'\n')}
console.log(JSON.stringify({states:report.states.length,writes:report.writes.length,checks:report.checks.length,errors:report.errors.length}))
