/**
 * Patches file 3 in p2.bin with Chinese scripts while preserving the
 * original 167936-byte archive size so the game's loading loop completes.
 *
 * Strategy:
 *   - Start from the original ISO's file 3 archive (167936 bytes, with all
 *     the original sector-aligned padding intact).
 *   - Patch sub[3] and sub[6] in-place with our LZSS-compressed Chinese scripts.
 *   - Keep bytes[4-7] of each patched sub-file at the ORIGINAL slot size (7312)
 *     so the archive reader still advances to the correct offset for the next
 *     sub-file.  The LZSS decompressor stops at uncompressed_size, so trailing
 *     zero padding is harmless.
 *   - Write the 167936-byte buffer back to p2.bin and update FILEPOS.DAT.
 */

import * as fs from "fs/promises";
import * as fss from "fs";
import * as scene from "../lib/scene_script.mjs";
import * as lzss from "../lib/lzss.mjs";
import * as cdimage from "../lib/cdimage.mjs";
import * as archive from "../lib/archive.mjs";

const SECTOR_SIZE = 0x930;   // 2352
const BLOCK_SIZE  = 2048;
const BLOCK_OFF   = 24;      // 12 (sync+header) + 8 (subheader) + 4

const conf     = JSON.parse(fss.readFileSync("conf.json"));
const orig_iso = conf.iso.replace("p2.bin", "Persona 2 - Tsumi - Innocent Sin (Japan).bin");

// ── helpers ──────────────────────────────────────────────────────────────────

async function read_raw(iso_path, file_block, file_size) {
  const h   = await fs.open(iso_path, "r");
  const out = Buffer.allocUnsafe(file_size);
  let off = 0;
  let sec = file_block * SECTOR_SIZE;
  const sector = Buffer.alloc(SECTOR_SIZE);
  while (off < file_size) {
    const { bytesRead } = await h.read(sector, 0, SECTOR_SIZE, sec);
    if (bytesRead < SECTOR_SIZE) throw new Error(`Short read at sector ${sec / SECTOR_SIZE}`);
    const chunk = Math.min(BLOCK_SIZE, file_size - off);
    sector.copy(out, off, BLOCK_OFF, BLOCK_OFF + chunk);
    off += chunk;
    sec += SECTOR_SIZE;
  }
  await h.close();
  return out;
}

async function write_raw(iso_path, file_block, buf) {
  const h = await fs.open(iso_path, "r+");
  let off = 0;
  let sec = file_block * SECTOR_SIZE;
  const sector = Buffer.alloc(SECTOR_SIZE);
  while (off < buf.byteLength) {
    const { bytesRead } = await h.read(sector, 0, SECTOR_SIZE, sec);
    if (bytesRead < SECTOR_SIZE) throw new Error(`Short read at sector ${sec / SECTOR_SIZE}`);
    const chunk = Math.min(BLOCK_SIZE, buf.byteLength - off);
    buf.copy(sector, BLOCK_OFF, off, off + chunk);
    if (chunk < BLOCK_SIZE)
      sector.fill(0, BLOCK_OFF + chunk, BLOCK_OFF + BLOCK_SIZE);
    await h.write(sector, 0, SECTOR_SIZE, sec);
    off += chunk;
    sec += SECTOR_SIZE;
  }
  await h.close();
}

// ── read FILEPOS.DAT from p2.bin ─────────────────────────────────────────────

async function read_fileposdat(iso_path) {
  // FILEPOS.DAT is always at block 0x17 (23), size 0x1b88
  return read_raw(iso_path, 0x17, 0x1b88);
}

async function write_fileposdat(iso_path, dat) {
  await write_raw(iso_path, 0x17, dat);
}

// ── patch one sub-file slot in the archive buffer ────────────────────────────

function patch_subfile(arch, slot_offset, original_slot_size, compressed_buf) {
  if (compressed_buf.byteLength > original_slot_size) {
    throw new Error(
      `Compressed script (${compressed_buf.byteLength} B) exceeds original slot (${original_slot_size} B)`
    );
  }
  // bytes[0-3]: LZSS magic (0x201); original was 0x101
  arch.writeUInt32LE(0x201, slot_offset);
  // bytes[4-7]: ACTUAL compressed size (NOT the original slot size).
  //   Setting this to original_slot_size caused the PS1 LZSS decompressor to
  //   consume 3011 bytes of zero padding, overflowing the decompressed buffer.
  //   Using the true size lets the decompressor stop at the right byte.
  //   The bytes from compressed_buf.byteLength to original_slot_size are already
  //   zeroed; the PS1 archive loader treats those zero bytes as type-0 sector
  //   padding entries and skips sector-by-sector to the next real sub-file.
  arch.writeUInt32LE(compressed_buf.byteLength, slot_offset + 4);
  // bytes[8-11]: new decompressed size
  arch.writeUInt32LE(compressed_buf.readUInt32LE(8), slot_offset + 8);
  // bytes[12..]: LZSS compressed data
  compressed_buf.copy(arch, slot_offset + 12, 12);
  // zero out the rest of the original slot (type=0 sector padding for PS1 loader)
  const data_end = slot_offset + compressed_buf.byteLength;
  const slot_end = slot_offset + original_slot_size;
  if (data_end < slot_end)
    arch.fill(0, data_end, slot_end);
}

