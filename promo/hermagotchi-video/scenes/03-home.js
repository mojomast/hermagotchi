import {box,text,title,slot,lower,cream,lerpCrop} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
// Habitat capture is 1920×1080 shell: main pane left, lobby rail right.
// Zoom ~2× onto care UI; pan with coral VO (feed → rest → train).
const CROP_PET={sx:0.02,sy:0.12,sw:0.48,sh:0.55};      // EmberByte card
const CROP_CARE={sx:0.02,sy:0.28,sw:0.52,sh:0.58};     // fullness/happiness bars
const CROP_ACTIONS={sx:0.02,sy:0.42,sw:0.55,sh:0.52};  // Feed / Play / Rest
export function draw(g,t,e){
  const c=e.copy.home;const phase=Math.min(2,Math.floor(t/4));const state=['happy','eat','sleep'][phase];
  box(g,0,0,1920,1080,['#343c3b','#48402e','#26283b'][phase]);
  for(let i=0;i<14;i++)box(g,i*150,0,3,1080,'#ffffff08');
  title(g,c.title,c.subtitle,t,'#e7ebc6');
  box(g,138,356,620,425,'#2c302b');box(g,138,777,620,25,'#ad8b60');
  g.strokeStyle='#c3c7a1';g.lineWidth=5;[[160,330,1,1],[740,330,-1,1],[160,802,1,-1],[740,802,-1,-1]].forEach(([x,y,a,b])=>{g.beginPath();g.moveTo(x+a*55,y);g.lineTo(x,y);g.lineTo(x,y+b*45);g.stroke();});
  pet(g,e,0,192,295,512,t,{state,items:false});
  text(g,c.states[phase],448,837,49,'#d4ffc1','BroadcastMono','center');
  box(g,860,345,920,470,'#6a4736');box(g,878,363,786,434,'#26252b');
  let crop=CROP_PET;
  if(t<4) crop=lerpCrop(CROP_PET,CROP_CARE,t/4);
  else if(t<8) crop=lerpCrop(CROP_CARE,CROP_ACTIONS,(t-4)/4);
  else crop=lerpCrop(CROP_ACTIONS,CROP_CARE,(t-8)/4);
  slot(g,e,'SHOT_PANE_HOME',895,385,752,390,crop);
  for(let i=0;i<2;i++){g.fillStyle='#c0ab86';g.beginPath();g.arc(1724,438+i*106,30,0,7);g.fill();box(g,1721,415+i*106,6,45,'#342e29');}
  for(let i=0;i<8;i++)box(g,1690,647+i*14,64,4,'#2f2824');
  text(g,c.readouts[phase],893,326,37,'#d4ffc1','BroadcastMono');
  lower(g,c.label,c.stats.join('     /     '),'#4c6250');
  text(g,c.date,132,1024,29,'#d4ffc1','BroadcastMono');text(g,c.battery,1776,1024,29,'#d4ffc1','BroadcastMono','right');
}
