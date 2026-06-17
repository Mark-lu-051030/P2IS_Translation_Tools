import fs from 'fs';
import * as lzss from './lib/lzss.mjs';
import * as rle from './lib/rle.mjs';
const SECTOR=0x930,BO=24,BS=2048;
const ISO='../Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin';
const fd=fs.openSync(ISO,'r');
function rs(lba,n){const o=Buffer.alloc(n),s=Buffer.alloc(SECTOR);let off=0,sec=lba*SECTOR;while(off<n){fs.readSync(fd,s,0,SECTOR,sec);const c=Math.min(BS,n-off);s.copy(o,off,BO,BO+c);off+=c;sec+=SECTOR;}return o;}
const fp=rs(0x17,0x12000);
const vram=fs.readFileSync('vram_edit/pos.bin');
// 正确名字指纹: byte-x 1936-1964, 名字行 y335-348
const needles=[];
for(const y of [336,338,340,342,344,346]){
  const seg=vram.subarray(y*2048+1936, y*2048+1964);
  let nz=0;for(const b of seg)if(b)nz++;
  if(nz>6) needles.push(Buffer.from(seg));
}
console.log('名字指纹数:',needles.length);
const hits=[];
for(let fid=1;fid<1144;fid++){
  const blk=fp.readUInt32LE(fid*8),sz=fp.readUInt32LE(fid*8+4);
  if(!blk||!sz||sz>0x200000)continue;
  let d;try{d=rs(blk,sz);}catch(e){continue;}
  // 12字节头 walk
  let ptr=0,idx=0;
  while(ptr+12<=d.length){
    if(d[ptr]===0){ptr=(ptr+0x800)&~0x7ff;if(ptr>=d.length)break;continue;}
    const st=d[ptr+1],tc=d.readUInt32LE(ptr+4),uc=d.readUInt32LE(ptr+8);
    if(tc<12||ptr+tc>sz)break;
    let dec=null;
    try{
      if(st===2)dec=lzss.decompress(d.subarray(ptr),12,tc-12,uc);
      else if(st===1)dec=rle.decompress(d.subarray(ptr),12,tc-12,uc);
      else dec=d.subarray(ptr+12,ptr+tc);
    }catch(e){}
    if(dec&&dec.length<5000000){
      for(let ni=0;ni<needles.length;ni++) if(dec.indexOf(needles[ni])>=0){hits.push([fid,idx,st,ni,dec.length]);break;}
    }
    idx++;ptr+=tc;while(ptr&3)ptr++;
  }
}
console.log('命中:',hits.length);
for(const[fid,idx,st,ni,dl]of hits)console.log(`  file${fid} sub${idx} st=${st} decoded=${dl} 名字指纹#${ni}`);
fs.closeSync(fd);
