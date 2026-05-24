/**
 * 验证注入结果：
 * 1. 读取主 ISO 文件 181 sub-file 8，检查 diag0 是否包含 code 2602
 * 2. 读取主 ISO F0086.BIN（file 86），检查 slot 2602 的 bitmap 是否非零
 */
import * as fs from "fs/promises";
import * as archive from "../lib/archive.mjs";
import * as lzss from "../lib/lzss.mjs";

const SECTOR = 0x930, BLOCK_OFF = 24, BLOCK_SIZE = 2048;
const ISO_PATH = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";

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

const fp = await fs.open(ISO_PATH, "r");
const fileposdat = await read_blocks(fp, 0x17, 0x1b88);

// ── 1. 检查文件 181 sub-file 8 的 diag0 ─────────────────────────
const file_block = fileposdat.readUInt32LE(181 * 8);
const file_size  = fileposdat.readUInt32LE(181 * 8 + 4);
console.log(`File 181: block=${file_block}, size=${file_size}`);
const arch_buf = await read_blocks(fp, file_block, file_size);

const { extract_files } = await import("../lib/archive.mjs");
const files = extract_files(arch_buf);
const sub = files[8];
const total_comp  = sub.readUInt32LE(4);
const uncomp_size = sub.readUInt32LE(8);
console.log(`Sub-file 8: tag=${sub.readUInt32LE(0).toString(16)}, comp=${total_comp}, uncomp=${uncomp_size}`);

const { decompress } = await import("../lib/lzss.mjs");
const orig = decompress(sub, 12, total_comp - 12, uncomp_size);

const diag_ptr = orig.readUInt32LE(20);
const script_ptr = orig.readUInt32LE(12);
const arg_ptr = orig.readUInt32LE(16);
console.log(`script_ptr=0x${script_ptr.toString(16)}, arg_ptr=0x${arg_ptr.toString(16)}, diag_ptr=0x${diag_ptr.toString(16)}`);

// 扫描 diag 偏移
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
console.log(`Found ${diag_list.length} dialogs`);

// 打印 diag0 的字节
const diag0_abs = diag_ptr + diag_list[0];
console.log(`diag0 at 0x${diag0_abs.toString(16)}, first 40 bytes:`);
for (let i = 0; i < 40; i += 2) {
  const code = orig.readUInt16LE(diag0_abs + i);
  process.stdout.write(`${code.toString(16).padStart(4,'0')} `);
}
console.log();

// 检查是否含 2602 (0x0A2A)
let has2602 = false;
for (let i = 0; i < 64; i += 2) {
  const code = orig.readUInt16LE(diag0_abs + i);
  if (code === 2602) { has2602 = true; break; }
  if (code >= 0x1100) break;
}
console.log(`diag0 含 code 2602: ${has2602 ? '✓ 是' : '✗ 否'}`);

// ── 2. 检查 F0086.BIN slot 2602 的 bitmap ───────────────────────
const font_block = fileposdat.readUInt32LE(86 * 8);
const font_size  = fileposdat.readUInt32LE(86 * 8 + 4);
console.log(`\nFile 86 (F0086.BIN): block=${font_block}, size=${font_size}`);
const font_data = await read_blocks(fp, font_block, font_size);

const slot = 2602;
const off = 0x480 + slot * 18;
const bmp = font_data.slice(off, off + 18);
console.log(`Slot 2602 bitmap (18 bytes): ${bmp.toString('hex')}`);
const nonzero = bmp.some(b => b !== 0);
console.log(`Bitmap 非零: ${nonzero ? '✓ 是' : '✗ 否（空白字符！）'}`);

// 打印 12×12 点阵图
console.log("\nBitmap 可视化 (12×12):");
for (let row = 0; row < 12; row++) {
  let line = "";
  for (let col = 0; col < 12; col++) {
    const bit_idx = row * 12 + col;
    const byte_idx = bit_idx >> 3;
    const bit = (bmp[byte_idx] >> (bit_idx & 7)) & 1;
    line += bit ? "█" : "·";
  }
  console.log(line);
}

await fp.close();
