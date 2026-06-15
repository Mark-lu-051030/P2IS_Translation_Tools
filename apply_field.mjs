// 字段文本回插（原位等长）。第一步：--verify 校验编码器正确性（read-only，不写 ISO）。
// 把每条提取出来的 jp 文本重新编码成 uint16 码 + RET，和原文件该 offset 的字节逐一比对。
// 全等 → 编码器(render 的逆)正确，原位等长写回才可靠。
//
// 用法:
//   node apply_field.mjs verify [fileId]   # 校验某文件(默认全部 field_text 涉及的文件)的 jp round-trip
import fs from "fs";
import * as lzss from "./lib/lzss.mjs";
import * as rle from "./lib/rle.mjs";

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
      const j = s.indexOf(">", i);
      let tag = j >= 0 ? s.slice(i + 1, j) : null;
      if (tag && tag.endsWith("/")) tag = tag.slice(0, -1);
      // 形如 c5:0,0 或 c6
      const m = tag ? tag.match(/^c([0-9a-f]+)(?::(.*))?$/) : null;
      if (m) {
        const cmd = parseInt(m[1], 16);
        const args = m[2] ? m[2].split(",").map(x => parseInt(x, 10)) : [];
        const len = 1 + args.length;
        codes.push(0x1000 | (len << 8) | cmd);
        for (const a of args) codes.push(a & 0xffff);
        i = j + 1;
      } else {
        // 不是合法 cXX 控制码标签 → 检查是否是已知的"非控制码占位符"
        // 这些是翻译时用来标记变量/动作的文本，不是真正的控制码，应整体保留
        const KNOWN_PLACEHOLDERS = [
          "舞耶跳下", "前", "舞耶", "克哉", "荣吉", "丽莎", "淳", "达哉", "报复",
          "银子", "雪野", "鼻血子", "花姐", "米歇尔", "丽", "无名", "JOKER", "绕道而行",
          "憎恨", "不憎恨", "自己可能也做过同样的事", "即使痛苦也要忍耐",
          // 新增：
          "迂回する",           // 日文占位符（保留日文的）
          "憎い", "憎くない",   // 日文选项
          "自分も同じ事をしたかもしれない",  // 日文选项
          "辛くても耐えろ",     // 日文选项
          "黛淳",               // 黑须淳的另一种称呼
          "ギンコ",             // 银子（日文）
          "黒須",               // 黑须
        ];
        const isPlaceholder = KNOWN_PLACEHOLDERS.some(p => tag === p);
        if (isPlaceholder) {
          // 整体作为普通文本编码：先编码 '<'，再编码内容，最后编码 '>'
          const lt = charToCode["<"];
          const gt = charToCode[">"];
          if (lt === undefined || gt === undefined) {
            ok = false; if (!miss) miss = "<或>"; codes.push(0);
          } else {
            codes.push(lt);
            for (const ch of tag) {
              const c = charToCode[ch];
              if (c === undefined) { ok = false; if (!miss) miss = ch; codes.push(0); }
              else codes.push(c);
            }
            codes.push(gt);
          }
          i = j + 1;
        } else {
          // 不是已知占位符 → 只把 '<' 当普通字符编码
          const c = charToCode["<"];
          if (c === undefined) { ok = false; if (!miss) miss = "<"; codes.push(0); } else codes.push(c);
          i += 1;
        }
      }
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

// 标签守恒比对用的归一化 key：剔除装饰性版面码 <c20/>（分句/缩进标记, DeepSeek 重组句子时
// 常丢 1 个; 丢了只是版面略变, 显示中文远好过整条退回日文）。其余结构码(c1d/c1e/c5/c6/c2/ce…)仍严格。
const COSMETIC_TAGS = new Set(["<c20/>"]);
// 标签守恒比对用的归一化 key：仅保留真正的控制码（cXX 格式），剔除装饰码 <c20/> 和所有占位符文本。
const tagKey = (s) => (s.match(/<[^>]+>/g) || [])
  .filter(t => {
    const inner = t.replace(/^<|>$/g, '').replace(/\/$/, '');  // 去掉尖括号和尾部斜杠
    // 只保留 c 开头 + 十六进制数字 的控制码（如 c5:15, c1d:11, c6 等）
    return /^c[0-9a-f]+/i.test(inner) && !COSMETIC_TAGS.has(t);
  })
  .sort().join();

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

