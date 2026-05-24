/**
 * 从备份 ISO 还原所有被修改的文件到主 ISO。
 * 修复：文件 3（脚本测试残留）、文件 181（字符码=1 残留）、fileposdat。
 */
import * as fs from "fs/promises";
import * as cdimage from "../lib/cdimage.mjs";

const SECTOR = 0x930;
const BLOCK_OFF = 24;
const BLOCK_SIZE = 2048;
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

const backup_fp = await fs.open(BACKUP_ISO, "r");
const fileposdat = await read_blocks(backup_fp, 0x17, 0x1b88);

async function restore_file(backup_fp, fileposdat, filenum, label) {
  const file_block = fileposdat.readUInt32LE(filenum * 8);
  const file_size = fileposdat.readUInt32LE(filenum * 8 + 4);
  console.log(`${label}: block=${file_block}, size=${file_size}`);
  return await read_blocks(backup_fp, file_block, file_size);
}

const arch3   = await restore_file(backup_fp, fileposdat, 3,   "File 3  ");
const arch181 = await restore_file(backup_fp, fileposdat, 181, "File 181");
await backup_fp.close();

// 写回主 ISO（原始数据，不做任何修改）
const cd = await cdimage.init();
cd.fileposdat = fileposdat;  // 用备份的 fileposdat，确保完全一致
await cdimage.write_file(cd, 3,   arch3);
await cdimage.write_file(cd, 181, arch181);
await cdimage.close(cd);  // 写回备份版本的 fileposdat

console.log("\n还原完成。运行 ECC 修复:");
console.log("  python3 fix_ecc.py 23 26");
console.log("  python3 fix_ecc.py 29297 29378");
console.log("  python3 fix_ecc.py 235195 235297");
