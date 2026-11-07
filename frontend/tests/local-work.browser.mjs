/** Exercise actual owner authorization and response recovery against the compiled UI and disposable SQLite API. */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const base='http://127.0.0.1:5295',out=path.resolve('../docs/design/audits/2026-11-07-local-continuation')
await fs.mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true}),report={states:[],writes:[],checks:[],errors:[]}
try{
 const context=await browser.newContext({viewport:{width:1440,height:2200}})
 const login=await context.request.post(base+'/api/session',{data:{code:'budget-web-fixture-owner-key-32-characters'},headers:{'X-Researcher-Client':'web'}});expect(login.status()).toBe(200)
 await context.addInitScript(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0})))
 const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',error=>report.errors.push(String(error)))
 await page.route('**/api/projects/101/local-work/continuations',async route=>{
  if(route.request().method()!=='POST')return route.continue()
  const response=await route.fetch();expect(response.status()).toBe(200)
  report.writes.push({request:route.request().postDataJSON(),receipt:await response.json()})
  return route.abort('failed')
 })
 await page.goto(base+'/agents')
 const local=page.getByRole('region',{name:'Historial de cálculos locales'})
 /** Capture the actual local-work component with its own accessibility and overflow observations. */
 async function capture(name,width){await page.setViewportSize({width,height:2200});await local.scrollIntoViewIfNeeded();await local.screenshot({path:path.join(out,name+'.png')});const axe=await new AxeBuilder({page}).include('[aria-label="Historial de cálculos locales"]').analyze();expect(axe.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);report.states.push({name,width,height:2200,axe_violations:0})}
 await local.getByRole('button',{name:'Revisar cálculos locales'}).click()
 await local.getByRole('button',{name:'Autorizar un nuevo cálculo'}).click()
 await expect(local).toContainText('La próxima solicitud idéntica del usuario o de un agente')
 await local.getByLabel('Motivo de la continuación (opcional)').fill('Volver a calcular después del cierre comprobado.')
 await capture('01-local-authorization-desktop',1440)
 await local.getByRole('button',{name:'Guardar autorización'}).click();await expect(local).toContainText('No se confirmó la autorización')
 await capture('02-local-response-lost-mobile',390)
 await page.reload();await local.getByRole('button',{name:'Consultar autorización original'}).click()
 await expect(local).toContainText('Autorización guardada. No se inició un cálculo.')
 expect(report.writes).toHaveLength(1)
 await local.getByRole('button',{name:'Revisar cálculos locales'}).click()
 await expect(local).toContainText('Ya autorizaste una sucesora.')
 await expect(local.getByRole('button',{name:'Autorizar un nuevo cálculo'})).toHaveCount(0)
 await capture('03-original-authorization-recovered',1440)
 const response=await context.request.get(base+'/api/projects/101/work-budget');expect(response.status()).toBe(200)
 report.budget=await response.json();expect(report.budget.auxiliary.used_operations).toBe(1);expect(report.budget.auxiliary.accounted_cpu_ms).toBe(3000)
 const foreign=await context.request.get(base+'/api/projects/202/local-work/continuations/'+report.writes[0].request.operation_key);expect(foreign.status()).toBe(404)
 expect(report.writes[0].receipt.work_started).toBe(false);expect(report.errors).toEqual([])
 report.checks.push('actual-owner-api','unknown-cpu-preserved','explicit-explanation-before-save','lost-post-response-after-commit','reload-recovers-original-receipt-without-post','permission-does-not-start-work','foreign-project-receipt-excluded')
}finally{await browser.close();await fs.writeFile(path.join(out,'browser-evidence.json'),JSON.stringify(report,null,2)+'\n')}
console.log(JSON.stringify({states:report.states.length,writes:report.writes.length,checks:report.checks.length,errors:report.errors.length}))
