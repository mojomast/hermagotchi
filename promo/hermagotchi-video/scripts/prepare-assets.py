"""One-time, read-only source import. No writes to the source checkout."""
from pathlib import Path
import json, shutil, subprocess, hashlib, re
from PIL import Image, ImageDraw, ImageFont

root = Path(__file__).resolve().parents[1]
src = root.parent / 'hermagotchi-src'
cast = json.loads((root/'cast.json').read_text())
manifest = json.loads((src/'assets/manifest.json').read_text())
npcs = json.loads((src/'assets/npc_lines.json').read_text())['npcs']
records = []

def copy(source, dest=None):
    dest = dest or source
    target = root/dest
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src/source, target)
    records.append((source, dest, hashlib.sha256(target.read_bytes()).hexdigest()))

used = {i for pet in cast for i in pet['items']}
manifest['assets'] = [a for a in manifest['assets'] if a['id'] in used]
manifest['animations']['clips'] = [c for c in manifest['animations']['clips'] if any(c['species']==p['species'] and c['palette']==p['palette'] for p in cast)]
for c in manifest['animations']['clips']:
    copy('assets/'+c['path'])
for a in manifest['assets']: copy('assets/'+a['path'])
for n in ['don_piedro','nous_girl','teknium','southpaw']:
    copy(f'assets/px3/npcs/{n}_portrait.png')
copy('assets/ui/wordmark.png')
copy('LICENSE','assets/SOURCE_LICENSE')
(root/'assets/manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')

copy_data = {
 'station': {'bug':'H-TV', 'osd':'PLAY', 'rec':'REC', 'tape':'SP', 'timePrefix':'02:', 'channelPrefix':'CH', 'station':'HERMAGOTCHI TELEVISION', 'subtitle':'YOUR AGENT. YOUR PET. YOUR VERY LATE NIGHT.', 'signOn':'TRANSMISSION BEGINS', 'signOff':'END OF BROADCAST', 'draft':'HACKATHON SUBMISSION / ASSET-ANIMATED DRAFT'},
 'forecast': {'title':'PET FORECAST', 'kicker':'10 SPECIES. STRONG PERSONALITIES.', 'lower':'A NEW COMPANION IS MOVING IN.', 'note':'ILLUSTRATED FORECAST · NOT A GAME MAP', 'regions':['CACHE COAST','STACK VALLEY','KERNEL COUNTY','NULL ISLAND'], 'fronts':['HAPPY FRONT','SNACK WATCH','SLEEP SYSTEM','ATTACK WARNING','COOL BREEZE','HIGH SPIRITS','NIGHT OWL','SLOW DRIZZLE','WARM WELCOME','PURPLE HAZE']},
 'home': {'title':'LIFE WITH YOUR PET', 'subtitle':'A COMPANION FOR YOUR AGENT\'S WORK.', 'states':['HAPPY','EAT','SLEEP'], 'readouts':['MOOD / HAPPY','CARE / FEED','ENERGY / REST'], 'stats':['XP · {{FROM CAPTURE}}','BITS · {{FROM CAPTURE}}'], 'label':'HOME MOVIES / HABITAT PANE', 'date':'NOV. 06 1996', 'battery':'BATTERY ▰▰▰'},
 'shop': {'title':"DON PIEDRO'S", 'title2':'DRIP SHOP', 'kicker':'81 COSMETICS. ZERO BORING OUTFITS.', 'call':'CALL NOW!  OPEN THE SHOP TAB.', 'before':'BEFORE','after':'AFTER', 'loadout':'MANIFEST-FITTED MAKEOVER', 'priceUnit':'BITS', 'priceNote':'CATALOG PRICE / BINARY CROWN', 'ticker':'HATS  •  FACE  •  BACK  •  FRONT  •  AURAS  •  EMOTES  •  HABITATS  •  TITLES', 'host':'DON PIEDRO / SHOPKEEPER'},
 'arena': {'title':'ARENA FIGHT NIGHT','kicker':'THE TALE OF THE TAPE','versus':'VS','round':'EXHIBITION / ANIMATED SEQUENCE','replay':'INSTANT REPLAY / ¼ SPEED','telestrator':'WATCH THE COUNTER!','ko':'K.O.','koNote':'ILLUSTRATED FINISH / REPLACE WITH RESULT','hp':'HP / ILLUSTRATION','ticker':'DETERMINISTIC BATTLES  •  REPLAYS  •  TACTICS  •  PRACTICE DOES NOT CHANGE RATING','status':'MULTIPLAYER SUPPORT / HOSTING OPEN','host':'SOUTHPAW / RINGSIDE'},
 'lobby': {'title':'AFTER HOURS','subtitle':'PUBLIC ACCESS / LOBBY LINE','caller':'CALLER CAPTIONS / AWAITING REAL CHAT','standings':'TONIGHT\'S STANDINGS','ticker':'LEADERBOARD + RATINGS  •  AWAITING VERIFIED CAPTURE  •  CHAT IS OPT-IN','tip':'TEKNIUM / PRACTICE TIP','host':'NOUS GIRL / YOUR HOST','rows':['01  {{PLAYER}}  {{RATING}}','02  {{PLAYER}}  {{RATING}}','03  {{PLAYER}}  {{RATING}}']},
 'how': {'title':'HOW IT WORKS','subtitle':'AN EDUCATIONAL FILM FOR NIGHT OWLS','nodes':['HERMES','PLUGIN PANE','GAME API','OTHER PLAYERS'], 'captions':['8 COMPOSABLE TOOLS','CARE / EQUIP / CHALLENGE','SHARED GAME STATE','OPT-IN MULTIPLAYER'], 'footer':'LOCAL-FIRST. NETWORK OFF BY DEFAULT.', 'plate':'FIG. 01 / THE COMPANION CIRCUIT'},
 'outro': {'anthem':'PLEASE STAND BY YOUR PET.', 'footer':'BUILT FOR THE HERMES HACKATHON', 'end':'GOOD NIGHT. KEEP GROWING.'},
 'slots': {s:{'label':s,'detail':d} for s,d in [('SHOT_PANE_HOME','REAL HABITAT PANE / AWAITING CAPTURE'),('CLIP_SHOP_GRID','BUY + EQUIP / AWAITING CAPTURE'),('CLIP_BATTLE_LIVE','ACTUAL BATTLE / AWAITING CAPTURE'),('SHOT_BATTLE_RESULT','RESULT + MATCH TYPE / AWAITING CAPTURE'),('SHOT_LEADERBOARD','VERIFIED STANDINGS / AWAITING CAPTURE'),('SHOT_CHAT','OPT-IN CHAT / AWAITING CAPTURE')]},
 'npcs': {}, 'pets': {p['species']:p['species'].upper() for p in cast}, 'items': {}
}
contexts={'don_piedro':('shop.greet',0),'nous_girl':('lobby.welcome',3),'teknium':('practice.tip',3),'southpaw':('leaderboard.announce',4)}
for n,(ct,i) in contexts.items(): copy_data['npcs'][n]={'name':npcs['npc.'+n]['name'],'quote':npcs['npc.'+n]['contexts'][ct][i]['text'],'context':ct,'index':i}
# Prices are source catalog values, never fabricated sales figures.
sql='\n'.join(p.read_text() for p in sorted((src/'server/app/migrations').glob('*.sql')))
for a in manifest['assets']:
    match=re.search(r"\('"+re.escape(a['id'])+r"',\s*'([^']+)',\s*'[^']+',\s*'[^']+',\s*(\d+)",sql)
    copy_data['items'][a['id']]={'name':match[1] if match else a['id'].split('.')[1].replace('_',' ').title(),'price':int(match[2]) if match else None}
