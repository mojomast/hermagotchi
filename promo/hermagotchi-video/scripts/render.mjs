import {execFileSync} from 'node:child_process';
import fs from 'node:fs';
const cli='node_modules/.bin/hyperframes';
// HyperFrames 0.9.19 accepts integer render-resolution scaling only. Capture the
// authored 1080p/60 master outside Git, then make the size-budgeted 720p handoff.
execFileSync(cli,['render','.build','--fps','60','--quality','draft','--workers','2','--output','out/hermagotchi-master.mp4'],{stdio:'inherit'});
execFileSync('ffmpeg',['-v','error','-threads','2','-i','out/hermagotchi-master.mp4','-vf','scale=1280:720:flags=lanczos','-c:v','libx264','-preset','medium','-b:v','2300k','-maxrate','2600k','-bufsize','5200k','-pix_fmt','yuv420p','-c:a','aac','-b:a','96k','-movflags','+faststart','-y','previews/hermagotchi-draft-720p.mp4'],{stdio:'inherit'});
const bytes=fs.statSync('previews/hermagotchi-draft-720p.mp4').size;
if(bytes>=36_000_000)throw new Error('Draft exceeds the video budget; reserve space for the scene PNGs.');
console.log(`720p/60 draft: ${(bytes/1e6).toFixed(2)} MB`);
