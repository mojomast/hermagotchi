import {bars,box,text,chrome,image,W,H,cream,ease} from '../shared/draw.js';
export function draw(g,t,e){
  const c=e.copy.station;
  if(t<1.8){bars(g);box(g,475,390,970,230,'#151323');text(g,c.station,960,480,64,cream,'Broadcast','center');text(g,c.signOn,960,556,42,cream,'BroadcastMono','center');return;}
  box(g,0,0,W,H,'#08070e');
  const power=ease((t-2.0)/.85);g.save();g.translate(960,540);g.scale(1,Math.max(.002,power));g.translate(-960,-540);
  const grad=g.createRadialGradient(960,520,10,960,520,950);grad.addColorStop(0,'#7b3457');grad.addColorStop(1,'#211c35');box(g,0,0,W,H,grad);
  for(let i=0;i<8;i++){g.strokeStyle=`rgba(240,197,127,${.12-i*.01})`;g.lineWidth=4;g.strokeRect(360-i*80,280-i*45,1200+i*160,520+i*90);}
  image(g,e.images['assets/ui/wordmark.png'],339,344,1242,198);
  chrome(g,c.station,960,650,64,'center');text(g,c.subtitle,960,728,39,cream,'BroadcastMono','center');
  box(g,550,810,820,60,'#e9c883');text(g,c.draft,960,850,30,'#281e32','BroadcastMono','center');g.restore();
  if(t<2.5){g.globalAlpha=1-power;box(g,0,535,1920,10,'#fff8de');g.globalAlpha=1;}
}
