/** Expose real headed Chromium controls to the isolated Orca session; native X keys drive the interaction. @module */
import {createRequire} from 'node:module'
import http from 'node:http'
import fs from 'node:fs/promises'
const require=createRequire('/opt/frontend/package.json'),{chromium,expect}=require('@playwright/test')
const server=http.createServer((_request,response)=>{response.writeHead(200,{'content-type':'text/html;charset=utf-8'});response.end('<!doctype html><html lang="es"><meta charset="utf-8"><title>Prueba de lectura</title><main><h1>Comparar dos fuentes</h1><p>Entrada: dos fuentes. Salida: una comparación con sus límites.</p><button id="review" onclick="document.getElementById(\'notice\').textContent=\'La segunda fuente no indica fecha. Comprueba la versión antes de comparar.\'">Revisar fuentes</button><p id="notice" role="alert"></p></main></html>')})
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve))
let browser;const result={status:'running',scope:'Synthetic reader capability only, not product acceptance'}
try{
 browser=await chromium.launch({headless:false,executablePath:'/opt/chromium/chrome',args:['--force-renderer-accessibility','--disable-dev-shm-usage']})
 const page=await browser.newPage({viewport:{width:1280,height:900}})
 await page.goto('http://127.0.0.1:'+server.address().port)
 await fs.writeFile('/out/browser-ready.json',JSON.stringify({version:browser.version(),title:await page.title()}))
 await expect(page.getByRole('alert')).toHaveText('La segunda fuente no indica fecha. Comprueba la versión antes de comparar.',{timeout:30000})
 await page.screenshot({path:'/out/page.png'})
 result.status='passed';result.notice=await page.getByRole('alert').innerText()
 await fs.writeFile('/out/browser-interaction.json',JSON.stringify(result,null,2)+'\n')
 await new Promise(resolve=>process.once('SIGTERM',resolve))
} catch(error){result.status='failed';result.error=String(error);throw error}
finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));await fs.writeFile('/out/browser-result.json',JSON.stringify(result,null,2)+'\n')}
