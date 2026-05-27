/**
 * 把 out/scripts_zh/ 里编码好的对话写回 ISO（二进制补丁方式）。
 * 用法: node apply_zh.mjs <file_id> <sub_id>
 * 例:   node apply_zh.mjs 181 8
 *
 * 流程：从备份读原始数据 → 解压 → 替换对话字节 → 重压缩 → 写回主 ISO → 输出 ECC 命令
 */
import * as fs from "fs/promises";
import * as archive from "./lib/archive.mjs";
import * as lzss from "./lib/lzss.mjs";
import * as cdimage from "./lib/cdimage.mjs";
import { parse as parse_dialog, calculate_dialog_length, compile_msg } from "./lib/msg_script.mjs";

const SECTOR = 0x930, BLOCK_OFF = 24, BLOCK_SIZE = 2048;
const BACKUP_ISO = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";

const [, , FILE_ID_STR, SUB_ID_STR] = process.argv;
if (!FILE_ID_STR || !SUB_ID_STR) {
  console.error("用法: node apply_zh.mjs <file_id> <sub_id>");
  process.exit(1);
}
const FILE_ID = parseInt(FILE_ID_STR);
const SUB_ID  = parseInt(SUB_ID_STR);

const zh_path = `out/scripts_zh/${FILE_ID}_${SUB_ID}.json`;
const zh_script = JSON.parse(await fs.readFile(zh_path, "utf-8"));
const new_dialogs = zh_script.dialogs;  // { diag0: [...], diag1: [...], ... }

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

// 1. 从备份读取目标文件
const backup_fp = await fs.open(BACKUP_ISO, "r");
const fileposdat = await read_blocks(backup_fp, 0x17, 0x1b88);
const file_block = fileposdat.readUInt32LE(FILE_ID * 8);
const file_size  = fileposdat.readUInt32LE(FILE_ID * 8 + 4);
console.log(`File ${FILE_ID}: block=${file_block}, size=${file_size}`);
const arch_buf = await read_blocks(backup_fp, file_block, file_size);
await backup_fp.close();

// 2. 解压 sub-file
const files = archive.extract_files(arch_buf);
const sub = files[SUB_ID];
const total_comp  = sub.readUInt32LE(4);
const uncomp_size = sub.readUInt32LE(8);
const orig = lzss.decompress(sub, 12, total_comp - 12, uncomp_size);

// 3. 找到各对话的偏移（从指令表扫描 op=0x13/0x10f 的参数）
const script_ptr = orig.readUInt32LE(12);
const arg_ptr    = orig.readUInt32LE(16);
const diag_ptr   = orig.readUInt32LE(20);

// 扫描所有指令找 diag 偏移
// 指令结构: [op:2][imm:2][arg_section_ptr:4]
// arg_section_ptr 指向参数区，参数区里存 uint32 参数值
// 对于 op 0x13/0x10f，第一个参数是 dialog 偏移（相对于 diag_ptr）
// 同一个 diag_off 可能被多条指令引用，要全部记下来以便后续重定向
const off_to_arg_ptrs = new Map();  // diag_off → [arg_section_ptr 列表]
let instr_ptr = script_ptr;
while (instr_ptr < arg_ptr) {
  const op = orig.readUInt16LE(instr_ptr);
  if (op === 0x13 || op === 0x10f) {
    const arg_section_ptr = orig.readUInt32LE(instr_ptr + 4);
    const diag_off = orig.readUInt32LE(arg_section_ptr);
    if (!off_to_arg_ptrs.has(diag_off)) off_to_arg_ptrs.set(diag_off, []);
    off_to_arg_ptrs.get(diag_off).push(arg_section_ptr);
  }
  instr_ptr += 8;
}
const raw_diag_list = [...off_to_arg_ptrs.keys()].sort((a, b) => a - b);
const final_offsets = {};
const diag_to_arg_ptrs = {};  // diagN → 写回新 offset 的所有位置
raw_diag_list.forEach((off, i) => {
  const name = `diag${i}`;
  final_offsets[name] = diag_ptr + off;
  diag_to_arg_ptrs[name] = off_to_arg_ptrs.get(off);
});

