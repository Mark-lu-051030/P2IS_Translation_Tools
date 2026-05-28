"""
二分定位脚本：inject 前 N 个字符（按 needed_new 排序），看能跑多远。

用法:
  python3 test_inject_n.py 1500   # 全部 (~崩)
  python3 test_inject_n.py 750    # 一半
  python3 test_inject_n.py 100    # 少量
"""
import os, sys, struct, subprocess, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from pylib.p2is import (
    read_sectors, write_sectors,
    lzss_decompress, lzss_compress,
    archive_subfile_offsets,
)

if len(sys.argv) < 2:
    print('用法: python3 test_inject_n.py <N>')
    sys.exit(1)
N = int(sys.argv[1])

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO_PATH   = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BACKUP_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
TTF_PATH   = os.path.join(ROOT, 'fusion-pixel-12px.otf')
FIX_ECC    = os.path.join(ROOT, 'fix_ecc.py')
CODETABLE_OG  = os.path.join(ROOT, 'codetable_og.json')
TRANS_JSON    = os.path.join(ROOT, 'all_translatable.json')
FONT_FILE  = 59
TARGET_OFFSET = 61440
ALLOC_TOP = 3575
ALLOC_BOTTOM = 100

TTF = ImageFont.truetype(TTF_PATH, 12)

def render_char(ch):
    img = Image.new('L', (12, 11), 0)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), ch, font=TTF)
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    x = (12 - w) // 2 - bbox[0]
    y = (11 - h) // 2 - bbox[1]
    draw.text((x, y), ch, fill=255, font=TTF)
    bits = [1 if p > 64 else 0 for p in img.getdata()]
    result = bytearray(18)
    for i, b in enumerate(bits):
        if b: result[i // 8] |= (1 << (i % 8))
    return bytes(result)

def create_valid_ps1_sector(lba):
    abs_sect = lba + 150
    m = abs_sect // 4500; s = (abs_sect % 4500) // 75; f = abs_sect % 75
    to_bcd = lambda v: (v // 10) * 16 + (v % 10)
    sector = bytearray(2352)
    sector[0:12] = b'\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x00'
    sector[12:15] = bytes([to_bcd(m), to_bcd(s), to_bcd(f)])
    sector[15] = 0x02
    sector[16:24] = b'\x00\x00\x08\x00\x00\x00\x08\x00'
    return sector

# 1. 收集 needed 字符（与 ijc.py 同样逻辑）
data = json.load(open(TRANS_JSON, encoding='utf-8'))
needed = set()
def collect_chars(text):
    clean = re.sub(r'<[^>]+/?>', '', text)
    for c in clean:
        if '一' <= c <= '鿿' or '㐀' <= c <= '䶿':
            needed.add(c)
for entry in data:
    for page in entry.get('pages', []):
        collect_chars(page.get('zh', '') or '')
    collect_chars(entry.get('meta_zh', '') or '')
needed = sorted(needed)

ct_og = json.load(open(CODETABLE_OG, encoding='utf-8'))
og_chars = set(v for v in ct_og.values() if isinstance(v, str) and len(v) == 1)

# 2. 只取 og 没有的新字符，前 N 个
needed_new = [c for c in needed if c not in og_chars]
print(f'needed_new 总数: {len(needed_new)}, 这次 inject 前 {N} 个')
inject_list = needed_new[:N]

# 3. 分配 slot：从 ALLOC_TOP 往下
og_slots = set(int(k) for k in ct_og.keys())
assignments = {}
slot = ALLOC_TOP
for ch in inject_list:
    while slot in og_slots and ct_og.get(str(slot)) in needed:  # 跳过 og 里的 needed 字
        slot -= 1
    if slot < ALLOC_BOTTOM:
        print(f'错误：slot 用到 {ALLOC_BOTTOM} 以下')
        sys.exit(1)
    assignments[ch] = slot
    slot -= 1

print(f'实际分配 {len(assignments)} 个 slot，范围 {min(assignments.values())} - {max(assignments.values())}')

# 4. 读 backup file 59，解压 sub0，inject，重压缩
fp = read_sectors(BACKUP_ISO, 0x17, 0x1b88)
block59 = struct.unpack_from('<I', fp, FONT_FILE * 8)[0]
size59  = struct.unpack_from('<I', fp, FONT_FILE * 8 + 4)[0]
arch = read_sectors(BACKUP_ISO, block59, size59)
subs = archive_subfile_offsets(arch)
sub0 = arch[subs[0][0]:subs[0][0]+subs[0][1]]
tag_bytes = bytes(sub0[0:4])
tc = struct.unpack_from('<I', sub0, 4)[0]
uc = struct.unpack_from('<I', sub0, 8)[0]
d = bytearray(lzss_decompress(sub0, 12, tc-12, uc))

for ch, idx in assignments.items():
    bmp = render_char(ch)
    off = 0x480 + idx * 18
    d[off:off+18] = bmp

recomp = bytearray(lzss_compress(bytes(d), 12))
recomp[0:4] = tag_bytes
struct.pack_into('<I', recomp, 4, len(recomp))
struct.pack_into('<I', recomp, 8, len(d))
print(f'重压缩: {len(recomp)} 字节')

if len(recomp) > TARGET_OFFSET:
    print(f'错误: recomp 太大: {len(recomp)} > {TARGET_OFFSET}')
    sys.exit(1)

# 5. 拼新 archive
sub1 = bytes(arch[subs[1][0]:subs[1][0]+subs[1][1]])
new_size = TARGET_OFFSET + len(sub1)
arch_new = bytearray(new_size)
arch_new[:len(recomp)] = recomp
arch_new[TARGET_OFFSET:TARGET_OFFSET+len(sub1)] = sub1

# 6. 追加到 working
with open(ISO_PATH, 'r+b') as f:
    f.seek(0, 2)
    new_lba = f.tell() // 2352
    nsec = (new_size + 2047) // 2048
    for i in range(nsec):
        f.write(create_valid_ps1_sector(new_lba + i))
write_sectors(ISO_PATH, new_lba, bytes(arch_new))

fp = bytearray(read_sectors(ISO_PATH, 0x17, 4*2048))
struct.pack_into('<I', fp, FONT_FILE * 8, new_lba)
struct.pack_into('<I', fp, FONT_FILE * 8 + 4, new_size)
write_sectors(ISO_PATH, 0x17, bytes(fp))

new_total = new_lba + nsec
pvd = bytearray(read_sectors(ISO_PATH, 16, 2048))
struct.pack_into('<I', pvd, 80, new_total)
struct.pack_into('>I', pvd, 84, new_total)
write_sectors(ISO_PATH, 16, bytes(pvd))

subprocess.run(['python3', FIX_ECC, str(new_lba), str(new_lba + nsec - 1)], check=True)
subprocess.run(['python3', FIX_ECC, '23', '26'], check=True)
subprocess.run(['python3', FIX_ECC, '16', '16'], check=True)
print(f'\n✅ inject {len(assignments)} 个字完成。LBA {new_lba}, sub0={len(recomp)}B')
