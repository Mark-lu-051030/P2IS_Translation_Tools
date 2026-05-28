"""inject N 个字到 [start, start+N) slot 范围。
用法: python3 test_inject_at.py <start_slot> <count>
"""
import os, sys, struct, subprocess, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from pylib.p2is import (
    read_sectors, write_sectors,
    lzss_decompress, lzss_compress, archive_subfile_offsets,
)

if len(sys.argv) < 3:
    print('用法: python3 test_inject_at.py <start_slot> <count>')
    print('  例: python3 test_inject_at.py 3556 1   (在 slot 3556 inject 1 个字)')
    print('       python3 test_inject_at.py 3000 20  (slot 3000-3019)')
    sys.exit(1)

START = int(sys.argv[1])
COUNT = int(sys.argv[2])

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BAK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')
TTF = ImageFont.truetype(os.path.join(ROOT, 'fusion-pixel-12px.otf'), 12)

def render(ch):
    img = Image.new('L', (12, 11), 0)
    dr = ImageDraw.Draw(img)
    bbox = dr.textbbox((0, 0), ch, font=TTF)
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    x = (12 - w) // 2 - bbox[0]; y = (11 - h) // 2 - bbox[1]
    dr.text((x, y), ch, fill=255, font=TTF)
    bits = [1 if p > 64 else 0 for p in img.getdata()]
    r = bytearray(18)
    for i, b in enumerate(bits):
        if b: r[i // 8] |= (1 << (i % 8))
    return bytes(r)

def make_sec(lba):
    a = lba + 150
    m, s, f = a // 4500, (a % 4500) // 75, a % 75
    bcd = lambda v: (v // 10) * 16 + (v % 10)
    sec = bytearray(2352)
    sec[0:12] = b'\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x00'
    sec[12:15] = bytes([bcd(m), bcd(s), bcd(f)])
    sec[15] = 0x02
    sec[16:24] = b'\x00\x00\x08\x00\x00\x00\x08\x00'
    return sec

# 读 backup file 59
fp = read_sectors(BAK, 0x17, 0x1b88)
b59 = struct.unpack_from('<I', fp, 59*8)[0]
s59 = struct.unpack_from('<I', fp, 59*8 + 4)[0]
arch = read_sectors(BAK, b59, s59)
subs = archive_subfile_offsets(arch)
sub0 = arch[subs[0][0]:subs[0][0]+subs[0][1]]
tag = bytes(sub0[0:4])
tc = struct.unpack_from('<I', sub0, 4)[0]
uc = struct.unpack_from('<I', sub0, 8)[0]
d = bytearray(lzss_decompress(sub0, 12, tc-12, uc))

# 准备中文字符
data = json.load(open(os.path.join(ROOT, 'all_translatable.json'), encoding='utf-8'))
needed = set()
def col(t):
    c = re.sub(r'<[^>]+/?>', '', t)
    for ch in c:
        if '一' <= ch <= '鿿' or '㐀' <= ch <= '䶿': needed.add(ch)
for e in data:
    for p in e.get('pages', []): col(p.get('zh', '') or '')
    col(e.get('meta_zh', '') or '')
ct_og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
og_chars = set(v for v in ct_og.values() if isinstance(v, str) and len(v) == 1)
needed_new = sorted(c for c in needed if c not in og_chars)

if COUNT > len(needed_new):
    print(f'警告: count > 可用新字数, 取所有 {len(needed_new)} 个')
    COUNT = len(needed_new)

print(f'inject {COUNT} 字到 slot {START}-{START+COUNT-1}:')
for i in range(COUNT):
    slot = START + i
    ch = needed_new[i]
    d[0x480 + slot*18:0x480 + slot*18 + 18] = render(ch)
    if i < 5 or i == COUNT - 1:
        og_val = ct_og.get(str(slot), '<空>')
        print(f'  slot {slot} ← {ch} (覆盖 og={og_val})')

recomp = bytearray(lzss_compress(bytes(d), 12))
recomp[0:4] = tag
struct.pack_into('<I', recomp, 4, len(recomp))
struct.pack_into('<I', recomp, 8, len(d))
print(f'重压缩: {len(recomp)} 字节')
assert len(recomp) <= 61440

sub1 = bytes(arch[subs[1][0]:subs[1][0]+subs[1][1]])
new_size = 61440 + len(sub1)
arch_new = bytearray(new_size)
arch_new[:len(recomp)] = recomp
arch_new[61440:61440 + len(sub1)] = sub1

with open(ISO, 'r+b') as f:
    f.seek(0, 2)
    new_lba = f.tell() // 2352
    nsec = (new_size + 2047) // 2048
    for i in range(nsec):
        f.write(make_sec(new_lba + i))
write_sectors(ISO, new_lba, bytes(arch_new))

fp = bytearray(read_sectors(ISO, 0x17, 4*2048))
struct.pack_into('<I', fp, 59*8, new_lba)
struct.pack_into('<I', fp, 59*8 + 4, new_size)
write_sectors(ISO, 0x17, bytes(fp))

new_total = new_lba + nsec
pvd = bytearray(read_sectors(ISO, 16, 2048))
struct.pack_into('<I', pvd, 80, new_total)
struct.pack_into('>I', pvd, 84, new_total)
write_sectors(ISO, 16, bytes(pvd))

subprocess.run(['python3', FIX_ECC, str(new_lba), str(new_lba + nsec - 1)], check=True)
subprocess.run(['python3', FIX_ECC, '23', '26'], check=True)
subprocess.run(['python3', FIX_ECC, '16', '16'], check=True)
print(f'\n✅ inject {COUNT} 字到 slot {START}-{START+COUNT-1} 完成')