console.log(`找到 ${raw_diag_list.length} 个对话`);

// 4. 替换对话字节
//    策略：
//      - new_len ≤ orig_len → 原地写
//      - new_len > orig_len → 追加到 script 末尾 + 修改 arg 段指针重定向（"relocation"）
const modified = Buffer.from(orig);
let changed = 0;
const report = { file: FILE_ID, sub: SUB_ID, success: [], skipped: [] };
const to_append = [];  // [{diag, new_items, new_len, orig_len}] - 末尾追加候选

for (const [diag_name, new_items] of Object.entries(new_dialogs)) {
  if (!(diag_name in final_offsets)) {
    report.skipped.push({ diag: diag_name, reason: "no_offset", detail: "dialog 不在 script 的指令表里" });
    continue;
  }
  if (!Array.isArray(new_items)) {
    report.skipped.push({ diag: diag_name, reason: "not_array", detail: `new_items 不是数组（type=${typeof new_items}, val=${JSON.stringify(new_items).slice(0,40)}），extract 阶段未解析成功` });
    continue;
  }
  const abs_off = final_offsets[diag_name];

  const orig_diag = parse_dialog(orig.slice(diag_ptr), abs_off - diag_ptr, true);
  if (!orig_diag) {
    const detail = `parse_dialog 返回 falsy（可能 extract 阶段就坏：dialogs[${diag_name}] 不是 list）`;
    console.warn(`跳过 ${diag_name}（解析失败）`);
    report.skipped.push({ diag: diag_name, reason: "parse_failed", detail });
    continue;
  }
  const orig_len = calculate_dialog_length(orig_diag);
  const new_len  = calculate_dialog_length(new_items);

  if (new_len > orig_len) {
    // 不在原地写，留到追加阶段处理
    to_append.push({ diag_name, new_items, new_len, orig_len });
    continue;
  }

  compile_msg(new_items, modified, abs_off);
  if (new_len < orig_len) {
    modified.fill(0, abs_off + new_len, abs_off + orig_len);
    console.log(`✓ ${diag_name}: ${new_len}/${orig_len} bytes (pad ${orig_len-new_len})`);
  } else {
    console.log(`✓ ${diag_name}: ${orig_len} bytes`);
  }
  report.success.push({ diag: diag_name, new_len, orig_len });
  changed++;
}

// 4b. 追加超长对话到 script 末尾，并修改 arg 段指针
const appended_chunks = [];
let append_offset = modified.byteLength;  // 起始追加位置（相对 script 头）
for (const { diag_name, new_items, new_len, orig_len } of to_append) {
  const buf = Buffer.alloc(new_len);
  compile_msg(new_items, buf, 0);
  appended_chunks.push(buf);
  const new_diag_off = append_offset - diag_ptr;  // 相对 diag_ptr 的新偏移
  // 更新所有引用该 diag 的 arg 段位置
  for (const arg_ptr_addr of diag_to_arg_ptrs[diag_name]) {
    modified.writeUInt32LE(new_diag_off, arg_ptr_addr);
  }
  // 清零原位置（让旧字节不会被误读为有效 dialog）
  const abs_off = final_offsets[diag_name];
  modified.fill(0, abs_off, abs_off + orig_len);
  console.log(`↗ ${diag_name}: 追加到末尾 offset=${new_diag_off}, ${new_len}>${orig_len} bytes`);
  report.success.push({ diag: diag_name, new_len, orig_len, relocated: true, new_offset: new_diag_off });
  append_offset += new_len;
  changed++;
}
const final_buf = appended_chunks.length > 0
  ? Buffer.concat([modified, ...appended_chunks])
  : modified;

