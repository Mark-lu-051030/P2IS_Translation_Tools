"""
Recalculate ECC/EDC for modified PS1 ISO sectors (Mode 2 Form 1).
Usage: python3 fix_ecc.py <lba_start> <lba_end>
"""
import struct, sys

SECTOR = 2352

# ── EDC ───────────────────────────────────────────────────────────
def _make_edc_lut():
    t = []
    for i in range(256):
        r = i
        for _ in range(8):
            r = (r >> 1) ^ (0xD8018001 if (r & 1) else 0)
        t.append(r & 0xFFFFFFFF)
    return t

_EDC_LUT = _make_edc_lut()

def _edc(data, start, length):
    r = 0
    for i in range(length):
        r = (r >> 8) ^ _EDC_LUT[(r ^ data[start + i]) & 0xFF]
    return r & 0xFFFFFFFF

# ── GF(2^8) for ECC ───────────────────────────────────────────────
_gf_exp = [0] * 512
_gf_log = [0] * 256

def _init_gf():
    x = 1
    for i in range(255):
        _gf_exp[i] = x
        _gf_log[x] = i
        x <<= 1
        if x & 0x100:
            x ^= 0x11D
        x &= 0xFF
    for i in range(255, 512):
        _gf_exp[i] = _gf_exp[i - 255]

_init_gf()

# ── ECC block ─────────────────────────────────────────────────────
def _ecc_block(src, major_count, minor_count, major_mult, minor_inc):
    out = bytearray(major_count * 2)
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a, b = 0, 0
        for _ in range(minor_count):
            temp = src[index]
            index += minor_inc
            if index >= len(src):
                index -= len(src)
            a ^= temp
            b ^= temp
            a = _gf_exp[_gf_log[a] + 1] if a else 0
        a = _gf_exp[255 - _gf_log[a]] if a else 0
        b ^= a
        out[major * 2]     = a
        out[major * 2 + 1] = _gf_exp[_gf_log[b] + 1] if b else 0
    return out

# ── Fix one sector ────────────────────────────────────────────────
def fix_sector(raw):
    """raw: 2352-byte bytes/bytearray. Returns corrected bytearray."""
    s = bytearray(raw)
    # 1. EDC covers subheader + user data = bytes [16..2071]
    edc = _edc(s, 16, 2056)
    struct.pack_into('<I', s, 2072, edc)
    # 2. P parity: src = bytes [12..2075] = 2064 bytes
    src_p = bytes(s[12:2076])
    p = _ecc_block(src_p, 86, 24, 2, 86)   # 172 bytes → [2076..2247]
    s[2076:2248] = p
    # 3. Q parity: src = bytes [12..2247] = 2236 bytes (includes P)
    src_q = bytes(s[12:2248])
    q = _ecc_block(src_q, 52, 43, 86, 88)  # 104 bytes → [2248..2351]
    s[2248:2352] = q
    return s

# ── Main ──────────────────────────────────────────────────────────
ISO = '/home/mark/Code/ROMHacking/games/Persona2IS/p2.bin'

def fix_range(lba_start, lba_end):
    fixed = 0
    with open(ISO, 'r+b') as f:
        for lba in range(lba_start, lba_end + 1):
            f.seek(lba * SECTOR)
            raw = f.read(SECTOR)
            if len(raw) < SECTOR:
                break
            # Only fix Mode 2 sectors
            if raw[15] != 2:
                continue
            new = fix_sector(raw)
            f.seek(lba * SECTOR)
            f.write(bytes(new))
            fixed += 1
    print(f'Fixed {fixed} sectors (LBA {lba_start}–{lba_end})')

def verify_one(lba):
    """Check that ECC/EDC are correct for given sector (self-test)."""
    with open(ISO, 'rb') as f:
        f.seek(lba * SECTOR)
        raw = bytearray(f.read(SECTOR))
    if raw[15] != 2:
        print(f'LBA {lba}: not Mode 2, skip')
        return
    # Compute expected EDC
    expected_edc = _edc(raw, 16, 2056)
    stored_edc   = struct.unpack_from('<I', raw, 2072)[0]
    print(f'LBA {lba}: EDC expected={expected_edc:08x} stored={stored_edc:08x} {"OK" if expected_edc==stored_edc else "MISMATCH"}')

if __name__ == '__main__':
    if len(sys.argv) == 3:
        fix_range(int(sys.argv[1]), int(sys.argv[2]))
    elif len(sys.argv) == 2 and sys.argv[1] == 'verify':
        # Verify a few known sectors
        verify_one(23)    # FILEPOS.DAT
        verify_one(29297) # file 3 (scripts)
        verify_one(67424) # file 86 (font)
    else:
        print('Usage:')
        print('  python3 fix_ecc.py <lba_start> <lba_end>   # fix range')
        print('  python3 fix_ecc.py verify                  # check EDC on key sectors')
