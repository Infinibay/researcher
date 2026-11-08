/** Accept the reference archive through actual owner uploads, immutable downloads, previews and recovery. @module */
import fs from 'node:fs/promises'
import path from 'node:path'
import {createHash,randomUUID} from 'node:crypto'
import {execFileSync} from 'node:child_process'
import {chromium,expect} from '@playwright/test'
import AxeBuilder from '@axe-core/playwright'

const origin=process.env.RESEARCHER_E2E_ORIGIN,owner=process.env.RESEARCHER_E2E_OWNER_FILE,out=process.env.RESEARCHER_E2E_OUTPUT,fixturesFile=process.env.RESEARCHER_E2E_FILE_FIXTURES
if(!origin||!owner||!out||!fixturesFile||new URL(origin).hostname!=='127.0.0.1')throw new Error('Use web_workspace.py --journey files with a NEW disposable host')
await fs.mkdir(out,{recursive:false})
const evidence={status:'running',states:[],errors:[],checks:[],files:[],model_turns:0}
const browser=await chromium.launch({headless:true})
let page,releaseLate,cleanupFaults
try{
 const context=await browser.newContext({viewport:{width:1440,height:1024}})
 const paired=await context.request.post(origin+'/api/session',{data:{code:(await fs.readFile(owner,'utf8')).trim()},headers:{Origin:origin,'X-Researcher-Client':'web'}});expect(paired.status()).toBe(200)
 const session=await paired.json();await context.setExtraHTTPHeaders({Origin:origin,'X-Researcher-CSRF':session.csrf_token,'X-Researcher-Endpoint':session.endpoint_id})
 /** Create only explicit metadata; no repository or runtime work is admitted. */
 async function create(name){const r=await context.request.post(origin+'/api/projects',{data:{name,description:'Synthetic attachment acceptance.',operation_key:randomUUID()}});expect(r.status()).toBe(201);return(await r.json()).id}
 const alpha=await create('Archivo principal'),beta=await create('Archivo independiente');evidence.identities={alpha,beta}
 /** Seed one complete original through the real multipart endpoint and retain its receipt and bytes. */
 async function upload(name,content,project=alpha,mime='text/plain'){const key=randomUUID(),data=Buffer.from(content);const r=await context.request.post(origin+`/api/files?project_id=${project}`,{multipart:{file:{name,mimeType:mime,buffer:data},description:'Adjunto sintético de aceptación',operation_key:key}});expect(r.status()).toBe(201);const v=await r.json();evidence.files.push({id:v.id,project,name,sha256:createHash('sha256').update(data).digest('hex'),operation_key:key});return v}
 for(let i=0;i<55;i++)await upload(`registro-${String(i).padStart(2,'0')}.txt`,`Registro sintético ${i}.`)
 await context.addInitScript(id=>localStorage.setItem('active-project',JSON.stringify({state:{activeProjectId:id},version:0})),alpha)
 page=await context.newPage();page.setDefaultTimeout(15000);page.on('pageerror',e=>evidence.errors.push(String(e)))
 /** Retain the actual viewport, layout and regional accessibility observations before accepting a state. */
 async function capture(name,width=1440){await page.setViewportSize({width,height:1024});const bounds=await page.locator('.files-layout').boundingBox();const axe=await new AxeBuilder({page}).include('.files-workbench').analyze();await page.screenshot({path:path.join(out,name+'.png'),fullPage:true});const fits=await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth);evidence.states.push({name,width,layout:bounds,fits,violations:axe.violations});expect(fits).toBe(true);expect(axe.violations).toEqual([])}
 await page.goto(origin+`/files?project=${alpha}`)
 await expect(page.locator('.files-list>li')).toHaveCount(50)
 await capture('01-representative-archive')
 // Confirmed historical operations must not displace the primary archive below the first viewport.
 const layout=await page.locator('.files-layout').boundingBox();expect(layout.y).toBeLessThan(850)
 evidence.checks.push('Confirmed historical operations do not displace the primary archive below the first viewport')

 /** Perform read-only owner inspection without turning lost mutation receipts into fresh effects. */
 async function history(project=alpha){const r=await context.request.get(origin+`/api/files/operations?project_id=${project}&limit=100`);expect(r.status()).toBe(200);return r.json()}
 /** Keep each original publication identity once, including exact upload retries. */
 function remember(file,content,key){const entry={id:file.id,project:file.project_id,name:file.filename,sha256:createHash('sha256').update(Buffer.from(content)).digest('hex'),operation_key:key};const old=evidence.files.find(f=>f.id===file.id);if(old)expect(old.sha256).toBe(entry.sha256);else evidence.files.push(entry);return entry}
 /** Switch the visible project through its actual owner selector. */
 async function selectProject(name){await page.getByRole('button',{name:/^Seleccionar proyecto:/}).click();await page.getByRole('button',{name:new RegExp('^'+name)}).click()}
 /** Open a concrete same-project reference; no preview request occurs until the owner asks. */
 async function view(file,width=1440){await page.setViewportSize({width,height:1024});await page.goto(origin+`/files?project=${file.project_id}&file=${file.id}`);await page.getByRole('heading',{name:file.filename,exact:true}).waitFor()}
 /** Retain the actual immutable bytes delivered by a user-initiated download. */
 async function download(file,content){const waiting=page.waitForEvent('download');await page.getByRole('button',{name:'Descargar original',exact:true}).click();const result=await waiting;expect(result.suggestedFilename()).toBe(file.filename);const chunks=[];for await(const chunk of await result.createReadStream())chunks.push(chunk);expect(Buffer.concat(chunks).equals(Buffer.from(content))).toBe(true)}
 /** Validate original scope and normalized text identity from the actual extraction response. */
 async function preview(file,marker,kind){const waiting=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/files/${file.id}/preview`);await page.getByRole('button',{name:'Extraer previa',exact:true}).click();const response=await waiting;expect(response.status()).toBe(200);const value=await response.json();expect(value.project_id).toBe(file.project_id);expect(value.file_id).toBe(file.id);expect(value.persisted_source).toBe(false);expect(value.source_id).toBeUndefined();expect(value.content_sha256).toBe(createHash('sha256').update(value.content).digest('hex'));if(kind&&kind!=='pdf')expect(value.provenance.format).toBe(kind);await expect(page.getByLabel('Texto extraído del adjunto',{exact:true})).toContainText(marker);evidence.previews??=[];evidence.previews.push({file_id:file.id,project_id:file.project_id,content_sha256:value.content_sha256,persisted_source:value.persisted_source,provenance:value.provenance});return value}
 /** Select complete original bytes but keep confirmation as a separate visible action. */
 async function pick(name,content,mime='text/plain'){await page.setViewportSize({width:1440,height:1024});await page.getByLabel('Seleccionar archivo',{exact:true}).setInputFiles({name,mimeType:mime,buffer:Buffer.from(content)})}
 /** Observe one explicit successful owner upload and its selected reference. */
 async function submit(){const waiting=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/files'&&r.request().method()==='POST');await page.getByRole('button',{name:'Subir archivo',exact:true}).click();const response=await waiting;expect(response.status()).toBe(201);const value=await response.json();await page.getByRole('heading',{name:value.filename,exact:true}).waitFor();return value}
 /** Confine fault injection to the NEW synthetic host, using real SQLite transactions/files rather than forged responses. */
 function fault(action,key=''){
  const database=process.env.RESEARCHER_E2E_DATABASE,python=process.env.RESEARCHER_E2E_PYTHON;if(!database||!python)throw new Error('Explicit disposable database and installed Python are required')
  return JSON.parse(execFileSync(python,['-I','-c',`
import json,sqlite3,sys
from pathlib import Path
p=Path(sys.argv[1]);assert p.name=='source.db' and (p.parent/'installation.json').is_file()
c=sqlite3.connect(p);assert c.execute('SELECT COUNT(*) FROM runtime_runs').fetchone()[0]==0
project=int(sys.argv[3]);assert c.execute('SELECT name FROM projects WHERE id=?',(project,)).fetchone()[0]=='Archivo principal'
action=sys.argv[2];result={}
if action=='publish':c.execute("CREATE TRIGGER acceptance_reject_publication BEFORE INSERT ON reference_files WHEN new.file_name IN ('pendiente.txt','incompleto.txt') BEGIN SELECT RAISE(ABORT,'synthetic unavailable publication'); END")
elif action=='delete':c.execute("CREATE TRIGGER acceptance_reject_delete BEFORE DELETE ON reference_files BEGIN SELECT RAISE(ABORT,'synthetic unavailable deletion'); END")
elif action=='clear':
 c.execute('DROP TRIGGER IF EXISTS acceptance_reject_publication');c.execute('DROP TRIGGER IF EXISTS acceptance_reject_delete')
elif action=='truncate':
 relative=c.execute('SELECT relative_path FROM reference_file_operations WHERE project_id=? AND operation_key=?',(project,sys.argv[4])).fetchone()[0]
 root=(p.parent/'uploads').resolve();target=(root/relative).resolve();assert target.is_relative_to(root)
 with target.open('r+b') as stream:stream.truncate(4)
 result={'bytes':target.stat().st_size}
c.commit();c.close();print(json.dumps(result))
`,database,action,String(alpha),key],{encoding:'utf8'}))
 }
 cleanupFaults=()=>fault('clear')
 // Historical records are still accessible without obscuring the archive by default.
 const toggle=page.getByRole('button',{name:'Ver historial de cargas y borrados',exact:true});await expect(toggle).toHaveAttribute('aria-expanded','false');await toggle.click();await expect(page.locator('.files-operations li')).toHaveCount(50);await page.getByRole('button',{name:'Ver operaciones anteriores',exact:true}).click();await expect(page.locator('.files-operations li')).toHaveCount(55);await page.getByRole('button',{name:'Ocultar historial confirmado',exact:true}).click();await expect(page.locator('.files-operations li')).toHaveCount(0)
 await page.getByRole('button',{name:'Mostrar más archivos',exact:true}).click();await expect(page.locator('.files-list>li')).toHaveCount(55)
 await page.getByRole('searchbox',{name:'Buscar archivos',exact:true}).fill('registro-00');await expect(page.locator('.files-list>li')).toHaveCount(1);await capture('02-paginated-search',390)
 await page.getByRole('searchbox',{name:'Buscar archivos',exact:true}).fill('SINCOINCIDENCIAS');await page.getByText('No hay adjuntos con esta búsqueda. Prueba otro nombre o descripción.',{exact:true}).waitFor();await capture('03-no-search-result',390)
 await selectProject('Archivo independiente');await page.getByText('Todavía no hay adjuntos. Puedes subir el primero desde el formulario.',{exact:true}).waitFor();await capture('04-actual-empty',390)
 const betaBytes='Original de Beta: sólo este proyecto.';await pick('registro-54.txt',betaBytes);const betaFile=await submit();remember(betaFile,betaBytes,(await history(beta)).find(r=>r.reference_id===betaFile.id).operation_key)
 await preview(betaFile,'Original de Beta');await download(betaFile,betaBytes);await capture('05-independent-same-name',390)
 // A committed upload with a lost response keeps its original request key and creates one reference only.
 await selectProject('Archivo principal');await page.goto(origin+`/files?project=${alpha}`)
 const lostBytes='La respuesta se perdió, el original sigue siendo el mismo.';await pick('respuesta-perdida.txt',lostBytes)
 let lostReceipt,drop=true
 const loseUpload=async route=>{if(route.request().method()==='POST'&&drop){drop=false;const response=await route.fetch();expect(response.status()).toBe(201);lostReceipt=await response.json();await route.abort('failed')}else await route.continue()}
 await page.route('**/api/files?*',loseUpload);await page.getByRole('button',{name:'Subir archivo',exact:true}).click();await page.getByRole('alert').filter({hasText:'Cargas y borrados'}).waitFor();const lostRows=(await history()).filter(r=>r.filename==='respuesta-perdida.txt');expect(lostRows).toHaveLength(1);await capture('06-lost-upload-receipt')
 await page.unroute('**/api/files?*',loseUpload);const retried=await submit();expect(retried.id).toBe(lostReceipt.id);remember(retried,lostBytes,lostRows[0].operation_key);await download(retried,lostBytes)
 evidence.checks.push('Lost actual upload response reuses the original operation and one reference only')
 // A retired upload callback cannot select its result over a new visit after A→B→A.
 await pick('respuesta-tardia.txt','Original tardío de Atlas.');let markCommitted
 const committed=new Promise(resolve=>{markCommitted=resolve}),hold=new Promise(resolve=>{releaseLate=resolve})
 const holdUpload=async route=>{if(route.request().method()!=='POST')return route.continue();const response=await route.fetch();expect(response.status()).toBe(201);const value=await response.json();markCommitted(value);await hold;await route.fulfill({response})}
 await page.route('**/api/files?*',holdUpload);await page.getByRole('button',{name:'Subir archivo',exact:true}).click();const late=await committed
 await selectProject('Archivo independiente');await selectProject('Archivo principal');const arrived=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/files'&&r.request().method()==='POST');releaseLate();await(await arrived).finished();await page.unroute('**/api/files?*',holdUpload)
 await expect(page.getByRole('heading',{name:retried.filename,exact:true})).toBeVisible();expect(new URL(page.url()).searchParams.get('file')).toBe(String(retried.id));remember(late,'Original tardío de Atlas.',(await history()).find(r=>r.reference_id===late.id).operation_key);await capture('07-late-upload-keeps-new-visit')
 evidence.checks.push('Late successful upload does not take over a replacement A visit after A-B-A')
 // Every supported structured format and PDF is really parsed; downloads retain the original binary bytes.
 for(const fixture of JSON.parse(await fs.readFile(fixturesFile,'utf8'))){const bytes=await fs.readFile(fixture.path),file=await upload(fixture.name,bytes,alpha,fixture.mime);await view(file);await expect(page.getByLabel('Texto extraído del adjunto',{exact:true})).toHaveCount(0);const kind=fixture.name.split('.').pop(),value=await preview(file,kind==='pdf'?'[Page 2]':'No improvement',kind);expect(value.provenance.byte_sha256).toBe(fixture.sha256);if(kind==='pdf')expect(value.provenance.page_count).toBe(2);await download(file,bytes);await page.getByText('Procedencia de esta previa',{exact:true}).click();await page.getByText(value.content_sha256,{exact:true}).waitFor();await capture('08-preview-'+kind,kind==='pdf'?1440:390)}
 evidence.checks.push('PDF/DOCX/CSV/JSON/XML extraction is explicit, normalized and scoped; original byte hashes survive downloads')
 // Literal text remains literal; long names and controls stay within a narrow reader.
 const literalName='observaciones-'+('registro-'.repeat(8))+'contexto.txt',literalBytes='Texto conservado: <img src=x onerror=window.fileXss=1>\nEl archivo es un adjunto, no una fuente capturada.'
 const literal=await upload(literalName,literalBytes);await view(literal,320);await preview(literal,'<img src=x');expect(await page.evaluate(()=>window.fileXss)).toBeUndefined();await capture('09-narrow-literal-preview',320)
 // The server enforces size even when a direct multipart client bypasses the visible form guard.
 await page.goto(origin+`/files?project=${alpha}`);await pick('excede.txt',Buffer.alloc(1000001));await page.getByRole('alert').filter({hasText:'supera el límite'}).waitFor();await expect(page.getByRole('button',{name:'Subir archivo',exact:true})).toBeDisabled();const tooBig=await context.request.post(origin+`/api/files?project_id=${alpha}`,{multipart:{file:{name:'excede.txt',mimeType:'text/plain',buffer:Buffer.alloc(1000001)},operation_key:randomUUID()}});expect(tooBig.status()).toBe(413);await capture('10-size-rejected')
 const transfer=await page.evaluateHandle(()=>{const d=new DataTransfer();d.items.add(new File(['one'],'one.txt'));d.items.add(new File(['two'],'two.txt'));return d});await page.locator('.files-drop').dispatchEvent('drop',{dataTransfer:transfer});await page.getByRole('alert').filter({hasText:'un solo archivo'}).waitFor();await capture('11-multiple-selection-rejected')
 // Broken content can be downloaded without representing a failed preview as empty success.
 const brokenBytes=Buffer.from('%PDF-broken'),broken=await upload('invalido.pdf',brokenBytes,alpha,'application/pdf');await view(broken);let waiting=page.waitForResponse(r=>new URL(r.url()).pathname===`/api/files/${broken.id}/preview`);await page.getByRole('button',{name:'Extraer previa',exact:true}).click();expect((await waiting).status()).toBe(422);await page.getByRole('alert').filter({hasText:'No se pudo extraer'}).waitFor();await download(broken,brokenBytes);await capture('12-invalid-preview-keeps-original',390)
 // Transport failures stay local to their operation and do not discard a previous actual extraction.
 await view(literal);await preview(literal,'Texto conservado')
 const rejectDownload=route=>route.abort('failed');await page.route(`**/api/files/${literal.id}/download?*`,rejectDownload);await page.getByRole('button',{name:'Descargar original',exact:true}).click();await page.getByRole('alert').filter({hasText:'Failed to fetch'}).waitFor();await capture('13-download-error');await page.unroute(`**/api/files/${literal.id}/download?*`,rejectDownload)
 const rejectPreview=route=>route.abort('failed');await page.route(`**/api/files/${literal.id}/preview?*`,rejectPreview);await page.getByRole('button',{name:'Volver a extraer previa',exact:true}).click();await page.getByRole('alert').filter({hasText:'Se conserva debajo la previa anterior'}).waitFor();await expect(page.getByLabel('Texto extraído del adjunto')).toContainText('Texto conservado');await capture('14-preview-error-retains-prior');await page.unroute(`**/api/files/${literal.id}/preview?*`,rejectPreview)
 evidence.checks.push('Oversize/multiple selections and broken preview are explicit; failed download/refresh cannot become success or erase prior text')
 // Real publication failure leaves complete durable bytes pending until an explicit recovery.
 await page.goto(origin+`/files?project=${alpha}`);await pick('pendiente.txt','Original completo pendiente de publicación.');fault('publish');await page.getByRole('button',{name:'Subir archivo',exact:true}).click();await page.getByRole('alert').filter({hasText:'Cargas y borrados'}).waitFor();const pending=(await history()).find(r=>r.filename==='pendiente.txt');expect(pending.state).toBe('pending');await capture('15-pending-recovery-visible')
 fault('clear');const pendingRow=page.locator('.files-operations li').filter({hasText:'pendiente.txt'});await pendingRow.getByRole('button',{name:'Comprobar y recuperar',exact:true}).click();await expect(page.locator('.files-operations [role="status"]')).toContainText('pendiente.txt: Carga registrada.');const recovered=(await history()).find(r=>r.operation_key===pending.operation_key);expect(recovered.state).toBe('published');expect((await submit()).id).toBe(recovered.reference_id);remember(recovered.receipt,'Original completo pendiente de publicación.',pending.operation_key)
 // Incomplete bytes cannot be published; explicit closure retains the original four bytes.
 await page.goto(origin+`/files?project=${alpha}`);await pick('incompleto.txt','PARTIAL-SYNTHETIC-CONTENT');fault('publish');await page.getByRole('button',{name:'Subir archivo',exact:true}).click();await page.getByRole('alert').filter({hasText:'Cargas y borrados'}).waitFor();const incomplete=(await history()).find(r=>r.filename==='incompleto.txt');expect(incomplete.state).toBe('pending');expect(fault('truncate',incomplete.operation_key).bytes).toBe(4);fault('clear')
 const incompleteRow=page.locator('.files-operations li').filter({hasText:'incompleto.txt'});await incompleteRow.getByRole('button',{name:'Comprobar y recuperar',exact:true}).click();await page.getByRole('alert').filter({hasText:'No se pudo confirmar la operación'}).waitFor();await capture('16-incomplete-recovery-refused');await incompleteRow.getByRole('button',{name:'Cerrar intento y conservar restos',exact:true}).click();await expect(page.locator('.files-operations [role="status"]')).toContainText('restos conservados');expect((await history()).find(r=>r.operation_key===incomplete.operation_key).state).toBe('abandoned');evidence.abandoned={project_id:alpha,operation_key:incomplete.operation_key,expected_bytes:'PART'}
 evidence.checks.push('Actual SQLite publication failure recovers only complete original bytes; incomplete original is refused and retained after explicit abandonment')
 // A rejected metadata deletion cannot remove the original bytes; retry remains the same reference.
 await view(literal,390);await page.getByRole('button',{name:'Eliminar adjunto',exact:true}).click();await expect(page.getByRole('button',{name:'Conservar adjunto',exact:true})).toBeFocused();await page.keyboard.press('Shift+Tab');await expect(page.getByRole('button',{name:'Eliminar definitivamente',exact:true})).toBeFocused();await page.keyboard.press('Tab');await expect(page.getByRole('button',{name:'Conservar adjunto',exact:true})).toBeFocused();await capture('17-delete-dialog',390);await page.keyboard.press('Escape');await expect(page.getByRole('dialog')).not.toBeVisible();await expect(page.getByRole('button',{name:'Eliminar adjunto',exact:true})).toBeFocused()
 fault('delete');await page.getByRole('button',{name:'Eliminar adjunto',exact:true}).click();await page.getByRole('button',{name:'Eliminar definitivamente',exact:true}).click();await page.getByRole('alert').filter({hasText:'No se pudo confirmar el borrado'}).waitFor();const stillThere=await context.request.get(origin+`/api/files/${literal.id}/download?project_id=${alpha}`);expect(stillThere.status()).toBe(200);expect((await stillThere.body()).equals(Buffer.from(literalBytes))).toBe(true);await capture('18-delete-failure-keeps-bytes',390);fault('clear');await page.getByRole('button',{name:'Eliminar definitivamente',exact:true}).click();await page.getByRole('button',{name:'Eliminar adjunto',exact:true}).waitFor({state:'detached'});evidence.deleted=[literal.id]
 // A lost delete response is resolved from its actual historical receipt, not a replacement operation.
 const deletion=await upload('borrado-sin-respuesta.txt','Original que será retirado.');await view(deletion);const loseDelete=async route=>{const response=await route.fetch();expect(response.status()).toBe(204);await route.abort('failed')};await page.route(`**/api/files/${deletion.id}?*`,async route=>route.request().method()==='DELETE'?loseDelete(route):route.continue());await page.getByRole('button',{name:'Eliminar adjunto',exact:true}).click();await page.getByRole('button',{name:'Eliminar definitivamente',exact:true}).click();await page.getByRole('heading',{name:'No se pudo cargar el adjunto',exact:true}).waitFor();await page.unroute(`**/api/files/${deletion.id}?*`);expect((await history()).find(r=>r.operation_key===`delete:${deletion.id}`).state).toBe('deleted');evidence.deleted.push(deletion.id);await page.getByRole('button',{name:'Ver historial de cargas y borrados',exact:true}).click();await expect(page.locator('.files-operations li').filter({hasText:'borrado-sin-respuesta.txt'}).filter({hasText:'Borrado confirmado'})).toHaveCount(1);await capture('19-lost-delete-receipt-history');await page.getByRole('button',{name:'Ocultar historial confirmado',exact:true}).click()
 evidence.checks.push('Keyboard deletion preserves focus; failed commit preserves original bytes; lost delete reply remains inspectable as the exact original result')
 // A foreign URL never supplies another project's file actions.
 await page.goto(origin+`/files?project=${beta}&file=${betaFile.id}`);await page.getByRole('status').filter({hasText:'otro proyecto'}).waitFor();await expect(page.getByRole('button',{name:'Descargar original',exact:true})).toHaveCount(0);await capture('20-foreign-link',390)
 await view(retried,390);await page.reload();await page.getByRole('heading',{name:retried.filename,exact:true}).waitFor();await download(retried,lostBytes);await capture('21-current-mobile-after-reload',390)
 expect(evidence.errors).toEqual([])

 evidence.status='passed'
}catch(error){evidence.status='failed';evidence.failure=String(error);throw error}
finally{releaseLate?.();if(cleanupFaults)cleanupFaults();await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(evidence,null,2)+'\n');await browser.close()}
