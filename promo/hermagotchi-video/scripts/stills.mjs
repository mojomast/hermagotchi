import fs from 'node:fs';
import {execFileSync} from 'node:child_process';
const beats=JSON.parse(fs.readFileSync('BEATS.json','utf8'));
for(const scene of beats){
  execFileSync('ffmpeg',['-v','error','-ss',String(scene.keyframe),'-i','previews/hermagotchi-draft-720p.mp4','-frames:v','1','-y',`previews/${scene.id}.png`],{stdio:'inherit'});
}
console.log('Extracted eight scene PNGs from the delivered draft.');
