/** Planning UI exercise with explicit controlled HTTP data, not a backend or native-model acceptance test. */
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'
const origin=process.env.PLANNING_ORIGIN??'http://127.0.0.1:5179'
const out=path.resolve('../docs/design/audits/2026-11-06-planning')
await fs.mkdir(out,{recursive:true})
const project={id:1,name:'Atlas',description:'Contrastar la precisión del buscador con fuentes verificables.',status:'planning'}
let epics=[{id:10,project_id:1,title:'Contrastar el buscador',description:'Reunir evidencia y contrastar los resultados.',status:'open',priority:2,task_count:2,tasks_done:1,milestone_count:1}]
let milestones=[{id:20,project_id:1,epic_id:10,title:'Fuentes contrastadas',description:'Corpus trazable.',status:'open',task_count:1,tasks_done:1,due_date:null}]
const tasks=[{id:31,project_id:1,epic_id:10,milestone_id:20,title:'Reunir fuentes',type:'research',status:'done'},{id:32,project_id:1,epic_id:10,title:'Comparar resultados',type:'investigation',status:'pending'},{id:30,project_id:1,title:'Plan original',type:'plan',status:'review_ready'}]
const plan={project_id:1,task_id:30,run_id:'plan-a',context_version:1,snapshot:{project,owner_request:'Contrastar el buscador',instruction_origin:'owner_message',sources:{}},proposal:{proposal_sha256:'a'.repeat(64),draft:{title:'Contrastar el buscador',rationale:'Comparar con un corpus verificable antes de cambiar código.',assumptions:['El corpus inicial representa las consultas habituales.'],basis:[{source:'owner_request',quote:'Contrastar el buscador'}],epics:[{key:'contrast',title:'Contrastar el buscador',description:'Evaluación con evidencia.'}],tasks:[{key:'sources',epic_key:'contrast',type:'research',title:'Reunir fuentes',description:'Conservar citas.',acceptance_criteria:'Fuentes verificables.',priority:2,depends_on:[]},{key:'compare',epic_key:'contrast',type:'investigation',title:'Comparar resultados',description:'Medir con fuentes.',acceptance_criteria:'Comparación reproducible.',priority:2,depends_on:['sources']}]}},acceptance:null,acceptance_current:false,eligible:true,blocked_reason:''}
const workspace={project_id:1,project,metadata_sha256:'b'.repeat(64),history_present:true,runtime_available:true,workspace_root:'/workspace',sources:[],source_operations:[],activity:[],graphs:[],legacy_registered:false,plans:[{run_id:'plan-a',task_id:30,title:'Plan original',status:'needs_review',accepted:0,proposed:1,context_current:true}],reports:[],report_validity:'not_rechecked',stop:null}
const evidence={scope:'Controlled API fixtures; UI reads/owner CRUD only; native acceptance remains in original Tasks route.',states:[],writes:[],errors:[],checks:[]}
const browser=await chromium.launch({headless:true})
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 await context.addInitScript(()=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:1},version:0})))
 const page=await context.newPage();page.setDefaultTimeout(8000)
 let failMilestones=false,failCreate=false
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 await page.route('**/api/**',async route=>{
  const r=route.request(),u=new URL(r.url()),p=u.pathname;if(!p.startsWith('/api/'))return route.continue()
  if(r.method()!=='GET')evidence.writes.push({method:r.method(),path:p,body:r.postDataJSON()})
  let body={}
  if(p==='/api/session')body={authenticated:true,csrf_token:'planning-fixture'}
  else if(p==='/api/projects')body={projects:[project,{...project,id:2,name:'Proyecto vacío'}],total:2}
  else if(p==='/api/projects/1')body=project
  else if(p==='/api/projects/2')body={...project,id:2,name:'Proyecto vacío'}
  else if(p.endsWith('/workspace'))body=p.includes('/2/')?{...workspace,project_id:2,project:{...project,id:2,name:'Proyecto vacío'},plans:[]}:workspace
  else if(p.endsWith('/project-plan'))body=plan
  else if(p==='/api/epics'&&r.method()==='POST'){
   if(failCreate)return route.fulfill({status:422,json:{detail:'Título rechazado por el fixture'}})
   const e={...r.postDataJSON(),id:11,status:'open',task_count:0,tasks_done:0,milestone_count:0};epics=[...epics,e];body=e
  }else if(p==='/api/epics')body=u.searchParams.get('project_id')==='2'?[]:epics
  else if(p==='/api/epics/11'&&r.method()==='DELETE'){epics=epics.filter(e=>e.id!==11);return route.fulfill({status:204})}
  else if(p==='/api/milestones'&&r.method()==='POST'){body={...r.postDataJSON(),id:21,project_id:1,status:'open',task_count:0,tasks_done:0};milestones=[...milestones,body]}
  else if(p==='/api/milestones'){
   if(failMilestones)return route.fulfill({status:503,json:{detail:'Hitos no disponibles'}})
   body=u.searchParams.get('project_id')==='2'?[]:milestones
  }else if(p==='/api/tasks')body=u.searchParams.get('project_id')==='2'?[]:tasks
  else if(p==='/api/tasks/32/dependencies')body=[{task_id:32,depends_on_task_id:31,dependency_type:'blocks'}]
  else if(p.endsWith('/dependencies'))body=[]
  else if(p.includes('/chat')||p.includes('/agents'))body=[]
  return route.fulfill({status:200,json:body})
 })
 /** Capture the current panel and reject accessibility or horizontal layout regressions. */
 async function capture(name,width){await page.setViewportSize({width,height:1024});await page.screenshot({path:path.join(out,`${name}.png`),fullPage:true});const axe=await new AxeBuilder({page}).include('.planning-workbench').analyze();expect(axe.violations).toEqual([]);expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);evidence.states.push({name,width,axe:0})}
 await page.goto(origin+'/epics')
 if(process.env.PLANNING_BASELINE==='1'){await page.getByRole('heading',{name:'Epics',exact:true}).waitFor();await page.screenshot({path:path.join(out,'before.png'),fullPage:true})}
 await expect(page.getByRole('heading',{name:'Planificación',exact:true})).toBeVisible()
 await page.locator('#planning-group-10').click()
 await expect(page.getByRole('heading',{name:'Contrastar el buscador',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Ver dependencias: Comparar resultados'}).click()
 await expect(page.getByRole('region',{name:'Dependencias de Comparar resultados'})).toContainText('Reunir fuentes')
 await capture('01-desktop-group',1440)
 await capture('02-mobile-group',390)
  await page.getByRole('region',{name:'Dependencias de Comparar resultados'}).scrollIntoViewIfNeeded()
  await capture('02b-mobile-dependencies',390)
 await page.getByRole('button',{name:'Volver al índice'}).click()
 await page.locator('#planning-plan-plan-a').click()
 await expect(page.getByRole('heading',{name:'Lo que se está suponiendo'})).toBeVisible()
 await expect(page.getByRole('link',{name:'Revisar y decidir en la tarea original'})).toHaveAttribute('href','/tasks?project=1&task=30&planRun=plan-a')
 await expect(page.locator('.planning-workbench')).toContainText('Depende de: Reunir fuentes')
 await capture('03-mobile-proposal',390)
  await page.getByRole('link',{name:'Revisar y decidir en la tarea original'}).scrollIntoViewIfNeeded()
  await capture('03b-mobile-original-decision',390)
 expect(evidence.writes).toEqual([]);evidence.checks.push('dependency-read','original-plan-link','proposal-is-not-execution')
 await page.getByRole('button',{name:'Volver al índice'}).click()
 await page.getByRole('button',{name:'Nuevo grupo'}).click()
 await page.getByLabel('Nombre del grupo').fill('Preparar evaluación')
 failCreate=true;await page.getByRole('button',{name:'Crear grupo',exact:true}).click()
 await expect(page.getByRole('alert')).toContainText('No se confirmó la creación')
 await expect(page.getByLabel('Nombre del grupo')).toHaveValue('Preparar evaluación')
  await capture('03c-create-error-draft',390)
 failCreate=false;await page.getByRole('button',{name:'Crear grupo',exact:true}).click()
 await expect(page.getByRole('heading',{name:'Preparar evaluación',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Añadir hito'}).click()
 await page.getByLabel('Nombre del hito').fill('Primera medición')
 await page.getByRole('button',{name:'Guardar hito'}).click()
 await expect(page.getByText('Primera medición',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'Eliminar grupo'}).click()
 await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByRole('button',{name:'Conservar grupo'})).toBeFocused()
  const dialogAxe=await new AxeBuilder({page}).include('.planning-delete').analyze();expect(dialogAxe.violations).toEqual([])
  await page.screenshot({path:path.join(out,'03d-delete-dialog.png'),fullPage:true})
 await page.getByRole('button',{name:'Conservar grupo'}).click()
 await expect(page.getByRole('dialog')).toHaveCount(0)
 await page.getByRole('button',{name:'Eliminar grupo'}).click()
 await page.getByRole('button',{name:'Eliminar este grupo'}).click()
 await expect(page.locator('#planning-group-11')).toHaveCount(0)
 evidence.checks.push('create-error-preserves-draft','create-group-and-milestone','delete-explicit-dialog')
 failMilestones=true;await page.reload();await page.locator('#planning-group-10').click()
 await expect(page.getByText('No pudimos consultar los hitos.')).toBeVisible()
 await expect(page.getByText('Este grupo no tiene hitos registrados.')).toHaveCount(0)
 await capture('04-partial-error',390)
 await page.getByRole('button',{name:'Seleccionar proyecto: Atlas'}).click();await page.getByRole('button',{name:'Proyecto vacío',exact:true}).click()
 await expect(page.getByText('Todavía no hay grupos en este proyecto.')).toBeVisible()
 await expect(page.locator('.planning-workbench')).not.toContainText('Comparar resultados')
 await capture('05-other-project',390)
 evidence.checks.push('partial-error-not-empty','project-scope-reset');expect(evidence.errors).toEqual([]);evidence.status='passed'
}finally{await browser.close();await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n')}
