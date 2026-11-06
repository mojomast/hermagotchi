import {box,text,chrome,npc,slot,lines,ticker,cream,yellow,holdPan} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
// Social hub → DMs → lobby rail; Southpaw → ranked rows → neighborhood.
const NOUS = {sx:0.00, sy:0.10, sw:0.55, sh:0.205};
const DMS  = {sx:0.00, sy:0.34, sw:0.55, sh:0.205};
const RAIL = {sx:0.72, sy:0.14, sw:0.28, sh:0.70}; // tall lobby column
const LB_HOST = {sx:0.00, sy:0.10, sw:0.55, sh:0.309};
const LB_ROWS = {sx:0.00, sy:0.26, sw:0.58, sh:0.326};
const LB_NBHD = {sx:0.00, sy:0.48, sw:0.58, sh:0.326};
export function draw(g,t,e){
  const c=e.copy.lobby;box(g,0,0,1920,1080,'#2f4f4d');
  for(let i=0;i<12;i++){box(g,i*180,0,88,1080,'#294744');}
  chrome(g,c.title,132,229,106);text(g,c.subtitle,136,281,37,yellow,'BroadcastMono');
  npc(g,e,'nous_girl',140,345,320);text(g,c.host,140,711,38,cream,'BroadcastMono');
  lines(g,e.copy.npcs.nous_girl.quote,140,762,380,43,yellow);
  box(g,548,330,695,322,'#252e39');
  const chatCrop=holdPan(t,[[NOUS,2.0],[DMS,2.2],[RAIL,2.5]],1.3);
  slot(g,e,'SHOT_CHAT',566,347,660,246,chatCrop);
  text(g,c.callers[Math.min(2,Math.floor(t/4))],565,637,34,cream,'BroadcastMono');
  text(g,c.caller,564,695,31,yellow,'BroadcastMono');
  npc(g,e,'teknium',553,733,160);text(g,c.tip,736,765,34,yellow,'BroadcastMono');lines(g,e.copy.npcs.teknium.quote,736,813,475,39);
  box(g,1280,330,490,600,'#d8c7a3');text(g,c.standings,1525,385,38,'#2b3336','Broadcast','center');
  const lbCrop=holdPan(t,[[LB_HOST,2.0],[LB_ROWS,2.5],[LB_NBHD,2.0]],1.3);
  slot(g,e,'SHOT_LEADERBOARD',1300,412,450,253,lbCrop);
  c.rows.forEach((row,i)=>text(g,row,1303,721+i*57,31,'#263f3c','BroadcastMono'));
  ticker(g,c.ticker,t);
}
