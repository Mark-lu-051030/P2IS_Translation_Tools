// 字段文本回插（原位等长）。第一步：--verify 校验编码器正确性（read-only，不写 ISO）。
// 把每条提取出来的 jp 文本重新编码成 uint16 码 + RET，和原文件该 offset 的字节逐一比对。
// 全等 → 编码器(render 的逆)正确，原位等长写回才可靠。
//
// 用法:
//   node apply_field.mjs verify [fileId]   # 校验某文件(默认全部 field_text 涉及的文件)的 jp round-trip
import fs from "fs";

const SECTOR = 0x930, BO = 24, BS = 2048;
const BACKUP = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";
const og = JSON.parse(fs.readFileSync("codetable_og.json", "utf8"));
const ogc = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) ogc[k] = v;
const ogRev = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) ogRev[v] = parseInt(k);

const fd = fs.openSync(BACKUP, "r");
// srcfd 默认从 backup 读（verify 用，校验原始编码）；apply 时传 WORK 的 fd，
// 这样在"已 apply 过 strtbl/script 等"的工作 ISO 基础上原位改字段文本，不会把别的 apply 冲回日文。
function rfile(id, srcfd = fd) {
  const o = Buffer.alloc(0x2400), s = Buffer.alloc(SECTOR); let off = 0, sec = 0x17 * SECTOR;
  while (off < 0x2400) { fs.readSync(srcfd, s, 0, SECTOR, sec); const c = Math.min(BS, 0x2400 - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; }
  const blk = o.readUInt32LE(id * 8), sz = o.readUInt32LE(id * 8 + 4); if (!sz) return null;
  const b = Buffer.alloc(sz), s2 = Buffer.alloc(SECTOR); let o2 = 0, sc2 = blk * SECTOR;
  while (o2 < sz) { fs.readSync(srcfd, s2, 0, SECTOR, sc2); const c = Math.min(BS, sz - o2); s2.copy(b, o2, BO, BO + c); o2 += c; sc2 += SECTOR; }
  return b;
}

// 把 jp 文本（render 产出的格式：字符 + <cXX[:a,b]/> + 字面 \n）编码成 uint16 码数组（不含结尾 RET）。
// charToCode: 字符→码（jp 用 ogRev）。返回 {codes, ok}（ok=false 表示有字符/标签无法编码）。
function encodeText(s, charToCode) {
  const codes = []; let ok = true; let i = 0; let miss = null;
  while (i < s.length) {
    if (s[i] === "<") {
      const j = s.indexOf(">", i); if (j < 0) { ok = false; break; }
      let tag = s.slice(i + 1, j); i = j + 1;
      if (tag.endsWith("/")) tag = tag.slice(0, -1);
      // 形如 c5:0,0 或 c6
      const m = tag.match(/^c([0-9a-f]+)(?::(.*))?$/);
      if (!m) { ok = false; continue; }
      const cmd = parseInt(m[1], 16);
      const args = m[2] ? m[2].split(",").map(x => parseInt(x, 10)) : [];
      const len = 1 + args.length;
      codes.push(0x1000 | (len << 8) | cmd);
      for (const a of args) codes.push(a & 0xffff);
    } else if (s[i] === "\\" && s[i + 1] === "n") {
      codes.push(0x1101); i += 2;               // 字面 \n（jp 来源）
    } else if (s[i] === "\n") {
      codes.push(0x1101); i += 1;               // 真换行 U+000A（DeepSeek 输出常见）
    } else {
      const c = charToCode[s[i]];
      if (c === undefined) { ok = false; if (!miss) miss = s[i]; codes.push(0); } else codes.push(c);
      i += 1;
    }
  }
  return { codes, ok, miss };
}

// 算一条对话的字节结束位置（与提取器同逻辑：遇 RET 0x1103 结束）
function dialogEnd(d, off) {
  let q = off;
  while (q + 1 < d.length) {
    const c = d.readUInt16LE(q); q += 2; const t = (c >> 12) & 0xf;
    if (t === 0) continue;
    if (t === 1) { q += Math.max(0, ((c >> 8) & 0xf) - 1) * 2; if ((c & 0xff) === 3) return q; continue; }
    return -1;
  }
  return -1;
}

function verify(fileFilter) {
  const ft = JSON.parse(fs.readFileSync("out/field_text_clean.json", "utf8"));
  const byFile = {};
  for (const e of ft) {
    const m = e.id.match(/^field:(\d+)(?:_\d+d?)?:0x([0-9a-f]+)$/);
    if (!m) continue;
    const id = parseInt(m[1]), off = parseInt(m[2], 16);
    if (e.id.includes("_") && e.id.includes("d:")) continue;   // 跳过解压 sub（offset 不在原文件）
    if (fileFilter && id !== fileFilter) continue;
    (byFile[id] = byFile[id] || []).push({ off, jp: e.jp });
  }
  let total = 0, match = 0, mismatch = [];
  for (const id of Object.keys(byFile).map(Number).sort((a, b) => a - b)) {
    const d = rfile(id); if (!d) continue;
    for (const { off, jp } of byFile[id]) {
      total++;
      const end = dialogEnd(d, off); if (end < 0) { mismatch.push(`${id}@0x${off.toString(16)}:无RET`); continue; }
      const orig = d.slice(off, end);
      const { codes, ok } = encodeText(jp, ogRev);
      if (!ok) { mismatch.push(`${id}@0x${off.toString(16)}:编码失败`); continue; }
      const buf = Buffer.alloc(codes.length * 2 + 2);
      for (let k = 0; k < codes.length; k++) buf.writeUInt16LE(codes[k], k * 2);
      buf.writeUInt16LE(0x1103, codes.length * 2);   // 补回 RET
      if (Buffer.compare(orig, buf) === 0) match++;
      else if (mismatch.length < 12) {
        // 找第一个差异码，看是不是同字不同槽
        let diff = "长度差";
        if (orig.length === buf.length) {
          for (let k = 0; k + 1 < orig.length; k += 2) {
            const a = orig.readUInt16LE(k), b = buf.readUInt16LE(k);
            if (a !== b) { diff = `@码${k / 2}: 原0x${a.toString(16)}(${ogc[String(a)] || "?"}) vs 编0x${b.toString(16)}(${ogc[String(b)] || "?"})`; break; }
          }
        }
        mismatch.push(`${id}@0x${off.toString(16)}(${orig.length}B) ${diff}`);
      }
    }
  }
  console.log(`round-trip: ${match}/${total} 字节级全等`);
  if (mismatch.length) console.log("不匹配样本:\n  " + mismatch.join("\n  "));
}

// ── 回插：原位等长写回 zh ──────────────────────────────────────
import { spawnSync } from "child_process";
const WORK = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
// 整文件级跳过（目前空）。1102 等的崩溃由下面的"结构性条目过滤"解决：只跳过被误提取的
// 文件头/指针表条目(「密集)，真正的文本消息照常翻译。验证过 apply 1102 在过滤后正常。
const SKIP_FILES = new Set();
// 结构性条目检测：有些"字段文本"其实是文件头/指针表(u32偏移)被误提取，渲染成 "「X「Y" 模式
// (「=code 0x0000=指针高字节零)。往这写中文会把指针表写烂 → 崩(如 file 1102 的存读档界面)。
// 真对话/消息几乎不含「。故「密集 = 结构性数据, 跳过不写。
function isStructural(jp) {
  const s = (jp || "").replace(/<[^>]*>/g, "").replace(/\\n/g, "");
  if (s.length < 4) return false;
  let q = 0; for (const c of s) if (c === "「" || c === "」") q++;
  return q >= 4 && q > s.length * 0.25;
}
const ct = JSON.parse(fs.readFileSync("codetable.json", "utf8"));
const rev = {}; for (const [k, v] of Object.entries(ct)) if (typeof v === "string" && v.length === 1) rev[v] = parseInt(k);
// 全角标点/缺字 → 复用已有半角/日文槽（与 encode_zh.py 的 FULLWIDTH_ALIASES 一致），
// 否则译文里的 ，。！？（）… 等查不到 rev → 整条编码失败被跳过。
const FW_ALIAS = { "！": "!", "？": "?", "…": ".", "，": "、", "。": "。", "：": ":", "；": ";",
  "（": "(", "）": ")", "　": " ", " ": "　", "~": "〜", "～": "〜", "—": "-", "–": "-", "―": "-",
  "《": "「", "》": "」", "‘": "'", "’": "'", "“": '"', "”": '"', "·": "・", "ó": "o" };
for (const [fw, hw] of Object.entries(FW_ALIAS)) if (rev[hw] !== undefined && rev[fw] === undefined) rev[fw] = rev[hw];
// JP→CN 等价别名（與 encode_zh 一致）：DeepSeek 偶尔输出繁体/旧字体(時/昇…)，映射到其 CN 简体槽
try {
  const equiv = JSON.parse(fs.readFileSync("jp_cn_equiv.json", "utf8"));
  for (const [jp, cn] of Object.entries(equiv)) if (rev[cn] !== undefined && rev[jp] === undefined) rev[jp] = rev[cn];
} catch { }
const FW = rev["　"] ?? rev[" "];

function apply(dry, fileFilter) {
  // strtbl 表区域：这些 offset 由 apply_strtbl 重建索引表+字符串处理。字段提取误把其中的
  // strtbl 串也提了；apply_field 若再写会和 apply_strtbl 的重建冲突 → 指针表写烂 → 越界崩。
  // 故跳过落在任何 strtbl 表 [offset, offset+max_len) 内的字段条目。
  const strtblRegions = {};
  try {
    for (const f of fs.readdirSync("out/string_table")) {
      if (!f.endsWith(".json")) continue;
      const t = JSON.parse(fs.readFileSync(`out/string_table/${f}`, "utf8"));
      if (t.file === undefined || t.offset === undefined || !t.max_len) continue;
      (strtblRegions[t.file] = strtblRegions[t.file] || []).push([t.offset, t.offset + t.max_len]);
    }
  } catch { }
  const inStrtbl = (id, off) => (strtblRegions[id] || []).some(([s, e]) => off >= s && off < e);

  const zh = JSON.parse(fs.readFileSync("out/field_text_zh.json", "utf8"));
  const byFile = {};
  let excl = 0;
  for (const e of zh) {
    if (!e.zh || !e.zh.trim()) continue;
    const m = e.id.match(/^field:(\d+):0x([0-9a-f]+)$/);   // 只处理原文件未压缩(无 _Nd)的条目
    if (!m) continue;
    const id = parseInt(m[1]), off = parseInt(m[2], 16);
    if (SKIP_FILES.has(id)) continue;                       // 整文件级跳过(目前无)
    if (fileFilter && !fileFilter(id)) continue;
    if (inStrtbl(id, off)) { excl++; continue; }            // 落在 strtbl 表区 → 归 apply_strtbl, 跳过
    if (isStructural(e.jp)) { excl++; continue; }           // 结构性条目(指针表/二进制误提取) → 跳过, 防写烂结构
    (byFile[id] = byFile[id] || []).push({ off, jp: e.jp, zh: e.zh });
  }
  if (excl) console.log(`跳过 ${excl} 条落在 strtbl 表区的条目（归 apply_strtbl 处理）`);
  // 读全文件表（含 >881）
  const o = Buffer.alloc(0x2400), s = Buffer.alloc(SECTOR); let off0 = 0, sec0 = 0x17 * SECTOR;
  while (off0 < 0x2400) { fs.readSync(fd, s, 0, SECTOR, sec0); const c = Math.min(BS, 0x2400 - off0); s.copy(o, off0, BO, BO + c); off0 += c; sec0 += SECTOR; }
  const wfd = dry ? null : fs.openSync(WORK, "r+");
  let totWrote = 0, totSkip = 0, totTooLong = 0, totTag = 0, totNoRet = 0, totEnc = 0;
  const encMiss = {};   // 编码失败时缺的字符 → 计数
  const eccRanges = [];
  for (const id of Object.keys(byFile).map(Number).sort((a, b) => a - b)) {
    const d = rfile(id, wfd || fd); if (!d) continue;       // apply 从 WORK 读(保留之前的apply); dry 从 backup
    const blk = o.readUInt32LE(id * 8), sz = o.readUInt32LE(id * 8 + 4);
    let wrote = 0, skip = 0;
    for (const { off, jp, zh: zhtext } of byFile[id]) {
      const end = dialogEnd(d, off); if (end < 0) { totNoRet++; skip++; continue; }
      const spanCodes = (end - off) / 2;                   // 含结尾 RET
      // 标签守恒检查
      const jpTags = (jp.match(/<[^>]+>/g) || []).sort().join();
      const zhTags = (zhtext.match(/<[^>]+>/g) || []).sort().join();
      if (jpTags !== zhTags) { totTag++; skip++; continue; }
      const { codes, ok, miss } = encodeText(zhtext, rev);
      if (!ok) { totEnc++; if (miss) encMiss[miss] = (encMiss[miss] || 0) + 1; skip++; continue; }
      if (codes.length + 1 > spanCodes) { totTooLong++; skip++; continue; }   // 放不下(+1=RET)
      // 写：zh codes + 全角空格补齐 + RET，总长 = spanCodes
      for (let k = 0; k < codes.length; k++) d.writeUInt16LE(codes[k], off + k * 2);
      let p = off + codes.length * 2;
      for (let k = codes.length; k < spanCodes - 1; k++) { d.writeUInt16LE(FW, p); p += 2; }
      d.writeUInt16LE(0x1103, p);
      wrote++;
    }
    totWrote += wrote; totSkip += skip;
    console.log(`file ${id}: 写 ${wrote} / 跳过 ${skip} (共 ${byFile[id].length})`);
    if (!dry && wrote) {
      // 写整个文件 buffer 回 ISO 扇区（同大小，FILEPOS 不变）
      let wo = 0, wsec = blk * SECTOR;
      while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(wfd, d, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
      const nSec = Math.ceil(sz / BS);
      eccRanges.push([blk, blk + nSec - 1]);
    }
  }
  if (wfd) fs.closeSync(wfd);
  console.log(`\n总: 写回 ${totWrote}, 跳过 ${totSkip} (无RET ${totNoRet}, 标签不符 ${totTag}, 编码失败/缺字 ${totEnc}, 太长 ${totTooLong})`);
  const missTop = Object.entries(encMiss).sort((a, b) => b[1] - a[1]).slice(0, 30);
  if (missTop.length) console.log("缺字 top30 (字:次数): " + missTop.map(([c, n]) => `${c}:${n}`).join(" "));
  if (!dry && eccRanges.length) {
    console.log(`修 ECC ${eccRanges.length} 段…`);
    for (const [a, b] of eccRanges) spawnSync("python3", ["fix_ecc.py", String(a), String(b)], { stdio: "ignore" });
    console.log("完成。");
  }
}

// 文件过滤：支持单个 "1075"、范围 "1000-1143"、列表 "64,84,1075"、组合。返回 id→bool 谓词或 null。
function parseFilter(spec) {
  if (!spec) return null;
  const parts = spec.split(",").map(p => {
    if (p.includes("-")) { const [a, b] = p.split("-").map(Number); return [a, b]; }
    const n = Number(p); return [n, n];
  });
  return id => parts.some(([a, b]) => id >= a && id <= b);
}

const cmd = process.argv[2];
if (cmd === "verify") verify(process.argv[3] ? parseInt(process.argv[3]) : null);
else if (cmd === "dry") apply(true, parseFilter(process.argv[3]));
else if (cmd === "apply") apply(false, parseFilter(process.argv[3]));
else console.log("用法: node apply_field.mjs verify|dry|apply [fileId|范围|列表]  (如 1075 / 1000-1143 / 64,84)");
fs.closeSync(fd);
