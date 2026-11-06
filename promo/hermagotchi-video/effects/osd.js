export function osd(g, copy, channel, time, rec=false) {
  g.save();g.font='38px BroadcastMono';g.fillStyle='#caffbc';g.shadowColor='#10160d';g.shadowOffsetX=3;g.shadowOffsetY=3;
  const minutes=String(Math.floor(time/60)).padStart(2,'0');const seconds=String(Math.floor(time%60)).padStart(2,'0');
  g.fillText(`${copy.station.channelPrefix} ${channel}`,135,106);
  g.textAlign='right';g.fillText(`${rec?copy.station.rec:copy.station.osd}  ▷  ${copy.station.timePrefix}${minutes}:${seconds}`,1780,106);
  if(rec && Math.floor(time*2)%2===0){g.fillStyle='#ff5753';g.fillRect(1350,81,16,16);}
  g.restore();
}
