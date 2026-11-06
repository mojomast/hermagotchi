from pathlib import Path
from PIL import Image
import json
root=Path(__file__).resolve().parents[1]
p=root/'.build/assets'
m=json.loads((root/'assets/manifest.json').read_text())
for clip in m['animations']['clips']:
    path=p/clip['path'];im=Image.open(path).convert('RGBA')
    n=im.width//512;native=im.resize((n*32,32),Image.Resampling.NEAREST)
    out=Image.new('RGBA',(128,32))
    for i in range(4):out.paste(native.crop((min(i,n-1)*32,0,(min(i,n-1)+1)*32,32)),(i*32,0))
    out.save(path)
for item in m['assets']:
    path=p/item['path'];im=Image.open(path);im.resize((32,32),Image.Resampling.NEAREST).save(path)
for path in (p/'px3/npcs').glob('*.png'):
    im=Image.open(path);im.resize((64,64),Image.Resampling.NEAREST).save(path)
