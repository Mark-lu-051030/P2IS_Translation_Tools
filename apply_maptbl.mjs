// 翻译地图文件(97-136) sub0 header 的区域名: 用 strtbl 138_0_7 区域索引的现成译文
import * as fs from "fs/promises";
import * as fss from "fs";
import * as archive from "./lib/archive.mjs";
import * as lzss from "./lib/lzss.mjs";
import * as cdimage from "./lib/cdimage.mjs";
import { spawn } from "child_process";
const SECTOR=0x930,BO=24,BS=2048;
const BACKUP="/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";
const FIX_ECC="/home/mark/Code/RomHacking/P2IS_Translation_Tools/fix_ecc.py";
const og=JSON.parse(fss.readFileSync("codetable_og.json","utf8"));
const ct=JSON.parse(fss.readFileSync("codetable.json","utf8"));
const ogChar={};for(const[k,v]of Object.entries(og))if(typeof v==='string'&&v.length===1)ogChar[k]=v;
const ogRev={};for(const[k,v]of Object.entries(og))if(typeof v==='string'&&v.length===1)ogRev[v]=parseInt(k);
const rev={};for(const[k,v]of Object.entries(ct))if(typeof v==='string'&&v.length===1)rev[v]=parseInt(k);
const FW=rev['　']??rev[' '];
// lookup: og area name → CN
// 优先用人工审定表 map_names_zh.json（正经译法，对齐对话正文）；
// 其余回落到 strtbl 138_0_7 的现成译文。审定表覆盖 138（138 多是逐字死译，如 驻轮场）。
const at=JSON.parse(fss.readFileSync("all_translatable.json","utf8"));
const lut={};
for(const e of at){if((e.id||'').startsWith('strtbl:138_0_7')){const p=e.pages?.[0];if(!p)continue;const jp=(p.jp||'').replace(/\n/g,'').replace(/^[0-9A-F]+\s+/,'').trim();const zh=(p.zh||'').replace(/\n/g,'').replace(/^[0-9A-F]+\s+/,'').trim();if(jp&&zh)lut[jp]=zh;}}
let curated=0;
if(fss.existsSync("map_names_zh.json")){
  const mn=JSON.parse(fss.readFileSync("map_names_zh.json","utf8"));
  for(const[jp,cn]of Object.entries(mn)){if(jp.startsWith('_')||!cn)continue;lut[jp]=cn;curated++;}
}
console.log(`lookup 区域名 ${Object.keys(lut).length} 条（审定表 ${curated} 条覆盖）`);

// room lut: 日房间名 → 中房间名。主译法来自 strtbl 138_0_5（剥掉区域名前缀），
// room_names_zh.json 覆盖个别（超长改短/更地道）。区域名按长度降序，避免短区域名误匹配长的。
const cleanSym=s=>(s||'').replace(/\n/g,'').replace(/^[◎▲★◆●○\s　]+/,'').trim();
const areaPairs=Object.entries(lut).sort((a,b)=>b[0].length-a[0].length);
const roomLut={};
for(const e of at){if(!(e.id||'').startsWith('strtbl:138_0_5'))continue;const p=e.pages?.[0];if(!p)continue;
  const jp=cleanSym(p.jp),zh=cleanSym(p.zh);if(!jp||!zh)continue;
  for(const[aj,az]of areaPairs){if(jp.startsWith(aj)&&zh.startsWith(az)){
    const rj=jp.slice(aj.length).replace(/^[\s　]+/,'').trim();
    const rz=zh.slice(az.length).replace(/^[\s　]+/,'').trim();
    if(rj&&rz&&!/[<>]/.test(rj)&&!/[<>]/.test(rz))roomLut[rj]=rz;break;}}}
let roomCurated=0;
if(fss.existsSync("room_names_zh.json")){
  const rn=JSON.parse(fss.readFileSync("room_names_zh.json","utf8"));
  for(const[jp,cn]of Object.entries(rn)){if(jp.startsWith('_')||!cn)continue;roomLut[jp]=cn;roomCurated++;}
}
// 预编译可用房间名：日码可编码 + 中码可编码 + 中码数≤日码数（原位等长，短的用{1000}补）。
// 长名优先匹配（避免长名被其短前缀先替换）。
const roomCands=[];
for(const[rj,rz]of Object.entries(roomLut)){
  const jc=[...rj].map(c=>ogRev[c]);if(jc.some(x=>x===undefined))continue;
  const zc=[...rz].map(c=>rev[c]);if(zc.some(x=>x===undefined))continue;
  if(zc.length>jc.length)continue;  // 超长跳过（应由 room_names_zh.json 覆盖修短）
  roomCands.push({rj,rz,jc,zc});
}
roomCands.sort((a,b)=>b.jc.length-a.jc.length);
console.log(`lookup 房间名 ${Object.keys(roomLut).length} 条（覆盖 ${roomCurated}）→ 可用 ${roomCands.length} 条`);