(root/'copy.json').write_text(json.dumps(copy_data,indent=2)+'\n')

# Generated dummy cards are clearly production slates, never product UI.
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf',42)
small=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',24)
for slot,v in copy_data['slots'].items():
    im=Image.new('RGB',(1280,720),'#211e32'); d=ImageDraw.Draw(im)
    colors=['#cabdb0','#d9b540','#3bbab0','#47a753','#b35a9f','#c65851','#486cb2']
    for i,c in enumerate(colors):d.rectangle((i*1280//7,0,(i+1)*1280//7,80),fill=c)
    d.rectangle((40,116,1240,680),outline='#c3b49e',width=3)
    d.text((640,315),slot,font=font,fill='#fff3cf',anchor='mm')
    d.text((640,385),v['detail'],font=small,fill='#e2ceb1',anchor='mm')
    if slot.startswith('SHOT'):
        im.save(root/'slots'/f'{slot}.png')
    else:
        temp=root/'slots'/f'{slot}.png'; im.save(temp)
        length=16 if slot=='CLIP_SHOP_GRID' else 18
        subprocess.run(['ffmpeg','-v','error','-loop','1','-i',str(temp),'-t',str(length),'-r','60','-c:v','libx264','-pix_fmt','yuv420p','-crf','30','-y',str(root/'slots'/f'{slot}.mp4')],check=True)
        temp.unlink()
import wave
for name,seconds in [('VO_MAIN',88),('MUSIC_BED',92)]:
    with wave.open(str(root/'slots'/f'{name}.wav'),'wb') as w:
        w.setnchannels(1);w.setsampwidth(2);w.setframerate(8000);w.writeframes(bytes(seconds*16000))
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=src,text=True).strip()
ledger=f'# Assets used\n\nRead-only source: `mojomast/hermagotchi`, branch `feat/hackathon`, commit `{sha}`.\n\nOnly the source files listed below are copied. PNGs are existing project art, not generated for this video. The manifest is reduced to used clips/items; quotes are copied verbatim into `copy.json`.\n\n| Source path | Video path | SHA-256 |\n|---|---|---|\n'
for s,d,h in records: ledger+=f'| `{s}` | `{d}` | `{h}` |\n'
ledger+='\n## Data sources\n\n- `assets/manifest.json`: rig/species anchors, item offsets, z-order, scale, animation deltas.\n- `assets/npc_lines.json`: four verbatim lines; context and index stored in `copy.json`.\n- `server/app/migrations/0004_shop.sql` and `0008_cosmetics_pack.sql`: displayed item names and Bits prices.\n- `README.md`, `docs/DEMO.md`, `docs/DESKTOP_UI.md`: feature claims and deployment status.\n\n## Derived / original code artwork\n\n- Three-frame strips are padded to four frames by holding frame 3 at build time (original copied PNGs remain unchanged). All pets are drawn at integer multiples of the native 32px grid. Cosmetic layer size and position follow the manifest, rounded to native-grid pixels before integer upscaling.\n- Dummy slates, abstract weather map, broadcast typography, diagrams, CRT/VHS shaders and sound effects are drawn/synthesized in code. No generated image service is used.\n- Bundled broadcast fonts and licenses are documented below.\n'
(root/'ASSETS_USED.md').write_text(ledger)
(root/'SOURCE.json').write_text(json.dumps({'repository':'mojomast/hermagotchi','branch':'feat/hackathon','commit':sha},indent=2)+'\n')
print(f'Imported {len(records)} assets, {len(used)} cosmetics, {len(cast)} species.')
