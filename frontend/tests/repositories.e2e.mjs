/** Exercise explicit source setup and immutable reading through actual owner HTTP and fixture-owned TLS Git. @module */
import fs from 'node:fs/promises'
import path from 'node:path'
import assert from 'node:assert/strict'
import {randomUUID} from 'node:crypto'
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const origin=process.env.RESEARCHER_E2E_ORIGIN,owner=process.env.RESEARCHER_E2E_OWNER_FILE,out=process.env.RESEARCHER_E2E_OUTPUT,fixtureFile=process.env.RESEARCHER_E2E_REPOSITORY_FIXTURE
if(!origin||!owner||!out||!fixtureFile||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use repositories_workspace.py with a NEW synthetic installation')
const fixture=JSON.parse(await fs.readFile(fixtureFile,'utf8'))
await fs.mkdir(out,{recursive:false})
const evidence={status:'running',states:[],operations:[],errors:[],checks:[],model_turns:0,external_contract:'Real TLS smart Git plus controlled Forgejo REST fixture; no user server'}
const browser=await chromium.launch({headless:true})
let context,page
try{
 context=await browser.newContext({viewport:{width:1440,height:1024}})
 const paired=await context.request.post(origin+'/api/session',{data:{code:(await fs.readFile(owner,'utf8')).trim()},headers:{Origin:origin,'X-Researcher-Client':'web'}});assert.equal(paired.status(),200)
 const session=await paired.json();await context.setExtraHTTPHeaders({Origin:origin,'X-Researcher-CSRF':session.csrf_token,'X-Researcher-Endpoint':session.endpoint_id})
 /** Create metadata only; no source is selected or prepared implicitly. */
 async function project(name){const r=await context.request.post(origin+'/api/projects',{data:{name,description:'Synthetic repository acceptance.',operation_key:randomUUID()}});assert.equal(r.status(),201);return(await r.json()).id}
 const alpha=await project('Exportador principal'),beta=await project('Exportador independiente');evidence.identities={alpha,beta}
 await context.addInitScript(id=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:id},version:0})),alpha)
 page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>evidence.errors.push(String(e)))
 /** Preserve actual visible regions, scoped accessibility and horizontal geometry without claiming human comprehension. */
 async function capture(name,selector='.repo-reading',width=1440){await page.setViewportSize({width,height:1024});await page.locator(selector).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(out,name+'.png')});const axe=await new AxeBuilder({page}).include('.repo-workbench').analyze();const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width,selector,fits,violations:axe.violations});assert.equal(fits,true);assert.deepEqual(axe.violations,[])}
 /** Send only a fixed test-control action to the fixture owner, never to an operator installation. */
 async function control(action){const r=await context.request.post(fixture.control+'/'+action);assert.equal(r.status(),200);return r.json()}
 /** Read the exact original operation until its actual worker stops, retaining its full public attribution on failure. */
 async function settled(key,expected='completed'){
  let value
  await expect.poll(async()=>{const r=await context.request.get(origin+`/api/projects/${alpha}/source-operations/${key}`);assert.equal(r.status(),200);value=await r.json();return !value.worker_active&&['completed','needs_reconciliation','stopped','rejected'].includes(value.status)},{timeout:45000}).toBe(true)
  assert.equal(value.status,expected,JSON.stringify(value));evidence.operations.push(value);return value
 }
 /** Consult the saved result explicitly when the worker's completion happened outside the visible polling interval. */
 async function refresh(){const button=page.getByRole('button',{name:'Consultar operación',exact:true});await expect(button).toBeEnabled();const waiting=page.waitForResponse(r=>new URL(r.url()).pathname.startsWith(`/api/projects/${alpha}/source-operations/`)&&r.request().method()==='GET');await button.click();assert.equal((await waiting).status(),200);await expect(button).toBeEnabled()}
 /** Await the actual mutation admission before interpreting an old terminal GET as the result of a new gesture. */
 async function effect(label,suffix,status=202){const waiting=page.waitForResponse(r=>new URL(r.url()).pathname.endsWith('/'+suffix)&&r.request().method()==='POST');await page.getByRole('button',{name:label,exact:true}).click();const response=await waiting;assert.equal(response.status(),status);return response.json()}
 /** Open a fresh form only after the prior original result is reviewed and explicitly resolved. */
 async function prepare(mode,name,folder,options={}){
  await page.getByRole('button',{name:'Preparar fuente Git',exact:true}).click()
  const another=page.getByRole('button',{name:'Preparar otra fuente',exact:true}),modeField=page.getByRole('combobox',{name:/^Operación/})
  await another.or(modeField).waitFor({state:'visible'});if(await another.isVisible())await another.click()
  await modeField.selectOption(mode)
  await page.getByLabel(mode==='create_remote'?'Nombre del repositorio remoto':'Nombre en este proyecto',{exact:true}).fill(name)
  if(mode!=='create_remote')await page.getByLabel(mode==='adopt'?'Carpeta Git existente':'Carpeta nueva de destino',{exact:true}).fill(folder)
  if(mode==='clone'){
   await page.getByLabel('URL HTTPS del remoto',{exact:true}).fill(fixture.remote_origin+'/owner/repo.git')
   await page.getByLabel('Usar la credencial configurada para este servidor',{exact:true}).check()
   await page.getByLabel('Rama a clonar (opcional)',{exact:true}).fill('main')
  }
  if(mode==='create_remote'){
   await page.getByRole('combobox',{name:/Servidor/}).selectOption(fixture.remote_origin+'/api/v1')
   await page.getByLabel('Cuenta u organización propietaria',{exact:true}).fill('research')
   await page.getByRole('combobox',{name:/^Visibilidad/}).selectOption('private')
  }
  const waiting=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/projects/${alpha}/source-operations`&&r.request().method()==='POST')
  await page.getByRole('button',{name:mode==='create_remote'?'Crear este remoto vacío':'Preparar esta fuente',exact:true}).click()
  const response=await waiting;assert.equal(response.status(),202);const body=response.request().postDataJSON();evidence.last_request=body
  return {key:body.operation_key,body}
 }
 await page.goto(origin+'/repositories')
 await page.getByText('No hay fuentes registradas en este proyecto.',{exact:true}).waitFor();await capture('01-actual-empty')
 let request=await prepare('create','nueva',fixture.root+'/nueva')
 const created=await settled(request.key);assert.match(created.observation.head_sha,/^[0-9a-f]{40}$/);await refresh();await page.getByRole('button',{name:'Abrir fuente registrada',exact:true}).waitFor();await capture('02-real-create-completed')
 await page.getByRole('button',{name:'Abrir fuente registrada',exact:true}).click();await page.getByText('La revisión consultada no contiene archivos.',{exact:true}).waitFor();await capture('03-empty-git-revision')
 request=await prepare('adopt','original',fixture.alpha.path)
 const adopted=await settled(request.key);assert.equal(adopted.observation.head_sha,fixture.alpha.head);assert.equal(adopted.observation.working_tree_clean,false);await refresh();await capture('04-adopt-preserves-local-note')
 await page.getByRole('button',{name:'Abrir fuente registrada',exact:true}).click()
 await page.getByRole('button',{name:'Carpeta src',exact:true}).click();await page.getByRole('button',{name:'Archivo catalog.py',exact:true}).click();await page.getByRole('region',{name:'Texto original de src/catalog.py',exact:true}).waitFor();await capture('05-immutable-code','.repo-file-pane')
 await page.getByRole('combobox',{name:/^Rama/}).selectOption('experimental');await page.getByRole('button',{name:'Archivo README.md',exact:true}).click();await page.getByRole('heading',{name:'Exportador de observaciones',exact:true}).waitFor();await capture('06-markdown-mobile','.repo-file-pane',390)
 await page.getByRole('button',{name:'Ver texto original',exact:true}).click();await page.getByRole('region',{name:'Texto original de README.md',exact:true}).waitFor();await capture('07-literal-markdown-mobile','.repo-file-pane',390)
 await page.setViewportSize({width:1440,height:1024})
 request=await prepare('clone','copia',fixture.root+'/copia')
 const cloned=await settled(request.key);assert.equal(cloned.observation.head_sha,fixture.remote_head);assert.equal(cloned.observation.origin,fixture.remote_origin+'/owner/repo.git');await refresh();await capture('08-actual-tls-clone')
 await control('fail-registration');request=await prepare('create','recuperable',fixture.root+'/recuperable');await settled(request.key,'needs_reconciliation');await refresh();await capture('09-failed-registration-retains-git')
 await control('allow-registration');await effect('Observar carpeta y cierre originales','observe');const recovered=await settled(request.key);await refresh();await capture('10-readonly-recovery')
 assert.equal(recovered.request.path,fixture.root+'/recuperable')
 await control('hold-clone');request=await prepare('clone','interrumpida',fixture.root+'/interrumpida')
 await expect.poll(async()=>(await control('state')).clone_entered,{timeout:15000}).toBe(true)
 await refresh()
 await effect('Detener este intento','stop',200);const stopped=await settled(request.key,'stopped');assert.equal(stopped.local_closure,'confirmed');await refresh();await capture('11-stopped-partial-clone')
 await control('release-clone');await control('note-partial')
 await effect('Autorizar reparación de etapas faltantes','repair');const repaired=await settled(request.key);assert.ok(repaired.repair);await refresh();await capture('12-explicit-repair-keeps-note')
 request=await prepare('create_remote','archivo-remoto',null);const remote=await settled(request.key);assert.equal(remote.repository_id,null);assert.equal(remote.receipt.remote.full_name,'research/archivo-remoto');assert.equal(remote.receipt.remote.private,true);await refresh();await capture('13-controlled-remote-creation')
 const external=await control('state');assert.equal(external.git_writes,0);assert.equal(external.remote_head,fixture.remote_head);assert.equal(external.create_posts.length,1);evidence.external=external
 await page.getByRole('button',{name:'Historia de preparación',exact:true}).click();await page.getByRole('button',{name:'Abrir operación: original',exact:true}).click();await page.getByRole('heading',{name:'Solicitud original: original',exact:true}).waitFor();await capture('14-original-history-mobile','.repo-registration',390)
 await page.getByRole('button',{name:/^Seleccionar proyecto:/}).click();await page.getByRole('button',{name:/^Exportador independiente/}).click();await page.getByText('No hay fuentes registradas en este proyecto.',{exact:true}).waitFor();await capture('15-independent-empty-mobile','.repo-register',390)
 assert.deepEqual(evidence.errors,[]);evidence.status='passed'
}catch(error){evidence.status='failed';evidence.failure=String(error);if(page){await page.screenshot({path:path.join(out,'failure.png')}).catch(()=>{});evidence.visible_failure=await page.locator('.repo-workbench').innerText().catch(()=>'workbench unavailable')}throw error}
finally{if(context)await context.request.post(fixture.control+'/release-clone').catch(()=>{});await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}
