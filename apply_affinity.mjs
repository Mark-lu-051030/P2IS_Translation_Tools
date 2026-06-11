// Persona 状态页属性抗性句子表翻译 (file 47/69/70/71/1109 完整副本 + 48/64/65/66/67/1103/1106 小副本)。
// 玩家见"火炎酱無頚"花字:原文"火炎糸無効"(糸=系)等 og 码未翻,糸/熱/効 槽被中文字占 → 渲染错字。
// 条目结构: {121c,arg}{1205,arg}{121e,arg} 文本({1101}内换行,可两行) {1101}{1106}{1101}{1103}。
// 带参控制码按 len-nibble 规则解析((c>>8)&0xf - 1 个参数),原样保留;文本模板句典翻译;
// 原位等长替换(ct码+全角空格填到原文本段码数),控制码/参数零改动 → 指针表不用动,绝对安全。
// 用法: node apply_affinity.mjs extract   → 打印全部唯一句子(填句典用)
//       node apply_affinity.mjs apply    → 写回 WORK 全部副本文件
import fs from "fs";
import { spawnSync } from "child_process";
const SECTOR = 0x930, BO = 24, BS = 2048;
const WORK = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
const og = JSON.parse(fs.readFileSync("codetable_og.json", "utf8"));
const ct = JSON.parse(fs.readFileSync("codetable.json", "utf8"));
const ogChar = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) ogChar[k] = v;
const rev = {}; for (const [k, v] of Object.entries(ct)) if (typeof v === "string" && v.length === 1) rev[v] = parseInt(k);
const FULL_SPACE = rev['　'] ?? rev[' '];

const FILES = [47, 48, 64, 65, 66, 67, 69, 70, 71, 1103, 1106, 1109];

// 模板句典: 属性名(NAME)+动作。NAME 先词典,动作后模板。中文必须 ≤ 原日文段码数。
const ATTR = { '神聖':'神圣','物理攻撃':'物理','魔法攻撃':'魔法','剣撃':'剑击','戦技':'战技','飛具':'飞具',
  '投具':'投具','火炎':'火炎','水撃':'水击','核熱':'核热','電撃':'电击','冷気':'冷气','疾風':'疾风',
  '大地':'大地','重力':'重力','雷撃':'雷击','閃光':'闪光','魔力':'魔力','呪殺':'咒杀','秘孔':'秘孔',
  '催眠':'催眠','神経':'神经','精神':'精神','降魔':'降魔','遠隔':'远程','全':'全',
  '地変':'地变','暗黒':'暗黑','氷結':'冰结','魔法':'魔法','打撃':'打击','物理':'物理' };
// 段级翻译: 一段日文(单行, 不含控制码)→中文。返回 null = 不会翻(保留原文)。
function transSeg(seg) {
  let s = seg;
  // 整段特例
  const SPECIAL = {
    '全ての攻撃に対して強い': '耐所有攻击', '全ての攻撃を無効にする': '所有攻击无效',
    '全ての攻撃に対して弱い': '怕所有攻击',
    '(リザーブ)': '(预留)', 'ボス用の相性へルプ表示部分': 'BOSS用相性帮助显示',
    '剣撃以外の物理攻撃無効': '剑击外物理无效', '回復しやすい': '容易回复',
    // 跨行截断段(同一句被 {1101} 拆成两段, 逐段翻)
    '無効にする': '无效', '神聖/暗黒/神経/精神糸を': '神圣/暗黑/神经/精神系',
  };
  if (SPECIAL[s] !== undefined) return SPECIAL[s];
  // 通用: [NAME](糸)?(を無効にする|に強い|に弱い|を反射する|を吸収する|無効|反射|吸収…)
  const m = s.match(/^(.+?)(糸)?(を無効にする|に対して強い|にやや強い|に強い|に弱い|を反射する|を吸収する|を反射|を吸収|無効|反射|吸収)$/);
  if (!m) return null;
  let [, name, kei, act] = m;
  let cn_name = ATTR[name];
  if (cn_name === undefined) {
    // 复合名 如 火炎/核熱 / 剣撃/戦技 / 飛具/投具
    const parts = name.split('/');
    if (parts.every(p => ATTR[p] !== undefined)) cn_name = parts.map(p => ATTR[p]).join('/');
    else return null;
  }
  const X = cn_name + (kei ? '系' : '');
  const ACT = { 'を無効にする': X + '无效', 'に対して強い': '耐' + X, 'にやや強い': '稍耐' + X, 'に強い': '耐' + X,
    'に弱い': '怕' + X, 'を反射する': X + '反射', 'を吸収する': X + '吸收', 'を反射': X + '反射', 'を吸収': X + '吸收',
    '無効': X + '无效', '反射': X + '反射', '吸収': X + '吸收' };
  return ACT[act];
}

