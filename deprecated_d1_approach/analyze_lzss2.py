"""详细看原版 vs inject 版 在 offset=1 (以及其他小 offset) 时的 length 分布。"""
import os, sys, struct, json, re
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageFont, ImageDraw
from pylib.p2is import (
    read_sectors, lzss_decompress, lzss_compress, archive_subfile_offsets,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKUP_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
TTF = ImageFont.truetype(os.path.join(ROOT, 'fusion-pixel-12px.otf'), 12)

def render_char(ch):
    img = Image.new('L', (12, 11), 0)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), ch, font=TTF)
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    x = (12 - w) // 2 - bbox[0]; y = (11 - h) // 2 - bbox[1]
    draw.text((x, y), ch, fill=255, font=TTF)
    bits = [1 if p > 64 else 0 for p in img.getdata()]
    r = bytearray(18)
    for i, b in enumerate(bits):
        if b: r[i // 8] |= (1 << (i % 8))
    return bytes(r)

def parse(data, start, end):
    tokens = []
    ptr = start
    while ptr < end:
        b = data[ptr]; ptr += 1
        if b & 0x80:
            count = (b & 0x7f) + 3
            offset = data[ptr] + 1; ptr += 1
            tokens.append(('ref', count, offset))
        else:
            count = b + 1
            tokens.append(('lit', count, 0))
            ptr += count
    return tokens

def length_dist_by_offset(toks):
    """{offset: Counter(length)}"""
    out = {}
    for kind, length, off in toks:
        if kind == 'ref':
            out.setdefault(off, Counter())[length] += 1
    return out

# 原版
arch = read_sectors(BACKUP_ISO, 66625, 102400)
subs = archive_subfile_offsets(arch)
sub0 = arch[subs[0][0]:subs[0][0]+subs[0][1]]
tc = struct.unpack_from('<I', sub0, 4)[0]
uc = struct.unpack_from('<I', sub0, 8)[0]
toks_og = parse(sub0, 12, tc)

# 重压缩 + inject 20
decompressed = lzss_decompress(sub0, 12, tc-12, uc)
TRANS = os.path.join(ROOT, 'all_translatable.json')
CT_OG = os.path.join(ROOT, 'codetable_og.json')
data = json.load(open(TRANS, encoding='utf-8'))
needed = set()
def col(t):
    c = re.sub(r'<[^>]+/?>', '', t)
    for ch in c:
        if '一' <= ch <= '鿿' or '㐀' <= ch <= '䶿': needed.add(ch)
for e in data:
    for p in e.get('pages', []): col(p.get('zh', '') or '')
    col(e.get('meta_zh', '') or '')
ct_og = json.load(open(CT_OG, encoding='utf-8'))
og_chars = set(v for v in ct_og.values() if isinstance(v, str) and len(v) == 1)
needed_new = sorted(c for c in needed if c not in og_chars)[:20]

d = bytearray(decompressed)
slot = 3575
for ch in needed_new:
    d[0x480 + slot*18:0x480 + slot*18 + 18] = render_char(ch)
    slot -= 1
recomp = bytearray(lzss_compress(bytes(d), 12))
toks_in = parse(bytes(recomp), 12, len(recomp))

dist_og = length_dist_by_offset(toks_og)
dist_in = length_dist_by_offset(toks_in)

# 看小 offset (1, 2, 3, 4, 5) 的 length 分布
print('=== offset 1-10 的 length 分布对比 ===')
print(f'{"offset":>6} {"原版 max":>10} {"原版 count":>12} {"inject max":>12} {"inject count":>14}')
for off in range(1, 11):
    og_lens = dist_og.get(off, Counter())
    in_lens = dist_in.get(off, Counter())
    og_max = max(og_lens) if og_lens else 0
    og_count = sum(og_lens.values())
    in_max = max(in_lens) if in_lens else 0
    in_count = sum(in_lens.values())
    marker = ' ← inject 超过原版' if in_max > og_max else ''
    print(f'{off:>6} {og_max:>10} {og_count:>12} {in_max:>12} {in_count:>14}{marker}')

# 看所有 offset 下 length 超过原版同 offset max 的情况
print('\n=== inject 版超过原版 length 上限的 backref (按 offset) ===')
violations = []
for off, in_lens in dist_in.items():
    og_lens = dist_og.get(off, Counter())
    og_max = max(og_lens) if og_lens else 0
    for ln, cnt in in_lens.items():
        if ln > og_max:
            violations.append((off, ln, cnt, og_max))
violations.sort(key=lambda x: (x[0], -x[1]))
for off, ln, cnt, og_max in violations[:30]:
    print(f'  offset={off}, length={ln} (inject {cnt} 次, 原版同 offset max length={og_max})')
print(f'\n总共 {len(violations)} 种 (offset, length) 超出原版上限')

# 全局最大 length per offset
print('\n=== 原版各 offset 的 length 上限（offset=1~30）===')
for off in range(1, 31):
    if off in dist_og:
        og_max = max(dist_og[off])
        print(f'  offset={off:>2}: max length={og_max}')
