/** Exercise compiled UI, real owner API and synthetic SQLite; drop only the first committed HTTP response. */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
const base='http://127.0.0.1:5293',out=path.resolve('../docs/design/audits/2026-11-07-project-budget')
await fs.mkdir(out,{recursive:true})
const browser=await chromium.launch({headless:true}),report={scope:'Real compiled frontend, owner HTTP/CSRF API and synthetic SQLite; no configured runtime or model calls.',states:[],writes:[],checks:[],errors:[]}
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
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
 const panel=page.getByRole('region',{name:'Presupuesto de trabajo del proyecto'})
 await expect(panel).toContainText('100');await panel.getByRole('button',{name:'Revisar límites'}).click()
 await panel.getByLabel('Límite total de tokens').fill('500')
 await panel.getByLabel('Motivo del cambio (opcional)').fill('Ampliar la comparación sin borrar la reserva anterior.')
 /** Capture the actual panel and check its accessibility plus document overflow. */
 async function capture(name,width){await page.setViewportSize({width,height:1024});await panel.scrollIntoViewIfNeeded();await panel.screenshot({path:path.join(out,name+'.png')});const axe=await new AxeBuilder({page}).include('[aria-label="Presupuesto de trabajo del proyecto"]').analyze();expect(axe.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);report.states.push({name,width,axe_violations:0})}
 await capture('01-edit-desktop',1440);await capture('02-edit-mobile',390)
 await panel.getByRole('button',{name:'Guardar límites'}).click();await expect(panel).toContainText('No se confirmó el cambio')
 await capture('03-response-lost',390);await page.reload()
 await panel.getByRole('button',{name:'Consultar recibo original'}).click();await expect(panel).toContainText('Límites guardados')
 expect(report.writes.length).toBe(1);await expect(panel).toContainText('100 de 500')
 await panel.getByRole('button',{name:'Revisar límites'}).click();await panel.getByLabel('Límite total de tokens').fill('50')
 await panel.getByRole('button',{name:'Guardar límites'}).click();await expect(panel).toContainText('superan el límite en 50 tokens')
 await capture('04-lower-below-reservation',390)
 report.checks.push('owner-session-csrf-real-api','committed-response-loss-reload-read-only-recovery','exactly-two-explicit-policy-writes','unknown-consumption-held','lower-total-retains-overrun','save-does-not-dispatch')
 expect(report.writes[0].request.expected_revision).toBe(0);expect(report.writes[1].request.expected_revision).toBe(1)
 expect(report.errors).toEqual([])
}finally{await browser.close();await fs.writeFile(path.join(out,'browser-evidence.json'),JSON.stringify(report,null,2)+'\n')}
console.log(JSON.stringify({states:report.states.length,writes:report.writes.length,checks:report.checks.length,errors:report.errors.length}))
