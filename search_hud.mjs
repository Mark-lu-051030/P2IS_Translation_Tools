import fs from 'fs';
import * as lzss from './lib/lzss.mjs';
import * as rle from './lib/rle.mjs';
const SECTOR=0x930,BO=24,BS=2048;
const ISO='../Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin';
const fd=fs.openSync(ISO,'r');
function rs(lba,n){const o=Buffer.alloc(n),s=Buffer.alloc(SECTOR);let off=0,sec=lba*SECTOR;while(off<n){fs.readSync(fd,s,0,SECTOR,sec);const c=Math.min(BS,n-off);s.copy(o,off,BO,BO+c);off+=c;sec+=SECTOR;}return o;}
const fp=rs(0x17,0x12000);
// 从 pos.bin 抽指纹(名字区多行)
const vram=fs.readFileSync('vram_edit/pos.bin');
const needles=[];
for(const y of [300,306,312,318,342,348]){
  const seg=vram.subarray(y*2048+1872, y*2048+1900);
  let nz=0;for(const b of seg) if(b)nz++;
  if(nz>15) needles.push(Buffer.from(seg));
}
console.log('指纹数:',needles.length);
function contains(hay,nd){return hay.indexOf(nd)>=0;}
const hits=[];
for(let fid=1;fid<1144;fid++){
  const blk=fp.readUInt32LE(fid*8),sz=fp.readUInt32LE(fid*8+4);
  if(!blk||!sz||sz>0x200000)continue;
  let d;try{d=rs(blk,sz);}catch(e){continue;}
  let ptr=0,idx=0;
  while(ptr+16<=d.length){
    if(d[ptr]===0){ptr=(ptr+0x800)&~0x7ff; if(ptr>=d.length)break; continue;}
    const tc=d.readUInt32LE(ptr+4),st=d[ptr+1],uc=d.readUInt32LE(ptr+8);
    if(tc<16||ptr+tc>sz)break;
    let dec=null;
    try{
      if(st===1) dec=rle.decompress(d.subarray(ptr),16,tc-16, 1<<24);
      else if(st===2) dec=lzss.decompress(d.subarray(ptr),16,tc-16, 1<<24);
      else dec=d.subarray(ptr+16,ptr+tc);
    }catch(e){}
    if(dec){
      for(let ni=0;ni<needles.length;ni++) if(contains(dec,needles[ni])){hits.push([fid,idx,st,ni,dec.length]);break;}
    }
    idx++;ptr+=tc;while(ptr&3)ptr++;
  }
}
console.log('命中:',hits.length);
for(const[fid,idx,st,ni,dl]of hits)console.log(`  file${fid} sub${idx} st=${st} decoded=${dl} 指纹#${ni}`);
fs.closeSync(fd);