// ── compile + compress one JSON script ───────────────────────────────────────

function compile_zh(json_path) {
  const script     = JSON.parse(fss.readFileSync(json_path));
  const compiled   = scene.compile_script(script);
  const compressed = lzss.compress(compiled, 0xc, true);
  compressed.writeUInt32LE(0x201,                0);
  compressed.writeUInt32LE(compressed.byteLength, 4);
  compressed.writeUInt32LE(compiled.byteLength,   8);
  return compressed;
}

// ── main ─────────────────────────────────────────────────────────────────────

async function main() {
  // 1. Read original archive (167936 B) from backup ISO
  //    Use original FILEPOS.DAT to get the correct block/size for file 3
  console.log("Reading original FILEPOS.DAT from backup ISO...");
  const orig_fpd     = await read_fileposdat(orig_iso);
  const file3_block  = orig_fpd.readUInt32LE(3 * 8);
  const file3_size   = orig_fpd.readUInt32LE(3 * 8 + 4);
  console.log(`File 3: block=${file3_block}, size=${file3_size}`);

  console.log("Reading original archive from backup ISO...");
  const arch = await read_raw(orig_iso, file3_block, file3_size);
  console.log(`Archive read: ${arch.byteLength} B`);

  // 2. Locate sub[3] and sub[6] offsets
  const files   = archive.extract_files(arch);
  const offsets = [];
  {
    let ptr = 0;
    while (ptr < arch.byteLength) {
      const type = arch[ptr];
      if (type === 0) { ptr += 0x7ff; ptr &= ~0x7ff; continue; }
      offsets.push(ptr);
      const len = arch.readUInt32LE(ptr + 4);
      ptr += len;
      while (ptr & 3) ptr++;
    }
  }
  const ORIG_SLOT = 7312; // bytes[4-7] of original sub[3]/sub[6]
  console.log(`sub[3] at offset 0x${offsets[3].toString(16)} (${offsets[3]})`);
  console.log(`sub[6] at offset 0x${offsets[6].toString(16)} (${offsets[6]})`);

  // 3. Compile + compress Chinese scripts
  console.log("Compiling Chinese scripts...");
  const comp3 = compile_zh("out/scripts_zh/3_3.json");
  const comp6 = compile_zh("out/scripts_zh/3_6.json");
  console.log(`sub[3]: compressed=${comp3.byteLength} B, decompressed=${comp3.readUInt32LE(8)} B`);
  console.log(`sub[6]: compressed=${comp6.byteLength} B, decompressed=${comp6.readUInt32LE(8)} B`);

  // Keep whatever bytes[2-3] from the original (already 0x0000 but be safe)
  comp3.writeUInt16LE(files[3].readUInt16LE(2), 2);
  comp6.writeUInt16LE(files[6].readUInt16LE(2), 2);

  // 4. Patch in-place (bytes[0-1] from 0x201 magic: 0x01 0x02; original was 0x01 0x01)
  //    The game handles both 0x101 (uncompressed) and 0x201 (LZSS).
  patch_subfile(arch, offsets[3], ORIG_SLOT, comp3);
  patch_subfile(arch, offsets[6], ORIG_SLOT, comp6);
  console.log(`Archive still ${arch.byteLength} B after patching`);

  // 5. Write patched archive to p2.bin
  console.log("Writing patched archive to p2.bin...");
  await write_raw(conf.iso, file3_block, arch);

  // 6. Update FILEPOS.DAT in p2.bin so file 3 size = 167936
  console.log("Updating FILEPOS.DAT in p2.bin...");
  const fpd = await read_fileposdat(conf.iso);
  const cur_size = fpd.readUInt32LE(3 * 8 + 4);
  console.log(`  file 3 size in FILEPOS.DAT: ${cur_size} → ${file3_size}`);
  fpd.writeUInt32LE(file3_size, 3 * 8 + 4);
  await write_fileposdat(conf.iso, fpd);

  console.log("Done. Run fix_ecc.py to recalculate EDC for modified sectors:");
  console.log(`  python3 fix_ecc.py 23 26`);
  console.log(`  python3 fix_ecc.py ${file3_block} ${file3_block + Math.ceil(file3_size / 2048) - 1}`);
}

main().catch(e => { console.error(e); process.exit(1); });
