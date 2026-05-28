"""
测试 sub-file 0 解压后扩容是否被 game 接受。

最小变化：把 decompressed 从 65520 扩到 81920 字节（多 16KB 全零 padding），
inject 内容不变（只覆盖 og kanji）。
LZSS header uncomp_size 自动更新为 81920。

测试结果：
- game 能跑 → SLPS 信任 LZSS header，可以继续扩到 128KB+
- game 崩 → SLPS 有硬编码 size 限制，需要进一步追

用法: python3 test_expand_subfile0.py [SIZE_BYTES]
默认 81920
"""
import os, sys, struct, subprocess, json, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from pylib.p2is import (
    read_sectors, write_sectors,
    lzss_decompress, lzss_compress, archive_subfile_offsets,
)

EXPANDED_SIZE = int(sys.argv[1]) if len(sys.argv) > 1 else 81920

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BAK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')

# 读 backup file 59
fp = read_sectors(BAK, 0x17, 0x1b88)
b59 = struct.unpack_from('<I', fp, 59*8)[0]
s59 = struct.unpack_from('<I', fp, 59*8 + 4)[0]
arch = read_sectors(BAK, b59, s59)
subs = archive_subfile_offsets(arch)

# 解 sub-file 0
sub0_off, sub0_len = subs[0]
sub0 = arch[sub0_off:sub0_off + sub0_len]
tag = bytes(sub0[0:4])
tc = struct.unpack_from('<I', sub0, 4)[0]
uc = struct.unpack_from('<I', sub0, 8)[0]
print(f'原 sub-file 0: comp={sub0_len}, uncomp={uc} (0x{uc:X})')

d = bytearray(lzss_decompress(sub0, 12, tc-12, uc))
assert len(d) == 65520

# 扩展 decompressed 数组（多余区域全零）
old_size = len(d)
d.extend(bytearray(EXPANDED_SIZE - old_size))
print(f'扩展后: {len(d)} 字节 (0x{len(d):X}) — 多 {EXPANDED_SIZE - old_size} 字节零填充')

# 重压缩
recomp = bytearray(lzss_compress(bytes(d), 12))
recomp[0:4] = tag
struct.pack_into('<I', recomp, 4, len(recomp))
struct.pack_into('<I', recomp, 8, len(d))   # ← 新 uncomp_size
print(f'重压缩: {len(recomp)} 字节 (header uncomp_size = {len(d)} = 0x{len(d):X})')

# 检查容量
sub1_off = subs[1][0]
available = sub1_off - sub0_off
if len(recomp) > available:
    print(f'❌ 重压缩 {len(recomp)} > sub-file 1 偏移 ({available})，装不下')
    sys.exit(1)

# 拼新 archive
arch_patched = bytearray(arch)
arch_patched[sub0_off:sub0_off + available] = bytes(available)  # 清原 sub0 区
arch_patched[sub0_off:sub0_off + len(recomp)] = recomp

# 写回 ISO + 修 ECC
write_sectors(ISO, b59, bytes(arch_patched))
sector_count = (s59 + 2047) // 2048
subprocess.run(['python3', FIX_ECC, str(b59), str(b59 + sector_count - 1)], check=True)

print(f'\n✅ 已写回 ISO。sub-file 0 解压后大小 = {EXPANDED_SIZE} (原 65520)')
print(f'   测试 game 能否加载：冷启动 DuckStation')
print(f'   - 能进游戏 → SLPS 信任 LZSS header，可继续扩到 128KB+')
print(f'   - 黑屏     → SLPS 有硬编码 size 限制，需进一步追')