// 检测字符串表文件：[count u32][count×u32 指针][字符串区]，首指针 == count*4+4。
function isStringTable(d) {
  if (d.length < 12) return false;
  const count = d.readUInt32LE(0);
  if (count < 2 || count > 100000 || count * 4 + 8 > d.length) return false;
  if (d.readUInt32LE(4) !== count * 4 + 4) return false;   // 首指针紧接指针表后
  const lo = count * 4 + 4;
  for (let i = 0; i < count; i++) {
    const p = d.readUInt32LE(4 + i * 4);
    if (p < lo || p > d.length) return false;               // 指针须落在字符串区内(允许 dedup 重复/回指)
  }
  return true;
}

// 解码 d 在 off 处的字符串为 jp 文本(与 extract_field_text 的 render 完全一致, 遇 RET 停)。
// 用于按"内容"匹配译文(offset 因对齐对不齐, 不可靠)。
function renderAt(d, off) {
  let s = "", q = off;
  while (q + 1 < d.length) {
    const c = d.readUInt16LE(q); q += 2; const t = (c >> 12) & 0xf;
    if (t === 0) { s += ogc[String(c)] || `{${c.toString(16)}}`; continue; }
    if (t === 1) {
      const cmd = c & 0xff, len = (c >> 8) & 0xf, args = [];
      for (let k = 1; k < len; k++) { args.push(d.readUInt16LE(q)); q += 2; }
      if (cmd === 1) s += "\\n";
      else if (cmd === 3) return s;                 // RET 结束
      else s += `<c${cmd.toString(16)}${args.length ? ":" + args.join(",") : ""}/>`;
      continue;
    }
    return s;
  }
  return s;
}

