"""精确对比 inject 16 字 vs 17 字时 LZSS 字节流的差异。
找出第 17 个字加入后字节流变了什么。"""
import os, sys, struct, json, re
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from pylib.p2is import (
    read_sectors, lzss_decompress, lzss_compress, archive_subfile_offsets,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
BAK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
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

def parse(data, start, end):
    toks = []
    ptr = start
    while ptr < end:
        b = data[ptr]; ptr += 1
        if b & 0x80:
            cnt = (b & 0x7f) + 3
            off = data[ptr] + 1; ptr += 1
            toks.append(('ref', cnt, off))
        else:
            cnt = b + 1
            toks.append(('lit', cnt, 0))
            ptr += cnt
    return toks

# 准备
arch = read_sectors(BAK, 66625, 102400)
subs = archive_subfile_offsets(arch)
sub0 = arch[subs[0][0]:subs[0][0]+subs[0][1]]
tc = struct.unpack_from('<I', sub0, 4)[0]
uc = struct.unpack_from('<I', sub0, 8)[0]
decompressed = bytearray(lzss_decompress(sub0, 12, tc-12, uc))

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

# 列出前 20 个 inject 的字符
print('前 20 个 inject 的字符:')
for i, c in enumerate(needed_new[:20]):
    marker = ' ← 第 17 个 (开始崩)' if i == 16 else ''
    print(f'  [{i+1}] slot {3575-i}: {c}{marker}')

# inject 16 字版本
d16 = bytearray(decompressed)
for i in range(16):
    slot = 3575 - i
    d16[0x480 + slot*18:0x480 + slot*18 + 18] = render(needed_new[i])
recomp16 = bytearray(lzss_compress(bytes(d16), 12))

# inject 17 字版本
d17 = bytearray(decompressed)
for i in range(17):
    slot = 3575 - i
    d17[0x480 + slot*18:0x480 + slot*18 + 18] = render(needed_new[i])
recomp17 = bytearray(lzss_compress(bytes(d17), 12))

print(f'\nN=16 重压缩: {len(recomp16)} 字节')
print(f'N=17 重压缩: {len(recomp17)} 字节')
print(f'差异:        {len(recomp17) - len(recomp16)} 字节')

t16 = parse(bytes(recomp16), 12, len(recomp16))
t17 = parse(bytes(recomp17), 12, len(recomp17))

# 各自 backref offset / length 分布
def stat(toks):
    refs = [(t[1], t[2]) for t in toks if t[0] == 'ref']
    return Counter(refs), Counter(t[1] for t in toks if t[0] == 'ref'), Counter(t[2] for t in toks if t[0] == 'ref')

r16, len16, off16 = stat(t16)
r17, len17, off17 = stat(t17)

# 找 17 版独有
unique_17 = set(r17) - set(r16)
unique_16 = set(r16) - set(r17)
print(f'\n17 版独有的 (length, offset): {len(unique_17)} 种')
for ln, off in sorted(unique_17, key=lambda x: (-x[0], -x[1]))[:15]:
    print(f'  length={ln}, offset={off}, 次数={r17[(ln, off)]}')

print(f'\n16 版有但 17 版没有的 (length, offset): {len(unique_16)} 种')
for ln, off in sorted(unique_16, key=lambda x: (-x[0], -x[1]))[:10]:
    print(f'  length={ln}, offset={off}, 次数={r16[(ln, off)]}')

# 最大 backref length / offset 对比
print(f'\nN=16 max backref length={max(len16)}, max offset={max(off16)}')
print(f'N=17 max backref length={max(len17)}, max offset={max(off17)}')

# 看 sub0 末尾区域的字节流变化（从哪个 offset 开始两者不同）
diff_start = None
for i in range(min(len(recomp16), len(recomp17))):
    if recomp16[i] != recomp17[i]:
        diff_start = i
        break
print(f'\n字节流首次出现差异: byte offset {diff_start}')
if diff_start is not None:
    print(f'  N=16 此处: {recomp16[diff_start:diff_start+20].hex()}')
    print(f'  N=17 此处: {recomp17[diff_start:diff_start+20].hex()}')
