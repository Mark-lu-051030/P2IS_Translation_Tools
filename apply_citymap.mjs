// 城市俯视图地点标签翻译。这些标签在 file 1113 的未压缩区, 是 og码地名 + 0x1000 终止符,
// 既不是 RET 对话也不是字符串表 → 字段提取(要 RET 定界+≥3汉字)漏了它们, 片假名地名一直是日文。
// 做法: 精确匹配 JP 标签的 og 码字节序列, 且其后紧跟 0x1000(确保是完整标签不是更长串的子串),
// 原位替换为 CN 码 + 0x1000 终止 + 0x1000 填充到原字节宽(CN 更短, 装得下)。直接写扇区, 大小不变。
import fs from "fs";
import { spawnSync } from "child_process";
const SECTOR = 0x930, BO = 24, BS = 2048;
const BACKUP = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";
const WORK = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
const og = JSON.parse(fs.readFileSync("codetable_og.json", "utf8"));
const ct = JSON.parse(fs.readFileSync("codetable.json", "utf8"));
const ogRev = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) ogRev[v] = parseInt(k);
const rev = {}; for (const [k, v] of Object.entries(ct)) if (typeof v === "string" && v.length === 1) rev[v] = parseInt(k);

const FILE = 1113;
// 城市图地点标签 JP→CN（片假名地名; 汉字地名本就可读不动）。可扩展: 发现别的没翻标签往这加。
const LABELS = {
  "スマル・プリズン": "苏摩鲁监狱",
};

function rfile(fd, id) {
  const o = Buffer.alloc(0x2400), s = Buffer.alloc(SECTOR); let off = 0, sec = 0x17 * SECTOR;
  while (off < 0x2400) { fs.readSync(fd, s, 0, SECTOR, sec); const c = Math.min(BS, 0x2400 - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; }
  const blk = o.readUInt32LE(id * 8), sz = o.readUInt32LE(id * 8 + 4);
  const b = Buffer.alloc(sz), s2 = Buffer.alloc(SECTOR); let o2 = 0, sc = blk * SECTOR;
  while (o2 < sz) { fs.readSync(fd, s2, 0, SECTOR, sc); const c = Math.min(BS, sz - o2); s2.copy(b, o2, BO, BO + c); o2 += c; sc += SECTOR; }
  return { buf: b, blk, sz };
}

const bfd = fs.openSync(BACKUP, "r");
const { buf: a, blk, sz } = rfile(bfd, FILE);
fs.closeSync(bfd);

// 预编码 JP/CN 码
const jobs = [];
for (const [jp, cn] of Object.entries(LABELS)) {
  const jc = [...jp].map(c => ogRev[c]);
  if (jc.some(x => x === undefined)) { console.log(`⚠ JP "${jp}" 含未知 og 码, 跳过`); continue; }
  const cc = [...cn].map(c => rev[c]);
  if (cc.some(x => x === undefined)) { console.log(`⚠ CN "${cn}" 含缺字, 跳过`); continue; }
  if (cc.length > jc.length) { console.log(`⚠ CN "${cn}"(${cc.length}) 比 JP "${jp}"(${jc.length}) 长, 跳过`); continue; }
  const jb = Buffer.alloc(jc.length * 2); jc.forEach((c, i) => jb.writeUInt16LE(c, i * 2));
  jobs.push({ jp, cn, jc, cc, jb });
}

// 在 1113 raw 找每个 JP 标签(且后跟 0x1000 = 完整标签), 原位替换
const touched = new Set();
let hits = 0;
for (const { jp, cn, jc, cc, jb } of jobs) {
  let p = a.indexOf(jb);
  let n = 0;
  while (p >= 0) {
    const after = (p + jb.length + 1 < a.length) ? a.readUInt16LE(p + jb.length) : -1;
    if (p % 2 === 0 && after === 0x1000) {   // 偶对齐 + 后跟终止符 → 完整标签
      for (let i = 0; i < cc.length; i++) a.writeUInt16LE(cc[i], p + i * 2);
      a.writeUInt16LE(0x1000, p + cc.length * 2);                          // CN 后紧跟终止符
      for (let i = cc.length + 1; i < jc.length; i++) a.writeUInt16LE(0x1000, p + i * 2);  // 余下填充(不被读)
      touched.add(blk + Math.floor(p / BS));
      if (p + jb.length > (Math.floor(p / BS) + 1) * BS) touched.add(blk + Math.floor((p + jb.length) / BS));  // 跨扇区
      n++; hits++;
    }
    p = a.indexOf(jb, p + 2);
  }
  console.log(`  ${jp} → ${cn}: ${n} 处`);
}

if (!hits) { console.log("无可改标签"); process.exit(0); }

// 写回 WORK 扇区(整文件, 大小不变)
const wfd = fs.openSync(WORK, "r+");
let wo = 0, wsec = blk * SECTOR;
while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(wfd, a, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
fs.closeSync(wfd);
const lo = Math.min(...touched), hi = Math.max(...touched);
spawnSync("python3", ["fix_ecc.py", String(lo), String(hi)], { stdio: "ignore" });
console.log(`✅ 城市图标签写回 ${hits} 处, ECC 修 sector ${lo}-${hi}`);