function rfile(fd, id) {
  const o = Buffer.alloc(0x2400), s = Buffer.alloc(SECTOR); let off = 0, sec = 0x17 * SECTOR;
  while (off < 0x2400) { fs.readSync(fd, s, 0, SECTOR, sec); const c = Math.min(BS, 0x2400 - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; }
  const blk = o.readUInt32LE(id * 8), sz = o.readUInt32LE(id * 8 + 4);
  const b = Buffer.alloc(sz), s2 = Buffer.alloc(SECTOR); let o2 = 0, sc = blk * SECTOR;
  while (o2 < sz) { fs.readSync(fd, s2, 0, SECTOR, sc); const c = Math.min(BS, sz - o2); s2.copy(b, o2, BO, BO + c); o2 += c; sc += SECTOR; }
  return { buf: b, blk, sz };
}

// 扫描: 找 {121c} 开头、{1103} 结尾的条目; 解析出文本"段"(连续可解码文字, 被控制码分隔)。
// 返回 [{segs:[{off,chars}]}]。控制码按 len-nibble 跳参数。
function parseEntries(a) {
  const entries = [];
  const n = a.length & ~1;
  for (let p = 0; p + 2 <= n; p += 2) {
    if (a.readUInt16LE(p) !== 0x121c) continue;
    // 条目内逐 token 走到 {1103}, 限 0x200 字节防失控
    let q = p, segs = [], cur = null, ok = false;
    while (q + 2 <= n && q - p < 0x200) {
      const c = a.readUInt16LE(q);
      if (c >= 0x1000) {
        if (cur) { segs.push(cur); cur = null; }
        const argn = ((c >> 8) & 0xf) - 1;
        q += 2 + Math.max(0, argn) * 2;
        if (c === 0x1103) { ok = true; break; }
        continue;
      }
      const ch = c === 0 ? null : ogChar[String(c)];
      if (ch === null || ch === undefined) { if (cur) { segs.push(cur); cur = null; } q += 2; continue; }
      if (!cur) cur = { off: q, txt: '' };
      cur.txt += ch; q += 2;
    }
    // ⚠ break 时 q 已越过 {1103} 指向下一条 {121c};外层还会 p+=2,故须 -2 补偿,否则隔条漏翻(实测严格交替漏一半)
    if (ok && segs.some(s => s.txt.length >= 3)) { entries.push({ off: p, segs: segs.filter(s => s.txt.length >= 2) }); p = q - 2; }
  }
  return entries;
}

const MODE = process.argv[2] || 'extract';
const fd = fs.openSync(WORK, MODE === 'apply' ? 'r+' : 'r');
const uniq = new Map();   // 句子 → 翻译/null
let wrote = 0, miss = 0;
for (const FILE of FILES) {
  let f; try { f = rfile(fd, FILE); } catch { continue; }
  const { buf: a, blk, sz } = f;
  const entries = parseEntries(a);
  if (!entries.length) continue;
  const touched = new Set();
  let fileHits = 0;
  for (const e of entries) for (const seg of e.segs) {
    const cn = transSeg(seg.txt);
    if (!uniq.has(seg.txt)) uniq.set(seg.txt, cn);
    if (MODE !== 'apply') continue;
    if (cn === null) continue;
    const cc = [...cn].map(c => rev[c]);
    if (cc.some(x => x === undefined) || cc.length > seg.txt.length) { miss++; continue; }
    for (let i = 0; i < cc.length; i++) a.writeUInt16LE(cc[i], seg.off + i * 2);
    for (let i = cc.length; i < seg.txt.length; i++) a.writeUInt16LE(FULL_SPACE, seg.off + i * 2);
    touched.add(blk + Math.floor(seg.off / BS)); touched.add(blk + Math.floor((seg.off + seg.txt.length * 2) / BS));
    wrote++; fileHits++;
  }
  if (MODE === 'apply' && touched.size) {
    let wo = 0, wsec = blk * SECTOR;
    while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(fd, a, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
    spawnSync("python3", ["fix_ecc.py", String(Math.min(...touched)), String(Math.max(...touched))], { stdio: "ignore" });
    console.log(`file${FILE}: ${fileHits} 段写回, ECC ${Math.min(...touched)}-${Math.max(...touched)}`);
  }
}
fs.closeSync(fd);
if (MODE !== 'apply') {
  console.log(`唯一句子 ${uniq.size} 条:`);
  for (const [jp, cn] of [...uniq.entries()].sort()) console.log(`  ${cn === null ? '❌' : '✓'} ${jp}  →  ${cn ?? '(句典未覆盖)'}`);
} else {
  console.log(`✅ 共写回 ${wrote} 段 (跳过 ${miss})`);
}
