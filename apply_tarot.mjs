// 塔罗/魔法卡描述副本翻译 (file 1105 主副本 + 64/65/66/67 表外残留)。
// 卡片界面描述(【EMPEROR(エンペラー)】のペルソナを召喚するのに必要 等)读 file1105,
// 而译文只进了 strtbl:64_0_2(apply_strtbl 写 file64 表区) → 界面仍日文。
// file1105 结构(与 strtbl 同构): 头部指针表 + 条目 {1205,0}{121e,0} 文本行({1101}分隔) {1101}{1106}{1101}{1103}。
// 做法: 解析条目 → 行拼接做键 → 查 strtbl:64_0_2 译文(jp→zh, 去标签规范化) → 逐行原位等长写回
// (ct码+全角空格填充, zh行少则余行全空格), 控制码/指针表零改动。幂等(翻过的匹配不到)。
// 用法: node apply_tarot.mjs extract | apply
import fs from "fs";
import { spawnSync } from "child_process";
const SECTOR = 0x930, BO = 24, BS = 2048;
const WORK = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
const og = JSON.parse(fs.readFileSync("codetable_og.json", "utf8"));
const ct = JSON.parse(fs.readFileSync("codetable.json", "utf8"));
const ogChar = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) ogChar[k] = v;
const rev = {}; for (const [k, v] of Object.entries(ct)) if (typeof v === "string" && v.length === 1) rev[v] = parseInt(k);
const FULL_SPACE = rev['　'] ?? rev[' '];
// 全角标点 fallback(freetbl 同款): zh 里的全角标点若码表无,映射到半角码
for (const [fw, hw] of Object.entries({'！':'!','？':'?','…':'.','，':'、','：':':','（':'(','）':')','·':'・'}))
  if (rev[hw] !== undefined && rev[fw] === undefined) rev[fw] = rev[hw];
const FILES = [1105, 64, 65, 66, 67];

// 译文 LUT: strtbl:64_0_2 的 jp→zh。键 = 去 <…/> 标签 + trim 尾换行的 jp;值 = zh 行数组(去标签)。
const at = JSON.parse(fs.readFileSync("all_translatable.json", "utf8"));
const strip = s => (s || '').replace(/<[^>]*>/g, '');
const LUT = {};
for (const e of at) {
  if (!/^strtbl:64_0_\d+:/.test(e.id || '')) continue;   // 64_0_0..4 全部表(卡描述/道具效果等)
  const p = (e.pages || [])[0]; if (!p) continue;
  const jp = strip(p.jp).replace(/\n+$/, ''), zh = strip(p.zh).replace(/\n+$/, '');
  if (jp && zh) LUT[jp] = zh.split('\n');
}
console.log(`LUT: ${Object.keys(LUT).length} 条 (strtbl:64_0_*)`);

