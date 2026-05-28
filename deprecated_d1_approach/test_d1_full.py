"""
完整 D1 测试：在 30-sector layout 下 inject 200 个字到扩展 slot。

前置条件：
  - ISO 已重置为干净原版
  - 已 patch Desc2 (sub-file 1 offset 22→30, 不动 Desc1)
  - 已跑 test_30sec_layout.py 把 file 59 搬到 ISO 末尾 + sub-file 1 在 archive 30 sectors offset

本脚本进一步：
  - 解压 sub-file 0 (65520 字节)
  - 扩 decompressed 到 N 字节 (N > 65520, 默认 100000)
  - inject 200 个字到 slot 3576+（扩展区，原本不存在）
  - 重压缩 → 写回 ISO

如果游戏能跑且新 slot 字符渲染出来 → D1 完整成功 → 字库扩容！
如果黑屏 → 还有别的限制

用法: python3 test_d1_full.py [DECOMPRESSED_SIZE] [INJECT_COUNT]
默认 100000 200
"""
import os, sys, struct, subprocess, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from pylib.p2is import (
    read_sectors, write_sectors,
    lzss_decompress, lzss_compress, archive_subfile_offsets,
)

EXPANDED_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
INJECT_COUNT = int(sys.argv[2]) if len(sys.argv) > 2 else 200

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')
TARGET_SUB1_OFFSET = 30 * 2048   # 61440

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

# 读当前 file 59（应该已是 30-sector layout, sub-file 1 在 0xf000 offset）
fp = read_sectors(ISO, 0x17, 4*2048)
b59 = struct.unpack_from('<I', fp, 59*8)[0]
s59 = struct.unpack_from('<I', fp, 59*8 + 4)[0]
arch = read_sectors(ISO, b59, s59)
print(f'file 59 当前: block={b59}, size={s59}')

# 解 sub-file 0
# 30-sector layout 下 sub-file 0 在 archive [0, 0xf000) 区间（含原 LZSS 数据 + 零 padding 或重压缩数据）
sub0 = arch[:TARGET_SUB1_OFFSET]
tag = bytes(sub0[0:4])
tc = struct.unpack_from('<I', sub0, 4)[0]
uc = struct.unpack_from('<I', sub0, 8)[0]
d = bytearray(lzss_decompress(sub0, 12, tc-12, uc))
print(f'sub-file 0 解压: {len(d)} 字节 (uncomp_size header = {uc})')

# 扩 decompressed
if EXPANDED_SIZE > len(d):
    d.extend(bytearray(EXPANDED_SIZE - len(d)))
print(f'扩展到: {len(d)} 字节')

# inject 中文字到扩展区 slot
data_json = json.load(open(os.path.join(ROOT, 'all_translatable.json'), encoding='utf-8'))
freq = {}
def col(t):
    c = re.sub(r'<[^>]+/?>', '', t)
    for ch in c:
        if '一' <= ch <= '鿿' or '㐀' <= ch <= '䶿':
            freq[ch] = freq.get(ch, 0) + 1
for entry in data_json:
    for page in entry.get('pages', []):
        col(page.get('zh', '') or '')
    col(entry.get('meta_zh', '') or '')
needed = sorted(freq.keys(), key=lambda c: (-freq[c], c))
ct_og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
og_chars = set(v for v in ct_og.values() if isinstance(v, str) and len(v) == 1)
needed_new = [c for c in needed if c not in og_chars][:INJECT_COUNT]

# inject 到 slot 3576+ (扩展区)
print(f'inject {len(needed_new)} 个字到 slot 3576-{3576 + len(needed_new) - 1} (扩展区)')
for i, ch in enumerate(needed_new):
    slot = 3576 + i
    off = 0x480 + slot * 18
    if off + 18 > len(d):
        print(f'  ⚠ slot {slot} 超出 decompressed 范围，停止')
        break
    d[off:off + 18] = render(ch)

# 重压缩
recomp = bytearray(lzss_compress(bytes(d), 12))
recomp[0:4] = tag
struct.pack_into('<I', recomp, 4, len(recomp))
struct.pack_into('<I', recomp, 8, len(d))
print(f'重压缩 sub-file 0: {len(recomp)} 字节 (header uncomp_size = {len(d)})')

if len(recomp) > TARGET_SUB1_OFFSET:
    print(f'❌ 重压缩 {len(recomp)} > 30 sectors ({TARGET_SUB1_OFFSET})，装不下')
    sys.exit(1)

# 写回 archive
arch_new = bytearray(arch)
arch_new[:TARGET_SUB1_OFFSET] = bytes(TARGET_SUB1_OFFSET)   # 清 sub-file 0 区
arch_new[:len(recomp)] = recomp
# sub-file 1 部分不动 (TARGET_SUB1_OFFSET 起的内容保持)

write_sectors(ISO, b59, bytes(arch_new))
sector_count = (s59 + 2047) // 2048
subprocess.run(['python3', FIX_ECC, str(b59), str(b59 + sector_count - 1)], check=True)

print(f'\n✅ D1 完整 inject 测试就绪')
print(f'   sub-file 0 重压缩 {len(recomp)} 字节 (<= 30 sectors)')
print(f'   inject {len(needed_new)} 个新字到 slot 3576+')
print(f'   启动 game 测试：能跑 → D1 真扩容成功，可以全部 inject')
