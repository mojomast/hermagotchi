import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {execFileSync} from 'node:child_process';
const json=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const cast=json('cast.json'),beats=json('BEATS.json'),manifest=json('assets/manifest.json'),copy=json('copy.json');
assert.equal(new Set(cast.map(p=>p.species)).size,10);
assert.ok(new Set(cast.map(p=>p.palette)).size>=6);
const cosmetics=new Set(cast.flatMap(p=>p.items));assert.ok(cosmetics.size>=20);
assert.equal(Object.keys(copy.npcs).length,4);
assert.equal(beats.length,8);assert.equal(beats[0].start,0);assert.equal(beats.at(-1).end,92);
beats.forEach((s,i)=>{assert.ok(s.end>s.start);if(i)assert.equal(s.start,beats[i-1].end);assert.ok(fs.existsSync(`scenes/${s.id}.js`));});
for(const pet of cast){
  const species=manifest.species[pet.species];assert.ok(species);
  for(const state of manifest.animations.states){const c=manifest.animations.clips.find(c=>c.id===`${pet.species}.${pet.palette}.${state}`);assert.ok(c);assert.ok(fs.existsSync('assets/'+c.path));}
  for(const id of pet.items){const item=manifest.assets.find(a=>a.id===id);assert.ok(item);assert.ok((species.overrides||{})[item.anchor]||manifest.rigs[species.rig].anchors[item.anchor]);assert.ok(fs.existsSync('assets/'+item.path));}
}
const expected=['SHOT_PANE_HOME.png','CLIP_SHOP_GRID.mp4','CLIP_BATTLE_LIVE.mp4','SHOT_BATTLE_RESULT.png','SHOT_LEADERBOARD.png','SHOT_CHAT.png','VO_MAIN.wav','MUSIC_BED.wav','TEXT_CTA.json'];
for(const f of expected)assert.ok(fs.statSync('slots/'+f).size>0);
assert.ok(copy.items['hat.binary_crown'].price===2000);
const previews=fs.readdirSync('previews');
assert.ok(previews.includes('hermagotchi-draft-720p.mp4'),'Render the draft first');
assert.equal(previews.filter(f=>f.endsWith('.png')).length,8);
const bytes=previews.reduce((n,f)=>n+fs.statSync(path.join('previews',f)).size,0);assert.ok(bytes<40_000_000);
const probe=JSON.parse(execFileSync('ffprobe',['-v','error','-show_streams','-show_format','-of','json','previews/hermagotchi-draft-720p.mp4'],{encoding:'utf8'}));
const video=probe.streams.find(s=>s.codec_type==='video');assert.equal(video.width,1280);assert.equal(video.height,720);assert.equal(video.r_frame_rate,'60/1');assert.equal(Number(video.nb_frames),5520);assert.equal(Number(video.duration),92);
// AAC packet padding can extend the container by less than one video frame.
assert.ok(Math.abs(Number(probe.format.duration)-92)<1/60);
assert.ok(probe.streams.some(s=>s.codec_type==='audio'));
console.log(`PASS: 10 species, ${new Set(cast.map(p=>p.palette)).size} palettes, ${cosmetics.size} cosmetics, 4 NPCs, 9 slots, 8 scenes, 5520 frames; previews ${(bytes/1e6).toFixed(2)} MB.`);
