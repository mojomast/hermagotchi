import {box,text,chrome,npc,slot,lines,ticker,cream,yellow,lerpCrop} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
// SHOT_CHAT: Social hub + lobby rail. Pan hub → dense lobby (shimmer VO).
const CHAT_HUB={sx:0.00,sy:0.10,sw:0.58,sh:0.55};
const CHAT_RAIL={sx:0.62,sy:0.10,sw:0.36,sh:0.85};
// SHOT_LEADERBOARD: Southpaw host → ranked rows.
const LB_HOST={sx:0.00,sy:0.10,sw:0.58,sh:0.50};
const LB_ROWS={sx:0.00,sy:0.28,sw:0.58,sh:0.55};
export function draw(g,t,e){
  const c=e.copy.lobby;box(g,0,0,1920,1080,'#2f4f4d');
  for(let i=0;i<12;i++){box(g,i*180,0,88,1080,'#294744');}
  chrome(g,c.title,132,229,106);text(g,c.subtitle,136,281,37,yellow,'BroadcastMono');
  npc(g,e,'nous_girl',140,345,320);text(g,c.host,140,711,38,cream,'BroadcastMono');
  lines(g,e.copy.npcs.nous_girl.quote,140,762,380,43,yellow);
  box(g,548,330,695,322,'#252e39');
  const chatCrop=t<5?lerpCrop(CHAT_HUB,CHAT_RAIL,t/5):lerpCrop(CHAT_RAIL,CHAT_HUB,(t-5)/7);
  slot(g,e,'SHOT_CHAT',566,347,660,246,chatCrop);
  text(g,c.callers[Math.min(2,Math.floor(t/4))],565,637,34,cream,'BroadcastMono');
  text(g,c.caller,564,695,31,yellow,'BroadcastMono');
  npc(g,e,'teknium',553,733,160);text(g,c.tip,736,765,34,yellow,'BroadcastMono');lines(g,e.copy.npcs.teknium.quote,736,813,475,39);
  box(g,1280,330,490,600,'#d8c7a3');text(g,c.standings,1525,385,38,'#2b3336','Broadcast','center');
  const lbCrop=t<6?lerpCrop(LB_HOST,LB_ROWS,t/6):lerpCrop(LB_ROWS,LB_HOST,(t-6)/6);
  slot(g,e,'SHOT_LEADERBOARD',1300,412,450,253,lbCrop);
  c.rows.forEach((row,i)=>text(g,row,1303,721+i*57,31,'#263f3c','BroadcastMono'));
  ticker(g,c.ticker,t);
}
