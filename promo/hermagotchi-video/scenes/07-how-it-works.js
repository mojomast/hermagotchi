import {box,text,title,cream,ink,ease} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
export function draw(g,t,e){
  const c=e.copy.how;box(g,0,0,1920,1080,'#d4c7a1');
  // Registration marks and hairline scratches evoke a telecined classroom reel.
  for(let i=0;i<8;i++)box(g,146+i*225+Math.floor(t*3)%3,120,1,810,'#382c2012');
  title(g,c.title,c.subtitle,t,'#493d32');
  text(g,c.plate,136,365,33,'#6a4739','BroadcastMono');
  c.nodes.forEach((label,i)=>{
    const reveal=ease((t-.5-i*.8)/.65);const x=140+i*435;
    g.save();g.globalAlpha=reveal;box(g,x+8,457,335,250,'#b09c7c');box(g,x,449,335,250,'#ede2bd');g.strokeStyle='#5a4a39';g.lineWidth=4;g.strokeRect(x,449,335,250);
    text(g,label,x+167,553,46,'#493c31','Broadcast','center');text(g,c.captions[i],x+167,621,29,'#71513c','BroadcastMono','center');g.restore();
    if(i<3&&t>1.3+i*.8){g.strokeStyle='#845043';g.lineWidth=6;g.beginPath();g.moveTo(x+348,573);g.lineTo(x+412,573);g.lineTo(x+395,559);g.moveTo(x+412,573);g.lineTo(x+395,587);g.stroke();
      const progress=((t-1.3-i*.8)%1.6)/1.6;box(g,x+348+Math.round(progress*60),569,8,8,'#a02f35');}
  });
  pet(g,e,0,832,695,192,t,{items:false,state:'happy'});text(g,c.footer,960,928,44,'#493d32','BroadcastMono','center');
}
