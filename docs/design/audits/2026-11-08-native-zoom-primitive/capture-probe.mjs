/** Verify full-viewport native-zoom screenshots independently of Playwright's cropped default capture. @module */
import {createRequire} from 'node:module'
import fs from 'node:fs/promises'
import path from 'node:path'
import http from 'node:http'
import assert from 'node:assert/strict'
const root=process.cwd(),require=createRequire(path.join(root,'frontend/package.json'))
const {chromium}=require('@playwright/test')
const out=path.join(root,'.superpowers/sdd/2026-10-31-actualizacion-proyecto/native-zoom-capture')
await fs.mkdir(out)
const profile=path.join(out,'profile');await fs.mkdir(path.join(profile,'Default'),{recursive:true})
await fs.writeFile(path.join(profile,'Default/Preferences'),JSON.stringify({partition:{default_zoom_level:{x:Math.log(4)/Math.log(1.2)}}}))
const server=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html;charset=utf-8'});res.end('<!doctype html><html lang="es"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prueba local</title><main><h1>Ejemplo de lectura</h1><p>Entrada: dos fuentes. Salida: una comparación con sus límites.</p><button>Consultar fuentes</button></main></html>')})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
let context
const result={status:'running',scope:'Screenshot primitive only; synthetic HTML, not a product UI acceptance'}
try{
 context=await chromium.launchPersistentContext(profile,{channel:'chromium',headless:true,viewport:null,args:['--window-size=1280,1024']})
 const page=await context.newPage();await page.goto('http://127.0.0.1:'+server.address().port)
 result.metrics=await page.evaluate(()=>({innerWidth,innerHeight,outerWidth,outerHeight,devicePixelRatio,rootZoom:getComputedStyle(document.documentElement).zoom,visualScale:visualViewport.scale}))
 assert.equal(result.metrics.innerWidth,320);assert.equal(result.metrics.devicePixelRatio,4);assert.equal(result.metrics.rootZoom,'1');assert.equal(result.metrics.visualScale,1)
 const cdp=await context.newCDPSession(page);result.layout=await cdp.send('Page.getLayoutMetrics')
 const screenshot=await cdp.send('Page.captureScreenshot',{format:'png',fromSurface:true,captureBeyondViewport:false})
 const bytes=Buffer.from(screenshot.data,'base64');result.png={width:bytes.readUInt32BE(16),height:bytes.readUInt32BE(20)}
 await fs.writeFile(path.join(out,'full-zoom-4.png'),bytes)
 assert.equal(result.png.width,result.layout.layoutViewport.clientWidth)
 assert.equal(result.png.height,result.layout.layoutViewport.clientHeight)
 assert.equal(result.png.width,1280)
 result.version=context.browser()?.version();result.status='passed'
}catch(error){result.error=String(error);throw error}
finally{
 if(context)await context.close()
 await new Promise(resolve=>server.close(resolve))
 await fs.writeFile(path.join(out,'result.json'),JSON.stringify(result,null,2)+'\n')
 process.stdout.write(JSON.stringify({status:result.status,metrics:result.metrics,png:result.png,error:result.error})+'\n')
}
