// 音乐堂上班族两段夹缝对话手工补丁 (file1115 sub20 @~0x5806)。
// 这两段(え?野外音楽堂?… / しかし、MUSESの人気は…)前面紧挨码密集数据,RET 定界单元
// 夹大量垃圾被 extract_field_text 的 CJK 过滤整条丢弃 → 从没进翻译管线(玩家反馈发现)。
// 做法: 解压 sub20 → 窗口(0x5700-0x5980)内逐段日文码搜索 → 原位等长替换(ct码+全角空格)
//       → compress_to_size 精确填满原槽(tc=op,无零padding) → round-trip 校验 → 塞回原槽。
// 幂等: 已翻后日文匹配不到 → hits=0 直接退出。build 注册于 field 之后。
import * as fs from "fs/promises";
import * as fss from "fs";
import * as archive from "./lib/archive.mjs";
import * as lzss from "./lib/lzss.mjs";
import { spawnSync } from "child_process";
const SECTOR = 0x930, BO = 24, BS = 2048;
const WORK = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
const og = JSON.parse(fss.readFileSync("codetable_og.json", "utf8"));
const ct = JSON.parse(fss.readFileSync("codetable.json", "utf8"));
const ogRev = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) (ogRev[v] = ogRev[v] || []).push(parseInt(k));
const rev = {}; for (const [k, v] of Object.entries(ct)) if (typeof v === "string" && v.length === 1) rev[v] = parseInt(k);
const SP = rev['　'] ?? rev[' '];
const FILE = 1115, SUB = 20, WIN = [0x5700, 0x5980];
const PAIRS = [
  ['サラリーマン', '上班族'],
  ['え?', '诶?'],
  ['野外音楽堂?', '露天音乐厅?'],
  ['ああ、それならそこの', '哦,那个就在'],
  ['青華公園の中だよ。', '青华公园里哦。'],
  ['キミもコンサートを見に行くのかい?', '你也要去看演唱会吗?'],
  ['しかし、MUSESの人気は大したもんだね。', '不过,MUSES人气真是厉害啊。'],
  ['私も興味はあるんだガチケットは完売らしいし…', '我也有兴趣,但票好像卖完了…'],
  ['あきらめるしかないのかなぁ。', '只能放弃了吗。'],
];
async function rblk(fp, fb, fsz) { const s = Buffer.alloc(SECTOR), o = Buffer.allocUnsafe(fsz); let off = 0, sec = fb * SECTOR; while (off < fsz) { await fp.read(s, 0, SECTOR, sec); const c = Math.min(BS, fsz - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; } return o; }
const fp = await fs.open(WORK, "r+");
const fpd = await rblk(fp, 0x17, 0x2400);
const blk = fpd.readUInt32LE(FILE * 8), fsz = fpd.readUInt32LE(FILE * 8 + 4);
const arch = await rblk(fp, blk, fsz);
const offsets = archive.extract_file_offsets(Buffer.from(arch));
const files = archive.extract_files(arch);
const sub = files[SUB], subOff = offsets[SUB];
const tc = sub.readUInt32LE(4), uc = sub.readUInt32LE(8);
const d = lzss.decompress(sub, 12, tc - 12, uc);
let hits = 0;
for (const [jp, zh] of PAIRS) {
  const sets = [...jp].map(c => ogRev[c]);
  if (sets.some(s => !s)) { console.log(`⚠ ${jp} 不可编码`); continue; }
  const cc = [...zh].map(c => rev[c]);
  if (cc.some(x => x === undefined) || cc.length > sets.length) { console.log(`⚠ ${zh} 缺字/超长`); continue; }
  for (let p = WIN[0]; p + sets.length * 2 <= Math.min(d.length, WIN[1]); p += 2) {
    let ok = true;
    for (let k = 0; k < sets.length; k++) { if (!sets[k].includes(d.readUInt16LE(p + k * 2))) { ok = false; break; } }
    if (!ok) continue;
    for (let i = 0; i < cc.length; i++) d.writeUInt16LE(cc[i], p + i * 2);
    for (let i = cc.length; i < sets.length; i++) d.writeUInt16LE(SP, p + i * 2);
    hits++; p += sets.length * 2 - 2;
  }
}
if (!hits) { console.log("[musichall] 无可改(已翻/幂等), 跳过"); await fp.close(); process.exit(0); }
const op = (sub.byteLength + 3) & ~3;
const r = lzss.compress_to_size(d, 12, op);
if (!r) { console.log("✗ compress_to_size 装不下"); process.exit(1); }
r.writeUInt32LE(sub.readUInt32LE(0), 0); r.writeUInt32LE(op, 4); r.writeUInt32LE(uc, 8);
const chk = lzss.decompress(r, 12, op - 12, uc);
if (!chk || Buffer.compare(chk, d) !== 0) { console.log("✗ round-trip 失败"); process.exit(1); }
const newArch = Buffer.from(arch);
r.copy(newArch, subOff);
let wo = 0, wsec = blk * SECTOR;
while (wo < fsz) { const c = Math.min(BS, fsz - wo); await fp.write(newArch, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
await fp.close();
spawnSync("python3", ["fix_ecc.py", String(blk), String(blk + Math.ceil(fsz / BS) - 1)], { stdio: "ignore" });
console.log(`✅ [musichall] ${hits} 段写回 file${FILE}_${SUB}, 精确填满 ${op}B round-trip ✓`);
