import {box,text,chrome,npc,slot,lines,ticker,cream,yellow} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
export function draw(g,t,e){
  const c=e.copy.lobby;box(g,0,0,1920,1080,'#2f4f4d');
  for(let i=0;i<12;i++){box(g,i*180,0,88,1080,'#294744');}
  chrome(g,c.title,132,229,106);text(g,c.subtitle,136,281,37,yellow,'BroadcastMono');
  npc(g,e,'nous_girl',140,345,320);text(g,c.host,140,711,38,cream,'BroadcastMono');
  lines(g,e.copy.npcs.nous_girl.quote,140,762,380,43,yellow);
  box(g,548,330,695,322,'#252e39');slot(g,e,'SHOT_CHAT',566,347,660,246);
  text(g,c.callers[Math.min(2,Math.floor(t/4))],565,637,34,cream,'BroadcastMono');
  text(g,c.caller,564,695,31,yellow,'BroadcastMono');
  npc(g,e,'teknium',553,733,160);text(g,c.tip,736,765,34,yellow,'BroadcastMono');lines(g,e.copy.npcs.teknium.quote,736,813,475,39);
  box(g,1280,330,490,600,'#d8c7a3');text(g,c.standings,1525,385,38,'#2b3336','Broadcast','center');
  slot(g,e,'SHOT_LEADERBOARD',1300,412,450,253);
  c.rows.forEach((row,i)=>text(g,row,1303,721+i*57,31,'#263f3c','BroadcastMono'));
  ticker(g,c.ticker,t);
}
