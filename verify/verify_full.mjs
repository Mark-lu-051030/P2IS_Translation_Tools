/**
 * 完整验证：
 * 1. 对比主 ISO vs 备份 ISO 的 diag0（确认写入生效）
 * 2. 检查原始 diag0 的字符码（了解预加载范围）
 * 3. 显示 slot 2602 的点阵
 */
import * as fs from "fs/promises";
import { extract_files } from "../lib/archive.mjs";
import { decompress } from "../lib/lzss.mjs";
import { parse as parse_dialog } from "../lib/msg_script.mjs";

const SECTOR = 0x930, BLOCK_OFF = 24, BLOCK_SIZE = 2048;
const MAIN_ISO   = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
const BACKUP_ISO = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";

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

async function get_diag0(iso_path) {
  const fp = await fs.open(iso_path, "r");
  const fileposdat = await read_blocks(fp, 0x17, 0x1b88);
  const file_block = fileposdat.readUInt32LE(181 * 8);
  const file_size  = fileposdat.readUInt32LE(181 * 8 + 4);
  const arch_buf = await read_blocks(fp, file_block, file_size);
  await fp.close();

  const files = extract_files(arch_buf);
  const sub = files[8];
  const total_comp  = sub.readUInt32LE(4);
  const uncomp_size = sub.readUInt32LE(8);
  const orig = decompress(sub, 12, total_comp - 12, uncomp_size);

  const diag_ptr = orig.readUInt32LE(20);
  const script_ptr = orig.readUInt32LE(12);
  const arg_ptr = orig.readUInt32LE(16);

  let instr_ptr = script_ptr;
  const seen = new Map();
  const diag_list = [];
  while (instr_ptr < arg_ptr) {
    const op = orig.readUInt16LE(instr_ptr);
    if (op === 0x13 || op === 0x10f) {
      const arg_sec = orig.readUInt32LE(instr_ptr + 4);
      const diag_off = orig.readUInt32LE(arg_sec);
      if (!seen.has(diag_off)) {
        seen.set(diag_off, seen.size);
        diag_list.push(diag_off);
      }
    }
    instr_ptr += 8;
  }
  diag_list.sort((a, b) => a - b);
  const diag0_abs = diag_ptr + diag_list[0];

  // 读取 diag0 的所有 uint16 直到 RET(0x1103)
  const codes = [];
  for (let i = 0; i < 200; i++) {
    const code = orig.readUInt16LE(diag0_abs + i * 2);
    codes.push(code);
    if (code === 0x1103) break;
  }
  return codes;
}

console.log("=== 主 ISO diag0 ===");
const main_codes = await get_diag0(MAIN_ISO);
console.log(main_codes.map(c => c.toString(16).padStart(4,'0')).join(' '));

console.log("\n=== 备份 ISO diag0 ===");
const backup_codes = await get_diag0(BACKUP_ISO);
console.log(backup_codes.map(c => c.toString(16).padStart(4,'0')).join(' '));

const same = JSON.stringify(main_codes) === JSON.stringify(backup_codes);
console.log(`\n两者相同: ${same ? '✗ 写入未生效！' : '✓ 写入已生效'}`);

// 找出差异
if (!same) {
  console.log("差异位置:");
  for (let i = 0; i < Math.max(main_codes.length, backup_codes.length); i++) {
    if (main_codes[i] !== backup_codes[i]) {
      console.log(`  [${i}]: main=0x${(main_codes[i]||0).toString(16)} backup=0x${(backup_codes[i]||0).toString(16)}`);
    }
  }
}

// 原始日文字符码分布
console.log("\n=== 备份 diag0 原始字符码（0x0000-0x0FFF 范围）===");
const orig_chars = backup_codes.filter(c => c < 0x1000);
console.log("字符码:", orig_chars.join(', '));
console.log("字符码范围:", Math.min(...orig_chars), '-', Math.max(...orig_chars));

console.log("\n=== 主 ISO diag0 字符码（0x0000-0x0FFF 范围）===");
const new_chars = main_codes.filter(c => c < 0x1000);
console.log("字符码:", new_chars.join(', '));
console.log("包含 2602:", new_chars.includes(2602) ? '✓ 是' : '✗ 否');
