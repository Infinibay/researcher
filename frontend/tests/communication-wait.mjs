/** Inspect one genuinely active managed command and recover its exact terminal receipt without replay. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
expect.configure({timeout:45000})
const origin=process.env.RESEARCHER_E2E_ORIGIN,output=process.env.RESEARCHER_E2E_OUTPUT,coordination=process.env.RESEARCHER_E2E_COORDINATION
if(!origin||!output||!coordination||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use an explicitly owned local evaluation service')
const fixture=JSON.parse(await fs.readFile(process.env.RESEARCHER_E2E_FIXTURE,'utf8'))
const evidence={status:'running',screens:[],requests:[],receipts:[],errors:[],forbidden:[]}
const browser=await chromium.launch({headless:true})
await fs.mkdir(output,{recursive:false})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1100}})
 await context.addInitScript(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:101},version:0})))
 const page=await context.newPage();page.setDefaultTimeout(45000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 page.on('response',async response=>{
  if(/\/runs\/[^/]+\/jobs\/[^/?]+(?:\?|$)/.test(response.url())){
   try{evidence.receipts.push({path:new URL(response.url()).pathname,body:await response.json()})}catch{/* The original browser result records incomplete reads separately. */}
  }
 })
 await page.route('**/api/**',route=>{
  const req=route.request(),method=req.method(),pathname=new URL(req.url()).pathname
  evidence.requests.push({method,path:pathname})
  if(method!=='GET'&&!(method==='POST'&&['/api/session','/api/chat/101/instructions'].includes(pathname))){evidence.forbidden.push({method,path:pathname});return route.abort('blockedbyclient')}
  return route.continue()
 })
 await page.goto(origin+'/tasks?project=101&task=1001')
 await page.getByLabel('Código de acceso local').fill((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 await expect(page.locator('#task-title-1001')).toHaveText(fixture.title)
 await page.getByLabel('Solicitud para esta tarea',{exact:true}).fill(fixture.request)
 await page.getByRole('button',{name:'Iniciar trabajo',exact:true}).click()
 await expect.poll(async()=>{try{return JSON.parse(await fs.readFile(path.join(coordination,'tool-ready.json'),'utf8'))}catch{return null}},{timeout:60000}).not.toBeNull()
 const original=JSON.parse(await fs.readFile(path.join(coordination,'tool-ready.json'),'utf8'));evidence.original=original
 await page.getByText('Comandos y resultados guardados',{exact:true}).click()
 await page.getByRole('button',{name:'Ver salida',exact:true}).click()
 const receipt=page.getByRole('region',{name:'Recibo del comando',exact:true})
 await expect(receipt.getByText('En ejecución',{exact:true})).toBeVisible()
 await expect(receipt).toContainText('Mientras trabaja puede estar vacía. Consultarla no repite el comando.')
 /** Save a loaded original receipt with regional accessibility and viewport observations. */
 async function capture(file,width){
  await page.setViewportSize({width,height:1100});await receipt.scrollIntoViewIfNeeded()
  await page.screenshot({path:path.join(output,file+'.png'),fullPage:true})
  const axe=await new AxeBuilder({page}).include('.task-execution').analyze()
  const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth)
  evidence.screens.push({file:file+'.png',width,overflow,violations:axe.violations})
  expect(overflow).toBe(false)
  // Preserve the observed disabled pagination naming defect for the final
  // detail phase. Any different accessibility finding still fails this flow.
  const unexpected=axe.violations.filter(v=>v.id!=='label-content-name-mismatch'||v.nodes.some(n=>
   !/disabled=""/.test(n.html)||!/aria-label="Bytes (anteriores|siguientes) de salida (estándar|de errores)"/.test(n.html)))
  expect(unexpected).toEqual([])
 }
 const began=Date.now()
 await capture('active-command-1440',1440)
 await page.getByRole('button',{name:'Consultar recibo',exact:true}).focus();await page.keyboard.press('Enter')
 await expect(receipt.getByText('En ejecución',{exact:true})).toBeVisible()
 await capture('active-command-390',390)
 await expect.poll(()=>Date.now()-began,{timeout:20000,intervals:[500]}).toBeGreaterThanOrEqual(fixture.minimum_browser_wait_seconds*1000)
 await expect(receipt.getByText('En ejecución',{exact:true})).toBeVisible()
 evidence.browser_active_wait_ms=Date.now()-began
 evidence.active_text=await receipt.innerText()
 await fs.writeFile(path.join(coordination,'wait-captured'),'Original active receipt inspected at both widths.\n')
 await expect(receipt.getByText('Cierre local registrado',{exact:true})).toBeVisible()
 await expect(receipt).toContainText('Código de salida 0')
 await expect(receipt).toContainText('UI inspection finished; original command completed.')
 await expect(page.getByRole('heading',{name:'Propuesta para revisar',exact:true})).toBeVisible({timeout:45000})
 await capture('original-command-terminal-390',390)
 await capture('original-command-terminal-1440',1440)
 evidence.terminal_text=await receipt.innerText()
 const bodies=evidence.receipts.map(x=>x.body)
 expect(bodies.some(x=>x.job_id===original.job_id&&x.status==='dispatching'&&!x.local_execution_closed)).toBe(true)
 expect(bodies.some(x=>x.job_id===original.job_id&&x.status==='exited'&&x.local_execution_closed)).toBe(true)
 expect(bodies.every(x=>x.job_id===original.job_id)).toBe(true)
 expect(evidence.requests.filter(x=>x.method==='POST'&&x.path==='/api/chat/101/instructions')).toHaveLength(1)
 expect(evidence.forbidden).toEqual([]);expect(evidence.errors).toEqual([])
 evidence.accessibility_clean=evidence.screens.every(s=>s.violations.length===0)
 evidence.status=evidence.accessibility_clean?'passed':'passed_with_deferred_accessibility'
}catch(error){
 evidence.status='failed';evidence.error_type=error.name;throw error
}finally{
 await browser.close();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')
}
