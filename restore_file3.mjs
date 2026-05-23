/**
 * 从备份 ISO 读取文件 3 的原始数据，写回主 ISO。
 * 这是纯通路测试——确认二进制修补路径工作正常。
 * 通过后可在此基础上修改对话区进行翻译。
 */
import * as fs from "fs/promises";
import * as archive from "./lib/archive.mjs";
import * as cdimage from "./lib/cdimage.mjs";

const SECTOR = 0x930;
const BLOCK_OFF = 24;
const BLOCK_SIZE = 2048;

const BACKUP_ISO = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";

// 直接从 ISO 文件读取 n 个扇区的数据
async function read_blocks(iso_fp, file_block, file_size) {
  const sector = Buffer.alloc(SECTOR);
  const output = Buffer.allocUnsafe(file_size);
  let off = 0, sec = file_block * SECTOR;
  while (off < file_size) {
    await iso_fp.read(sector, 0, SECTOR, sec);
    const chunk = Math.min(BLOCK_SIZE, file_size - off);
    sector.copy(output, off, BLOCK_OFF, BLOCK_OFF + chunk);
    off += chunk; sec += SECTOR;
  }
  return output;
}

// 1. 读取备份 ISO 的 FILEPOS.DAT 获取文件信息
const backup_fp = await fs.open(BACKUP_ISO, "r");
const fileposdat = await read_blocks(backup_fp, 0x17, 0x1b88);
const FILE_ID = 3;
const file_block = fileposdat.readUInt32LE(FILE_ID * 8);
const file_size = fileposdat.readUInt32LE(FILE_ID * 8 + 4);
console.log(`File ${FILE_ID}: block=${file_block}, size=${file_size}`);

// 2. 从备份 ISO 读取文件 3
const arch_buf = await read_blocks(backup_fp, file_block, file_size);
await backup_fp.close();

// 3. 取出原始压缩 sub-file 6（不解压、不重压缩，原样使用）
const files = archive.extract_files(arch_buf);
const sub6_orig = files[6];
console.log(`Sub-file 6: ${sub6_orig.byteLength} bytes (原始压缩数据)`);

// ── 纯通路测试：直接用原始压缩数据 ──────────────────────
// 如需修改对话，这里应先解压、改内容、再用 patch_dialog_inplace 处理
// ──────────────────────────────────────────────────────

// 4. 写回主 ISO
const replacements = { 6: sub6_orig };
const patched = archive.patch_archive_inplace(arch_buf, replacements);
console.log(`Archive: ${arch_buf.byteLength} → ${patched.byteLength} bytes`);

const cd = await cdimage.init();
await cdimage.write_file(cd, FILE_ID, patched);
await cdimage.close(cd);
console.log("写入完成。运行 ECC 修复:");
console.log("  python3 fix_ecc.py 23 26 && python3 fix_ecc.py 29297 29378");
