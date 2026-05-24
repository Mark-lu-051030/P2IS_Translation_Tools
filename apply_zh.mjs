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
let instr_ptr = script_ptr;
// 指令结构: [op:2][imm:2][arg_section_ptr:4]
// arg_section_ptr 指向参数区，参数区里存 uint32 参数值
// 对于 op 0x13/0x10f，第一个参数是 dialog 偏移（相对于 diag_ptr）
const temp_seen = new Map();
const raw_diag_list = [];
instr_ptr = script_ptr;
while (instr_ptr < arg_ptr) {
  const op = orig.readUInt16LE(instr_ptr);
  if (op === 0x13 || op === 0x10f) {
    const arg_section_ptr = orig.readUInt32LE(instr_ptr + 4);  // 指向参数区
    const diag_off = orig.readUInt32LE(arg_section_ptr);        // 读取第一个参数
    if (!temp_seen.has(diag_off)) {
      temp_seen.set(diag_off, temp_seen.size);
      raw_diag_list.push(diag_off);
    }
  }
  instr_ptr += 8;
}
raw_diag_list.sort((a, b) => a - b);
const final_offsets = {};
raw_diag_list.forEach((off, i) => {
  final_offsets[`diag${i}`] = diag_ptr + off;
});

console.log(`找到 ${raw_diag_list.length} 个对话`);

// 4. 替换对话字节，记录每条 dialog 的结果到 report
const modified = Buffer.from(orig);
let changed = 0;
const report = { file: FILE_ID, sub: SUB_ID, success: [], skipped: [] };

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

  // 跳过未翻译的（new_items 和原版完全一样的情况——无 zh 翻译）
  // 这通过看 new_items 的开头是否含 0xd7d7d7 之类的方式判断比较 hacky，
  // 这里简单的方式：只要 diag 在 new_dialogs 里就走流程；reapply 原数据也无妨。

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
    const detail = `译文 ${new_len} bytes > 原文 ${orig_len} bytes`;
    console.warn(`⚠ ${diag_name}: ${detail}，跳过（无法塞入原槽）`);
    report.skipped.push({ diag: diag_name, reason: "too_big", detail, new_len, orig_len });
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
const recomp = lzss.compress(modified, 0xc, true);
recomp.writeUInt32LE(sub.readUInt32LE(0), 0);
recomp.writeUInt32LE(recomp.byteLength, 4);
recomp.writeUInt32LE(modified.byteLength, 8);
console.log(`重压缩: ${sub.byteLength} → ${recomp.byteLength} bytes`);

// 6. 写回主 ISO
const replacements = { [SUB_ID]: recomp };
const patched = archive.patch_archive_inplace(arch_buf, replacements);
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
