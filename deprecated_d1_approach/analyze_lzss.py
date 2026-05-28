"""
对比原版 sub-file 0 的 LZSS 字节流 vs 我们 inject 后重压缩的字节流。
找出我们产生但原版没出现的 backref / literal 模式 — 这些就是 PS1 解压器可能挂的根因。

输出:
  - 原版 backref (count, offset) 分布
  - 重压缩后 backref 分布
  - 差异：仅在新版出现的模式
  - literal run 长度分布
"""
import os, sys, struct, json, re
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from pylib.p2is import (
    read_sectors, lzss_decompress, lzss_compress, archive_subfile_offsets,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKUP_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
TTF_PATH = os.path.join(ROOT, 'fusion-pixel-12px.otf')
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


def parse_lzss_tokens(data, start, end):
    """返回 [(kind, count, offset/0), ...]
    kind: 'lit' = literal run, 'ref' = backref"""
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


def analyze(label, stream, comp_start, comp_end):
    toks = parse_lzss_tokens(stream, comp_start, comp_end)
    n_lit = sum(1 for t in toks if t[0] == 'lit')
    n_ref = sum(1 for t in toks if t[0] == 'ref')
    lit_lengths = Counter(t[1] for t in toks if t[0] == 'lit')
    ref_lengths = Counter(t[1] for t in toks if t[0] == 'ref')
    ref_offsets = Counter(t[2] for t in toks if t[0] == 'ref')

    print(f'\n=== {label} ===')
    print(f'  字节流: {comp_end - comp_start} 字节, tokens: {len(toks)}')
    print(f'  literal: {n_lit}, backref: {n_ref}')
    print(f'  literal 长度: min={min(lit_lengths)}, max={max(lit_lengths)}, top5={lit_lengths.most_common(5)}')
    print(f'  backref length: min={min(ref_lengths)}, max={max(ref_lengths)}, top5={ref_lengths.most_common(5)}')
    print(f'  backref offset: min={min(ref_offsets)}, max={max(ref_offsets)}, top5={ref_offsets.most_common(5)}')

    return toks, ref_lengths, ref_offsets, lit_lengths


# 1. 读原版 sub0
arch = read_sectors(BACKUP_ISO, 66625, 102400)
subs = archive_subfile_offsets(arch)
sub0 = arch[subs[0][0]:subs[0][0]+subs[0][1]]
tc = struct.unpack_from('<I', sub0, 4)[0]
uc = struct.unpack_from('<I', sub0, 8)[0]

# 原版字节流（从 backup ISO 上直接读取）
toks_og, ref_len_og, ref_off_og, lit_len_og = analyze(
    '原版 sub0 (backup ISO 原始 LZSS 流)', sub0, 12, tc
)

# 2. 重压缩 (不 inject)
decompressed = lzss_decompress(sub0, 12, tc-12, uc)
recomp = bytearray(lzss_compress(bytes(decompressed), 12))
recomp_total = len(recomp)
toks_re, ref_len_re, ref_off_re, lit_len_re = analyze(
    '重压缩 sub0 (no inject)', bytes(recomp), 12, recomp_total
)

# 3. 重压缩 + inject 20 个字（崩溃的最低量级）
TRANS_JSON = os.path.join(ROOT, 'all_translatable.json')
CODETABLE_OG = os.path.join(ROOT, 'codetable_og.json')
data = json.load(open(TRANS_JSON, encoding='utf-8'))
needed = set()
def collect(text):
    clean = re.sub(r'<[^>]+/?>', '', text)
    for c in clean:
        if '一' <= c <= '鿿' or '㐀' <= c <= '䶿':
            needed.add(c)
for entry in data:
    for page in entry.get('pages', []):
        collect(page.get('zh', '') or '')
    collect(entry.get('meta_zh', '') or '')
ct_og = json.load(open(CODETABLE_OG, encoding='utf-8'))
og_chars = set(v for v in ct_og.values() if isinstance(v, str) and len(v) == 1)
needed_new = sorted(c for c in needed if c not in og_chars)[:20]

d = bytearray(decompressed)
slot = 3575
for ch in needed_new:
    bmp = render_char(ch)
    d[0x480 + slot * 18:0x480 + slot * 18 + 18] = bmp
    slot -= 1

recomp_inject = bytearray(lzss_compress(bytes(d), 12))
recomp_inject_total = len(recomp_inject)
toks_in, ref_len_in, ref_off_in, lit_len_in = analyze(
    '重压缩 sub0 (inject 20 字, 崩溃版本)', bytes(recomp_inject), 12, recomp_inject_total
)

# 4. 关键差异：仅在新版出现的 (length, offset) backref 组合
print('\n\n========== 关键差异 ==========')
og_ref_set = set((t[1], t[2]) for t in toks_og if t[0] == 'ref')
in_ref_set = set((t[1], t[2]) for t in toks_in if t[0] == 'ref')
new_only = in_ref_set - og_ref_set
print(f'\nbackref (length, offset) 组合:')
print(f'  原版有: {len(og_ref_set)} 种')
print(f'  inject 版有: {len(in_ref_set)} 种')
print(f'  inject 版独有 (原版没有): {len(new_only)} 种')

# 5. 看 inject 版的 max offset 是否超过原版
print(f'\nbackref offset 范围:')
print(f'  原版 max offset: {max(ref_off_og)}')
print(f'  inject max offset: {max(ref_off_in)}')

print(f'\nbackref length 范围:')
print(f'  原版 max length: {max(ref_len_og)}')
print(f'  inject max length: {max(ref_len_in)}')

print(f'\nliteral run 范围:')
print(f'  原版 max literal: {max(lit_len_og)}')
print(f'  inject max literal: {max(lit_len_in)}')

# 6. 看 inject 版独有的极端 backref（长 length / 远 offset）
print('\ninject 版独有的极端 backref (top 10 by length 然后 by offset):')
unique_refs = sorted(new_only, key=lambda x: (-x[0], -x[1]))[:10]
for ln, off in unique_refs:
    in_og_offset = off in ref_off_og
    in_og_length = ln in ref_len_og
    print(f'  length={ln}, offset={off}  (offset 在原版出现过: {in_og_offset}, length 在原版出现过: {in_og_length})')