// 写 report
const path_mod = await import("path");
const fileURL_mod = await import("url");
const __dirname_now = path_mod.dirname(fileURL_mod.fileURLToPath(import.meta.url));
const REPORT_DIR = path_mod.join(__dirname_now, "out", "build_report");
await fs.mkdir(REPORT_DIR, { recursive: true });
await fs.writeFile(
  path_mod.join(REPORT_DIR, `${FILE_ID}_${SUB_ID}.json`),
  JSON.stringify(report, null, 2),
  "utf-8"
);

if (changed === 0) {
  console.log("没有对话被修改，退出。");
  process.exit(0);
}

// 5. 重压缩
function compress_with_header(buf) {
  const r = lzss.compress(buf, 0xc, true);
  r.writeUInt32LE(sub.readUInt32LE(0), 0);
  r.writeUInt32LE(r.byteLength, 4);
  r.writeUInt32LE(buf.byteLength, 8);  // uncomp_size
  return r;
}

let recomp = compress_with_header(final_buf);
console.log(`重压缩: orig sub-file ${sub.byteLength} → recomp ${recomp.byteLength} bytes (decomp: ${orig.byteLength} → ${final_buf.byteLength})`);

// 真正能不能塞下要看 archive 的 sector padding，由 patch_archive_inplace 内部判断
// 我们在 step 6 try/catch 整个 patch，如果失败再回退到 in-place only

// 6. 写回主 ISO（含追加 dialog 的版本；如果 archive 装不下就回退到 in-place only）
let patched;
try {
  patched = archive.patch_archive_inplace(arch_buf, { [SUB_ID]: recomp });
} catch (err) {
  if (!err.message.includes("exceeds available space") || to_append.length === 0) {
    throw err;  // 非容量问题或没有追加项就直接抛
  }
  console.warn(`⚠ 追加后超 archive 容量，回退为 in-place only：${err.message}`);
  // 把追加项从 success 移到 skipped
  for (const t of to_append) {
    const idx = report.success.findIndex(s => s.diag === t.diag_name && s.relocated);
    if (idx >= 0) report.success.splice(idx, 1);
    report.skipped.push({
      diag: t.diag_name, reason: "too_big",
      detail: `archive 容量不够（追加超出）`,
      new_len: t.new_len, orig_len: t.orig_len,
    });
    changed--;
  }
  // 只做 in-place 重新生成 modified
  const modified_inplace = Buffer.from(orig);
  for (const succ of report.success) {
    const new_items = new_dialogs[succ.diag];
    const abs_off = final_offsets[succ.diag];
    compile_msg(new_items, modified_inplace, abs_off);
    if (succ.new_len < succ.orig_len) {
      modified_inplace.fill(0, abs_off + succ.new_len, abs_off + succ.orig_len);
    }
  }
  recomp = compress_with_header(modified_inplace);
  console.log(`回退后重压缩: ${recomp.byteLength} bytes`);
  patched = archive.patch_archive_inplace(arch_buf, { [SUB_ID]: recomp });
}
const cd = await cdimage.init();
cd.fileposdat = fileposdat;
await cdimage.write_file(cd, FILE_ID, patched);
await cdimage.close(cd);

const patched_sectors = Math.ceil(patched.byteLength / BLOCK_SIZE);
const ecc_end = file_block + patched_sectors - 1;
console.log(`写入完成。自动修复 ECC: FILEPOS (23-26) + file ${FILE_ID} (${file_block}-${ecc_end})`);

// 自动跑 ECC 修复
import { spawn } from "child_process";
import * as path from "path";
import { fileURLToPath } from "url";
const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FIX_ECC = path.join(__dirname, "fix_ecc.py");
const run = (args) => new Promise((resolve, reject) => {
  const p = spawn("python3", [FIX_ECC, ...args], { stdio: "inherit" });
  p.on("exit", code => code === 0 ? resolve() : reject(new Error(`fix_ecc.py exited ${code}`)));
});
await run(["23", "26"]);
await run([String(file_block), String(ecc_end)]);
