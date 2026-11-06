import {box,text,image,bars,cream,ease} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
export function draw(g,t,e){
  const c=e.copy.outro;box(g,0,0,1920,1080,'#281d35');
  if(t>=5.4){
    bars(g);box(g,410,380,1100,230,'#181522');text(g,e.copy.station.signOff,960,470,69,cream,'Broadcast','center');text(g,c.end,960,553,44,cream,'BroadcastMono','center');
    const collapse=ease((t-6.05)/.55);
    if(collapse>0){
      const h=Math.max(2,1080*(1-collapse));box(g,0,0,1920,(1080-h)/2,'#050509');box(g,0,(1080+h)/2,1920,1080,'#050509');
      if(collapse>.99){box(g,0,0,1920,1080,'#050509');const width=Math.max(0,1200*(1-ease((t-6.6)/.22)));box(g,960-width/2,538,width,4,'#fff7df');}
    }return;
  }
  for(let i=0;i<12;i++){g.strokeStyle='#563349';g.lineWidth=3;g.beginPath();g.moveTo(960,300);g.lineTo(-700+i*310,1080);g.stroke();}
  image(g,e.images['assets/ui/wordmark.png'],339,235,1242,198);
  text(g,c.anthem,960,518,58,cream,'Broadcast','center');
  e.cast.forEach((p,i)=>pet(g,e,i,145+i*162,557+(i%2)*48,160,t,{state:'happy'}));
  box(g,255,828,1410,83,'#dfbc85');text(g,e.cta,960,885,39,'#2b2032','BroadcastMono','center');text(g,c.footer,960,967,36,cream,'BroadcastMono','center');
}
