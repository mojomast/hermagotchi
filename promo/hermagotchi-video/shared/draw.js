export const W=1920,H=1080;
export const ink='#241c29',cream='#fff0cb',yellow='#f9dc60',red='#be3345';
export const clamp=(x,a=0,b=1)=>Math.max(a,Math.min(b,x));
export const ease=x=>1-Math.pow(1-clamp(x),4);
export function box(g,x,y,w,h,color){g.fillStyle=color;g.fillRect(Math.round(x),Math.round(y),w,h);}
export function text(g,str,x,y,size=40,color=cream,font='Broadcast',align='left'){
  g.save();g.fillStyle=color;g.font=`${size}px ${font}`;g.textAlign=align;g.textBaseline='alphabetic';g.fillText(String(str),Math.round(x),Math.round(y));g.restore();
}
export function lines(g,str,x,y,width,size=36,color=cream,font='BroadcastMono',leading=1.06){
  g.save();g.font=`${size}px ${font}`;let line='',n=0;
  for(const word of String(str).split(' ')){
    if(g.measureText(line+word).width>width && line){text(g,line,x,y+n*size*leading,size,color,font);line='';n++;}
    line+=word+' ';
  }
  text(g,line,x,y+n*size*leading,size,color,font);g.restore();return (n+1)*size*leading;
}
export function chrome(g,str,x,y,size=100,align='left'){
  g.save();g.font=`${size}px Broadcast`;g.textAlign=align;
  g.lineWidth=9;g.strokeStyle='#29192c';g.strokeText(str,x+5,y+7);
  const grad=g.createLinearGradient(0,y-size,0,y);grad.addColorStop(0,'#fff9e7');grad.addColorStop(.43,'#9ba3b0');grad.addColorStop(.49,'#fff');grad.addColorStop(.52,'#504b6e');grad.addColorStop(1,'#ede7d6');
  g.fillStyle=grad;g.fillText(str,x,y);g.restore();
}
export function stripeBG(g,a,b,time=0){
  box(g,0,0,W,H,a);g.save();g.fillStyle=b;
  for(let i=-3;i<12;i++){g.beginPath();g.moveTo(i*240+time*4,0);g.lineTo(i*240+120+time*4,0);g.lineTo(i*240-500+time*4,H);g.lineTo(i*240-620+time*4,H);g.fill();}g.restore();
}
export function lower(g,headline,sub,color=red){
  box(g,110,865,1690,116,'#1a1721');box(g,110,865,18,116,yellow);box(g,128,865,1672,68,color);
  text(g,headline,153,916,45);if(sub)text(g,sub,153,966,31,cream,'BroadcastMono');
}
export function ticker(g,str,t,y=978){
  box(g,100,y,1720,51,'#171821');g.save();g.beginPath();g.rect(110,y,1700,51);g.clip();
  g.font='33px BroadcastMono';const width=g.measureText(str).width+90;const offset=(t*86)%width;
  for(let i=0;i<3;i++)text(g,str,120+i*width-offset,y+36,33,cream,'BroadcastMono');g.restore();
}
export function star(g,x,y,r,color,turn=0){
  g.save();g.translate(x,y);g.rotate(turn);g.beginPath();
  for(let i=0;i<32;i++){const a=i*Math.PI/16;const rr=i%2?r*.78:r;g.lineTo(Math.cos(a)*rr,Math.sin(a)*rr);}g.closePath();g.fillStyle=color;g.fill();g.lineWidth=6;g.strokeStyle=ink;g.stroke();g.restore();
}
export function title(g,headline,kicker,t,color=cream){
  const offset=Math.round((1-ease(t/0.65))*-130);
  text(g,headline,132+offset,235,92,color);text(g,kicker,137+offset,282,34,color,'BroadcastMono');
}
export function image(g,img,x,y,w,h){if(img)g.drawImage(img,Math.round(x),Math.round(y),Math.round(w),Math.round(h));}
export function bars(g){
  ['#d5d1be','#cebf3c','#4ab9b3','#46b257','#ba4d9a','#bc4b43','#4b55a6'].forEach((c,i)=>box(g,i*W/7,0,W/7+1,720,c));
  ['#4b55a6','#111','#ba4d9a','#111','#4ab9b3','#111','#d5d1be'].forEach((c,i)=>box(g,i*W/7,720,W/7+1,100,c));
  ['#162753','#e9e5cd','#37174b','#101114','#1b1c1f','#090a0b'].forEach((c,i)=>box(g,i*W/6,820,W/6+1,260,c));
}
export function npc(g,env,name,x,y,size=256){
  box(g,x,y,size,size,'#e2c49c');image(g,env.images[`assets/px3/npcs/${name}_portrait.png`],x,y,size,size);
}
export function slot(g,env,id,x,y,w,h){
  box(g,x-6,y-6,w+12,h+12,'#b9ae9a');box(g,x,y,w,h,'#161523');
  const img=env.slotFrames[id];if(img){
    const scale=Math.min(w/img.width,h/img.height);const iw=img.width*scale,ih=img.height*scale;
    g.save();g.imageSmoothingEnabled=true;image(g,img,x+(w-iw)/2,y+(h-ih)/2,iw,ih);g.restore();
  }
}