async function rblk(fp,fb,fsz){const s=Buffer.alloc(SECTOR),o=Buffer.allocUnsafe(fsz);let off=0,sec=fb*SECTOR;while(off<fsz){await fp.read(s,0,SECTOR,sec);const c=Math.min(BS,fsz-off);s.copy(o,off,BO,BO+c);off+=c;sec+=SECTOR;}return o;}
const bfp=await fs.open(BACKUP,"r");const fpd=await rblk(bfp,0x17,0x1b88);
const cd=await cdimage.init();
const run=(a)=>new Promise((res,rej)=>{const p=spawn("python3",[FIX_ECC,...a],{stdio:"ignore"});p.on("exit",c=>c===0?res():rej(new Error("ecc")));});
let done=0,miss=[],toolong=[],nofit=[],rtfail=[],roomHits=0,roomMaps=0;
for(let id=97;id<=136;id++){
  const fb=fpd.readUInt32LE(id*8),fsz=fpd.readUInt32LE(id*8+4);if(!fsz)continue;
  const arch=await rblk(bfp,fb,fsz);const files=archive.extract_files(arch);const sub=files[0];if(!sub)continue;
  const tc=sub.readUInt32LE(4),uc=sub.readUInt32LE(8);let d;try{d=lzss.decompress(sub,12,tc-12,uc);}catch{continue;}if(!d)continue;
  let changed=false;
  // ── 区域名（sub0 开头那串 og 码 = 左上角第一行）──
  let N=0,name='';for(let p=0;p+1<d.length;p+=2){const c=d.readUInt16LE(p);if(c>=0x1000||c===0)break;const ch=ogChar[String(c)];if(!ch)break;name+=ch;N++;}
  if(N>=2){
    const cn=lut[name];
    if(!cn) miss.push(`${id}:${name}`);
    else{
      const codes=[];let bad=false;for(const ch of cn){if(!(ch in rev)){bad=true;break;}codes.push(rev[ch]);}
      if(bad) toolong.push(`${id}:${cn}(缺字)`);
      else if(codes.length>N) toolong.push(`${id}:${name}→${cn}(${codes.length}>${N})`);
      else{ while(codes.length<N)codes.push(FW); for(let i=0;i<N;i++)d.writeUInt16LE(codes[i],i*2); changed=true; }
    }
  }
  // ── 房间名（名表固定宽记录 = 左上角第二行）──
  // 边界：名字前一码∈{0(∅),1(」) 记录标志}，后一码≥0x1000({1000}填充=名字结束)。
  // 原位等长替换：写中文码 + 用{1000}补齐到原日文码数（短名留原表填充约定）。
  const nU=Math.floor(d.length/2);let rHit=0;
  for(const{jc,zc}of roomCands){
    for(let pos=0;pos+jc.length<=nU;pos++){
      let hit=true;for(let k=0;k<jc.length;k++)if(d.readUInt16LE((pos+k)*2)!==jc[k]){hit=false;break;}
      if(!hit)continue;
      const prev=pos>0?d.readUInt16LE((pos-1)*2):0;
      const next=(pos+jc.length<nU)?d.readUInt16LE((pos+jc.length)*2):0;
      if(!((prev===0||prev===1)&&next>=0x1000))continue;  // 边界校验，防误伤瓦片数据
      for(let k=0;k<zc.length;k++)d.writeUInt16LE(zc[k],(pos+k)*2);
      for(let k=zc.length;k<jc.length;k++)d.writeUInt16LE(0x1000,(pos+k)*2);
      changed=true;rHit++;
    }
  }
  if(rHit){roomHits+=rHit;roomMaps++;}
  if(!changed)continue;
  // ── 重压(最优) + round-trip 校验 + 写回 ──
  let r=lzss.compress_optimal(d,0xc);r.writeUInt32LE(sub.readUInt32LE(0),0);r.writeUInt32LE(r.byteLength,4);r.writeUInt32LE(uc,8);
  const chk=lzss.decompress(r,12,r.byteLength-12,uc);
  if(!chk||Buffer.compare(d,chk)!==0){rtfail.push(`${id}`);continue;}
  const op=(sub.byteLength+3)&~3;if(r.byteLength<op){const pb=Buffer.alloc(op);r.copy(pb);pb.writeUInt32LE(op,4);r=pb;}
  let patched;try{patched=archive.patch_archive_inplace(arch,{0:r});}catch(e){nofit.push(`${id}(+${r.byteLength-((sub.byteLength+3)&~3)})`);continue;}
  await cdimage.write_file(cd,id,patched);
  const ps=Math.ceil(patched.byteLength/BS);await run([String(fb),String(fb+ps-1)]);
  done++;
}
await cdimage.close(cd);await bfp.close();await run(["23","26"]);
console.log(`✅ 写回 ${done} 个地图文件（区域名 + 房间名 ${roomHits} 处/${roomMaps} 个图）`);
if(miss.length)console.log(`⚠ 区域名无译文: ${miss.join(' ')}`);
if(toolong.length)console.log(`⚠ 区域名太长/缺字: ${toolong.join(' ')}`);
if(nofit.length)console.log(`⚠ 重压超容量: ${nofit.join(' ')}`);
if(rtfail.length)console.log(`⚠ round-trip 失败(已跳过): ${rtfail.join(' ')}`);
