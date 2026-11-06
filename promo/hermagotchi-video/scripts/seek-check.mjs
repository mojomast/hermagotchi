// Meaningful regression check: same shader pixels after out-of-order seeks,
// using the same frame-source entry point and assets as the HyperFrames export.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import http from 'node:http';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import puppeteer from 'puppeteer-core';
const root=path.resolve('.build');
function findChrome(dir){
  if(!fs.existsSync(dir))return;
  for(const f of fs.readdirSync(dir,{withFileTypes:true})){
    const p=path.join(dir,f.name);if(f.isFile()&&f.name==='chrome-headless-shell')return p;
    if(f.isDirectory()){const result=findChrome(p);if(result)return result;}
  }
}
const executablePath=process.env.CHROME_BIN||findChrome(path.join(os.homedir(),'.cache/hyperframes/chrome'));
assert.ok(executablePath,'Set CHROME_BIN to the HyperFrames Chromium executable.');
let html=fs.readFileSync(path.join(root,'index.html'),'utf8');
html=html.replace('<script src="runtime.js"></script>','<script>window.__hyperframes={assetUrl:p=>p,registerFrameSource:()=>{}};</script><script src="runtime.js"></script>');
html=html.replace(/(<div id="host-\d+"[^>]*data-composition-src="([^"]+)"[^>]*>)<\/div>/g,(_,host,src)=>{
  const scene=fs.readFileSync(path.join(root,src),'utf8').replace('<template>','').replace('</template>','');return host+scene+'</div>';
});
const server=http.createServer((req,res)=>{
  if(req.url==='/'){res.setHeader('Content-Type','text/html');res.end(html);return;}
  const p=path.resolve(root,'.'+decodeURIComponent(req.url.split('?')[0]));
  if(!p.startsWith(root+path.sep)||!fs.existsSync(p)){res.statusCode=404;res.end();return;}
  const types={'.js':'text/javascript','.css':'text/css','.png':'image/png','.jpg':'image/jpeg','.ttf':'font/ttf','.wav':'audio/wav'};
  res.setHeader('Content-Type',types[path.extname(p)]||'application/octet-stream');fs.createReadStream(p).pipe(res);
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const browser=await puppeteer.launch({headless:true,executablePath,args:['--no-sandbox','--enable-unsafe-swiftshader']});
try{
  const page=await browser.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${server.address().port}`,{waitUntil:'load'});
  const samples=[[0,4],[1,9],[2,6],[3,5],[3,13],[4,11],[5,6],[6,5],[7,3]];
  const capture=async([index,time])=>{
    const data=await page.evaluate(async({index,time})=>{const m=Hermagotchi.test.mounts[index];await m.render(time);return m.canvas.toDataURL('image/png');},{index,time});
    return createHash('sha256').update(data).digest('hex');
  };
  const reference=[];for(const s of samples)reference.push(await capture(s));
  for(const i of [8,2,6,0,7,4,1,5,3])assert.equal(await capture(samples[i]),reference[i],`Non-deterministic seek: ${samples[i]}`);
  assert.equal(new Set(reference).size,reference.length,'Scenes must have distinct visible frames');
  assert.notEqual(await capture([1,8]),await capture([1,8.3]),'Sprite/OSD/noise motion must change');
  // Intensity is a real global picture control, not a decorative unused setting.
  await page.evaluate(()=>{Hermagotchi.test.settings.effectIntensity=0;});
  assert.notEqual(await capture(samples[1]),reference[1]);
  assert.deepEqual(errors,[]);
  console.log('PASS: nine shader frames match exactly after shuffled seeks; motion and effect toggle change pixels; no browser errors.');
}finally{await browser.close();server.close();}
