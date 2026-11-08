/** Accept the actual document route across owner edits, conflicts, revision retention, connectivity and scope. @module */
import fs from 'node:fs';
import assert from 'node:assert/strict';
import crypto from 'node:crypto';
import {chromium,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
const origin=process.env.RESEARCHER_E2E_ORIGIN,ownerFile=process.env.RESEARCHER_E2E_OWNER_FILE,out=process.env.RESEARCHER_E2E_OUTPUT
if(!origin||!ownerFile||!out||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use the retained disposable installed-host driver')
fs.mkdirSync(out,{recursive:false})
const browser=await chromium.launch({headless:true})
const evidence={result:'running',states:[],actions:[],errors:[],model_turns:0,identities:{}}
/** Preserve every observation without claiming a failed generation is a product result. */
const persist=()=>fs.writeFileSync(out+'/evidence.json',JSON.stringify(evidence,null,2)+'\n')
try {
 const context=await browser.newContext()
 const paired=await context.request.post(origin+'/api/session',{data:{code:fs.readFileSync(ownerFile,'utf8').trim()},headers:{Origin:origin,'X-Researcher-Client':'web'}});assert.equal(paired.status(),200)
 const session=await paired.json();await context.setExtraHTTPHeaders({'X-Researcher-CSRF':session.csrf_token,'X-Researcher-Endpoint':session.endpoint_id,Origin:origin})
 /** Seed metadata through real owner requests; this fixture never starts an agent. */
 const createProject=async name=>{const response=await context.request.post(origin+'/api/projects',{data:{name,description:'Synthetic document acceptance fixture.',operation_key:crypto.randomUUID()}});assert.equal(response.status(),201);return(await response.json()).id}
 const alpha=await createProject('Cuaderno Atlas'),beta=await createProject('Cuaderno Beta')
 /** Create an exact independently scoped document through the actual revision store. */
 const write=async(project,path,title,content,namespace='project')=>{const response=await context.request.post(origin+'/api/wiki',{data:{project_id:project,namespace,path,title,content,parent_path:null,operation_key:crypto.randomUUID()}});assert.equal(response.status(),201);return response.json()}
 const first=await write(alpha,'modernization/context','Contexto compartido','# Contexto compartido\n\nEl objetivo es exportar las observaciones a CSV. Se conservarán el orden y las columnas id y value.\n\n## Decisión pendiente\n\nEl código permite leer las observaciones; todavía no se ha implementado la exportación. El plan propone reutilizar esa lectura, escribir con la biblioteca csv y comprobar cabecera y valores con unittest.')
 await write(alpha,'modernization/decisions','Decisiones de arquitectura','# Decisiones\n\nEl propietario elegirá cuándo ejecutar las tareas propuestas. Preparar el plan no las inicia.')
 const foreign=await write(beta,'modernization/context','Contexto Beta','OTHER PROJECT SECRET')
 await write(alpha,'modernization/context','Guía global de contexto','# Guía global\n\nEsta nota compartida no sustituye el alcance de un proyecto.','global')
 const fixtures={context:{page_id:first.id},foreign:{page_id:foreign.id}}
 evidence.identities={alpha,beta,context:first.id,foreign:foreign.id};persist()
 await context.addInitScript(id=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:id},version:0})),alpha)
 const page=await context.newPage();page.on('pageerror',error=>evidence.errors.push(String(error)));
 const path='/api/wiki/'+encodeURIComponent('modernization/context')+`?project_id=${alpha}`;
 /** Read the actual retained page independently of rendered labels. */
 const apiGet=async()=>{const response=await context.request.get(origin+path);assert.equal(response.status(),200);return response.json()};
 /** Inspect page-level layout, keyboard landmarks and automatic accessibility at the current state. */
 const capture=async name=>{
  const axe=await new AxeBuilder({page}).include('.wiki-workbench').analyze();const layout=await page.evaluate(()=>({viewport:innerWidth,scroll:document.documentElement.scrollWidth,heading:document.querySelector('.wiki-pane h1')?.getBoundingClientRect().toJSON(),workbench:document.querySelector('.wiki-workbench')?.getBoundingClientRect().toJSON()}));
  const target=out+'/'+name+'.png';await page.screenshot({path:target,fullPage:true});
  evidence.states.push({name,viewport:page.viewportSize(),layout,violations:axe.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.length})),screenshot:name+'.png',sha256:crypto.createHash('sha256').update(fs.readFileSync(target)).digest('hex')});persist();
  assert.deepEqual(axe.violations,[]);assert.ok(layout.scroll<=layout.viewport);if(layout.heading?.width)assert.ok(layout.heading.x>=0&&layout.heading.right<=layout.viewport+1,'Reader heading is clipped');
 };
 /** Capture an actual locked session without pretending protected document content is visible. */
 const captureSession=async name=>{const target=out+'/'+name+'.png';await page.screenshot({path:target,fullPage:true});evidence.states.push({name,viewport:page.viewportSize(),session_gate:true,screenshot:name+'.png'});persist()};
 page.setDefaultTimeout(15000);
 await page.setViewportSize({width:1440,height:1024});
 await page.goto(origin+`/wiki?project=${alpha}&namespace=project&path=modernization%2Fcontext&pageId=${fixtures.context.page_id}`);
 await page.getByRole('heading',{name:'Contexto compartido',exact:true}).waitFor();await capture('desktop-reading-final');
 const original=await apiGet();
 await page.getByRole('button',{name:'Ver versiones',exact:true}).click();await page.getByRole('heading',{name:'Versiones guardadas',exact:true}).waitFor();
 await page.getByRole('button',{name:`Ver texto de revisión ${original.revision}`,exact:true}).click();
 await page.getByLabel(`Texto de revisión ${original.revision}`,{exact:true}).waitFor();await capture('desktop-history');
 await page.getByRole('button',{name:'Ver versiones',exact:true}).click();await page.getByRole('button',{name:'Editar',exact:true}).click();
 const draftText=original.content+'\n\nBorrador local: evidencia y suposición se distinguen.';
 await page.getByLabel('Texto en Markdown',{exact:true}).fill(draftText);
 const remote=await context.request.put(origin+path,{data:{page_id:original.id,expected_revision:original.revision,title:original.title,content:original.content+'\n\nGuardado en otro editor.',parent_path:original.parent_path,operation_key:crypto.randomUUID()}});assert.equal(remote.status(),200);const remotePage=await remote.json();
 await page.getByRole('button',{name:'Guardar página',exact:true}).click();await page.getByRole('alert').filter({hasText:'La página o el intento cambió'}).waitFor();assert.equal(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue(),draftText);await capture('desktop-conflict');
 await page.getByRole('button',{name:'Comparar con la versión guardada',exact:true}).click();await page.getByRole('heading',{name:`Versión consultada · revisión ${remotePage.revision}`,exact:true}).waitFor();
 assert.match(await page.getByLabel('Texto de la versión consultada',{exact:true}).textContent(),/Guardado en otro editor/);await capture('desktop-comparison');
 await page.getByRole('button',{name:`Preparar mi borrador sobre la revisión ${remotePage.revision}`,exact:true}).click();assert.equal(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue(),draftText);
 await page.getByRole('button',{name:'Guardar página',exact:true}).click();await page.waitForURL(url=>!url.searchParams.has('draft'));await page.getByRole('heading',{name:'Contexto compartido',exact:true}).waitFor();assert.equal((await apiGet()).content,draftText);await capture('desktop-saved');
 evidence.actions.push('Concurrent external edit produces409; draft retained, exact comparison shown, explicit overwrite preparation preserves local text and guarded save succeeds');persist();
 // Commit the real request, then drop only its receipt before the browser observes it.
 await page.getByRole('button',{name:'Editar',exact:true}).click();const beforeLost=await apiGet(),lostText=beforeLost.content+'\n\nRespuesta perdida sintética.';
 await page.getByLabel('Texto en Markdown',{exact:true}).fill(lostText);let dropped=false;
 const loseReceipt=async route=>{if(route.request().method()==='PUT'&&!dropped){dropped=true;const response=await route.fetch();assert.equal(response.status(),200);await route.abort('failed')}else await route.continue()};
 await page.route('**/api/wiki/**',loseReceipt);await page.getByRole('button',{name:'Guardar página',exact:true}).click();await page.getByRole('alert').filter({hasText:'No se pudo confirmar el guardado'}).waitFor();assert.equal((await apiGet()).revision,beforeLost.revision+1);assert.equal(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue(),lostText);await capture('desktop-uncertain-receipt');
 await page.unroute('**/api/wiki/**',loseReceipt);await page.getByRole('button',{name:'Guardar página',exact:true}).click();await page.waitForURL(url=>!url.searchParams.has('draft'));assert.equal((await apiGet()).revision,beforeLost.revision+1);evidence.actions.push('A lost HTTP receipt after committed write is retried with the same intent; one revision only');persist();
 // Hold a submitted save while the owner chooses a different document.
 await page.getByRole('button',{name:'Editar',exact:true}).click();const beforeLate=await apiGet(),lateText=beforeLate.content+'\n\nRespuesta tardía de guardado.';await page.getByLabel('Texto en Markdown',{exact:true}).fill(lateText);
 let release,markReached;const released=new Promise(resolve=>release=resolve),reached=new Promise(resolve=>markReached=resolve);
 const holdSave=async route=>{if(route.request().method()==='PUT'){markReached();await released;await route.continue()}else await route.continue()};
 await page.route('**/api/wiki/**',holdSave);await page.getByRole('button',{name:'Guardar página',exact:true}).click();await Promise.race([reached,new Promise((_,reject)=>setTimeout(()=>reject(new Error('Save never reached transport')),10000))]);
 await page.getByRole('button',{name:/^Decisiones de arquitectura modernization\/decisions/}).click();await page.getByRole('heading',{name:'Decisiones de arquitectura',exact:true}).waitFor();
 const arrived=page.waitForResponse(response=>response.request().method()==='PUT'&&response.url().includes('/api/wiki/'));
 release();const lateResponse=await arrived;await lateResponse.finished();await page.getByText(/^Borradores en esta ventana/).waitFor({state:'detached',timeout:5000});
 assert.equal(new URL(page.url()).searchParams.get('path'),'modernization/decisions');assert.equal(await page.getByRole('heading',{name:'Decisiones de arquitectura',exact:true}).count(),1);assert.equal((await apiGet()).content,lateText);assert.equal(await page.getByText(/^Borradores en esta ventana/).count(),0);await page.unroute('**/api/wiki/**',holdSave);await capture('desktop-late-response-new-document');
 evidence.actions.push('Late successful save is recorded but never redirects a newer selected document or leaves a false pending draft');persist();
 // Project changes cannot redirect an unsaved edit's origin.
 await page.getByRole('button',{name:'Editar',exact:true}).click();const unsaved=(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue())+'\n\nCambio pendiente conservado.';await page.getByLabel('Texto en Markdown',{exact:true}).fill(unsaved);
 await page.getByRole('button',{name:/^Seleccionar proyecto:/}).click();await page.getByRole('button',{name:/^Cuaderno Beta/}).click();await page.getByRole('heading',{name:'Este enlace corresponde a otro proyecto',exact:true}).waitFor();await capture('desktop-project-changed');
 await page.getByText('Borradores en esta ventana (1)',{exact:true}).click();await page.getByRole('button',{name:`Decisiones de arquitectura · Proyecto ${alpha}`,exact:true}).click();await page.getByRole('heading',{name:'Editar documento',exact:true}).waitFor();assert.equal(new URL(page.url()).searchParams.get('project'),String(alpha));assert.equal(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue(),unsaved);await capture('desktop-recovered-draft');
 page.once('dialog',dialog=>dialog.dismiss());await page.getByRole('button',{name:'Cerrar sesión',exact:true}).click();assert.equal(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue(),unsaved);
 await page.getByText('Descartar este borrador',{exact:true}).click();await page.getByRole('button',{name:'Descartar cambios sin guardar',exact:true}).click();await page.getByRole('heading',{name:'Decisiones de arquitectura',exact:true}).waitFor();evidence.actions.push('Draft survives project switch and returns to original scope; cancelling logout preserves it; explicit discard is separate');persist();
 await page.setViewportSize({width:390,height:844});await page.getByRole('button',{name:'‹ Volver a documentos',exact:true}).click();await page.getByRole('heading',{name:'Documentos',exact:true}).waitFor();await capture('mobile-index');
 await page.getByLabel('Mostrar páginas de',{exact:true}).selectOption('global');await page.getByRole('button',{name:/^Guía global de contexto modernization\/context/}).click();await page.getByRole('heading',{name:'Guía global de contexto',exact:true}).waitFor();await capture('mobile-global-reader');
 await page.getByRole('button',{name:'Editar',exact:true}).click();assert.match(await page.locator('.wiki-editor').textContent(),/Guardar afecta a la biblioteca global/);await page.getByLabel('Texto en Markdown',{exact:true}).fill('# Guía global\n\nNota global actualizada por el propietario.');await page.getByRole('button',{name:'Guardar página',exact:true}).click();await page.waitForURL(url=>!url.searchParams.has('draft'));assert.equal((await apiGet()).content,lateText);
 await page.getByRole('button',{name:'‹ Volver a documentos',exact:true}).click();await page.getByLabel('Mostrar páginas de',{exact:true}).selectOption('project');await page.getByRole('button',{name:'Nueva página',exact:true}).click();
 const newPath='qa/archivo?ejemplo#marca',newTitle='Nota de prueba <script>';
 await page.getByLabel('Ruta, por ejemplo arquitectura/contexto',{exact:true}).fill(newPath);await page.getByLabel('Título',{exact:true}).fill(newTitle);await page.getByLabel('Texto en Markdown',{exact:true}).fill('# '+newTitle+'\n\nTexto literal: <img src=x onerror=window.wikiXss=1>');await capture('mobile-new-document');
 await page.getByRole('button',{name:'Guardar página',exact:true}).click();await page.waitForURL(url=>!url.searchParams.has('draft'));await page.getByRole('heading',{name:newTitle,exact:true}).waitFor();assert.equal(new URL(page.url()).searchParams.get('path'),newPath);assert.equal(await page.evaluate(()=>window.wikiXss),undefined);const newId=Number(new URL(page.url()).searchParams.get('pageId'));assert.ok(newId>0);await capture('mobile-literal-reader');
 await page.getByText('Más opciones',{exact:true}).click();await page.getByRole('button',{name:'Eliminar página',exact:true}).click();await page.getByRole('dialog').waitFor();assert.equal(await page.getByRole('button',{name:'Conservar página',exact:true}).evaluate(element=>element===document.activeElement),true);await page.keyboard.press('Shift+Tab');assert.equal(await page.getByRole('button',{name:'Eliminar página definitivamente',exact:true}).evaluate(element=>element===document.activeElement),true);await page.keyboard.press('Tab');assert.equal(await page.getByRole('button',{name:'Conservar página',exact:true}).evaluate(element=>element===document.activeElement),true);await capture('mobile-delete-dialog');await page.keyboard.press('Escape');await page.getByRole('dialog').waitFor({state:'detached'});assert.equal(await page.getByRole('button',{name:'Eliminar página',exact:true}).evaluate(element=>element===document.activeElement),true);
 await page.getByRole('button',{name:'Eliminar página',exact:true}).click();await page.getByRole('button',{name:'Eliminar página definitivamente',exact:true}).click();await page.getByRole('heading',{name:'Documentos',exact:true}).waitFor();assert.equal((await context.request.get(origin+'/api/wiki/'+encodeURIComponent(newPath)+`?project_id=${alpha}`)).status(),404);assert.equal((await context.request.get(origin+`/api/wiki-revisions/${newId}?project_id=${alpha}`)).status(),200);
 await page.goto(origin+`/wiki?project=${alpha}&namespace=project&path=${encodeURIComponent(newPath)}&pageId=${newId}`);await page.getByRole('heading',{name:'No se pudo consultar la página',exact:true}).waitFor();await page.getByRole('button',{name:'Ver versiones',exact:true}).click();await page.getByRole('button',{name:'Ver texto de revisión 1',exact:true}).click();await page.getByLabel('Texto de revisión 1',{exact:true}).waitFor();await capture('mobile-deleted-history');
 evidence.actions.push('Owner global edit is explicit and leaves same-path project page intact; mobile create handles path punctuation and literal HTML; delete traps/restores keyboard focus and retained history remains readable');persist();
 await page.goto(origin+`/wiki?project=${beta}&namespace=project&path=modernization%2Fcontext&pageId=${fixtures.foreign.page_id}`);await page.getByRole('heading',{name:'Este enlace corresponde a otro proyecto',exact:true}).waitFor();assert.equal(await page.getByText('OTHER PROJECT SECRET',{exact:true}).count(),0);assert.equal(await page.getByRole('button',{name:'Editar',exact:true}).count(),0);await capture('mobile-foreign-link');

 // A real read transport failure is visible, then recovers without changing saved bytes.
 const retainedBeforeFailure=await apiGet()
 const blockRead=route=>route.request().method()==='GET'?route.abort('failed'):route.continue()
 await page.route('**/api/wiki/**',blockRead)
 await page.goto(origin+`/wiki?project=${alpha}&namespace=project&path=modernization%2Fcontext&pageId=${first.id}`)
 await page.getByRole('heading',{name:'No se pudo consultar la página',exact:true}).waitFor()
 await capture('mobile-connectivity-error')
 assert.equal((await apiGet()).content,retainedBeforeFailure.content)
 await page.unroute('**/api/wiki/**',blockRead)
 await page.getByRole('button',{name:'Volver a consultar',exact:true}).click()
 await page.getByRole('heading',{name:'Contexto compartido',exact:true}).waitFor()
 await capture('mobile-connectivity-recovered')
 evidence.actions.push('Actual GET transport failure is visible; retry recovers the original retained document without a write');persist()
 // Actual session revocation tears down private reads but retains the unsent draft in memory.
 await page.getByRole('button',{name:'Editar',exact:true}).click()
 const transientDraft=(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue())+'\n\nBorrador conservado durante la renovación de sesión.'
 await page.getByLabel('Texto en Markdown',{exact:true}).fill(transientDraft)
 let reloadDialog=false
 page.once('dialog',async dialog=>{assert.equal(dialog.type(),'beforeunload');reloadDialog=true;await dialog.dismiss()})
 await page.reload({timeout:5000}).catch(()=>{})
 assert.equal(reloadDialog,true)
 assert.equal(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue(),transientDraft)
 const revoked=await context.request.delete(origin+'/api/session');assert.equal(revoked.status(),204)
 await page.getByRole('button',{name:'Comparar con la versión guardada',exact:true}).click()
 await page.getByLabel('Código de acceso local',{exact:true}).waitFor()
 await captureSession('session-locked-draft-retained')
 await page.getByLabel('Código de acceso local',{exact:true}).fill(fs.readFileSync(ownerFile,'utf8').trim())
 const pairedAgain=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/session'&&r.request().method()==='POST')
 await page.getByRole('button',{name:'Abrir espacio',exact:true}).click()
 const renewed=await(await pairedAgain).json()
 await context.setExtraHTTPHeaders({'X-Researcher-CSRF':renewed.csrf_token,'X-Researcher-Endpoint':renewed.endpoint_id,Origin:origin})
 await page.getByRole('heading',{name:'Editar documento',exact:true}).waitFor()
 assert.equal(await page.getByLabel('Texto en Markdown',{exact:true}).inputValue(),transientDraft)
 await capture('mobile-session-restored-draft')
 await page.getByText('Descartar este borrador',{exact:true}).click();await page.getByRole('button',{name:'Descartar cambios sin guardar',exact:true}).click()
 evidence.actions.push('Real session revocation locks protected content; pairing restores the original unsent draft; cancelling browser reload preserves it');persist()
 // More than one actual index page, lexical search and no-result state stay project scoped.
 for(let n=0;n<53;n++)await write(alpha,`carga/page-${String(n).padStart(2,'0')}`,`Página de carga ${n}`,n===52?'CONTINUACIONFINAL':'Contenido sintético de carga.')
 await page.goto(origin+`/wiki?project=${alpha}&namespace=project`)
 await page.getByRole('button',{name:'Cargar más páginas',exact:true}).waitFor()
 assert.equal(await page.locator('.wiki-page-list>li').count(),50)
 await page.getByRole('button',{name:'Cargar más páginas',exact:true}).click()
 await expect(page.locator('.wiki-page-list>li')).toHaveCount(55)
 await page.getByLabel('Buscar en los documentos',{exact:true}).fill('CONTINUACIONFINAL');await page.getByRole('button',{name:'Buscar',exact:true}).click()
 await expect(page.locator('.wiki-page-list>li')).toHaveCount(1)
 assert.match(await page.locator('.wiki-page-list').textContent(),/carga\/page-52/)
 await capture('mobile-paginated-search')
 await page.getByLabel('Buscar en los documentos',{exact:true}).fill('TERMINOINEXISTENTE');await page.getByRole('button',{name:'Buscar',exact:true}).click()
 await page.getByText(/No hubo resultados para esta consulta/).waitFor();await capture('mobile-no-search-result')
 evidence.actions.push('55 real scoped documents span two index pages; lexical search finds the last page and empty results explain their limits');persist()
 // Retained history has its own real cursor and does not replace the current document.
 let historyPage=await apiGet()
 for(let n=0;n<20;n++){
   const response=await context.request.put(origin+path,{data:{page_id:historyPage.id,expected_revision:historyPage.revision,title:historyPage.title,content:first.content+`\n\nRevisión adicional ${n+1}.`,parent_path:historyPage.parent_path,operation_key:crypto.randomUUID()}})
   assert.equal(response.status(),200);historyPage=await response.json()
 }
 await page.goto(origin+`/wiki?project=${alpha}&namespace=project&path=modernization%2Fcontext&pageId=${first.id}`)
 await page.reload();await page.getByRole('heading',{name:'Contexto compartido',exact:true}).waitFor()
 await page.getByRole('button',{name:'Ver versiones',exact:true}).click();await page.getByRole('button',{name:'Más versiones',exact:true}).waitFor()
 assert.equal(await page.getByRole('button',{name:/^Ver texto de revisión /}).count(),20)
 await page.getByRole('button',{name:'Más versiones',exact:true}).click()
 await expect(page.getByRole('button',{name:/^Ver texto de revisión /})).toHaveCount(historyPage.revision)
 await page.getByRole('button',{name:'Ver texto de revisión 1',exact:true}).click()
 await expect(page.getByLabel('Texto de revisión 1',{exact:true})).toHaveText(first.content)
 assert.equal((await apiGet()).revision,historyPage.revision)
 await capture('mobile-paginated-retained-history')
 evidence.history_revisions=historyPage.revision;evidence.actions.push('25 retained revisions span two history pages; original text remains exact without restoring or mutating the current revision');persist()
 // Representative long Markdown remains readable at320px; native browser zoom requires a separate observation.
 const longText='# Documento extenso\n\n'+('Una nota conserva una decisión y su evidencia. La lectura no ejecuta tareas.\n\n'.repeat(1400))+'\n\nFINCOMPROBADO: conserva la limitación del alcance.'
 const long=await write(alpha,'carga/lectura-extensa','Documento extenso',longText)
 await page.goto(origin+`/wiki?project=${alpha}&namespace=project&path=carga%2Flectura-extensa&pageId=${long.id}`)
 await page.getByRole('heading',{name:'Documento extenso',exact:true}).waitFor()
 await expect(page.locator('.wiki-document')).toContainText('FINCOMPROBADO')
 await page.setViewportSize({width:320,height:844});await page.locator('.wiki-document p').last().scrollIntoViewIfNeeded();await capture('narrow-long-document-tail')
 await page.setViewportSize({width:1440,height:1024});await page.goto(origin+`/wiki?project=${alpha}&namespace=project&path=modernization%2Fcontext&pageId=${first.id}`)
 await page.getByRole('heading',{name:'Contexto compartido',exact:true}).waitFor()
 await capture('desktop-current-reading-final')
 evidence.long_document_utf8_bytes=Buffer.byteLength(longText);evidence.native_browser_zoom='not_observed'
 evidence.actions.push('A long actual saved Markdown document exposes its final limitation at320px; desktop reading returns to the selected notebook layout; no native browser zoom or screen-reader claim');persist()

 assert.deepEqual(evidence.errors,[]);evidence.result='passed';evidence.new_reference_deleted=true;persist();
} catch(error) {evidence.result='failed';evidence.failure=String(error);persist();throw error;}
finally {await browser.close();}
console.log(JSON.stringify({result:evidence.result,states:evidence.states.length,actions:evidence.actions.length}));
