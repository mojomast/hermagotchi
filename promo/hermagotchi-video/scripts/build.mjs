import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {execFileSync} from 'node:child_process';
import {build as bundle} from 'esbuild';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
process.chdir(root);
const read=file=>JSON.parse(fs.readFileSync(file,'utf8'));
const beats=read('BEATS.json'), settings=read('settings.json');
fs.mkdirSync('.build/compositions',{recursive:true});
fs.cpSync('assets','.build/assets',{recursive:true});
execFileSync('python3',['scripts/runtime-assets.py'],{stdio:'inherit'});
fs.copyFileSync('style.css','.build/style.css');
fs.copyFileSync('hyperframes.json','.build/hyperframes.json');
const slots={SHOT_PANE_HOME:[2,'png'],CLIP_SHOP_GRID:[3,'mp4'],CLIP_BATTLE_LIVE:[4,'mp4'],SHOT_BATTLE_RESULT:[4,'png'],SHOT_LEADERBOARD:[5,'png'],SHOT_CHAT:[5,'png']};
const config={};
fs.mkdirSync('.build/assets/slots',{recursive:true});
for(const [id,[scene,ext]] of Object.entries(slots)){
  const src=`slots/${id}.${ext}`;
  if(!fs.existsSync(src))throw new Error(`Missing required slot: ${src}`);
  if(ext==='png'){
    const dest=`assets/slots/${id}.png`;fs.copyFileSync(src,`.build/${dest}`);config[id]={scene,kind:'image',path:dest,frames:1};
  }else{
    const dest=`assets/slot-frames/${id}`,dir=`.build/${dest}`;
    const stat=fs.statSync(src),stamp=`${stat.size}:${stat.mtimeMs}`;
    const marker=`${dir}/.stamp`;
    if(!fs.existsSync(marker)||fs.readFileSync(marker,'utf8')!==stamp){
      fs.rmSync(dir,{recursive:true,force:true});fs.mkdirSync(dir,{recursive:true});
      execFileSync('ffmpeg',['-v','error','-i',src,'-t',String(beats[scene].end-beats[scene].start),'-vf','fps=60,scale=1280:720:force_original_aspect_ratio=decrease','-q:v','3',`${dir}/%05d.jpg`],{stdio:'inherit'});
      fs.writeFileSync(marker,stamp);
    }
    const frames=fs.readdirSync(dir).filter(p=>p.endsWith('.jpg')).length;
    if(!frames)throw new Error(`${id} has no decodable frames`);
    config[id]={scene,kind:'video-frames',path:dest,frames};
  }
}
fs.writeFileSync('.build/slot-config.json',JSON.stringify(config));
await bundle({entryPoints:['shared/runtime.js'],bundle:true,format:'iife',globalName:'Hermagotchi',outfile:'.build/runtime.js',target:'chrome120'});
const hosts=beats.map((s,index)=>{
  const id=`scene-${index+1}`;const duration=s.end-s.start;
  fs.writeFileSync(`.build/compositions/${s.id}.html`,`<template>\n<section id="${id}" class="broadcast-scene" data-composition-id="${id}" data-duration="${duration}" data-width="1920" data-height="1080" data-no-timeline><canvas class="broadcast-screen" width="1920" height="1080" aria-label="${s.id}" data-layout-ignore></canvas></section>\n<script>Hermagotchi.mount('${id}', ${index});</script>\n</template>\n`);
  return `<div id="host-${index+1}" class="scene-host clip" data-composition-id="${id}" data-no-timeline data-composition-src="compositions/${s.id}.html" data-start="${s.start}" data-duration="${duration}" data-track-index="1" data-track-kind="graphics"></div>`;
}).join('\n    ');
const audio=[['VO_MAIN',2,88,settings.voiceGain],['MUSIC_BED',0,92,settings.musicGain]];
const audioTags=audio.map(([id,start,duration,gain])=>{fs.copyFileSync(`slots/${id}.wav`,`.build/assets/slots/${id}.wav`);return `<audio id="${id}" class="clip" data-start="${start}" data-duration="${duration}" data-track-index="${id==='VO_MAIN'?2:3}" data-volume="${gain}" src="assets/slots/${id}.wav"></audio>`;});
if(!fs.existsSync('assets/broadcast.wav'))execFileSync('python3',['scripts/sound.py'],{stdio:'inherit'});
fs.copyFileSync('assets/broadcast.wav','.build/assets/broadcast.wav');
audioTags.push(`<audio id="broadcast-sound" class="clip" data-start="0" data-duration="92" data-track-index="4" data-volume="${settings.broadcastGain}" src="assets/broadcast.wav"></audio>`);
fs.writeFileSync('.build/index.html',fs.readFileSync('index.html','utf8').replace('<!-- SCENES -->',hosts).replace('<!-- AUDIO -->',audioTags.join('\n    ')));
fs.mkdirSync('out',{recursive:true});fs.mkdirSync('previews',{recursive:true});
console.log('Built 8 broadcast channels / 92 seconds / 60 fps; slots decoded deterministically.');
