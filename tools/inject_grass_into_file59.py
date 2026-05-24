"""
THE FIX: inject 草 at slot 16 of file 59 sub-file 0 (the REAL dialog font).

Background: F0086.BIN looked like the font but isn't — the game uses a COMPRESSED
copy in file 59 sub-file 0 (decompresses to 65520 bytes, same format as F0086.BIN
with 0x480 header + 18-byte 12×12 1bpp glyphs).

Also: restore F0086.BIN slot 16 and 63 to their original backup values (since
modifying F0086.BIN has no visible effect — keep it clean).
"""
import struct, sys, subprocess, os

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

GRASS_BYTES = bytes.fromhex('88e07f88c01ffc4110fc0102ff0702200000')  # 草 (18 bytes, slot 16)

# ──────────────────────────────────────────────────────────────────────────────
# Step 1: Restore F0086.BIN to original (undo useless prior modifications)
# ──────────────────────────────────────────────────────────────────────────────
print('Step 1: Restore F0086.BIN to original (was modified pointlessly)')
fp = read_sectors(BACKUP, 0x17, 0x1b88)
block86 = struct.unpack_from('<I', fp, 86*8)[0]
size86  = struct.unpack_from('<I', fp, 86*8 + 4)[0]
font_orig = read_sectors(BACKUP, block86, size86)
write_sectors(MAIN, block86, bytes(font_orig))
print(f'  F0086.BIN restored from backup ({size86} bytes)')

# Step 2: Modify file 59 sub-file 0 → set slot 16 to 草
# ──────────────────────────────────────────────────────────────────────────────
print('\nStep 2: Modify file 59 sub-file 0 (the REAL font)')
block59 = struct.unpack_from('<I', fp, 59*8)[0]
size59  = struct.unpack_from('<I', fp, 59*8 + 4)[0]
print(f'  File 59: block={block59}, size={size59}')

arch = read_sectors(BACKUP, block59, size59)
subs = archive_subfile_offsets(arch)
print(f'  Sub-files: {len(subs)}')

sub0_off, sub0_len = subs[0]
sub0 = arch[sub0_off:sub0_off + sub0_len]
tag_bytes = bytes(sub0[0:4])
total_comp = struct.unpack_from('<I', sub0, 4)[0]
uncomp_size = struct.unpack_from('<I', sub0, 8)[0]
print(f'  Sub 0: tag={tag_bytes.hex()}, comp={total_comp}, uncomp={uncomp_size}')

# Decompress sub 0
decompressed = bytearray(lzss_decompress(sub0, 12, total_comp - 12, uncomp_size))
print(f'  Decompressed to {len(decompressed)} bytes')
assert len(decompressed) == 65520

# Verify slot 16 has original い bytes
slot16_off = 0x480 + 16 * 18  # = 1440 = 0x5A0
original_slot16 = bytes(decompressed[slot16_off:slot16_off + 18])
print(f'  Slot 16 BEFORE: {original_slot16.hex()}')
expected_i = bytes.fromhex('00000081101001112001122002a200040000')
assert original_slot16 == expected_i, f'Expected い bytes, got something else'

# Inject 草
decompressed[slot16_off:slot16_off + 18] = GRASS_BYTES
new_slot16 = bytes(decompressed[slot16_off:slot16_off + 18])
print(f'  Slot 16 AFTER:  {new_slot16.hex()}')
assert new_slot16 == GRASS_BYTES

# Recompress
print('  Recompressing...')
recomp = bytearray(lzss_compress(bytes(decompressed), 12))
recomp[0:4] = tag_bytes  # preserve original tag
struct.pack_into('<I', recomp, 4, len(recomp))
struct.pack_into('<I', recomp, 8, len(decompressed))
print(f'  Recompressed: {len(recomp)} bytes (was {sub0_len})')

# Check size fits
available_for_sub0 = subs[1][0] - sub0_off  # next sub-file's offset - current start
print(f'  Available space for sub 0: {available_for_sub0} bytes')
if len(recomp) > available_for_sub0:
    print(f'  ERROR: recompressed too large ({len(recomp)} > {available_for_sub0})')
    sys.exit(1)

# Patch archive: zero sub 0 space, then write new
arch_patched = bytearray(arch)
arch_patched[sub0_off:sub0_off + available_for_sub0] = bytes(available_for_sub0)
arch_patched[sub0_off:sub0_off + len(recomp)] = recomp
assert len(arch_patched) == size59

# Step 3: Write file 59 back to ISO
# ──────────────────────────────────────────────────────────────────────────────
print('\nStep 3: Write modified file 59 to MAIN ISO')
write_sectors(MAIN, block59, bytes(arch_patched))
print('  Done')

# Verify written tag
verify = read_sectors(MAIN, block59, 32)
print(f'  First 16 bytes of file 59 in MAIN: {bytes(verify[:16]).hex()}')

# Step 4: Compute ECC fix range
# ──────────────────────────────────────────────────────────────────────────────
sector_count = (size59 + BLOCK_SIZE - 1) // BLOCK_SIZE
lba_end = block59 + sector_count - 1
print(f'\nStep 4: Fixing ECC for file 59 (LBA {block59} to {lba_end}, {sector_count} sectors)')
subprocess.run(['python3', FIX_ECC, str(block59), str(lba_end)], check=True)

# Also fix F0086.BIN ECC (since we restored it from backup, ECC should be ok but verify)
sector_count_86 = (size86 + BLOCK_SIZE - 1) // BLOCK_SIZE
lba_end_86 = block86 + sector_count_86 - 1
print(f'Fixing ECC for F0086.BIN (LBA {block86} to {lba_end_86})')
subprocess.run(['python3', FIX_ECC, str(block86), str(lba_end_86)], check=True)

print('\n🎯 DONE. Expected result in game:')
print('  - File 181 diag0 position [9] = code 16 (we set this earlier)')
print('  - File 59 sub 0 slot 16 = 草 glyph bitmap')
print('  - Dialog should show 草 in the name brackets instead of い')
