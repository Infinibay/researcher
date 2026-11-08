/** Compare the former early PageDown check with actual scrollend on one real zoomed route. @module */
import {createRequire} from 'node:module'
import fs from 'node:fs/promises'
import path from 'node:path'
import {pathToFileURL} from 'node:url'
const root=process.cwd(),require=createRequire(path.join(root,'frontend/package.json'))
const {chromium,expect}=require('@playwright/test')
const {tabTo}=await import(pathToFileURL(path.join(root,'frontend/tests/navigation-audit.mjs')))
const {scrollWithKeyboard}=await import(pathToFileURL(path.join(root,'frontend/tests/native-zoom-audit.mjs')))
const out=process.env.RESEARCHER_E2E_OUTPUT,origin=process.env.RESEARCHER_E2E_ORIGIN
const profile=path.join(out,'profile');await fs.mkdir(path.join(profile,'Default'),{recursive:true})
await fs.writeFile(path.join(profile,'Default/Preferences'),JSON.stringify({partition:{default_zoom_level:{x:Math.log(4)/Math.log(1.2)}}}))
const result={status:'running',states:[]};let context
/** Read final target clipping and document movement without changing focus or scroll. */
async function measure(page){return page.locator('#planning-new').evaluate(button=>{const r=button.getBoundingClientRect();return{scrollTop:document.scrollingElement.scrollTop,top:r.top,bottom:r.bottom,height:r.height,innerHeight,focused:document.activeElement===button}})}
try{
 context=await chromium.launchPersistentContext(profile,{channel:'chromium',headless:true,viewport:null,args:['--window-size=1280,1024']})
 const page=await context.newPage();await page.goto(origin+'/projects')
 const code=page.getByLabel('Código de acceso local');await tabTo(page,code)
 await page.keyboard.type((await fs.readFile(process.env.RESEARCHER_E2E_OWNER_FILE,'utf8')).trim())
 await tabTo(page,page.getByRole('button',{name:'Abrir espacio',exact:true}));await page.keyboard.press('Enter')
 const project=page.locator('#project-select-'+process.env.RESEARCHER_PROBE_PROJECT);await expect(project).toBeVisible();await tabTo(page,project);await page.keyboard.press('Enter')
 for(const waitEnd of [false,true]){
  await page.goto(origin+'/epics');await expect(page.locator('#planning-new')).toBeVisible()
  await tabTo(page,page.getByRole('link',{name:'Ir al contenido',exact:true}));await page.keyboard.press('Enter')
  const before=await measure(page)
  let early
  if(waitEnd){await scrollWithKeyboard(page,'PageDown')}
  else{
   await page.evaluate(()=>{window.__probeEnd=false;document.addEventListener('scrollend',()=>{window.__probeEnd=true},{once:true,capture:true})})
   await page.keyboard.press('PageDown');await expect.poll(async()=>(await measure(page)).scrollTop).toBeGreaterThan(before.scrollTop)
   early=await measure(page)
  }
  await tabTo(page,page.locator('#planning-new'))
  if(!waitEnd)await expect.poll(()=>page.evaluate(()=>window.__probeEnd)).toBe(true)
  const final=await measure(page);result.states.push({waitEnd,before,early,final})
  if(waitEnd){await expect.poll(async()=>(await measure(page)).top).toBeGreaterThanOrEqual(0);expect(final.bottom).toBeLessThanOrEqual(final.innerHeight)}
  const cdp=await context.newCDPSession(page);const shot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false});await fs.writeFile(path.join(out,`${waitEnd?'scrollend':'early'}-focus.png`),Buffer.from(shot.data,'base64'));await cdp.detach()
 }
 result.status='passed'
}catch(error){result.status='failed';result.error=String(error);throw error}
finally{if(context)await context.close();await fs.writeFile(path.join(out,'evidence.json'),JSON.stringify(result,null,2)+'\n')}
