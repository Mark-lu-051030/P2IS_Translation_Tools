// 提取"未被主管道提取"的字段文本（人物简介/场景文本等，散在自定义格式文件里）。
// 这些文件不是标准 scene_script（无 START 标记），但文本仍是标准 msg_script 控制码格式
// （{1101}换行、{1103}RET 结尾、{12xx}带参命令）。策略：
//   1. 顺序 msg.parse 解析对话（遇 RET 0x1103 结束，自动消费带参码）
//   2. 用"对话链 + CJK 密度"识别文本区，排除代码区/二进制产生的垃圾解析
//   3. 渲染成 JP 文本（字符 + <cXX/> 标签 + \n），输出到 out/field_text.json
// 用法: node extract_field_text.mjs [起 [止]]   默认扫全部未提取文件
import * as fss from "fs";
import * as fs from "fs/promises";
import * as lzss from "./lib/lzss.mjs";
import * as rle from "./lib/rle.mjs";
import * as msg from "./lib/msg_script.mjs";

const SECTOR = 0x930, BO = 24, BS = 2048;
const BACKUP = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";
const og = JSON.parse(fss.readFileSync("codetable_og.json", "utf8"));
const ogc = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) ogc[k] = v;

// 已被主管道提取的脚本文件（不再重复）
const extracted = new Set([3, 4, 90, 178]); for (let i = 181; i <= 577; i++) extracted.add(i);
// 名表/地图等已单独处理的，也跳过（138=strtbl, 97-136=map）
for (let i = 97; i <= 138; i++) extracted.add(i);

