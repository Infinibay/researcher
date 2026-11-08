/** Capture a retained real review outcome with read-only owner navigation before changing execution communication. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT
if(!origin||!output||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use an explicitly owned local reader')
const evidence={status:'running',screens:[],errors:[],forbidden:[],requests:[]}
const fixture=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
let fault=false
const browser=await chromium.launch({headless:true})
await fs.mkdir(output,{recursive:false})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1100}})
 await context.addInitScript(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0})))
 const page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 await page.route('**/api/**',route=>{
  const req=route.request(),method=req.method(),pathname=new URL(req.url()).pathname
  evidence.requests.push({method,path:pathname})
  if(fault&&method==='GET'&&pathname==='/api/projects/101/tasks/1001/workspace')return route.abort('connectionfailed')
  if(method!=='GET'&&!(method==='POST'&&pathname==='/api/session')){evidence.forbidden.push({method,path:pathname});return route.abort('blockedbyclient')}
  return route.continue()
 })
 await page.goto(origin+'/tasks?project=101&task=1001'+(fixture.run?'&planRun='+fixture.run:''))
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.locator('#task-title-1001')).toHaveText(fixture.title)
 await expect(page.getByText('Cargando la tarea…',{exact:true})).toHaveCount(0)
 /** Capture an actually loaded region and its scoped accessibility/overflow evidence. */
 async function capture(file,width,anchor){
  await page.setViewportSize({width,height:1100})
  await anchor.scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(output,file+'.png'),fullPage:true})
  const scope=await page.locator('.task-execution').count()?'.task-execution':'main [role="alert"]'
  const audit=await new AxeBuilder({page}).include(scope).analyze()
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  evidence.screens.push({file:file+'.png',width,overflow,scope,violations:audit.violations})
  expect(overflow).toBe(false);expect(audit.violations).toEqual([])
 }
 for(const width of [1440,390]){
  if(fixture.kind==='code_review'){
   await expect(page.getByRole('heading',{name:'Revisión terminada',exact:true})).toBeVisible()
   await expect(page.getByRole('button',{name:'Cerrar intento pendiente',exact:true})).toBeVisible()
   await expect(page.getByRole('button',{name:'Detener ejecución',exact:true})).toHaveCount(0)
   await capture('review-status-'+width,width,page.locator('#task-title-1001'))
   await capture('saved-review-'+width,width,page.getByRole('heading',{name:'Propuesta',exact:true}))
  }else{
   await expect(page.getByRole('heading',{name:'Ejecución fallida',exact:true})).toBeVisible()
   await expect(page.getByRole('heading',{name:fixture.proposal,exact:true})).toBeVisible()
   await expect(page.getByRole('button',{name:'Aceptar plan y crear tareas pendientes',exact:true})).toHaveCount(0)
   await expect(page.locator('.task-execution')).not.toContainText('falta comprobar su cierre o su contexto cambió')
   await capture('partial-issue-'+width,width,page.getByRole('heading',{name:'Ejecución fallida',exact:true}))
   await capture('saved-plan-'+width,width,page.getByRole('heading',{name:fixture.proposal,exact:true}))
  }
 }
 fault=true
 const unavailable=page.getByRole('alert').filter({hasText:'No se pudo recuperar esta tarea.'})
 await expect(unavailable).toBeVisible()
 await capture('read-failure',390,unavailable)
 fault=false
 await page.getByRole('button',{name:'Volver a consultar',exact:true}).focus()
 await page.keyboard.press('Enter')
 await expect(unavailable).toHaveCount(0)
 const recovered=page.getByRole('heading',{name:fixture.kind==='code_review'?'Revisión terminada':fixture.proposal,exact:true})
 await expect(recovered).toBeVisible()
 await capture('original-result-recovered',390,recovered)
 evidence.visible_text=await page.locator('main').innerText()
 expect(evidence.forbidden).toEqual([]);expect(evidence.errors).toEqual([])
 evidence.status='passed'
}finally{
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}
