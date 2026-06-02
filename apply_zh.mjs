/**
 * 把 out/scripts_zh/ 里编码好的对话写回 ISO（二进制补丁方式）。
 * 用法: node apply_zh.mjs <file_id> [sub_id]
 *   - 给 sub_id: 只处理该 sub
 *   - 不给 sub_id: 处理该 file 的所有 sub（推荐！避免互相覆盖）
 *
 * ⚠ 关键：一个 file 有多个 sub-file（如 file 90 有 160 个），它们在同一个 archive 里。
 *   必须一次性把所有 sub 的修改合并成一次 patch_archive_inplace，否则逐个 sub 写回会
 *   互相覆盖（每次从 backup 读 → 只保留最后一个 sub 的中文）。
 *
 * 流程：从备份读 archive → 对每个 sub 解压+替换对话+重压缩 → 一次 patch 所有 sub → 写回 + ECC
 */
import * as fs from "fs/promises";
import * as fss from "fs";
import * as archive from "./lib/archive.mjs";
import * as lzss from "./lib/lzss.mjs";
import * as rle from "./lib/rle.mjs";
import * as cdimage from "./lib/cdimage.mjs";
import { parse as parse_dialog, calculate_dialog_length, compile_msg } from "./lib/msg_script.mjs";
import { spawn } from "child_process";
import * as path from "path";
import { fileURLToPath } from "url";

const SECTOR = 0x930, BLOCK_OFF = 24, BLOCK_SIZE = 2048;
const BACKUP_ISO = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const SCRIPTS_ZH_DIR = path.join(__dirname, "out", "scripts_zh");
const REPORT_DIR = path.join(__dirname, "out", "build_report");
const FIX_ECC = path.join(__dirname, "fix_ecc.py");

const [, , FILE_ID_STR, SUB_ID_STR] = process.argv;
if (!FILE_ID_STR) {
  console.error("用法: node apply_zh.mjs <file_id> [sub_id]");
  process.exit(1);
}
const FILE_ID = parseInt(FILE_ID_STR);
const ONLY_SUB = SUB_ID_STR !== undefined ? parseInt(SUB_ID_STR) : null;

async function read_blocks(fp, file_block, file_size) {
  const sector = Buffer.alloc(SECTOR);
  const output = Buffer.allocUnsafe(file_size);
  let off = 0, sec = file_block * SECTOR;
  while (off < file_size) {
    await fp.read(sector, 0, SECTOR, sec);
    const chunk = Math.min(BLOCK_SIZE, file_size - off);
    sector.copy(output, off, BLOCK_OFF, BLOCK_OFF + chunk);
    off += chunk; sec += SECTOR;
  }
  return output;
}

