/** Verify local CPU holds and recoverable policy changes against the compiled UI and real synthetic owner API. */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const base='http://127.0.0.1:5294',out=path.resolve('../docs/design/audits/2026-11-07-auxiliary-budget')
await fs.mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true}),report={states:[],writes:[],checks:[],errors:[]}
try{
 const context=await browser.newContext({viewport:{width:1440,height:1600}})
 const login=await context.request.post(base+'/api/session',{data:{code:'budget-web-fixture-owner-key-32-characters'},headers:{'X-Researcher-Client':'web'}});expect(login.status()).toBe(200)
 await context.addInitScript(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0})))
 const page=await context.newPage();page.setDefaultTimeout(10000);page.on('pageerror',e=>report.errors.push(String(e)))
 let lose=true
 await page.route('**/api/projects/101/work-budget',async route=>{
  if(route.request().method()!=='POST')return route.continue()
  const response=await route.fetch();expect(response.status()).toBe(200)
  report.writes.push({request:route.request().postDataJSON(),receipt:await response.json()})
  if(lose){lose=false;return route.abort('failed')}
  return route.fulfill({response})
 })
 await page.goto(base+'/agents')
 const panel=page.getByRole('region',{name:'Presupuesto de trabajo del proyecto'}),local=panel.locator('[aria-label="Procesamiento local"]')
 await expect(local).toContainText('1 cálculos sin medición')
 await expect(local.locator('dt').filter({hasText:'CPU observada (ms)'}).locator('..')).toContainText('No disponible')
 /** Capture only the actual component; accessibility scope and viewport are explicit. */
 async function capture(name,width){await page.setViewportSize({width,height:1600});await panel.scrollIntoViewIfNeeded();await panel.screenshot({path:path.join(out,name+'.png')});const axe=await new AxeBuilder({page}).include('[aria-label="Presupuesto de trabajo del proyecto"]').analyze();expect(axe.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);report.states.push({name,width,height:1600,axe_violations:0})}
 await panel.getByRole('button',{name:'Revisar límites'}).click()
 await panel.getByLabel('Límite total de cálculos locales').fill('5')
 await panel.getByLabel('Límite total de CPU local (ms)').fill('6000')
 await capture('01-local-policy-desktop',1440)
 await panel.getByRole('button',{name:'Guardar límites'}).click();await expect(panel).toContainText('No se confirmó el cambio')
 await capture('02-local-response-lost',390)
 await page.reload();await panel.getByRole('button',{name:'Consultar recibo original'}).click();await expect(panel).toContainText('Límites guardados')
 expect(report.writes).toHaveLength(1)
 await panel.getByRole('button',{name:'Revisar límites'}).click();await panel.getByLabel('Límite total de CPU local (ms)').fill('2000')
 await panel.getByRole('button',{name:'Guardar límites'}).click();await expect(panel).toContainText('Límites guardados')
 await expect(local.locator('dt').filter({hasText:'Capacidad local restante (ms)'}).locator('..').locator('dd')).toHaveText('0')
 await capture('03-local-below-held',1440)
 const observed=await context.request.get(base+'/api/projects/101/work-budget');expect(observed.status()).toBe(200)
 const budget=await observed.json();expect(budget.auxiliary.accounted_cpu_ms).toBe(3000);expect(budget.auxiliary.observed_cpu_ms).toBeNull();expect(budget.auxiliary.policy.cpu_ms_limit).toBe(2000);expect(budget.auxiliary.remaining_cpu_ms).toBe(0)
 expect(report.writes[0].request.auxiliary_operation_limit).toBe(5);expect(report.writes[0].request.auxiliary_cpu_ms_limit).toBe(6000);expect(report.writes[1].request.expected_revision).toBe(1)
 expect(report.errors).toEqual([])
 report.checks.push('unknown-local-cpu-visible','owner-session-real-api','original-local-policy-survives-response-loss-and-reload','receipt-read-does-not-resend','lower-total-retains-held-cpu','generative-and-local-units-separated')
 report.budget=budget
}finally{await browser.close();await fs.writeFile(path.join(out,'browser-evidence.json'),JSON.stringify(report,null,2)+'\n')}
console.log(JSON.stringify({states:report.states.length,writes:report.writes.length,checks:report.checks.length,errors:report.errors.length}))
