import settings from '../settings.json';
import copy from '../copy.json';
import cast from '../cast.json';
import beats from '../BEATS.json';
import manifest from '../assets/manifest.json';
import cta from '../slots/TEXT_CTA.json';
import slotConfig from '../.build/slot-config.json';
import {createCRT} from '../effects/crt.js';
import {osd} from '../effects/osd.js';
import {staticAmount} from '../effects/static.js';
import {image} from './draw.js';
import * as signOn from '../scenes/01-sign-on.js';
import * as forecast from '../scenes/02-forecast.js';
import * as home from '../scenes/03-home.js';
import * as shop from '../scenes/04-shop.js';
import * as arena from '../scenes/05-arena.js';
import * as lobby from '../scenes/06-lobby.js';
import * as how from '../scenes/07-how-it-works.js';
import * as signOff from '../scenes/08-sign-off.js';
const scenes=[signOn,forecast,home,shop,arena,lobby,how,signOff];
const images={}, cache=new Map();
const assetUrl=path=>window.__hyperframes?.assetUrl?window.__hyperframes.assetUrl(path):path;
function load(path){
  if(cache.has(path))return cache.get(path);
  const result=new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error(`Asset failed: ${path}`));img.src=assetUrl(path);});
  cache.set(path,result);return result;
}
let ready;
function initialize(){
  if(ready)return ready;
  const paths=[...manifest.animations.clips.map(c=>'assets/'+c.path),...manifest.assets.map(a=>'assets/'+a.path),'assets/ui/wordmark.png',...['don_piedro','nous_girl','teknium','southpaw'].map(n=>`assets/px3/npcs/${n}_portrait.png`)];
  ready=Promise.all([document.fonts.load('60px Broadcast'),document.fonts.load('38px BroadcastMono'),...paths.map(async p=>{images[p]=await load(p);})]);return ready;
}
const mounts={};
export function mount(id,index){
  const element=document.getElementById('host-'+(index+1));const canvas=element.querySelector('canvas');
  const source=document.createElement('canvas');source.width=1920;source.height=1080;
  const g=source.getContext('2d',{alpha:false});const crt=createCRT(canvas,source,settings);
  const env={copy,cast,manifest,images,cta:cta.text,slotFrames:{},clips:Object.fromEntries(manifest.animations.clips.map(c=>[c.id,c])),items:Object.fromEntries(manifest.assets.map(a=>[a.id,a]))};
  async function render(time,signal){
    await initialize();if(signal?.aborted)return;
    const t=Math.max(0,Math.min(beats[index].end-beats[index].start-1/60,time));
    const active=Object.entries(slotConfig).filter(([,s])=>s.scene===index);
    await Promise.all(active.map(async([id,s])=>{
      const sourceTime=id==='CLIP_BATTLE_LIVE'&&t>=9&&t<13?4+(t-9)*.25:t;
      const f=Math.min(s.frames-1,Math.max(0,Math.floor(sourceTime*60+.00001)));
      const path=s.kind==='image'?s.path:`${s.path}/${String(f+1).padStart(5,'0')}.jpg`;
      env.slotFrames[id]=await load(path);
      // Bound frame memory during long capture; exported pictures depend only on t.
      if(cache.size>180){for(const key of cache.keys()){if(key.startsWith('assets/slot-frames/'))cache.delete(key);if(cache.size<120)break;}}
    }));
    if(signal?.aborted)return;g.save();g.imageSmoothingEnabled=false;
    scenes[index].draw(g,t,env);
    if(!(index===7&&t>=6.05)){
      osd(g,copy,beats[index].channel,beats[index].start+t,index===2);
      if(index>0&&index<7)image(g,images['assets/ui/wordmark.png'],1380,154,414,66);
    }
    g.restore();crt.draw(beats[index].start+t,staticAmount(t,index));
  }
  mounts[index]={render,canvas};
  window.__hyperframes.registerFrameSource({element,ready:initialize(),render,dispose:()=>crt.dispose()});
}
// Exposed only for reproducibility tests; HyperFrames owns normal playback.
export const test={mounts,settings,beats};
