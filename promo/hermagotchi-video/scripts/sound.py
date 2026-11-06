"""Original synthetic station tones, tape cuts and short musical idents."""
from pathlib import Path
import math, wave, array, json, random
root=Path(__file__).resolve().parents[1]
rate=22050;length=92;track=[0.]*(rate*length);rng=random.Random(1996)
def tone(start,duration,freq,amp=.12,decay=5):
    for i in range(int(duration*rate)):
        t=i/rate;env=min(1,t/.008)*min(1,(duration-t)/.025)*math.exp(-decay*t)
        val=math.sin(2*math.pi*freq*t)+.23*math.sin(2*math.pi*freq*2*t)
        n=int(start*rate)+i
        if n<len(track):track[n]+=val*amp*env
tone(0,1.65,1000,.07,0)
for start in [2.35,6,18,30,46,64,76,85]:
    for i in range(int(.19*rate)):
        t=i/rate;track[int(start*rate)+i]+=(rng.random()*2-1)*.11*(1-t/.19)
    for i,f in enumerate([261.63,329.63,392,523.25]):tone(start+.22+i*.11,.4,f,.085,5)
for start in [31,32,33,35,38,39,40,42]:tone(start,.16,880,.07,15)
for start in [50,55,61]:
    for f in [590,845,1190]:tone(start,1.2,f,.10,4)
for i,f in enumerate([392,523.25,659.25,783.99,659.25,523.25,392]):tone(85.35+i*.4,.65,f,.09,3)
tone(90.4,.55,1000,.055,0);tone(91.05,.65,220,.08,8)
samples=array.array('h',[round(max(-.95,min(.95,v))*32767) for v in track])
with wave.open(str(root/'assets/broadcast.wav'),'wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(samples.tobytes())