// 处理一个 sub-file，返回 { recomp, report } 或 null（无翻译/无变化）
function processSub(arch_buf, sub_id) {
  const zh_path = path.join(SCRIPTS_ZH_DIR, `${FILE_ID}_${sub_id}.json`);
  if (!fss.existsSync(zh_path)) return null;
  const new_dialogs = JSON.parse(fss.readFileSync(zh_path, "utf-8")).dialogs;

  const files = archive.extract_files(arch_buf);
  const sub = files[sub_id];
  if (!sub) return null;
  const comp_type = sub[1];   // 1=RLE, 2=LZSS
  const total_comp  = sub.readUInt32LE(4);
  const uncomp_size = sub.readUInt32LE(8);
  let orig;
  if (comp_type === 1) {
    orig = rle.decompress(sub, 12, total_comp - 12, uncomp_size);
  } else {
    orig = lzss.decompress(sub, 12, total_comp - 12, uncomp_size);
  }

  // 扫指令表找 diag 偏移
  const script_ptr = orig.readUInt32LE(12);
  const arg_ptr    = orig.readUInt32LE(16);
  const diag_ptr   = orig.readUInt32LE(20);
  const off_to_arg_ptrs = new Map();
  for (let ip = script_ptr; ip < arg_ptr; ip += 8) {
    const op = orig.readUInt16LE(ip);
    if (op === 0x13 || op === 0x10f) {
      const asp = orig.readUInt32LE(ip + 4);
      const doff = orig.readUInt32LE(asp);
      if (!off_to_arg_ptrs.has(doff)) off_to_arg_ptrs.set(doff, []);
      off_to_arg_ptrs.get(doff).push(asp);
    }
  }
  const raw_diag_list = [...off_to_arg_ptrs.keys()].sort((a, b) => a - b);
  const final_offsets = {}, diag_to_arg_ptrs = {};
  raw_diag_list.forEach((off, i) => {
    final_offsets[`diag${i}`] = diag_ptr + off;
    diag_to_arg_ptrs[`diag${i}`] = off_to_arg_ptrs.get(off);
  });

  const modified = Buffer.from(orig);
  let changed = 0;
  const report = { file: FILE_ID, sub: sub_id, success: [], skipped: [] };
  const to_append = [];

  for (const [diag_name, new_items] of Object.entries(new_dialogs)) {
    if (!(diag_name in final_offsets)) {
      report.skipped.push({ diag: diag_name, reason: "no_offset", detail: "dialog 不在 script 的指令表里" });
      continue;
    }
    if (!Array.isArray(new_items)) {
      report.skipped.push({ diag: diag_name, reason: "not_array", detail: "new_items 不是数组" });
      continue;
    }
    const abs_off = final_offsets[diag_name];
    const orig_diag = parse_dialog(orig.slice(diag_ptr), abs_off - diag_ptr, true);
    if (!orig_diag) {
      report.skipped.push({ diag: diag_name, reason: "parse_failed", detail: "parse_dialog 返回 falsy" });
      continue;
    }
    const orig_len = calculate_dialog_length(orig_diag);
    const new_len  = calculate_dialog_length(new_items);
    if (new_len > orig_len) {
      to_append.push({ diag_name, new_items, new_len, orig_len });
      continue;
    }
    compile_msg(new_items, modified, abs_off);
    if (new_len < orig_len) modified.fill(0, abs_off + new_len, abs_off + orig_len);
    report.success.push({ diag: diag_name, new_len, orig_len });
    changed++;
  }

  // 追加超长对话
  const appended_chunks = [];
  let append_offset = modified.byteLength;
  for (const { diag_name, new_items, new_len, orig_len } of to_append) {
    const buf = Buffer.alloc(new_len);
    compile_msg(new_items, buf, 0);
    appended_chunks.push(buf);
    const new_diag_off = append_offset - diag_ptr;
    for (const ap of diag_to_arg_ptrs[diag_name]) modified.writeUInt32LE(new_diag_off, ap);
    modified.fill(0, final_offsets[diag_name], final_offsets[diag_name] + orig_len);
    report.success.push({ diag: diag_name, new_len, orig_len, relocated: true });
    append_offset += new_len;
    changed++;
  }
  let final_buf = appended_chunks.length ? Buffer.concat([modified, ...appended_chunks]) : modified;

  if (changed === 0) return { recomp: null, report };

  // 重压缩：RLE 文件(byte[1]==1)仍压成 RLE，LZSS 仍 LZSS —— 绝不改 byte[1]。
  // ⚠ 关键修复(2026-06-01)：旧版强制 r[1]=2 把 RLE 剧情/战斗脚本(file 3/4 等)的
  //   subtype 从 1 改成 2，cutscene/战斗引擎据 byte[1] 走错处理 → 进场景纯白屏。
  //   实证：53d3c1a(RLE文件未翻=原版RLE)正常 vs c408510(RLE翻成LZSS,byte1=2)白屏。
  function compress_with_header(buf) {
    const r = comp_type === 1 ? rle.compress(buf, 0xc) : lzss.compress(buf, 0xc, true);
    r.writeUInt32LE(sub.readUInt32LE(0), 0);   // 保留原 tag（byte[1]=subtype 保持不变）
    r.writeUInt32LE(r.byteLength, 4);
    r.writeUInt32LE(buf.byteLength, 8);
    // ⚠ 紧排 archive（如 file 90）的 sub 之间无 sector padding。若 recomp 比原 sub 短，
    //   留下的 0 会被 extract_files 误判为 sector padding → 后续 sub 错位/损坏。
    //   解决：把 recomp 补齐到原 sub 的"对齐长度"，并让 len 字段=补齐后长度（解压看 uncomp_size 停，多余字节无害）。
    const orig_padded = (sub.byteLength + 3) & ~3;   // 原 sub 4字节对齐占用
    if (r.byteLength < orig_padded) {
      const padded = Buffer.alloc(orig_padded);
      r.copy(padded);
      padded.writeUInt32LE(orig_padded, 4);   // len = 补齐后长度，保持 sub 边界不变
      return padded;
    }
    return r;
  }
  let recomp = compress_with_header(final_buf);

  // 容量检查：若 append 版太大，回退 in-place only
  // （这里不能单独 patch 验证，留给主流程合并 patch 时统一 try）
  return { recomp, report, orig, final_offsets, new_dialogs, to_append, sub, compress_with_header };
}

// ── 主流程 ────────────────────────────────────────────
const backup_fp = await fs.open(BACKUP_ISO, "r");
const fileposdat = await read_blocks(backup_fp, 0x17, 0x1b88);
const file_block = fileposdat.readUInt32LE(FILE_ID * 8);
const file_size  = fileposdat.readUInt32LE(FILE_ID * 8 + 4);
const arch_buf = await read_blocks(backup_fp, file_block, file_size);
await backup_fp.close();
console.log(`File ${FILE_ID}: block=${file_block}, size=${file_size}`);

// 找出要处理的 sub 列表
let sub_ids;
if (ONLY_SUB !== null) {
  sub_ids = [ONLY_SUB];
} else {
  sub_ids = fss.readdirSync(SCRIPTS_ZH_DIR)
    .map(f => f.match(new RegExp(`^${FILE_ID}_(\\d+)\\.json$`)))
    .filter(Boolean).map(m => parseInt(m[1])).sort((a, b) => a - b);
}

