"""
Extract candidate font files from ISO for CrystalTile2 inspection.
Extracts:
  - file 86  (F0086.BIN, 65520 bytes, 0x480 header + 3558 × 18-byte glyphs)
  - file 140 (68814 bytes, 3823 × 18-byte glyphs, no header)

CrystalTile2 settings to view the extracted .bin files:
  Graphics → Open → select .bin file
  Bit depth : 1 BPP (1 bit per pixel)
  Tile width : 12
  Tile height: 12
  The tiles will appear left-to-right, top-to-bottom in slot order.
"""
import struct, os

ISO    = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
SECTOR = 2352
BLOCK_OFF  = 0x18
BLOCK_SIZE = 0x800

def read_file(iso_path, block, size):
    data = bytearray()
    sec  = block * SECTOR
    with open(iso_path, 'rb') as f:
        while len(data) < size:
            f.seek(sec)
            raw   = f.read(SECTOR)
            chunk = min(BLOCK_SIZE, size - len(data))
            data += raw[BLOCK_OFF:BLOCK_OFF + chunk]
            sec  += SECTOR
    return bytes(data[:size])

# Read FILEPOS.DAT
with open(ISO, 'rb') as f:
    f.seek(0x17 * SECTOR)
    raw = bytearray()
    for _ in range((0x1b88 + BLOCK_SIZE - 1) // BLOCK_SIZE):
        s = f.read(SECTOR)
        raw += s[BLOCK_OFF:BLOCK_OFF + BLOCK_SIZE]
filepos = raw[:0x1b88]

def get_entry(n):
    block = struct.unpack_from('<I', filepos, n * 8)[0]
    size  = struct.unpack_from('<I', filepos, n * 8 + 4)[0]
    return block, size

for file_num, label in [(86, 'F0086'), (140, 'F0140')]:
    block, size = get_entry(file_num)
    print(f'File {file_num}: block={block}  size={size}')
    data = read_file(ISO, block, size)
    out = f'extracted_{label}.bin'
    open(out, 'wb').write(data)
    print(f'  → {out}  ({len(data)} bytes)')

    # Show first few glyph slots
    if label == 'F0086':
        header = 0x480
        print(f'  Header: 0x480 ({header} bytes), glyphs start at offset {header}')
        print(f'  Glyph count: {(len(data) - header) // 18}')
        for slot in [16, 35, 215]:
            off = header + slot * 18
            bmp = data[off:off+18]
            print(f'  Slot {slot:4d}: {bmp.hex()}')
    else:  # F0140
        print(f'  No header, glyph count: {len(data) // 18}  (remainder {len(data) % 18})')
        for slot in [16, 35, 215]:
            off = slot * 18
            bmp = data[off:off+18]
            print(f'  Slot {slot:4d}: {bmp.hex()}')

print('\nDone. Open extracted_F0140.bin in CrystalTile2:')
print('  Codec: 1BPP  |  Width: 12  |  Height: 12')
print('  Slot 35 should show the … glyph (top-left area of tile view)')
print('  Slot 215 should be visible to compare with in-game rendering')
