"""
Safe fix: modify exactly ONE '...' (code 0xd7=215) to code 0x10 (=16, '草')
in file 181 sub-file 8 diag0.

Reads file 181 from BACKUP, modifies only the target byte, writes to MAIN ISO.
Preserves the original LZSS sub-file tag bytes exactly.
F0086.BIN slot 16 already has '草' glyph in MAIN ISO - not touched here.
"""
import struct, sys, os, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from pylib.p2is import (
    SECTOR, BLOCK_OFF, BLOCK_SIZE,
    read_sectors, write_sectors,
    lzss_decompress, lzss_compress,
    archive_subfile_offsets,
)
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')

MAIN   = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BACKUP = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'

# ── Main ─────────────────────────────────────────────────────────────────────

# 1. Read FILEPOS from backup
filepos = read_sectors(BACKUP, 0x17, 0x1b88)
block181 = struct.unpack_from('<I', filepos, 181*8)[0]
size181  = struct.unpack_from('<I', filepos, 181*8 + 4)[0]
print(f'File 181 (from backup): block={block181}, size={size181}')

# 2. Read archive from backup
arch = read_sectors(BACKUP, block181, size181)
offsets = archive_subfile_offsets(arch)
print(f'Sub-file count: {len(offsets)}')

# 3. Locate sub-file 8
assert len(offsets) > 8, "Archive has fewer than 9 sub-files"
sub8_start, sub8_len = offsets[8]
sub8 = arch[sub8_start:sub8_start + sub8_len]
print(f'Sub-file 8: archive offset=0x{sub8_start:x}, len={sub8_len}')

# Save the original tag bytes (must be preserved exactly)
tag_bytes = bytes(sub8[0:4])
total_comp = struct.unpack_from('<I', sub8, 4)[0]
uncomp_size = struct.unpack_from('<I', sub8, 8)[0]
print(f'  tag={tag_bytes.hex()}, comp={total_comp}, uncomp={uncomp_size}')
assert total_comp == sub8_len, f"comp={total_comp} != sub8_len={sub8_len}"

# 4. Decompress
decompressed = bytearray(lzss_decompress(sub8, 12, total_comp - 12, uncomp_size))
print(f'  Decompressed: {len(decompressed)} bytes')
assert len(decompressed) == uncomp_size

# 5. Find diag0 and locate position [9] (the first '...' = 0xd7)
#    diag0 sequence: 1d 12 0b 00 3f 00 3f 00 3f 00 1d 12 01 00 01 11 20 11 d7 00
DIAG0_PREFIX = bytes.fromhex('1d120b003f003f003f001d120100011120 11'.replace(' ', ''))
# pos [9] is at byte offset 18 from start of diag0
target_pos = 18  # byte offset within diag0 where 0xd7 lives (uint16 LE at [9]*2)

found = -1
for i in range(len(decompressed) - len(DIAG0_PREFIX)):
    if decompressed[i:i+len(DIAG0_PREFIX)] == DIAG0_PREFIX:
        found = i
        break

if found == -1:
    print('ERROR: diag0 prefix not found in decompressed data!')
    sys.exit(1)

print(f'  diag0 found at decompressed offset 0x{found:x}')
diag0_seq_raw = decompressed[found:found+32]
print(f'  diag0 raw bytes: {diag0_seq_raw.hex()}')

# Verify position [9] = 0x00d7
code_at_9 = struct.unpack_from('<H', decompressed, found + target_pos)[0]
print(f'  diag0[9] = 0x{code_at_9:04x} (expected 0x00d7)')
assert code_at_9 == 0x00d7, f"Expected 0xd7 at position [9], got 0x{code_at_9:04x}"

# 6. Patch: change position [9] from 0xd7 to 0x10
decompressed[found + target_pos]     = 0x10
decompressed[found + target_pos + 1] = 0x00
code_after = struct.unpack_from('<H', decompressed, found + target_pos)[0]
print(f'  After patch: diag0[9] = 0x{code_after:04x} (should be 0x0010)')
assert code_after == 0x0010

# 7. Recompress
print('Recompressing...')
recomp = bytearray(lzss_compress(bytes(decompressed), 12))
print(f'  Recompressed: {len(recomp)} bytes (was {sub8_len})')