// 处理每个 sub，收集 recomp
const replacements = {};   // sub_id → recomp
const results = [];
fss.mkdirSync(REPORT_DIR, { recursive: true });
for (const sid of sub_ids) {
  const r = processSub(arch_buf, sid);
  if (!r) continue;
  fss.writeFileSync(path.join(REPORT_DIR, `${FILE_ID}_${sid}.json`), JSON.stringify(r.report, null, 2));
  results.push({ sid, r });
  if (r.recomp) replacements[sid] = r.recomp;
}

const nSucc = results.reduce((s, x) => s + x.r.report.success.length, 0);
console.log(`处理 ${results.length} 个 sub，共 ${nSucc} 条对话成功`);

if (Object.keys(replacements).length === 0) {
  console.log("没有对话被修改，退出。");
  process.exit(0);
}

// 一次性 patch 所有 sub
// 先对有 append 的 sub 预生成 in-place 版本（避免 append 超容量）
// 然后逐 sub 验证容量，塞不下的直接从 replacements 删除（保留原日文 sub，不破坏 archive）
const resultMap = {};
for (const { sid, r } of results) resultMap[sid] = r;

// 生成某 sub 的 in-place only 版本（不 append，超长 diag 保留原文）
function inplaceRecomp(r) {
  const mod = Buffer.from(r.orig);
  for (const succ of r.report.success) {
    if (succ.relocated) continue;  // append 的不原地写
    const ni = r.new_dialogs[succ.diag];
    const ao = r.final_offsets[succ.diag];
    compile_msg(ni, mod, ao);
    if (succ.new_len < succ.orig_len) mod.fill(0, ao + succ.new_len, ao + succ.orig_len);
  }
  return r.compress_with_header(mod);
}

// 三级降级试 patch：
//   1. 先全用 append 版（保留 relocate，译文完整）
//   2. 某 sub 超容量 → 该 sub 回退 in-place（放弃它的 append diag，标 too_big）
//   3. in-place 仍超 → drop 该 sub（整个保留原日文）
let patched;
let dropped = [], fellback = [];
const triedInplace = new Set();
for (let attempt = 0; attempt < 500; attempt++) {
  try {
    patched = archive.patch_archive_inplace(arch_buf, replacements);
    break;
  } catch (err) {
    const m = err.message.match(/Sub-file (\d+):/);
    if (!m) throw err;
    const bad = parseInt(m[1]);
    if (!(bad in replacements)) throw err;
    const r = resultMap[bad];
    if (r && r.to_append && r.to_append.length && !triedInplace.has(bad)) {
      // 先尝试回退 in-place（保留能原地写的，放弃 append 的）
      triedInplace.add(bad);
      replacements[bad] = inplaceRecomp(r);
      fellback.push(bad);
      for (const s of r.report.success.filter(s => s.relocated)) {
        r.report.skipped.push({ diag: s.diag, reason: "too_big", detail: "append 超容量，保留原文" });
      }
      r.report.success = r.report.success.filter(s => !s.relocated);
      fss.writeFileSync(path.join(REPORT_DIR, `${FILE_ID}_${bad}.json`), JSON.stringify(r.report, null, 2));
      continue;
    }
    // in-place 仍超 → drop
    delete replacements[bad];
    dropped.push(bad);
    if (r) {
      for (const s of r.report.success) r.report.skipped.push({ diag: s.diag, reason: "too_big", detail: "重压缩超 archive 容量，保留原文" });
      r.report.success = [];
      fss.writeFileSync(path.join(REPORT_DIR, `${FILE_ID}_${bad}.json`), JSON.stringify(r.report, null, 2));
    }
  }
}
if (fellback.length) console.warn(`⚠ ${fellback.length} 个 sub 的 append 超容量，回退 in-place: ${fellback.join(',')}`);
if (dropped.length) console.warn(`⚠ ${dropped.length} 个 sub 太长塞不下，保留原文: ${dropped.join(',')}`);

// 写回 working ISO
const cd = await cdimage.init();
await cdimage.write_file(cd, FILE_ID, patched);
await cdimage.close(cd);

const patched_sectors = Math.ceil(patched.byteLength / BLOCK_SIZE);
const ecc_end = file_block + patched_sectors - 1;
console.log(`写入完成。修复 ECC: FILEPOS (23-26) + file ${FILE_ID} (${file_block}-${ecc_end})`);

const run = (args) => new Promise((resolve, reject) => {
  const p = spawn("python3", [FIX_ECC, ...args], { stdio: "inherit" });
  p.on("exit", code => code === 0 ? resolve() : reject(new Error(`fix_ecc.py exited ${code}`)));
});
await run(["23", "26"]);
await run([String(file_block), String(ecc_end)]);