function rfile(fd, id) {
  const o = Buffer.alloc(0x2400), s = Buffer.alloc(SECTOR); let off = 0, sec = 0x17 * SECTOR;
  while (off < 0x2400) { fs.readSync(fd, s, 0, SECTOR, sec); const c = Math.min(BS, 0x2400 - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; }
  const blk = o.readUInt32LE(id * 8), sz = o.readUInt32LE(id * 8 + 4);
  const b = Buffer.alloc(sz), s2 = Buffer.alloc(SECTOR); let o2 = 0, sc = blk * SECTOR;
  while (o2 < sz) { fs.readSync(fd, s2, 0, SECTOR, sc); const c = Math.min(BS, sz - o2); s2.copy(b, o2, BO, BO + c); o2 += c; sc += SECTOR; }
  return { buf: b, blk, sz };
}

// 解析: 条目起点 {1205}, 终点 {1103}。行 = 文本 run(off+txt), {1101} 换行切行。
function parseEntries(a) {
  const entries = [];
  const n = a.length & ~1;
  for (let p = 0; p + 2 <= n; p += 2) {
    if (a.readUInt16LE(p) !== 0x1205) continue;
    let q = p, lines = [], cur = null, ok = false;
    while (q + 2 <= n && q - p < 0x300) {
      const c = a.readUInt16LE(q);
      if (c >= 0x1000) {
        if (cur) { lines.push(cur); cur = null; }
        const argn = ((c >> 8) & 0xf) - 1;
        q += 2 + Math.max(0, argn) * 2;
        if (c === 0x1103) { ok = true; break; }
        continue;
      }
      const ch = c === 0 ? null : ogChar[String(c)];
      if (ch === null || ch === undefined) { if (cur) { lines.push(cur); cur = null; } q += 2; continue; }
      if (!cur) cur = { off: q, txt: '' };
      cur.txt += ch; q += 2;
    }
    // q 已越过 {1103}; 外层 p+=2 补偿 -2 (同 apply_affinity 的隔条漏翻教训)
    if (ok && lines.some(l => l.txt.length >= 2)) { entries.push({ lines: lines.filter(l => l.txt.length >= 1) }); p = q - 2; }
  }
  return entries;
}

const MODE = process.argv[2] || 'extract';
const fd = fs.openSync(WORK, MODE === 'apply' ? 'r+' : 'r');
const unmatched = new Map();
let wrote = 0, skip = 0;
for (const FILE of FILES) {
  let f; try { f = rfile(fd, FILE); } catch { continue; }
  const { buf: a, blk, sz } = f;
  const entries = parseEntries(a);
  if (!entries.length) continue;
  const touched = new Set();
  let fileHits = 0;
  for (const e of entries) {
    const key = e.lines.map(l => l.txt).join('\n');
    const zhLines = LUT[key];
    if (!zhLines) { if (/[ぁ-ゖァ-ヺ]/.test(key)) unmatched.set(key, (unmatched.get(key) || 0) + 1); continue; }
    if (MODE !== 'apply') { fileHits++; continue; }
    // 行数/行长校验
    if (zhLines.length > e.lines.length) { skip++; if(skip<=8)console.log(`  skip[行数] ${key.replace(/\n/g,'|').slice(0,40)} → zh${zhLines.length}行>jp${e.lines.length}行`); continue; }
    let bad = false;
    const enc = zhLines.map((z, i) => {
      const cc = [...z].map(c => rev[c]);
      if (cc.some(x => x === undefined) || cc.length > e.lines[i].txt.length) bad = true;
      return cc;
    });
    if (bad) { skip++; if(skip<=8)console.log(`  skip[超长/缺字] ${key.replace(/\n/g,'|').slice(0,36)} → ${zhLines.join('|').slice(0,36)}`); continue; }
    for (let i = 0; i < e.lines.length; i++) {
      const L = e.lines[i], cc = i < enc.length ? enc[i] : [];
      for (let k = 0; k < cc.length; k++) a.writeUInt16LE(cc[k], L.off + k * 2);
      for (let k = cc.length; k < L.txt.length; k++) a.writeUInt16LE(FULL_SPACE, L.off + k * 2);
      touched.add(blk + Math.floor(L.off / BS)); touched.add(blk + Math.floor((L.off + L.txt.length * 2) / BS));
    }
    wrote++; fileHits++;
  }
  if (MODE === 'apply' && touched.size) {
    let wo = 0, wsec = blk * SECTOR;
    while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(fd, a, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
    spawnSync("python3", ["fix_ecc.py", String(Math.min(...touched)), String(Math.max(...touched))], { stdio: "ignore" });
  }
  console.log(`file${FILE}: ${MODE === 'apply' ? '写回' : '可匹配'} ${fileHits} 条`);
}
fs.closeSync(fd);
if (MODE !== 'apply') {
  console.log(`\n未匹配(含假名,真日文) ${unmatched.size} 种:`);
  for (const [k, n] of [...unmatched.entries()].slice(0, 30)) console.log(`  ×${n} ${k.replace(/\n/g, '|')}`);
} else {
  console.log(`✅ 共写回 ${wrote} 条 (跳过 ${skip})`);
}