async function rblk(fp, fb, fsz) { const s = Buffer.alloc(SECTOR), o = Buffer.allocUnsafe(fsz); let off = 0, sec = fb * SECTOR; while (off < fsz) { await fp.read(s, 0, SECTOR, sec); const c = Math.min(BS, fsz - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; } return o; }

const cjk = s => { let n = 0; for (const c of s) if ((c >= "　" && c <= "鿿") || (c >= "＀" && c <= "￯")) n++; return n; };
const render = (items) => { let s = ""; for (const it of items) { if (typeof it === "number") s += ogc[String(it)] || `{${it.toString(16)}}`; else if (it[0] === 1) s += "\\n"; else if (it[0] === 3) { } else s += `<c${it[0].toString(16)}${it.length > 1 ? ":" + it.slice(1).join(",") : ""}/>`; } return s; };

// 走一个对话的字节长度（与 msg.parse 同步：遇 RET 结束，带参码消费 arg）。返回 end off 或 -1。
function dialogEnd(d, off) {
  let q = off;
  while (q + 1 < d.length) {
    const c = d.readUInt16LE(q); q += 2; const t = (c >> 12) & 0xf;
    if (t === 0) continue;            // 字符
    if (t === 1) { q += Math.max(0, ((c >> 8) & 0xf) - 1) * 2; if ((c & 0xff) === 3) return q; continue; }  // 命令(len=0视作0参,不可倒退否则死循环)
    return -1;                        // 非法 → 不是对话
  }
  return -1;
}

// 快速 CJK 密度: 统计 buffer 里映射到 CJK 字符的 uint16 数. 用于跳过纯二进制 buffer。
function cjkDensity(d) {
  const lim = Math.min(d.length, 0x40000);
  let cnt = 0; for (let p = 0; p + 1 < lim; p += 2) { const c = d.readUInt16LE(p); if (c > 0 && c < 0x1000) { const ch = ogc[String(c)]; if (ch && ch >= "　" && ch <= "鿿") cnt++; } }
  return cnt;
}

// 有界 sub 枚举：替代 archive.extract_files（后者在伪 archive 上会拆出上万假 sub 卡死）。
// 上限 300 sub，每个 sub 头部 len 必须合理，遇非法立即停。
function enumSubs(arch) {
  if (arch[0] < 1 || arch[0] > 3) return null;   // 非 archive 标志 → 当单文件(只扫 raw)
  const subs = [];
  let ptr = 0;
  while (ptr + 12 <= arch.length && subs.length < 300) {
    const type = arch[ptr];
    if (type === 0) {                              // 扇区填充
      if (arch.readUInt32LE(ptr) !== 0) break;
      ptr = (ptr & 0x7ff) ? ((ptr + 0x800) & ~0x7ff) : ptr + 0x800;
      continue;
    }
    if (type > 3) break;                           // 非法 sub 类型 → 停
    const len = arch.readUInt32LE(ptr + 4);
    if (len < 12 || ptr + len > arch.length) break;  // len 不合理 → 停
    subs.push(arch.slice(ptr, ptr + len));
    ptr += len; while (ptr & 3) ptr++;
  }
  return subs.length > 1 ? subs : null;
}

function extractFile(d) {
  // 先预筛：CJK 字符太少 → 纯二进制，跳过（省时）
  if (cjkDensity(d) < 30) return [];
  // RET 定界法：对话以 {1103}(RET) 结尾，相邻对话连续。先线性收集所有 RET 位置（偶对齐），
  // 每个 RET 用上一对话结束点作起点试解析一次 → O(RET数)，避免逐字节 O(n²)。
  const out = [];
  let prevEnd = 0;
  const nU = Math.floor(d.length / 2);
  for (let p = 0; p < nU; p++) {
    if (d.readUInt16LE(p * 2) !== 0x1103) continue;
    const retEnd = (p + 1) * 2;
    const start = prevEnd;
    prevEnd = retEnd;                 // 无论成功与否都推进，下个 RET 重新对齐
    if (retEnd - start > 4000) continue;   // 起点离太远 = 中间有非对话数据，跳过
    const end = dialogEnd(d, start);
    if (end !== retEnd) continue;     // 从 start 干净解析到正好这个 RET 才算对齐对话
    const items = msg.parse(d, start, true);
    if (!items) continue;
    const jp = render(items);
    if (cjk(jp) >= 3) out.push({ off: start, jp });
  }
  return out;
}

// 静音 lib 内的解压/解析调试输出（lzss DEBUG_SCRIPT 每次解压都 console.log，会刷屏拖慢）。
// 进度/汇总用 process.stderr.write，不走 console，故不受影响。
console.log = () => { };
console.error = () => { };
const log = (s) => process.stderr.write(s + "\n");

const start = process.argv[2] ? parseInt(process.argv[2]) : 0;
const end = process.argv[3] ? parseInt(process.argv[3]) : 1143;   // 真实文件表到 1143（原版 cdimage 漏读了 881-1143）

// 去重：构建 all_translatable.json 里已有日文的"归一化内容"集合（剥标签/空格/换行，只留实际字符）。
// 这些文件(46/47/64-72/84/138…)有些 strtbl 内容已翻，避免重复提取。
const norm = (s) => (s || "").replace(/<[^>]*>/g, "").replace(/\\n/g, "").replace(/[\s　\n]/g, "").replace(/\{[0-9a-f]+\}/g, "");
const seen = new Set();
try {
  const at = JSON.parse(fss.readFileSync("all_translatable.json", "utf8"));
  for (const e of at) {
    for (const p of (e.pages || [])) { const n = norm(p.jp); if (n.length >= 2) seen.add(n); }
    const m = norm(e.meta); if (m.length >= 2) seen.add(m);
  }
} catch { }
log(`已翻内容去重集: ${seen.size} 条`);

const bfp = await fs.open(BACKUP, "r");
const fpd = await rblk(bfp, 0x17, 0x2400);   // 读全文件表（>1144 条；原版只读 0x1b88=881）
let all = [];
let dedup = 0;
const perFile = [];
const scriptFiles = [];   // 含 START 标记 = 标准 scene_script，应走正式提取管道
for (let id = start; id <= end; id++) {
  if (extracted.has(id)) continue;
  const fb = fpd.readUInt32LE(id * 8), fsz = fpd.readUInt32LE(id * 8 + 4);
  if (!fsz || fsz > 0x1000000) continue;
  process.stderr.write(`\r处理 file ${id} (${(fsz / 1024 | 0)}KB)  已提取 ${all.length} 条          `);
  const _t0 = Date.now();
  process.stderr.write(`file ${id} (${(fsz / 1024 | 0)}KB) 读取…`);
  let arch; try { arch = await rblk(bfp, fb, fsz); } catch { process.stderr.write(" 读取失败\n"); continue; }
  if (arch.indexOf("START") >= 0) scriptFiles.push(id);   // 标准 scene_script（未被原管道提取的）
  process.stderr.write(` 扫描…`);
  // 待扫 buffer 列表：① 原始 buffer（未压缩文本，如 file 46）
  //                   ② archive 各 sub 解压后（RLE/LZSS 压缩的文本）
  const bufs = [{ tag: "", buf: arch }];
  if (!process.env.NODECOMP) {
    try {
      const files = enumSubs(arch);
      if (files && files.length > 1 && files.length < 400) {
        for (let si = 0; si < files.length; si++) {
          const sub = files[si];
          if (!sub || sub.length < 16) continue;
          const type = sub[1], tc = sub.readUInt32LE(4), uc = sub.readUInt32LE(8);
          // 严格校验，防坏头部导致超大/越界解压拖死：压缩类型必须 1/2，解压尺寸合理，压缩尺寸落在 sub 内
          if ((type === 1 || type === 2) && uc > 0 && uc < 0x40000 && tc > 12 && tc <= sub.length && (tc - 12) <= uc * 2) {
            try {
              const dc = (type === 1) ? rle.decompress(sub, 12, tc - 12, uc) : lzss.decompress(sub, 12, tc - 12, uc);
              if (dc && dc.length === uc) bufs.push({ tag: `_${si}d`, buf: dc });
            } catch { }
          }
        }
      }
    } catch { }
  }
  let cnt = 0, bi = 0;
  process.stderr.write(`(${bufs.length}buf)`);
  for (const { tag, buf } of bufs) {
    bi++;
    process.stderr.write(` b${bi}:${(buf.length / 1024 | 0)}K`);
    const ds = extractFile(buf);
    for (const x of ds) {
      if (seen.has(norm(x.jp))) { dedup++; continue; }   // 已翻(strtbl等)，跳过
      all.push({ id: `field:${id}${tag}:0x${x.off.toString(16)}`, jp: x.jp, zh: "" });
      cnt++;
    }
  }
  if (cnt) perFile.push([id, cnt]);
  process.stderr.write(`\rfile ${id} (${(fsz / 1024 | 0)}KB) bufs=${bufs.length} +${cnt}新 (${Date.now() - _t0}ms) 累计 ${all.length}            \n`);
}
await bfp.close();
fss.writeFileSync("out/field_text.json", JSON.stringify(all, null, 1));
log(`\n提取 ${all.length} 条新字段文本（已去重跳过 ${dedup} 条已翻）, 跨 ${perFile.length} 个文件 → out/field_text.json`);
perFile.sort((a, b) => b[1] - a[1]);
log("Top 文件 (id:条数): " + perFile.slice(0, 20).map(x => x[0] + ":" + x[1]).join("  "));
const newScripts = scriptFiles.filter(id => !(id === 3 || id === 4 || id === 90 || id === 178 || (id >= 181 && id <= 577)));
log(`含 START 的标准 script 文件: ${scriptFiles.length} 个; 其中未被原管道提取的(应补提取): [${newScripts.join(", ")}]`);
