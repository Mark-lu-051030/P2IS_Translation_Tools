/**
 * 修补文件 181 sub-file 8 的 diag0（游戏开头霸凌场景）。
 * 当前模式：把所有字符码替换为 300，验证管道是否工作。
 */
import * as fs from "fs/promises";
import * as archive from "../lib/archive.mjs";
import * as lzss from "../lib/lzss.mjs";
import * as cdimage from "../lib/cdimage.mjs";
import { parse as parse_dialog, calculate_dialog_length, compile_msg } from "../lib/msg_script.mjs";

const SECTOR = 0x930;
const BLOCK_OFF = 24;
const BLOCK_SIZE = 2048;
const BACKUP_ISO = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";

const FILE_ID = 181;
const SUB_ID  = 8;

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

// 1. 从备份读取文件 181
const backup_fp = await fs.open(BACKUP_ISO, "r");
const fileposdat = await read_blocks(backup_fp, 0x17, 0x1b88);
const file_block = fileposdat.readUInt32LE(FILE_ID * 8);
const file_size  = fileposdat.readUInt32LE(FILE_ID * 8 + 4);
console.log(`File ${FILE_ID}: block=${file_block}, size=${file_size}`);
const arch_buf = await read_blocks(backup_fp, file_block, file_size);
await backup_fp.close();

// 2. 解压 sub-file 8
const files = archive.extract_files(arch_buf);
const sub = files[SUB_ID];
const total_comp = sub.readUInt32LE(4);
const uncomp_size = sub.readUInt32LE(8);
const orig = lzss.decompress(sub, 12, total_comp - 12, uncomp_size);
console.log(`解压: ${sub.byteLength} bytes → ${orig.length} bytes`);

const diag_ptr = orig.readUInt32LE(20);
console.log(`diag_ptr=0x${diag_ptr.toString(16)}`);

// 3. 修改 diag0（测试：替换所有字符码为 300）
const modified = Buffer.from(orig);
const diag_data = modified.slice(diag_ptr);
const diag0 = parse_dialog(diag_data, 0);
const diag0_len = calculate_dialog_length(diag0);
console.log(`diag0: ${diag0.length} 项, ${diag0_len} bytes`);
console.log("diag0 原始内容:", JSON.stringify(diag0));

const diag0_modified = diag0.map(item => (typeof item === "number" ? 16 : item));
compile_msg(diag0_modified, modified, diag_ptr);

// 4. 重压缩
const recomp = lzss.compress(modified, 0xc, true);
recomp.writeUInt32LE(sub.readUInt32LE(0), 0);  // 保留原始 tag（含 sub-file 序号）
recomp.writeUInt32LE(recomp.byteLength, 4);
recomp.writeUInt32LE(modified.byteLength, 8);
console.log(`重压缩: ${sub.byteLength} → ${recomp.byteLength} bytes`);

// 5. 写回主 ISO
const replacements = { [SUB_ID]: recomp };
const patched = archive.patch_archive_inplace(arch_buf, replacements);
console.log(`Archive: ${arch_buf.byteLength} → ${patched.byteLength} bytes`);

const cd = await cdimage.init();
cd.fileposdat = fileposdat;
await cdimage.write_file(cd, FILE_ID, patched);
await cdimage.close(cd);

// 计算 ECC 修复范围
const patched_sectors = Math.ceil(patched.byteLength / BLOCK_SIZE);
const ecc_end = file_block + patched_sectors - 1;
console.log("\n写入完成。运行 ECC 修复:");
console.log(`  python3 fix_ecc.py 23 26 && python3 fix_ecc.py ${file_block} ${ecc_end}`);
