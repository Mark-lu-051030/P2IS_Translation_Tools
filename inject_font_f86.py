"""
把注入 file 59 的同一批中文字形，**同步写进 file 86**（F0086.BIN）。

⚠️ 为什么需要这步：命名界面（及可能的其他画面）渲染汉字**不读 file 59**，
   而是读 file 86 这份独立字库。证据：我们注入 file 59 时挤占了 og kanji 区
   931 个槽（如 slot 279 戦→综），但命名界面里那些位置仍显示原日文（戦）
   → 命名界面读的是没被动过的 file 86。
   不同步 86 → 读 86 的画面会显示错字（原日文）或缺我们的新中文字形。

file 86 在 ISO 上的格式（与 file 59 sub-file 0 不同）：
   block 67424, 65520 字节, **裸的未压缩 12×12 字库**（无 archive 头/无压缩）。
   字形布局和 file 59 解压后一样：slot k 的 18 字节 bitmap 在 offset 0x480 + k*18。
   不用解压/重压缩/relocate/动态N —— 直接在槽位写 bitmap。

做法：读 backup 的 pristine file 86 → 对所有 codetable != codetable_og 的槽
   渲染新字形写入（复用 inject_chinese_font.render_char 保证逐字节一致）
   → 写回 working ISO → 修 ECC。幂等：每次从 pristine 重建，只覆盖改过的槽。

用法: python3 inject_font_f86.py
"""
import json, struct, subprocess, sys, os

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from pylib.p2is import read_sectors, write_sectors, BLOCK_SIZE
from inject_chinese_font import render_char   # 复用同一渲染，保证与 file 59 一致

ISO_PATH   = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BACKUP_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
CODETABLE     = os.path.join(ROOT, 'codetable.json')
CODETABLE_OG  = os.path.join(ROOT, 'codetable_og.json')
FIX_ECC    = os.path.join(ROOT, 'fix_ecc.py')
FONT_FILE  = 86
GLYPH_BASE = 0x480   # 第一个字形 bitmap 的 offset
GLYPH_SIZE = 18      # 12×12 1bpp = 18 字节

def main():
    ct = json.load(open(CODETABLE, encoding='utf-8'))
    og = json.load(open(CODETABLE_OG, encoding='utf-8'))

    # 1. 定位 file 86（backup = 原始布局，pristine）
    fp = read_sectors(BACKUP_ISO, 0x17, 4 * 2048)
    block = struct.unpack_from('<I', fp, FONT_FILE * 8)[0]
    size  = struct.unpack_from('<I', fp, FONT_FILE * 8 + 4)[0]
    print(f'[1/4] file 86: block={block}, size={size} ({size/BLOCK_SIZE:.0f} sectors, 裸未压缩)')
    font = bytearray(read_sectors(BACKUP_ISO, block, size))

    # 2. 找出所有与 og 不同的槽（= 我们注入 file 59 时改过的字）
    changed = [(int(k), v) for k, v in ct.items()
               if isinstance(v, str) and len(v) == 1 and og.get(k) != v]
    changed.sort()
    print(f'[2/4] 需要同步的槽: {len(changed)} 个（codetable 与 og 不同的）')

    # 3. 渲染并写入每个改过的槽
    written = skipped = 0
    for slot, ch in changed:
        off = GLYPH_BASE + slot * GLYPH_SIZE
        if off + GLYPH_SIZE > size:
            print(f'      ⚠ slot {slot} ({ch!r}) 超出 file 86 容量，跳过')
            skipped += 1
            continue
        font[off:off + GLYPH_SIZE] = render_char(ch)
        written += 1
    print(f'[3/4] 已写入 {written} 个字形' + (f'，跳过 {skipped}' if skipped else ''))

    # 4. 写回 working ISO + 修 ECC（file 86 在 working 里位置不变，没 relocate）
    fp_wk = read_sectors(ISO_PATH, 0x17, 4 * 2048)
    blk_wk = struct.unpack_from('<I', fp_wk, FONT_FILE * 8)[0]
    sz_wk  = struct.unpack_from('<I', fp_wk, FONT_FILE * 8 + 4)[0]
    if blk_wk != block or sz_wk != size:
        print(f'      ⚠ working 的 file 86 位置/大小变了 (block={blk_wk}, size={sz_wk})，按 working 为准写回')
        block, size = blk_wk, sz_wk
        font = font[:size] if len(font) >= size else font + bytearray(size - len(font))
    write_sectors(ISO_PATH, block, bytes(font))
    nsec = (size + BLOCK_SIZE - 1) // BLOCK_SIZE
    subprocess.run(['python3', FIX_ECC, str(block), str(block + nsec - 1)], check=True)
    print(f'[4/4] ✅ file 86 已同步中文字形（{written} 字），写回 block {block}')
    print('      命名界面等读 86 的画面现在应与 file 59 一致')

if __name__ == '__main__':
    main()
