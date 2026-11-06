/** Native graph inspector with controlled HTTP data; never a physical engine or human-comprehension acceptance test. @module */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
const out=path.resolve('../docs/design/audits/2026-11-06-flow')
await fs.mkdir(out,{recursive:true})
const hash='a'.repeat(64),project={id:1,name:'Atlas',status:'planning'}
const plans=[{run_id:'plan-a',task_id:30,title:'Contrastar el buscador',status:'accepted',accepted:1,proposed:1,context_current:true},{run_id:'plan-old',task_id:20,title:'Plan anterior',status:'accepted',accepted:1,proposed:1,context_current:false},{run_id:'plan-new',task_id:40,title:'Plan por ejecutar',status:'accepted',accepted:1,proposed:1,context_current:true}]
const tasks=[{task_id:31,title:'Reunir fuentes',type:'research',depends_on:[]},{task_id:32,title:'Contrastar resultados',type:'investigation',depends_on:[31]},{task_id:33,title:'Preparar el informe',type:'documentation',depends_on:[32]}]
const deliveries=[{delivery_id:'d-old',task_id:31,run_id:'r-old',predecessor_delivery_id:null,current:false,status:'failed',issue:null,handoff:null},{delivery_id:'d1',task_id:31,run_id:'r1',predecessor_delivery_id:'d-old',current:true,status:'accepted',issue:null,handoff:null},{delivery_id:'d2',task_id:32,run_id:'r2',predecessor_delivery_id:null,current:true,status:'reconciling',issue:{code:'peer_unconfirmed',next_action:'inspect_original'},handoff:{kind:'work.request',cause:{plan_run_id:'plan-a'},prerequisites:[{task_id:31,run_id:'r1',kind:'research',context_version:1}]}},{delivery_id:'d3',task_id:33,run_id:null,predecessor_delivery_id:null,current:true,status:'pending',issue:null,handoff:null}]
let graphStatus='active',pauseKey=null,failRead=false,pauseLost=true
const workspace={project_id:1,project,metadata_sha256:hash,history_present:true,runtime_available:true,workspace_root:'/workspace',sources:[],source_operations:[],activity:[{run_id:'r2',task_id:32,status:'reconciling',attempt_id:'a2',context_version:1,fence:1}],graphs:[{execution_id:'graph-a',plan_run_id:'plan-a',task_id:30,authorization_revision:0}],legacy_registered:false,plans,reports:[],report_validity:'not_rechecked',stop:null}
const evidence={scope:'Controlled HTTP fixtures; no model, process recovery or user data affected.',states:[],writes:[],errors:[],checks:[]}
const browser=await chromium.launch({headless:true})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>{if(!localStorage.getItem('active-project'))localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:1},version:0}))})
 const page=await context.newPage();page.setDefaultTimeout(8000)
 page.on('pageerror',e=>evidence.errors.push(String(e)))
 await page.route('**/api/**',async route=>{
  const r=route.request(),u=new URL(r.url()),p=u.pathname;if(!p.startsWith('/api/'))return route.continue()
  if(r.method()!=='GET')evidence.writes.push({path:p,method:r.method(),body:r.postDataJSON()})
  let body={}
  if(p==='/api/session')body={authenticated:true,csrf_token:'flow-fixture'}
  else if(p==='/api/projects')body={projects:[project,{...project,id:2,name:'Proyecto vacío'}],total:2}
  else if(p==='/api/projects/1')body=project
  else if(p==='/api/projects/2')body={...project,id:2,name:'Proyecto vacío'}
  else if(p.endsWith('/workspace')){
   if(failRead)return route.fulfill({status:503,json:{detail:'Consulta interrumpida'}})
   body=p.includes('/2/')?{...workspace,project_id:2,project:{...project,id:2,name:'Proyecto vacío'},plans:[],graphs:[],activity:[]}:workspace
  }else if(p.endsWith('/project-plan/execution')){
   const old=p.includes('/plan-old/'),fresh=p.includes('/plan-new/')
   body={project_id:1,task_id:old?20:fresh?40:30,plan_run_id:old?'plan-old':fresh?'plan-new':'plan-a',manifest_sha256:old?null:hash,manifest:old?null:{tasks},eligible:fresh,blocked_reason:old?'Original context changed':'',execution:fresh?null:{execution_id:old?'graph-old':'graph-a',operation_key:'start-original',manifest_sha256:hash,status:old?'paused':graphStatus,current:!old,authorization_revision:0,deliveries:old?[{...deliveries[1],task_id:21}]:deliveries}}
  }else if(p==='/api/projects/1/plan-executions/graph-a/control'){
   const b=r.postDataJSON();if(pauseKey)expect(b.operation_key).toBe(pauseKey);pauseKey=b.operation_key;graphStatus='paused'
   if(pauseLost){pauseLost=false;return route.fulfill({status:503,json:{detail:'Respuesta no confirmada'}})}
   body={project_id:1,task_id:30,plan_run_id:'plan-a',execution_id:'graph-a',operation_key:b.operation_key,manifest_sha256:hash,status:'paused'}
  }else if(p.includes('/agents')||p.includes('/tasks')||p.includes('/chat'))body=[]
  return route.fulfill({status:200,json:body})
 })
 /** Capture the graph region at a real viewport and check accessible names, contrast and horizontal fit. */
 async function capture(name,width){await page.setViewportSize({width,height:1024});await expect(page.getByRole('heading',{name:'Ejecución',exact:true})).toBeVisible();await page.screenshot({path:path.join(out,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include('.flow-workbench').analyze();expect(axe.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);evidence.states.push({name,width,axe:0})}
 await page.goto((process.env.FLOW_ORIGIN??'http://127.0.0.1:5179')+'/flow')
 if(process.env.FLOW_BASELINE==='1'){await page.getByRole('heading',{name:'Flow Progress',exact:true}).waitFor();await page.screenshot({path:path.join(out,'before.png'),fullPage:true})}
 await expect(page.getByRole('heading',{name:'Ejecución',exact:true})).toBeVisible()
 await page.locator('#flow-plan-plan-a').click()
 await expect(page.getByRole('heading',{name:'Contrastar el buscador',exact:true})).toBeVisible()
 await expect(page.locator('.flow-detail')).toContainText('1 de 3 entregas actuales con resultado aceptado')
 await page.locator('#flow-task-32').click()
 await expect(page.getByRole('region',{name:'Detalle de la tarea'})).toContainText('Reunir fuentes')
 await expect(page.getByRole('region',{name:'Detalle de la tarea'})).toContainText('peer_unconfirmed')
 await expect(page.getByRole('link',{name:'Abrir tarea y recuperación'})).toHaveAttribute('href','/tasks?project=1&task=32')
 await capture('01-desktop-inspector',1440);await capture('02-mobile-inspector',390)
 await page.getByRole('link',{name:'Abrir tarea y recuperación'}).scrollIntoViewIfNeeded();await capture('02b-mobile-intervention',390)
 await page.getByRole('region',{name:'Detalle de la tarea'}).getByRole('button',{name:'Reunir fuentes',exact:true}).click()
 await page.getByText('1 entrega(s) anterior(es)',{exact:true}).click()
 await expect(page.getByRole('region',{name:'Detalle de la tarea'})).toContainText('Intento fallido · entrega histórica')
 await capture('02c-mobile-history',390)
 await page.getByRole('button',{name:'Volver a tareas'}).click();await page.locator('#flow-task-32').click()
 expect(evidence.writes).toEqual([])
 await page.getByText('Controles del plan',{exact:true}).click()
 await page.getByRole('button',{name:'Pausar despacho y solicitar detención'}).click()
 await expect(page.getByRole('alert')).toContainText('No se confirmó la decisión')
 await capture('03-uncertain-pause',390)
 await page.reload();await page.locator('#flow-plan-plan-a').click();await page.getByText('Controles del plan',{exact:true}).click()
 await page.getByRole('button',{name:'Reenviar la misma decisión de ejecución'}).click()
 await expect(page.getByText('Decisión registrada. El estado de cada intento y su cierre se muestran por separado.')).toBeVisible()
 await expect(page.locator('.flow-detail')).toContainText('Despacho pausado')
 await capture('04-original-pause-recovered',390)
 expect(evidence.writes).toHaveLength(2);expect(evidence.writes[0].body).toEqual(evidence.writes[1].body)
 await page.getByRole('button',{name:'Volver a planes'}).click();await page.locator('#flow-plan-plan-old').click()
 await expect(page.locator('.flow-detail')).toContainText('El contexto cambió')
 await expect(page.locator('.flow-detail')).toContainText('Dependencias no verificables')
 await expect(page.locator('.flow-detail')).not.toContainText('1 de 1 entregas actuales con resultado aceptado')
 await capture('05-stale-context',390)
 await page.getByRole('button',{name:'Volver a planes'}).click();await page.locator('#flow-plan-plan-new').click()
 await expect(page.locator('.flow-detail')).toContainText('Plan aceptado, ejecución aún no autorizada')
 await expect(page.locator('.flow-detail')).not.toContainText('En ejecución')
 await capture('06-not-authorized',390)
 await page.getByRole('button',{name:'Seleccionar proyecto: Atlas'}).click();await page.getByRole('button',{name:'Proyecto vacío',exact:true}).click()
 await expect(page.getByText('Todavía no hay planes aceptados en este proyecto.')).toBeVisible();await expect(page.locator('.flow-workbench')).not.toContainText('Contrastar el buscador')
 await capture('07-project-switch',390)
 failRead=true;await page.reload();await expect(page.getByRole('alert')).toContainText('No pudimos consultar el recorrido')
 await expect(page.getByText('Todavía no hay planes aceptados en este proyecto.')).toHaveCount(0)
 await capture('08-read-error',390)
 evidence.checks.push('actual-dependencies','current-deliveries-exclude-history','issue-and-original-recovery','reading-does-not-execute','lost-pause-retains-packet-across-reload','stale-context-is-not-progress','accepted-plan-is-not-authorization','project-isolation','read-error-is-not-empty')
 expect(evidence.errors).toEqual([])
}finally{await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}
