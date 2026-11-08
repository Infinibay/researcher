/** Exercise the selected project dossier with real storage, late replies and two explicitly bounded subscription planning requests. @module */
import { chromium, expect } from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'
import fs from 'node:fs/promises'
import path from 'node:path'

const origin=process.env.RESEARCHER_E2E_ORIGIN,ownerFile=process.env.RESEARCHER_E2E_OWNER_FILE,output=process.env.RESEARCHER_E2E_OUTPUT,source=process.env.RESEARCHER_E2E_PROJECT_SOURCE
if(!origin||!ownerFile||!output||!source||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use web_workspace.py --journey projects --live-projects on a NEW disposable installation')
await fs.mkdir(output,{recursive:false})
const evidence={status:'running',scope:'Real owner UI/HTTP/SQLite; held replies are fetched from the server, never fabricated; maximum two real planning requests',states:[],errors:[],planning:[]}
const browser=await chromium.launch({headless:true})
let page,releaseCreate,releaseStart
try{
 const context=await browser.newContext({viewport:{width:1440,height:1100}});page=await context.newPage();page.setDefaultTimeout(15000)
 page.on('pageerror',error=>evidence.errors.push(String(error)))
 /** Capture the visible dossier and automatic accessibility observations without treating them as human comprehension. */
 async function capture(name,width=1440){await page.setViewportSize({width,height:1100});await page.locator('.project-dossier').first().evaluate(el=>{for(let p=el;p;p=p.parentElement)p.scrollTop=0}).catch(()=>{});await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});const axe=await new AxeBuilder({page}).include('.project-workbench').analyze();const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width,fits,violations:axe.violations});expect(fits).toBe(true)}
 /** Submit one explicit creation and retain the identity assigned by the real server. */
 async function create(name,description){await page.getByRole('button',{name:'Nuevo proyecto',exact:true}).click();await page.getByLabel('Nombre del proyecto',{exact:true}).fill(name);await page.getByLabel('Alcance inicial',{exact:true}).fill(description);const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/projects'&&r.request().method()==='POST');await page.getByRole('button',{name:'Crear proyecto',exact:true}).click();const result=await response;expect(result.status()).toBe(201);const value=await result.json();await expect(page.getByRole('heading',{name,exact:true})).toBeVisible();return value.id}
 /** Return from task review to the project dossier using its actual navigation and scoped row. */
 async function projects(id){await page.setViewportSize({width:1440,height:1100});await page.goto(origin+'/projects');await page.locator('#project-select-'+id).click()}
 await page.goto(origin+'/projects');await page.getByLabel('Código de acceso local').fill((await fs.readFile(ownerFile,'utf8')).trim());await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 if(!process.env.RESEARCHER_E2E_PROJECT_RESUME&&!process.env.RESEARCHER_E2E_PROJECT_REVIEW){await expect(page.getByText('No hay proyectos. Crea uno con el alcance que quieras investigar; no iniciará agentes por su cuenta.')).toBeVisible();await capture('01-empty')}
 if(process.env.RESEARCHER_E2E_PROJECT_REVIEW){
  const id=Number(process.env.RESEARCHER_E2E_PROJECT_REVIEW)
  await page.locator('#project-select-'+id).click();await expect(page.getByText('Plan aceptado',{exact:true})).toBeVisible();await capture('10-current-desktop-review');await capture('11-current-mobile-review',390)
  await page.getByRole('button',{name:'Volver a proyectos',exact:true}).click();await expect(page.locator('#project-select-'+id)).toBeFocused();await page.locator('#project-select-'+id).click();await expect(page.getByRole('heading',{name:'Plan CSV comprobado',exact:true})).toBeFocused()
  await page.route(`**/api/projects/${id}/workspace`,route=>route.abort('failed'),{times:1});await page.getByRole('button',{name:'Actualizar observación',exact:true}).click();await expect(page.getByText(/No pudimos observar el proyecto/)).toBeVisible();await capture('12-transport-error-keeps-history',390)
  await page.getByRole('button',{name:'Actualizar observación',exact:true}).click();await expect(page.getByText(/No pudimos observar el proyecto/)).toHaveCount(0);await expect(page.getByText('Plan aceptado',{exact:true})).toBeVisible();evidence.status='passed';evidence.review_only=true
 }else{
 let alpha,beta
 const resume=process.env.RESEARCHER_E2E_PROJECT_RESUME?JSON.parse(process.env.RESEARCHER_E2E_PROJECT_RESUME):null
 if(resume?.mode==='fresh-generation'){
  beta=resume.beta
  alpha=await create(process.env.RESEARCHER_E2E_PROJECT_NAME||'Plan CSV comprobado','Sólo prepara un plan pequeño de dos o tres tareas para añadir exportación CSV a observations.py. Columnas id y value, orden original y cabecera, biblioteca csv estándar y pruebas unittest. Reutiliza list_observations. No implementes ni ejecutes el trabajo propuesto. No hacen falta fechas ni elegir otro formato.')
  await page.getByRole('button',{name:'Registrar carpeta existente',exact:true}).click();await page.getByLabel('Nombre del registro',{exact:true}).fill('observations-fresh');await page.getByLabel('Ruta absoluta de la carpeta',{exact:true}).fill(source);await page.getByRole('button',{name:'Registrar esta fuente',exact:true}).click();await expect(page.getByText('Carpeta registrada. No se cambió ningún archivo ni remoto.')).toBeVisible();await capture('03c-independent-project-before-generation')
 }
 else if(resume){alpha=resume.alpha;beta=resume.beta;await page.locator('#project-select-'+alpha).click();await capture('03b-original-installation-resumed')}
 else{
 beta=await create('Beta separado','No hereda el alcance ni el plan de otro proyecto.')
 let committed
 const created=new Promise(resolve=>{committed=resolve})
 await page.route('**/api/projects',async route=>{if(route.request().method()!=='POST')return route.continue();const response=await route.fetch();const value=await response.json();committed(value);await new Promise(resolve=>{releaseCreate=resolve});await route.fulfill({response})})
 await page.getByRole('button',{name:'Nuevo proyecto',exact:true}).click();await page.getByLabel('Nombre del proyecto',{exact:true}).fill('Atlas CSV');await page.getByLabel('Alcance inicial',{exact:true}).fill('Alcance original antes de la revisión.');await page.getByRole('button',{name:'Crear proyecto',exact:true}).click()
 alpha=(await created).id;await page.locator('#project-select-'+beta).click();releaseCreate();await page.locator('#project-select-'+alpha).waitFor();await expect(page.getByRole('heading',{name:'Beta separado',exact:true})).toBeVisible();await page.unroute('**/api/projects');await capture('02-late-creation-keeps-beta')
 await page.locator('#project-select-'+alpha).click();await page.getByRole('button',{name:'Editar alcance',exact:true}).click()
 const scope='Sólo prepara un plan pequeño de dos o tres tareas para añadir exportación CSV a observations.py. Columnas id y value, orden original y cabecera, biblioteca csv estándar y pruebas unittest. Reutiliza list_observations. No implementes ni ejecutes el trabajo propuesto. No hacen falta fechas ni elegir otro formato.'
 await page.getByLabel(/^Descripción actual/).fill(scope);await page.getByRole('button',{name:'Guardar alcance',exact:true}).click();await expect(page.getByText('Alcance actualizado. Las propuestas anteriores conservan su contexto original.')).toBeVisible();await page.reload();await expect(page.locator('.project-purpose')).toHaveText(scope)
 await page.getByRole('button',{name:'Registrar carpeta existente',exact:true}).click();await page.getByLabel('Nombre del registro',{exact:true}).fill('observations');await page.getByLabel('Ruta absoluta de la carpeta',{exact:true}).fill(source);await page.getByRole('button',{name:'Registrar esta fuente',exact:true}).click();await expect(page.getByText('Carpeta registrada. No se cambió ningún archivo ni remoto.')).toBeVisible();await capture('03-source-and-scope')
 let admitted,finishRoute
 const routeFinished=new Promise(resolve=>{finishRoute=resolve})
 const firstAdmission=new Promise(resolve=>{admitted=resolve})
 await page.route(`**/api/projects/${alpha}/start`,async route=>{const response=await route.fetch();expect(response.status()).toBe(200);admitted(await response.json());await new Promise(resolve=>{releaseStart=resolve});await route.fulfill({response});finishRoute()})
 await page.getByRole('button',{name:'Preparar un plan',exact:true}).click();const first=await firstAdmission;evidence.planning.push(first)
 await page.locator('#project-select-'+beta).click();await page.locator('#project-select-'+alpha).click();releaseStart();await routeFinished;await page.unroute(`**/api/projects/${alpha}/start`)
 await expect(page.getByRole('button',{name:'Recuperar planificación original',exact:true})).toHaveCount(0)
 expect(new URL(page.url()).pathname).toBe('/projects');await capture('04-late-planning-keeps-new-visit')
 await page.getByRole('button',{name:'Solicitar detención del trabajo observado',exact:true}).click()
 await expect(page.getByText(/Sin ejecución nativa activa observada/)).toBeVisible({timeout:45000});await capture('05-original-attempt-stopped')
 }
 const secondReply=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/projects/${alpha}/start`&&r.request().method()==='POST')
 await page.getByRole('button',{name:'Preparar un plan',exact:true}).click();const secondResponse=await secondReply;expect(secondResponse.status()).toBe(200);const second=await secondResponse.json();evidence.planning.push(second)
 await page.waitForURL(url=>url.pathname==='/tasks');await page.goto(origin+'/projects');await page.locator('#project-select-'+alpha).click()
 await expect(page.getByText('Propuesta guardada · revisar decisión',{exact:true})).toBeVisible({timeout:240000});await capture('06-real-plan-ready');await capture('07-real-plan-mobile',390)
 await page.locator('a[href*="planRun='+encodeURIComponent(second.run.run_id)+'"]').click()
 await expect(page.getByRole('button',{name:'Aceptar plan y crear tareas pendientes',exact:true})).toBeVisible();await page.getByRole('button',{name:'Aceptar plan y crear tareas pendientes',exact:true}).click();await expect(page.getByText('Plan aceptado. Las tareas se crearon pendientes; no se iniciaron automáticamente.',{exact:true})).toBeVisible()
 await projects(alpha);await expect(page.getByText('Plan aceptado',{exact:true})).toBeVisible();await expect(page.getByRole('button',{name:'Eliminar proyecto sin historial',exact:true})).toBeDisabled();await page.reload();await expect(page.getByText('Plan aceptado',{exact:true})).toBeVisible();await capture('08-plan-decision-after-reload')
 const unused=await create('Descartable','Proyecto de prueba sin historia.');await page.getByRole('button',{name:'Eliminar proyecto sin historial',exact:true}).click();await expect(page.getByRole('button',{name:'Conservar proyecto',exact:true})).toBeFocused();await page.keyboard.press('Escape');await expect(page.locator('#project-select-'+unused)).toBeVisible();await page.getByRole('button',{name:'Eliminar proyecto sin historial',exact:true}).click();await page.getByRole('button',{name:'Eliminar definitivamente',exact:true}).click();await expect(page.locator('#project-select-'+unused)).toHaveCount(0)
 await page.locator('#project-select-'+beta).click();await expect(page.getByText('No hay planes nativos guardados. No convertimos una tarea cualquiera en el plan del proyecto.')).toBeVisible();await capture('09-other-project-isolated')
 evidence.identities={alpha,beta,unused};expect(evidence.errors).toEqual([]);evidence.status='passed'
 }
}catch(error){evidence.status='failed';evidence.error=String(error);if(page){await page.screenshot({path:path.join(output,'failure.png'),fullPage:true}).catch(()=>{});await fs.writeFile(path.join(output,'failure.txt'),await page.locator('body').innerText()).catch(()=>{})}throw error
}finally{releaseCreate?.();releaseStart?.();await fs.writeFile(path.join(output,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}