# Write the header with original tag bytes + new sizes
recomp[0:4] = tag_bytes                              # preserve original tag
struct.pack_into('<I', recomp, 4, len(recomp))       # total compressed size
struct.pack_into('<I', recomp, 8, len(decompressed)) # uncompressed size
print(f'  tag={bytes(recomp[0:4]).hex()}, comp={struct.unpack_from("<I",recomp,4)[0]}, uncomp={struct.unpack_from("<I",recomp,8)[0]}')

# 8. Check that new sub-file fits in available space
# Available space: from sub8_start to end of archive (or next sub-file)
# Since sub-file 8 is the last one, available = size181 - sub8_start
available = size181 - sub8_start
print(f'  Available space: {available} bytes')
assert len(recomp) <= available, f"Recompressed {len(recomp)} > available {available}"

# 9. Build the patched archive buffer (copy from backup, replace sub-file 8 region)
arch_patched = bytearray(arch)  # copy of backup archive (size181 bytes)
# Zero from sub8_start to end of archive
arch_patched[sub8_start:size181] = bytes(size181 - sub8_start)
# Write recompressed sub-file 8
arch_patched[sub8_start:sub8_start + len(recomp)] = recomp
print(f'  Archive patched, size={len(arch_patched)} (should be {size181})')
assert len(arch_patched) == size181

# 10. Write to main ISO
print(f'\nWriting file 181 to main ISO at block {block181}...')
write_sectors(MAIN, block181, bytes(arch_patched))
print('  Done.')

# 11. Update FILEPOS in main ISO if size changed (should be same)
main_filepos = read_sectors(MAIN, 0x17, 0x1b88)
main_size181 = struct.unpack_from('<I', main_filepos, 181*8 + 4)[0]
if main_size181 != size181:
    main_filepos[181*8+4:181*8+8] = struct.pack('<I', size181)
    write_sectors(MAIN, 0x17, bytes(main_filepos))
    print(f'  FILEPOS updated: {main_size181} -> {size181}')

# 12. Verify
verify_arch = read_sectors(MAIN, block181, size181)
verify_sub8_start, _ = archive_subfile_offsets(bytes(verify_arch))[8]
verify_sub8 = verify_arch[verify_sub8_start:verify_sub8_start + len(recomp)]
verify_tag = bytes(verify_sub8[0:4])
print(f'\nVerify: sub-file 8 tag in main ISO = {verify_tag.hex()} (should be {tag_bytes.hex()})')
assert verify_tag == tag_bytes, f"Tag mismatch: got {verify_tag.hex()}"
print('Tag OK ✓')

# 13. Auto-run ECC fix
sector_count = (size181 + BLOCK_SIZE - 1) // BLOCK_SIZE
lba_end = block181 + sector_count - 1
print(f'\nFixing ECC for file 181 (LBA {block181}–{lba_end}, {sector_count} sectors)')
subprocess.run(['python3', FIX_ECC, str(block181), str(lba_end)], check=True)

# 14. Verify the REAL font in file 59 sub-file 0 slot 16 has 草
# (F0086.BIN is NOT the font source — the game uses file 59 sub-file 0)
block59 = struct.unpack_from('<I', main_filepos, 59*8)[0]
size59  = struct.unpack_from('<I', main_filepos, 59*8 + 4)[0]
arch59 = read_sectors(MAIN, block59, size59)
sub0_off, sub0_len = archive_subfile_offsets(bytes(arch59))[0]
sub0 = bytes(arch59[sub0_off:sub0_off + sub0_len])
sub0_total = struct.unpack_from('<I', sub0, 4)[0]
sub0_uncomp = struct.unpack_from('<I', sub0, 8)[0]
font_data = lzss_decompress(sub0, 12, sub0_total - 12, sub0_uncomp)
slot16 = font_data[0x480 + 16*18 : 0x480 + 16*18 + 18]
GRASS_BYTES = bytes.fromhex('88e07f88c01ffc4110fc0102ff0702200000')
print(f'\n文件 59 sub-file 0 slot 16: {slot16.hex()}')
if slot16 == GRASS_BYTES:
    print(f'  ✓ 草 bitmap 已就绪 → 游戏对话第二行应显示 草……？')
else:
    print(f'  ⚠ slot 16 不是 草。')
    print(f'    如果还没运行 inject_grass_into_file59.py，请先跑：')
    print(f'    python3 tools/inject_grass_into_file59.py')