// 重建字符串表（不缩短）：解析 count+指针，每条按 jp 内容查 zh、重新编码(变长)，更新指针，整表装回原区域。
// 中文整体更短 → 装得下。entries: [{jp,zh}]。原地改 d。返回 {ok, wrote, kept, total, regionEnd}。
function rebuildTable(d, entries, encodeFn) {
  const jpToZh = new Map();
  for (const e of entries) if (e.zh && e.zh.trim()) jpToZh.set(e.jp, e.zh);
  const count = d.readUInt32LE(0);
  const ptrTableEnd = count * 4 + 4;
  const ptrs = [];
  for (let i = 0; i < count; i++) ptrs.push(d.readUInt32LE(4 + i * 4));
  const uniq = [...new Set(ptrs)].sort((a, b) => a - b);
  // regionEnd = 最后一条字符串的结束(扫到 RET)
  const lastP = uniq[uniq.length - 1];
  let regionEnd = d.length;
  for (let q = lastP; q + 1 < d.length; q += 2) { if (d.readUInt16LE(q) === 0x1103) { regionEnd = q + 2; break; } if (q - lastP > 8000) break; }
  // 每个 unique 指针的原始字节 [p, 下一个unique指针 或 regionEnd)
  const origBytes = new Map();
  for (let j = 0; j < uniq.length; j++) {
    const p = uniq[j], e = (j + 1 < uniq.length) ? uniq[j + 1] : regionEnd;
    origBytes.set(p, Buffer.from(d.subarray(p, e)));   // 拷贝(防 nt.copy(d) 后别名失效)
  }
  // 每个 unique 指针的新字节：能译则 zh 编码+RET，否则保留原字节
  let wrote = 0, kept = 0;
  const newBytes = new Map();
  for (const p of uniq) {
    const jp = renderAt(d, p);                 // 按内容匹配(避开 offset 对齐问题)
    const zh = jpToZh.get(jp);
    let bytes = null;
    if (zh) {
      const { codes, ok } = encodeFn(zh, rev);
      if (ok && tagKey(jp) === tagKey(zh)) {
        const buf = Buffer.alloc(codes.length * 2 + 2);
        for (let k = 0; k < codes.length; k++) buf.writeUInt16LE(codes[k], k * 2);
        buf.writeUInt16LE(0x1103, codes.length * 2);
        bytes = buf; wrote++;
      }
    }
    if (!bytes) { bytes = origBytes.get(p); kept++; }
    newBytes.set(p, bytes);
  }
  // 组装：指针表后顺序排新字符串
  const newOff = new Map();
  let cur = ptrTableEnd;
  for (const p of uniq) { newOff.set(p, cur); cur += newBytes.get(p).length; }
  if (cur > regionEnd) return { ok: false };                // 装不下(罕见) → 放弃重建此表
  const nt = Buffer.alloc(regionEnd);
  nt.writeUInt32LE(count, 0);
  for (let i = 0; i < count; i++) nt.writeUInt32LE(newOff.get(ptrs[i]), 4 + i * 4);
  for (const p of uniq) newBytes.get(p).copy(nt, newOff.get(p));
  nt.copy(d, 0);                                            // 覆写 [0, regionEnd)，其余保留
  return { ok: true, wrote, kept, total: cur, regionEnd };
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
const WORK = process.env.P2IS_WORK_ISO || "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
// 整文件级跳过。1102 等的崩溃由下面的"结构性条目过滤"解决：只跳过被误提取的
// 文件头/指针表条目(「密集)，真正的文本消息照常翻译。验证过 apply 1102 在过滤后正常。
//
// file 160 = F0160.EXT，片头 ATLUS 影片(STR)。ISO9660 大小 4503552，但 FILEPOS[160]
// 过读到 5136864(多 309 扇区)。提取器把影片之后过读区里的角色立绘情绪标签
// (`01_英雄(18岁)通常`/`笑い`/`怒り`…，玩家永不可见)误当字段文本提取，apply 会把它们
// 写进 offset 4.75MB+。这块仍在 FILEPOS[160] 过读范围内，若播放器按 FILEPOS 大小整段
// 读进 STR 解码 → 尾端破音(有玩家反馈片头有破音)。这些标签翻译零收益，整文件跳过，
// 让 file 160 与原版逐字节一致。
const SKIP_FILES = new Set([160]);
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

function apply(dry, fileFilter, dump) {
  const toolong = [];   // dump 模式：收集"太长"条目供重译更短
  const tagmiss = [], misschar = [];   // dump 模式：收集"标签不符""缺字"条目供排查
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
    // 仅对"未注册 strtbl 的字符串表文件"(如 1103/1106/1102, >881)重建——apply_strtbl 够不到;
    // 已注册的(64-72 等)由 apply_strtbl 处理, apply_field 不碰(防冲突)。按 jp 内容匹配译文。
    const isTable = isStringTable(d) && !strtblRegions[id];
    if (isTable) {
      // 字符串表文件 → 重建(变长,不缩短,不会太长)。dry/dump 不重建(表文件无"太长")。
      if (!dry) {
        const r = rebuildTable(d, byFile[id], encodeText);
        if (r.ok) { wrote = r.wrote; console.log(`file ${id}: [字符串表重建] 写 ${r.wrote} / 保留 ${r.kept} (${r.total}/${r.regionEnd}B)`); }
        else console.log(`file ${id}: [字符串表重建] 装不下→跳过(未改)`);
      } else {
        console.log(`file ${id}: [字符串表] ${byFile[id].length} 条 → apply 时重建(无太长)`);
      }
    } else {
      for (const { off, jp, zh: zhtext } of byFile[id]) {
        const end = dialogEnd(d, off); if (end < 0) { totNoRet++; skip++; continue; }
        const spanCodes = (end - off) / 2;                   // 含结尾 RET
        // 标签守恒检查(忽略装饰码 <c20/>)
        if (tagKey(jp) !== tagKey(zhtext)) { totTag++; skip++; tagmiss.push({ id: `field:${id}:0x${off.toString(16)}`, jp, zh: zhtext }); continue; }
        const { codes, ok, miss } = encodeText(zhtext, rev);
        if (!ok) { totEnc++; if (miss) encMiss[miss] = (encMiss[miss] || 0) + 1; skip++; misschar.push({ id: `field:${id}:0x${off.toString(16)}`, jp, zh: zhtext, miss }); continue; }
        if (codes.length + 1 > spanCodes) {
          totTooLong++; skip++;
          // 导出供重译更短：budget = jp 可见字符数(去标签/换行), zh 须 ≤ 此数
          const vis = jp.replace(/<[^>]*>/g, "").replace(/\\n/g, "").length;
          toolong.push({ id: `field:${id}:0x${off.toString(16)}`, jp, oldzh: zhtext, budget: vis });
          continue;
        }
        // 写：zh codes + RET(紧跟,避免逐字"打字"渲染 padding 卡住) + 余下填充(RET 后不会被读)
        for (let k = 0; k < codes.length; k++) d.writeUInt16LE(codes[k], off + k * 2);
        let p = off + codes.length * 2;
        d.writeUInt16LE(0x1103, p); p += 2;
        for (let k = codes.length + 1; k < spanCodes; k++) { d.writeUInt16LE(FW, p); p += 2; }
        wrote++;
      }
      console.log(`file ${id}: 写 ${wrote} / 跳过 ${skip} (共 ${byFile[id].length})`);
    }
    totWrote += wrote; totSkip += skip;
    if (!dry && wrote) {
      // 写整个文件 buffer 回 ISO 扇区（同大小，FILEPOS 不变）
      let wo = 0, wsec = blk * SECTOR;
      while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(wfd, d, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
      const nSec = Math.ceil(sz / BS);
      eccRanges.push([blk, blk + nSec - 1]);
    }
  }
  // ── 归档子文件(压缩)字段文本回插 ──────────────────────────────
  // id 形如 field:FILE_SId:0xOFF。FILE=多子文件归档(1112-1117/77 等), SI=enumSubs 序号,
  // OFF=该 sub 解压后 buffer 内偏移。逐 sub: 解压→原位等长改→重压缩(保留头tag)→塞回原 sub 槽
  // (≤槽则写+槽内补零, 否则跳过保原)。sub 偏移不动(多为扇区对齐), 文件总大小不变, FILEPOS 不变。
  const arcByFile = {};
  for (const e of zh) {
    if (!e.zh || !e.zh.trim()) continue;
    const m = e.id.match(/^field:(\d+)_(\d+)d:0x([0-9a-f]+)$/);
    if (!m) continue;
    const id = parseInt(m[1]), si = parseInt(m[2], 10), off = parseInt(m[3], 16);
    if (fileFilter && !fileFilter(id)) continue;
    if (isStructural(e.jp)) continue;
    const f = (arcByFile[id] = arcByFile[id] || {});
    (f[si] = f[si] || []).push({ off, jp: e.jp, zh: e.zh });
  }
  for (const id of Object.keys(arcByFile).map(Number).sort((a, b) => a - b)) {
    const arch = rfile(id, wfd || fd); if (!arch) continue;
    const blk = o.readUInt32LE(id * 8), sz = o.readUInt32LE(id * 8 + 4);
    // enumSubs(带偏移): 与 extract_field_text 同逻辑
    const subs = []; let ptr = 0;
    while (ptr + 12 <= arch.length && subs.length < 300) {
      const t = arch[ptr];
      if (t === 0) { if (arch.readUInt32LE(ptr) !== 0) break; ptr = (ptr & 0x7ff) ? ((ptr + 0x800) & ~0x7ff) : ptr + 0x800; continue; }
      if (t > 3) break;
      const len = arch.readUInt32LE(ptr + 4); if (len < 12 || ptr + len > arch.length) break;
      subs.push({ off: ptr, len }); ptr += len; while (ptr & 3) ptr++;
    }
    let fileWrote = 0;
    for (const si of Object.keys(arcByFile[id]).map(Number).sort((a, b) => a - b)) {
      const sub = subs[si]; if (!sub) continue;
      const type = arch[sub.off + 1], tc = arch.readUInt32LE(sub.off + 4), uc = arch.readUInt32LE(sub.off + 8);
      if (!((type === 1 || type === 2) && uc > 0 && uc < 0x40000 && tc > 12 && tc <= sub.len && (tc - 12) <= uc * 2)) continue;
      let dc; try { dc = (type === 1) ? rle.decompress(arch, sub.off + 12, tc - 12, uc) : lzss.decompress(arch, sub.off + 12, tc - 12, uc); } catch { continue; }
      if (!dc || dc.length !== uc) continue;
      dc = Buffer.from(dc);
      let subWrote = 0;
      for (const { off, jp, zh: zhtext } of arcByFile[id][si]) {
        const end = dialogEnd(dc, off); if (end < 0) { totNoRet++; totSkip++; continue; }
        const spanCodes = (end - off) / 2;
        if (tagKey(jp) !== tagKey(zhtext)) { totTag++; totSkip++; tagmiss.push({ id: `field:${id}_${si}d:0x${off.toString(16)}`, jp, zh: zhtext }); continue; }
        const { codes, ok, miss } = encodeText(zhtext, rev);
        if (!ok) { totEnc++; if (miss) encMiss[miss] = (encMiss[miss] || 0) + 1; totSkip++; misschar.push({ id: `field:${id}_${si}d:0x${off.toString(16)}`, jp, zh: zhtext, miss }); continue; }
        if (codes.length + 1 > spanCodes) {
          totTooLong++; totSkip++;
          const vis = jp.replace(/<[^>]*>/g, "").replace(/\\n/g, "").length; toolong.push({ id: `field:${id}_${si}d:0x${off.toString(16)}`, jp, oldzh: zhtext, budget: vis });
          continue;
        }
        for (let k = 0; k < codes.length; k++) dc.writeUInt16LE(codes[k], off + k * 2);
        let p = off + codes.length * 2;
        dc.writeUInt16LE(0x1103, p); p += 2;
        for (let k = codes.length + 1; k < spanCodes; k++) { dc.writeUInt16LE(FW, p); p += 2; }
        subWrote++;
      }
      if (dry || !subWrote) continue;
      // ⚠ 重压必须保持 tc 与原 sub 完全一致(compress_to_size 用有效 token 精确填满):
      //   游戏按 tc 链式定位同组后续 sub(本函数 354 行的 ptr+=len 就是同款走法),
      //   tc 变短 → 同组后续 sub 全部错位 → 错位垃圾被当压缩数据解压 → 白屏/卡死
      //   (实证: 変異台词 file77 归档 sub 链条错位 = v0.3.0 融合白屏根因, RAM 0x800ad870 错位类MIPS垃圾)。
      let recomp;
      try { recomp = (type === 2) ? lzss.compress_to_size(dc, 12, tc) : rle.compress_to_size(dc, 12, tc); } catch { recomp = null; }
      if (!recomp) { console.log(`file ${id}_${si}d 压不进原tc(${tc}),跳过保原`); continue; }
      arch.copy(recomp, 0, sub.off, sub.off + 4);
      recomp.writeUInt32LE(tc, 4); recomp.writeUInt32LE(dc.length, 8);
      recomp.copy(arch, sub.off);   // 长度==tc, tc 之后到下一 sub 的原始对齐字节不动
      fileWrote += subWrote;
      console.log(`file ${id}_${si}d: [归档sub重压] 写 ${subWrote} (精确填满原tc ${tc})`);
    }
    totWrote += fileWrote;
    if (!dry && fileWrote) {
      let wo = 0, wsec = blk * SECTOR;
      while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(wfd, arch, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
      const nSec = Math.ceil(sz / BS); eccRanges.push([blk, blk + nSec - 1]);
    }
  }

  if (wfd) fs.closeSync(wfd);
  console.log(`\n总: 写回 ${totWrote}, 跳过 ${totSkip} (无RET ${totNoRet}, 标签不符 ${totTag}, 编码失败/缺字 ${totEnc}, 太长 ${totTooLong})`);
  const missTop = Object.entries(encMiss).sort((a, b) => b[1] - a[1]).slice(0, 30);
  if (missTop.length) console.log("缺字 top30 (字:次数): " + missTop.map(([c, n]) => `${c}:${n}`).join(" "));
  // 三个诊断 json 在 dry / dumptoolong / apply 都刷新（apply 读 WORK，是真实落地状态，
  // 才是该照着修的"太长/缺字/标签不符"清单；dumptoolong 读原版副本会漏掉被前序 apply 挤短的占位）。
  fs.writeFileSync("out/field_toolong.json", JSON.stringify(toolong, null, 1));
  fs.writeFileSync("out/field_tagmiss.json", JSON.stringify(tagmiss, null, 1));
  fs.writeFileSync("out/field_misschar.json", JSON.stringify(misschar, null, 1));
  console.log(`\n导出: 太长 ${toolong.length} → field_toolong.json, 标签不符 ${tagmiss.length} → field_tagmiss.json, 缺字 ${misschar.length} → field_misschar.json`);
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
else if (cmd === "dumptoolong") apply(true, parseFilter(process.argv[3]), true);   // 导出太长条目(dry, 不写ISO)
else console.log("用法: node apply_field.mjs verify|dry|apply|dumptoolong [fileId|范围|列表]");
fs.closeSync(fd);
