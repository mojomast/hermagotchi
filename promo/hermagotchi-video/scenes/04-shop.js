import {stripeBG,box,text,chrome,npc,lines,star,slot,ticker,cream,ink,yellow,ease,image,holdPan} from '../shared/draw.js';
import {pet} from '../shared/pets.js';
export function draw(g,t,e){
  const c=e.copy.shop;stripeBG(g,'#492451','#5b2d62',t);
  chrome(g,c.title,133,202,71);chrome(g,c.title2,640,235,112);
  text(g,c.kicker,137,288,39,yellow,'BroadcastMono');
  star(g,1230,213,100,yellow,Math.sin(t)*.08);
  text(g,e.copy.items['hat.binary_crown'].price,1230,214,57,ink,'Broadcast','center');text(g,c.priceUnit,1230,254,33,ink,'BroadcastMono','center');
  npc(g,e,'don_piedro',133,353,256);
  text(g,c.host,134,651,34,yellow,'BroadcastMono');
  lines(g,e.copy.npcs.don_piedro.quote,134,703,340,35);
  text(g,c.priceNote,1660,359,25,cream,'BroadcastMono','right');
  if(t<12){
    const group=t<8?[0,1,2,3,4,5]:[6,7,8,9];const local=t<8?t:t-8;
    group.forEach((index,j)=>{
      const x=540+(j%3)*403,y=325+Math.floor(j/3)*266;
      box(g,x+7,y+18,352,249,j%2?'#6c3869':'#633a69');
      const count=Math.max(0,Math.min(3,Math.floor((local-.5)*2.5)));
      pet(g,e,index,x+46,y-4,256,local,{state:'happy',itemCount:count});
      text(g,e.copy.pets[e.cast[index].species],x+180,y+251,30,yellow,'BroadcastMono','center');
      if(count<3){
        const item=e.items[e.cast[index].items[count]];
        const fly=ease((local-.5-count*.4)/.4);const ix=x+300-(fly*120),iy=y+70+fly*35;
        star(g,ix,iy,60,yellow,local*3);
        g.save();g.translate(ix,iy);g.rotate((1-fly)*Math.PI*2);image(g,e.images['assets/'+item.path],-64,-64,128,128);g.restore();
      }
    });
  }else{
    box(g,506,350,594,446,'#ecd6ad');box(g,802,350,5,446,'#722955');
    text(g,c.before,660,398,43,ink,'Broadcast','center');text(g,c.after,953,398,43,ink,'Broadcast','center');
    pet(g,e,0,526,440,256,t,{state:'happy',items:false});pet(g,e,0,815,440,256,t,{state:'happy'});
    text(g,c.loadout,803,772,29,ink,'BroadcastMono','center');
    // Film 42–46 / source 12–16s: hold Don Piedro+wallet, pan to mythic price row.
    const shopCrop=holdPan(t-12,[
      [{sx:0.00,sy:0.12,sw:0.55,sh:0.31},1.5],
      [{sx:0.00,sy:0.18,sw:0.62,sh:0.349},0.8],
      [{sx:0.00,sy:0.55,sw:0.68,sh:0.383},1.5]
    ],0.9);
    slot(g,e,'CLIP_SHOP_GRID',1150,423,600,338,shopCrop);
  }
  box(g,115,870,1680,93,yellow);text(g,c.call,955,939,63,ink,'Broadcast','center');ticker(g,c.ticker,t);
}
