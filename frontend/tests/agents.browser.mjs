/** Exercise the native agent ledger with controlled HTTP receipts; this is UI evidence, not real execution. */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
const out=path.resolve('../docs/design/audits/2026-11-06-agents')
await fs.mkdir(out,{recursive:true})
const base={project_id:1,actor_id:'researcher-a',task_id:31,task_title:'Contrastar las fuentes',task_type:'research',execution_kind:'research',context_version:1,status:'running',cancel_requested:false,attempt_id:'attempt-a',attempt_count:1,attempt_status:'running',model:'gpt-5',model_selection:{model:'gpt-5',reasoning_effort:'medium',source:'project:1'},dispatch_status:'reserved',observed_tokens:1240,token_ceiling:12000,peer_count:2,unclosed_peer_count:2,created_at:1793980000,started_at:1793980001}
let records=[{...base,seq:'3',run_id:'run-a'},{...base,seq:'2',run_id:'run-b',task_id:32,task_title:'Preparar comparación',actor_id:'planner-a',status:'queued',attempt_id:null,attempt_status:null,attempt_count:0,model:null,model_selection:null,dispatch_status:null,observed_tokens:null,token_ceiling:null,peer_count:0,unclosed_peer_count:0}]
const earlier={...base,seq:'1',run_id:'run-old',task_id:33,task_title:'Revisión anterior',status:'reconciling',attempt_id:'attempt-old',observed_tokens:null,dispatch_status:'unknown'}
const project={id:1,name:'Atlas',status:'planning',description:'Contrastar fuentes con evidencia.'}
const evidence={scope:'Controlled HTTP fixtures; no actual model, runtime or user data.',states:[],writes:[],errors:[],checks:[]}
const browser=await chromium.launch({headless:true})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:1},version:0}))})
 const page=await context.newPage();page.setDefaultTimeout(8000)
 let readError=false,stopError=true
 page.on('pageerror',e=>evidence.errors.push(String(e)))
 await page.route('**/api/**',async route=>{
  const r=route.request(),u=new URL(r.url()),p=u.pathname;if(!p.startsWith('/api/'))return route.continue()
  if(r.method()!=='GET')evidence.writes.push({method:r.method(),path:p})
  let body={}
  if(p==='/api/session')body={authenticated:true,csrf_token:'agents-fixture',endpoint_id:'fixture-agents-installation'}
  else if(p==='/api/projects')body={projects:[project,{...project,id:2,name:'Proyecto vacío'}],total:2}
  else if(p==='/api/projects/1')body=project
  else if(p==='/api/projects/2')body={...project,id:2,name:'Proyecto vacío'}
  else if(p.endsWith('/agent-runs')){
   if(readError)return route.fulfill({status:503,json:{detail:'Consulta interrumpida'}})
   body={project_id:p.includes('/2/')?2:1,total_runs:3,total_actors:2,runtime_configured:true,items:u.searchParams.has('before_seq')?[earlier]:records,next_before_seq:u.searchParams.has('before_seq')?null:'2'}
   if(p.includes('/2/'))body={...body,total_runs:0,total_actors:0,items:[],next_before_seq:null}
  }else if(p==='/api/projects/1/runs/run-a/stop'){
   if(stopError)return route.fulfill({status:503,json:{detail:'No se pudo confirmar el cierre'}})
   records=records.map(r=>r.run_id==='run-a'?{...r,status:'cancelling',cancel_requested:true}:r);body=records[0]
  }else if(p.includes('/agents')||p.includes('/tasks')||p.includes('/chat'))body=[]
  return route.fulfill({status:200,json:body})
 })
 /** Capture actual layout and accessibility of the redesigned agent region. */
 async function capture(name,width){await page.setViewportSize({width,height:1024});await page.screenshot({path:path.join(out,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include('.agents-workbench').analyze();expect(axe.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);evidence.states.push({name,width,axe:0})}
 await page.goto((process.env.AGENTS_ORIGIN??'http://127.0.0.1:5179')+'/agents')
 if(process.env.AGENTS_BASELINE==='1'){await page.getByText('No agents yet',{exact:true}).waitFor();await page.screenshot({path:path.join(out,'before.png'),fullPage:true})}
 await expect(page.getByRole('heading',{name:'Agentes',exact:true})).toBeVisible()
 await page.locator('#agent-run-run-a').click()
 await expect(page.getByRole('heading',{name:'Contrastar las fuentes',exact:true})).toBeVisible()
 await expect(page.getByRole('link',{name:'Abrir tarea e historial'})).toHaveAttribute('href','/tasks?project=1&task=31')
 await expect(page.locator('.agents-detail')).toContainText('1.240')
 await capture('01-desktop',1440);await capture('02-mobile',390)
 await page.getByRole('button',{name:'Detener esta ejecución',exact:true}).scrollIntoViewIfNeeded();await capture('02b-mobile-control',390)
 expect(evidence.writes).toEqual([])
 await page.getByRole('button',{name:'Detener esta ejecución',exact:true}).click()
 await expect(page.getByRole('alert')).toContainText('No se confirmó la parada')
 await expect(page.locator('.agents-detail')).toContainText('En ejecución')
 await capture('03-stop-uncertain',390)
 stopError=false;await page.getByRole('button',{name:'Detener esta ejecución',exact:true}).click()
 await expect(page.locator('.agents-detail')).toContainText('Parada solicitada')
 await expect(page.getByRole('button',{name:'Detener esta ejecución',exact:true})).toBeDisabled()
 await capture('04-stop-requested',390)
 await page.getByRole('button',{name:'Volver a ejecuciones'}).click();await page.locator('#agent-run-run-b').click()
 await expect(page.locator('.agents-detail')).toContainText('No disponible')
 await expect(page.locator('.agents-detail')).toContainText('Sin intento registrado')
 await expect(page.locator('.agents-detail')).not.toContainText('0 tokens')
 await capture('05-queued-unknown',390)
 await page.getByRole('button',{name:'Volver a ejecuciones'}).click();await page.getByRole('button',{name:'Cargar ejecuciones anteriores'}).click();await page.locator('#agent-run-run-old').click()
 await expect(page.locator('.agents-detail')).toContainText('Requiere comprobación')
 await expect(page.locator('.agents-detail')).toContainText('No disponible')
 evidence.checks.push('scoped-native-ledger','unknown-is-not-zero','original-task-link','stop-failure-not-success','stop-request-not-closure','older-run-pagination')
 await page.getByRole('button',{name:'Seleccionar proyecto: Atlas'}).click();await page.getByRole('button',{name:'Proyecto vacío',exact:true}).click()
 await expect(page.getByText('Todavía no hay ejecuciones nativas en este proyecto.')).toBeVisible()
 await expect(page.locator('.agents-workbench')).not.toContainText('Contrastar las fuentes')
 await capture('06-project-isolation',390)
 readError=true;await page.reload();await expect(page.getByRole('alert')).toContainText('No pudimos consultar las ejecuciones')
 await expect(page.getByText('Todavía no hay ejecuciones nativas en este proyecto.')).toHaveCount(0)
 await capture('07-read-error',390)
 readError=false;await page.getByRole('button',{name:'Volver a consultar'}).click();await expect(page.getByText('Todavía no hay ejecuciones nativas en este proyecto.')).toBeVisible()
 evidence.checks.push('project-switch-clears-selection','query-error-is-not-empty','explicit-read-retry')
 expect(evidence.errors).toEqual([]);expect(evidence.writes).toEqual([{method:'POST',path:'/api/projects/1/runs/run-a/stop'},{method:'POST',path:'/api/projects/1/runs/run-a/stop'}])
}finally{await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}
