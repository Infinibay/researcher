/** Inspect the restored-installation correction gate with controlled HTTP and a real browser. @module */
import {chromium, expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const output = path.resolve(process.env.BROWSER_AUDIT_OUT ?? '../docs/design/audits/restored-session')
await fs.mkdir(output,{recursive:true})
const browser = await chromium.launch({headless:true})
const evidence = {states:[],errors:[],writes:[],limits:'Controlled session responses; real browser interaction, no backend, model or full-page acceptance claim.'}
try {
  const context = await browser.newContext()
  const page = await context.newPage()
  page.on('pageerror',error=>evidence.errors.push(error.message))
  await page.route('**/api/**',async route=>{
    if(!new URL(route.request().url()).pathname.startsWith('/api/'))return route.continue()
    if(route.request().method()!=='GET')evidence.writes.push(route.request().url())
    await route.fulfill({status:200,json:new URL(route.request().url()).pathname==='/api/session'?{authenticated:true,csrf_token:'controlled',endpoint_id:'restored-endpoint'}:[]})
  })
  await page.addInitScript(()=>{
    sessionStorage.setItem('researcher:owner-endpoint:v1','original-endpoint')
    sessionStorage.setItem('researcher:source-setup:v1:101','exact pending publication')
  })
  await page.goto(process.env.OWNER_ORIGIN ?? 'http://127.0.0.1:5187')
  for(const [name,width] of [['desktop',1440],['mobile',390]]) {
    await page.setViewportSize({width,height:1000})
    await expect(page.getByRole('heading',{name:'Esta instalación cambió'})).toBeVisible()
    await page.screenshot({path:path.join(output,name+'.png'),fullPage:true})
    const axe = await new AxeBuilder({page}).analyze()
    expect(axe.violations).toEqual([])
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true)
    evidence.states.push({name,width,axe:0})
  }
  const download = page.waitForEvent('download')
  await page.getByRole('button',{name:'Descargar solicitudes y borradores anteriores'}).click()
  const file = await download
  const archived = JSON.parse(await fs.readFile(await file.path(),'utf8'))
  expect(archived.entries['researcher:source-setup:v1:101']).toBe('exact pending publication')
  expect(archived.previous).toBe('original-endpoint')
  await page.evaluate(()=>{Storage.prototype.setItem=function(){throw new Error('No hay espacio para guardar el archivo')}})
  await page.getByRole('button',{name:'Archivar anteriores y abrir esta instalación'}).click()
  await expect(page.getByRole('alert')).toContainText('No hay espacio')
  expect(await page.evaluate(()=>sessionStorage.getItem('researcher:source-setup:v1:101'))).toBe('exact pending publication')
  await page.screenshot({path:path.join(output,'storage-refusal.png'),fullPage:true})
  evidence.states.push({name:'storage-refusal',preserved:true})
  expect(evidence.errors).toEqual([])
  expect(evidence.writes).toEqual([])
  await context.close()
} finally {
  await browser.close()
  await fs.writeFile(path.join(output,'results.json'),JSON.stringify(evidence,null,2)+'\n')
}
