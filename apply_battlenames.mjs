// 战斗 HP/SP 面板角色名补丁 (file 1129)。
// 面板名字不读 SLPS 的 SLUS_0_1(那份翻了也不显示),读 file1129 @~0xc608 的
// 名字簇: og码 + {1000} 终止,后跟 RAM 指针表(0x8009F608→舞耶 等)。
// 原位等长替换: ct 中文码 + {1000} 填充到原码数,指针表不动。達哉=玩家存档名(命名界面),不在此表。
// 定位用"名字+0x1000"模式搜索(不硬编码偏移)。从 WORK 读(保留其他 apply)改写回 WORK。
import fs from "fs";
import { spawnSync } from "child_process";
const SECTOR = 0x930, BO = 24, BS = 2048;
const WORK = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
const og = JSON.parse(fs.readFileSync("codetable_og.json", "utf8"));
const ct = JSON.parse(fs.readFileSync("codetable.json", "utf8"));
const ogRev = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) (ogRev[v] = ogRev[v] || []).push(parseInt(k));
const rev = {}; for (const [k, v] of Object.entries(ct)) if (typeof v === "string" && v.length === 1) rev[v] = parseInt(k);

const FILE = 1129;
const NAMES = {            // 面板名 JP→CN (glossary: 米切/银子/小雪/丽莎/纯)
  "舞耶": "舞耶", "ミッシェル": "米切", "リサ": "丽莎",
  "淳": "纯", "ユッキー": "小雪", "ギンコ": "银子",
};

function rfile(fd, id) {
  const o = Buffer.alloc(0x2400), s = Buffer.alloc(SECTOR); let off = 0, sec = 0x17 * SECTOR;
  while (off < 0x2400) { fs.readSync(fd, s, 0, SECTOR, sec); const c = Math.min(BS, 0x2400 - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; }
  const blk = o.readUInt32LE(id * 8), sz = o.readUInt32LE(id * 8 + 4);
  const b = Buffer.alloc(sz), s2 = Buffer.alloc(SECTOR); let o2 = 0, sc = blk * SECTOR;
  while (o2 < sz) { fs.readSync(fd, s2, 0, SECTOR, sc); const c = Math.min(BS, sz - o2); s2.copy(b, o2, BO, BO + c); o2 += c; sc += SECTOR; }
  return { buf: b, blk, sz };
}

const fd = fs.openSync(WORK, "r+");
const { buf: a, blk, sz } = rfile(fd, FILE);
const touched = new Set();
let hits = 0;
for (const [jp, cn] of Object.entries(NAMES)) {
  const jsets = [...jp].map(c => ogRev[c]);
  if (jsets.some(s => !s)) { console.log(`⚠ ${jp} 含未知og码`); continue; }
  const cc = [...cn].map(c => rev[c]);
  if (cc.some(x => x === undefined)) { console.log(`⚠ ${cn} 缺字`); continue; }
  if (cc.length > jsets.length) { console.log(`⚠ ${cn} 超长`); continue; }
  for (let p = 0; p + (jsets.length + 1) * 2 <= a.length; p += 2) {
    let ok = true;
    for (let k = 0; k < jsets.length; k++) { if (!jsets[k].includes(a.readUInt16LE(p + k * 2))) { ok = false; break; } }
    if (!ok || a.readUInt16LE(p + jsets.length * 2) !== 0x1000) continue;
    for (let i = 0; i < cc.length; i++) a.writeUInt16LE(cc[i], p + i * 2);
    for (let i = cc.length; i < jsets.length; i++) a.writeUInt16LE(0x1000, p + i * 2);
    touched.add(blk + Math.floor(p / BS)); touched.add(blk + Math.floor((p + jsets.length * 2) / BS));
    console.log(`  ${jp}→${cn} @0x${p.toString(16)}`); hits++;
  }
}
if (hits) {
  let wo = 0, wsec = blk * SECTOR;
  while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(fd, a, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
  spawnSync("python3", ["fix_ecc.py", String(Math.min(...touched)), String(Math.max(...touched))], { stdio: "ignore" });
}
fs.closeSync(fd);
console.log(`✅ file${FILE} 战斗面板名 ${hits} 处`);
