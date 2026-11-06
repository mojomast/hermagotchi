import {stripeBG,box,text,chrome,npc,lines,slot,ticker,cream,red,yellow,ease,lerpCrop} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
export function draw(g,t,e){
  const c=e.copy.arena;stripeBG(g,'#281f30','#4b2032',-t*2);
  chrome(g,c.title,133,233,102);text(g,c.status,136,285,34,yellow,'BroadcastMono');
  if(t<4){
    box(g,160,350,680,468,'#a43543');box(g,1080,350,680,468,'#354567');
    pet(g,e,3,232,355,384,t,{state:'idle'});pet(g,e,9,1220,355,384,t,{state:'idle',flip:true});
    text(g,e.copy.pets[e.cast[3].species],500,805,62,cream,'Broadcast','center');text(g,e.copy.pets[e.cast[9].species],1420,805,62,cream,'Broadcast','center');
    chrome(g,c.versus,960,620,128,'center');text(g,c.kicker,960,893,46,yellow,'BroadcastMono','center');
  }else{
    const replay=t>=9&&t<13,ko=t>=15;const anim=ko?1.28:replay?(t-9)*.25+1:(t-4);
    box(g,132,351,1050,477,'#191b2a');box(g,150,710,1010,110,'#55506b');
    for(let i=0;i<3;i++)box(g,155,452+i*85,1010,6,i===1?'#e8d2bb':'#9e3e4f');
    const lunge=ko?0:Math.round(Math.max(0,Math.sin(anim*4))*74);
    pet(g,e,3,167+lunge,356,384,anim,{state:'attack'});pet(g,e,9,743-lunge,356,384,ko?0:anim,{state:'hurt',flip:true});
    box(g,165,370,385,26,'#663d43');box(g,754,370,385,26,'#663d43');
    box(g,165,370,Math.round(340-Math.min(anim,4)*18),26,'#d5d68a');box(g,754,370,Math.round(ko?0:320-Math.min(anim,4)*44),26,'#d5d68a');
    text(g,c.hp,652,398,24,cream,'BroadcastMono','center');
    text(g,replay?c.replay:c.round,653,862,35,yellow,'BroadcastMono','center');
    if(replay){
      g.strokeStyle=yellow;g.lineWidth=7;g.beginPath();g.ellipse(923,581,135,151,-.25,-Math.PI/2,-Math.PI/2+Math.PI*2*ease((t-9.3)/1));g.stroke();
      g.beginPath();g.moveTo(555,566);g.lineTo(760,526);g.lineTo(726,515);g.moveTo(760,526);g.lineTo(739,552);g.stroke();text(g,c.telestrator,654,915,36,yellow,'BroadcastMono','center');
    }
    if(ko){chrome(g,c.ko,654,650,190,'center');text(g,c.koNote,654,919,28,yellow,'BroadcastMono','center');}
    // Zoom ~2.2× onto battle UI: result card → turn log / HP rows (onyx VO).
    const battleCrop = ko
      ? lerpCrop({sx:0.00,sy:0.10,sw:0.55,sh:0.55},{sx:0.00,sy:0.35,sw:0.58,sh:0.58}, Math.min(1,(t-15)/2.5))
      : lerpCrop({sx:0.00,sy:0.08,sw:0.58,sh:0.52},{sx:0.00,sy:0.38,sw:0.62,sh:0.55}, Math.min(1,Math.max(0,(t-4)/8)));
    slot(g,e,ko?'SHOT_BATTLE_RESULT':'CLIP_BATTLE_LIVE',1230,355,540,304,battleCrop);
    npc(g,e,'southpaw',1230,697,160);text(g,c.host,1407,726,30,yellow,'BroadcastMono');lines(g,e.copy.npcs.southpaw.quote,1407,771,365,36);
  }
  ticker(g,c.ticker,t);
}
