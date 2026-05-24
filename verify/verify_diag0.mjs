/**
 * 验证 diag0 修改是否已写入主 ISO。
 * 同时从备份读取原始内容做对比。
 */
import * as fs from "fs/promises";
import * as archive from "../lib/archive.mjs";
import * as lzss from "../lib/lzss.mjs";
import { parse as parse_dialog } from "../lib/msg_script.mjs";

const SECTOR = 0x930;
const BLOCK_OFF = 24;
const BLOCK_SIZE = 2048;
const MAIN_ISO  = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
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
  const file_block = fileposdat.readUInt32LE(3 * 8);
  const file_size  = fileposdat.readUInt32LE(3 * 8 + 4);
  const arch_buf = await read_blocks(fp, file_block, file_size);
  await fp.close();

  const files = archive.extract_files(arch_buf);
  const sub = files[6];
  const total_comp = sub.readUInt32LE(4);
  const uncomp_size = sub.readUInt32LE(8);
  const decompressed = lzss.decompress(sub, 12, total_comp - 12, uncomp_size);

  const diag_ptr = decompressed.readUInt32LE(20);
  const diag_data = decompressed.slice(diag_ptr);
  const diag0 = parse_dialog(diag_data, 0, true);

  // 取 diag0 原始字节（前 N 字节）
  const { calculate_dialog_length } = await import("../lib/msg_script.mjs");
  const len = calculate_dialog_length(diag0);
  const raw_bytes = decompressed.slice(diag_ptr, diag_ptr + len);
  return { diag0, raw_bytes, file_size };
}

const main_data   = await get_diag0(MAIN_ISO);
const backup_data = await get_diag0(BACKUP_ISO);

console.log("=== 主 ISO diag0 ===");
console.log("items:", JSON.stringify(main_data.diag0));
console.log("file3 size:", main_data.file_size);

console.log("\n=== 备份 ISO diag0 ===");
console.log("items:", JSON.stringify(backup_data.diag0));
console.log("file3 size:", backup_data.file_size);

const same = main_data.raw_bytes.equals(backup_data.raw_bytes);
console.log(`\n字节对比: ${same ? "相同（修改未写入）" : "不同（修改已写入）✓"}`);

if (!same) {
  console.log("\n主 ISO diag0 字节（hex）:");
  console.log(main_data.raw_bytes.toString("hex").match(/.{4}/g).join(" "));
  console.log("\n备份 diag0 字节（hex）:");
  console.log(backup_data.raw_bytes.toString("hex").match(/.{4}/g).join(" "));
}
