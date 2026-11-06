import {box,text,title,lower,cream,ink,ease} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
export function draw(g,t,e){
  const c=e.copy.forecast;box(g,0,0,1920,1080,'#c8bda3');box(g,0,0,1920,310,'#463345');
  title(g,c.title,c.kicker,t);box(g,120,335,370,488,'#e4d9b8');
  const focus=Math.min(9,Math.floor(t/1.16));const p=e.cast[focus];
  text(g,e.copy.pets[p.species],305,395,47,ink,'Broadcast','center');pet(g,e,focus,145,415,320,t,{items:false,state:p.state});
  text(g,c.fronts[focus],305,780,31,'#633e4a','BroadcastMono','center');
  // Invented geography is explicitly labeled; this is a weather-show metaphor.
  g.fillStyle='#758b75';g.strokeStyle='#52695c';g.lineWidth=7;g.beginPath();
  [[530,350],[785,330],[890,380],[1130,334],[1280,360],[1430,335],[1740,398],[1790,620],[1650,790],[1380,813],[1210,772],[1010,805],[800,775],[570,810],[520,650]].forEach(([x,y],i)=>i?g.lineTo(x,y):g.moveTo(x,y));g.closePath();g.fill();g.stroke();
  g.strokeStyle='#a7b69a';g.lineWidth=3;
  for(let i=0;i<5;i++){g.beginPath();g.ellipse(1150,570,120+i*110,70+i*40,-.2,0,Math.PI*2);g.stroke();}
  c.regions.forEach((s,i)=>text(g,s,550+i*310,343,26,'#394f48','BroadcastMono'));
  e.cast.forEach((p,i)=>{
    const reveal=ease((t-.2-i*.16)/.45);if(reveal<=0)return;
    const x=548+(i%5)*244,y=350+Math.floor(i/5)*233;const state=e.manifest.animations.states[(Math.floor(t/2)+i)%6];
    g.save();g.globalAlpha=reveal;pet(g,e,i,x,y+Math.round((1-reveal)*35),192,t,{items:false,state});
    box(g,x-7,y+188,220,37,'#392e3c');text(g,e.copy.pets[p.species],x+103,y+217,29,cream,'BroadcastMono','center');g.restore();
  });
  lower(g,c.lower,c.note,'#764452');
}
