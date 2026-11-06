// steps(4, end), sampled from absolute scene time. No interpolated sprite frames.
// This is the canvas equivalent of a paused CSS steps(4) animation.
export function step4(time, fps=6){return Math.floor(((Math.max(0,time)*fps/4)%1)*4);}
export function pet(g,env,index,x,y,size,time,{state,items=true,itemCount=3,flip=false}={}){
  if(size%32) throw new Error('Pet size must be an integer multiple of the native 32px grid.');
  const p=env.cast[index],s=state||p.state;
  const clip=env.clips[`${p.species}.${p.palette}.${s}`];
  const frame=step4(time,clip.fps),original=Math.min(frame,clip.frame_count-1);
  const delta=clip.frames[original]?.anchor_delta||[0,0];
  const k=size/32;const rig=env.manifest.species[p.species];
  const anchors={...env.manifest.rigs[rig.rig].anchors,...rig.overrides};
  const layers=items?p.items.slice(0,itemCount).map(id=>env.items[id]):[];
  const layer=a=>{
    const [ax,ay]=anchors[a.anchor];const d=a.slot==='aura'||a.anchor==='ground'?[0,0]:delta;
    const side=Math.round(32*a.scale);const ix=Math.round(ax*32+a.offset_px[0]/16-side/2)+d[0];const iy=Math.round(ay*32+a.offset_px[1]/16-side/2)+d[1];
    g.drawImage(env.images['assets/'+a.path],ix*k,iy*k,side*k,side*k);
  };
  g.save();g.translate(Math.round(x+(flip?size:0)),Math.round(y));if(flip)g.scale(-1,1);g.imageSmoothingEnabled=false;
  layers.filter(a=>a.z<0).sort((a,b)=>a.z-b.z).forEach(layer);
  g.drawImage(env.images['assets/'+clip.path],frame*32,0,32,32,0,0,size,size);
  layers.filter(a=>a.z>=0).sort((a,b)=>a.z-b.z).forEach(layer);g.restore();
}
