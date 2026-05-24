/**
 * 诊断：打印 file 181 sub-file 8 原始头部字节，并对比 roundtrip 结果。
 */
import * as fs from "fs/promises";
import * as archive from "../lib/archive.mjs";
import * as lzss from "../lib/lzss.mjs";
import { parse as parse_dialog, calculate_dialog_length, compile_msg } from "../lib/msg_script.mjs";

const SECTOR = 0x930, BLOCK_OFF = 24, BLOCK_SIZE = 2048;
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

const fp = await fs.open(BACKUP_ISO, "r");
const fileposdat = await read_blocks(fp, 0x17, 0x1b88);
const file_block = fileposdat.readUInt32LE(181 * 8);
const file_size  = fileposdat.readUInt32LE(181 * 8 + 4);
const arch_buf = await read_blocks(fp, file_block, file_size);
await fp.close();

const files = archive.extract_files(arch_buf);
const sub = files[8];

// 1. 打印原始头部（前 12 字节）
console.log("sub-file 8 原始头部 (hex):", sub.slice(0, 12).toString("hex"));
console.log("  sub[0..3] (tag)  :", sub.readUInt32LE(0).toString(16).padStart(8, "0"), "→ 我们写入 00000101");
console.log("  sub[4..7] (size) :", sub.readUInt32LE(4));
console.log("  sub[8..11](ucomp):", sub.readUInt32LE(8));

// 2. roundtrip 测试：解压 → 不改内容 → 重压，对比头部差异
const total_comp = sub.readUInt32LE(4);
const uncomp_size = sub.readUInt32LE(8);
const orig = lzss.decompress(sub, 12, total_comp - 12, uncomp_size);

const recomp = lzss.compress(orig, 0xc, true);
// 不硬编码 0x101，保留原始 tag
recomp.writeUInt32LE(sub.readUInt32LE(0), 0);  // 原始 tag
recomp.writeUInt32LE(recomp.byteLength, 4);
recomp.writeUInt32LE(orig.byteLength, 8);

console.log("\nroundtrip 重压缩头部 (hex):", recomp.slice(0, 12).toString("hex"));
console.log("  原始 size:", total_comp, "  重压后 size:", recomp.byteLength);

// 3. 对比 diag0 原始字节 vs roundtrip 字节
const diag_ptr = orig.readUInt32LE(20);
const diag_data = orig.slice(diag_ptr);
const diag0 = parse_dialog(diag_data, 0, true);
const diag0_len = calculate_dialog_length(diag0);

// 原始 diag0 字节
const orig_diag0_bytes = orig.slice(diag_ptr, diag_ptr + diag0_len);

// roundtrip diag0 字节
const rt_buf = Buffer.from(orig);
compile_msg(diag0, rt_buf, diag_ptr);
const rt_diag0_bytes = rt_buf.slice(diag_ptr, diag_ptr + diag0_len);

console.log("\ndiag0 原始字节:", orig_diag0_bytes.toString("hex"));
console.log("diag0 roundtrip:", rt_diag0_bytes.toString("hex"));
console.log("是否相同:", orig_diag0_bytes.equals(rt_diag0_bytes) ? "✓ 完全一致" : "✗ 存在差异！");
