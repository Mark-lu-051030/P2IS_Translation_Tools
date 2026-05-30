"""
扫描 all_translatable.json 中所有 zh 字段的汉字，渲染 12×12 bitmap，
注入到游戏对话字体（文件 59 sub-file 0，LZSS 压缩）。

⚠️ 关键：游戏的对话字体在文件 59 sub-file 0，不是 F0086.BIN。
F0086.BIN 是格式相同的"参考副本"，游戏运行时不读它。

流程：
  1. 收集 zh 字段中所有汉字
  2. 分配槽位（codetable 里有的复用，没有的从 FIRST_SLOT 开始分配）
  3. 用 PIL 渲染每个字 → 12×12 1bpp bitmap → 18 字节
  4. 读取文件 59 → 提取 sub-file 0 → LZSS 解压（→ 65520 字节）
  5. 在每个分配的槽位写入 bitmap（offset = 0x480 + slot * 18）
  6. LZSS 重压缩（保留原始 tag 字节）
  7. patch_archive_inplace 替换 sub-file 0
  8. 写回 ISO，修复 ECC
  9. 更新 codetable.json

用法: python3 inject_chinese_font.py
"""
import json, shutil, re, struct, subprocess, sys, os
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from pylib.p2is import (
    read_sectors, write_sectors,
    lzss_decompress, lzss_compress,
    archive_subfile_offsets,
    read_filepos, get_file_entry,
)

# ── 路径配置 ────────────────────────────────────────────────────────────────
ISO_PATH   = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BACKUP_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
TTF_PATH   = os.path.join(ROOT, 'fusion-pixel-12px.otf')  # OFL-1.1, 专为像素显示设计
CODETABLE     = os.path.join(ROOT, 'codetable.json')      # 输出（被本脚本重建）
CODETABLE_OG  = os.path.join(ROOT, 'codetable_og.json')   # 输入：原始日文 codetable（基线）
TRANS_JSON    = os.path.join(ROOT, 'all_translatable.json')
FIX_ECC    = os.path.join(ROOT, 'fix_ecc.py')
FONT_FILE  = 59         # 文件 59 = 对话字体 archive
FONT_SUB   = 0          # sub-file 0 = LZSS 压缩的字形数据
# 槽位分配策略：D1 扩容方案
# build.py 流程先跑 patch_subfile_table.py (Desc1+Desc2 = 30 sectors) + relocate_file59.py
# 这把 SLPS 期待的 sub-file 0 容量从 22 sectors 扩到 30 sectors (45056 → 61440 字节)
# 同时把 file 59 搬到 ISO 末尾让 sub-file 1 在 30 sectors offset
# 这里 inject 时可以用扩展 slot 3576+（原来空区）
ALLOC_TOP    = 3800     # D1 扩容后可达 (sub-file 0 解压上限 ~69000, (69000-0x480)/18=3825)
ALLOC_BOTTOM = 100      # 不低于这里（保护常用标点和 UI 字符）
EXPANDED_DECOMP_SIZE = 65520   # D1 字库 RAM 区上限（实测临界值）
SUBFILE_1_OFFSET = 30 * 2048    # D1 layout: sub-file 1 在 30 sectors offset

# SECTOR/BLOCK 常量、扇区 IO、LZSS、archive 解析 都从 pylib.p2is 引入
from pylib.p2is import SECTOR, BLOCK_OFF, BLOCK_SIZE

# ── 字形渲染 ────────────────────────────────────────────────────────────────

try:
    TTF = ImageFont.truetype(TTF_PATH, 12)  # fusion-pixel 是 12px，不像 Noto 要缩到 11
except Exception as e:
    print(f'警告: 加载 {TTF_PATH} 失败 ({e})，使用默认字体')
    TTF = ImageFont.load_default()

def render_char(ch):
    """渲染汉字为 12×12 1bpp bitmap → 18 字节（LSB 优先，行优先）"""
    img = Image.new('L', (12, 12), 0)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), ch, font=TTF)
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    x = (12 - w) // 2 - bbox[0]
    y = (12 - h) // 2 - bbox[1]
    draw.text((x, y), ch, fill=255, font=TTF)
    bits = [1 if p > 64 else 0 for p in img.getdata()]
    result = bytearray(18)
    for i, b in enumerate(bits):
        if b: result[i // 8] |= (1 << (i % 8))
    return bytes(result)

# ── 主流程 ──────────────────────────────────────────────────────────────────

def main():
    # 1. 收集需要注入的汉字 + 统计出现频率（容量不够时按频率取舍）
    print('[1/7] 扫描 all_translatable.json 中的汉字...')
    data = json.load(open(TRANS_JSON, encoding='utf-8'))
    from collections import Counter
    freq = Counter()
    # og 已有的字符集合（用于判断假名是否需要 inject）
    _ct_og_early = json.load(open(CODETABLE_OG, encoding='utf-8'))
    _og_chars = set(v for v in _ct_og_early.values() if isinstance(v, str) and len(v) == 1)
    def collect_chars(text):
        clean = re.sub(r'<[^>]+/?>', '', text)
        for c in clean:
            if '一' <= c <= '鿿' or '㐀' <= c <= '䶿':
                freq[c] += 1
            # 假名/特殊字符：只在 og 字库没有时才 inject（如 が ヘ ホ ョ 这类 og 缺的）
            elif ('぀' <= c <= 'ヿ') and c not in _og_chars:
                freq[c] += 1
    for entry in data:
        for page in entry.get('pages', []):
            collect_chars(page.get('zh', '') or '')
        collect_chars(entry.get('meta_zh', '') or '')
    # 按频率从高到低排序，频率相同按 unicode 顺序
    needed = sorted(freq.keys(), key=lambda c: (-freq[c], c))
    print(f'      需要 {len(needed)} 个汉字（按频率排序，高频在前）')

    if not needed:
        print('没有汉字需要注入，退出。')
        return

    # 2. 分配槽位（2 层优先级）：
    #   优先级 1: 复用 codetable_og 里已有的同字符（CJK 共用字，~1277 字可省）
    #   优先级 2: 新分配（从 ALLOC_TOP 往下，跳过 og 非 kanji slot）
    # ⚠ 不再复用上次 inject 的 codetable.json — 那会让上次的污染（覆盖 ASCII 等）传染到本次。
    #   每次重新分配 slot 号变但 build 流程会重跑 encode+apply 所以无碍。
    print('[2/7] 分配槽位（替换 og 日文 kanji slot）...')
    ct_og = json.load(open(CODETABLE_OG, encoding='utf-8'))
    needed_set = set(needed)

    # 优先级 1: og 里同字复用（不渲染，不写 bitmap，只是更新 codetable mapping）
    og_reused = {}
    for k, v in ct_og.items():
        if isinstance(v, str) and len(v) == 1 and v in needed_set:
            og_reused[v] = int(k)
    print(f'      og 共用字复用: {len(og_reused)} 字（不需要 inject bitmap）')

    assignments = {}   # char → slot
    used_slots = set(og_reused.values())
    og_reused_slots = set(og_reused.values())
    for ch, slot in og_reused.items():
        assignments[ch] = slot
    ct_existing = {}  # 留个空对象给后面的打印用

    # 优先级 3: 新分配（按频率从高到低 — needed 已排好序）
    # D1 扩容后规则：
    #   - og 里是 kanji 的 slot (100-2574): 可覆盖（中文替换日文 kanji）
    #   - og 里是 ASCII/标点的 slot: 保护（如 '~' slot 126）
    #   - og 没有的 slot (2575+, 扩展区): 可写（D1 扩容空间）
    def is_kanji_slot(slot):
        og_ch = ct_og.get(str(slot))
        if og_ch is None:
            return True    # D1 扩展区 slot (og 没有) — 可写
        if len(og_ch) != 1:
            return False   # 特殊条目（多字符 / 控制码）保护
        # og 里是单字符：只有 kanji 可覆盖
        return '一' <= og_ch <= '鿿' or '㐀' <= og_ch <= '䶿'

    # D1 优化分配顺序：
    #   - 先填 og 非 needed kanji slot (slot 100-2574 中非 og_reused 的 kanji)：
    #     替换 bitmap，LZSS 重压缩几乎不膨胀
    #   - 不够再填扩展区 slot (>2574)：
    #     bitmap 替换零，每字膨胀 ~14 字节
    OG_MAX = 2574

    # 收集 og kanji slot (可覆盖，按 slot 从高到低)
    og_kanji_slots = sorted(
        [int(k) for k, v in ct_og.items()
         if int(k) > ALLOC_BOTTOM and int(k) <= OG_MAX
         and isinstance(v, str) and len(v) == 1
         and ('一' <= v <= '鿿' or '㐀' <= v <= '䶿')
         and int(k) not in og_reused_slots],
        reverse=True
    )
    # 扩展区 slot：⚠ 必须从低位 2575 往上紧凑分配！
    # decompressed 大小 = 0x480 + (最高slot+1)*18。原版字库 buffer 65520 字节对应最高 slot
    # = (65520-0x480)//18 = 3575。超过 slot 3575 会让 decompressed > 65520，覆盖字库后面
    # RAM 0x801DE7F0+ 的 UI 数据 → HP/¥/菜单标题颜色乱、选项框空、战斗 invalid read。
    # 所以从 2575 往上用最小 slot 号，让 decompressed 尽量小（611 字只到 slot ~3185 = 58500 字节）。
    MAX_SAFE_SLOT = (65520 - 0x480) // 18   # = 3575
    ext_slots = list(range(OG_MAX + 1, MAX_SAFE_SLOT + 1))   # 2575,2576,...,3575 低到高

    # 合并：先 og kanji（替换日文，不增 decompressed），再扩展区（从低位填，最小化 decompressed）
    free_slots = og_kanji_slots + ext_slots

    new_alloc_count = 0
    new_og_count = 0
    new_ext_count = 0
    skipped_chars = []
    slot_iter = iter(free_slots)
    for ch in needed:
        if ch in assignments:
            continue
        slot = None
        for s in slot_iter:
            if s not in used_slots:
                slot = s
                break
        if slot is None:
            skipped_chars.append(ch)
            continue
        assignments[ch] = slot
        used_slots.add(slot)
        new_alloc_count += 1
        if slot <= OG_MAX:
            new_og_count += 1
        else:
            new_ext_count += 1

    # 只对【真正需要写 bitmap 的字】生成渲染列表 = og 没有的
    inject_chars = {ch: slot for ch, slot in assignments.items() if ch not in og_reused}
    used_in_run = set(assignments.values())
    print(f'      槽位范围: {min(used_in_run)} ~ {max(used_in_run)}（{len(used_in_run)} 个 mapping）')
    print(f'      og 复用 {len(og_reused)} + 旧 CN 复用 {len(ct_existing)} + 新分配 {new_alloc_count} (og kanji 替换 {new_og_count} + 扩展区 {new_ext_count})')
    print(f'      实际需要 inject bitmap 的字: {len(inject_chars)}')
    if skipped_chars:
        # 把 skipped 字符写到文件供 encode_zh.py 检查
        skip_log = os.path.join(ROOT, 'out', 'skipped_chars.txt')
        os.makedirs(os.path.dirname(skip_log), exist_ok=True)
        with open(skip_log, 'w', encoding='utf-8') as f:
            for ch in skipped_chars:
                f.write(f'{ch}\t{freq[ch]}\n')
        print(f'      ⚠ {len(skipped_chars)} 字超容量被跳过（按频率从低到高）')
        sample = ''.join(skipped_chars[:30])
        print(f'        最低频 30 字: {sample}')
        print(f'        完整列表已写: out/skipped_chars.txt')

    # 3. 读取文件 59 archive — D1 模式从 working ISO 读（已经 layout 转换过）
    print('[3/7] 读取文件 59 archive (D1 layout)...')
    filepos = read_sectors(ISO_PATH, 0x17, 4 * 2048)
    block59 = struct.unpack_from('<I', filepos, FONT_FILE * 8)[0]
    size59  = struct.unpack_from('<I', filepos, FONT_FILE * 8 + 4)[0]
    arch = read_sectors(ISO_PATH, block59, size59)
    print(f'      文件 59: block={block59}, size={size59} (应在 ISO 末尾)')
    # D1 layout: sub-file 0 在 [0, ~22 sectors), padding 到 30 sectors, sub-file 1 在 30 sectors offset
    sub0_len_max = SUBFILE_1_OFFSET  # 30 sectors = 61440 字节 (D1 扩容上限)

    # 4. 提取并解压 sub-file 0
    print('[4/7] 解压 sub-file 0...')
    sub0 = arch[:sub0_len_max]
    tag_bytes = bytes(sub0[0:4])
    total_comp  = struct.unpack_from('<I', sub0, 4)[0]
    uncomp_size = struct.unpack_from('<I', sub0, 8)[0]
    decompressed = bytearray(lzss_decompress(sub0, 12, total_comp - 12, uncomp_size))
    print(f'      tag={tag_bytes.hex()}, total_comp={total_comp} → {len(decompressed)} 字节')

    # D1: 扩 decompressed 到 EXPANDED_DECOMP_SIZE 字节（多出区域写新 slot bitmap）
    if len(decompressed) < EXPANDED_DECOMP_SIZE:
        decompressed.extend(bytearray(EXPANDED_DECOMP_SIZE - len(decompressed)))
        print(f'      D1 扩展 decompressed: {len(decompressed)} 字节')

    # 5. 渲染并写入需要注入的字（og 共用字不动）
    print(f'[5/7] 渲染并注入 {len(inject_chars)} 个汉字 bitmap...')
    for ch, idx in inject_chars.items():
        bmp = render_char(ch)
        off = 0x480 + idx * 18
        if off + 18 > len(decompressed):
            print(f'      ⚠ slot {idx} bitmap 超出 decompressed 范围，跳过')
            continue
        decompressed[off:off + 18] = bmp

    # 6. 重压缩 sub-file 0
    print('[6/7] LZSS 重压缩...')
    recomp = bytearray(lzss_compress(bytes(decompressed), 12))
    recomp[0:4] = tag_bytes  # 保留原始 tag（关键！否则游戏崩溃）
    struct.pack_into('<I', recomp, 4, len(recomp))
    struct.pack_into('<I', recomp, 8, len(decompressed))
    print(f'      重压缩 sub-file 0: {len(recomp)} 字节 (uncomp_size header = {len(decompressed)})')

    # === D1 容量策略 ===
    # D1 layout: sub-file 0 占 [0, 30 sectors), sub-file 1 在 30 sectors offset
    # SLPS 已 patch 读 30 sectors of sub-file 0
    if len(recomp) > SUBFILE_1_OFFSET:
        print(f'错误：sub-file 0 重压缩 ({len(recomp)}) 超过 30 sectors ({SUBFILE_1_OFFSET})')
        print(f'      减少 inject 字数 或 调低 EXPANDED_DECOMP_SIZE')
        sys.exit(1)
    print(f'      D1 容量 OK ({len(recomp)} ≤ {SUBFILE_1_OFFSET} = 30 sectors)')

    # 拼新 archive：sub-file 0 重压缩 + 零 padding + sub-file 1 原内容
    sub1_orig = bytes(arch[SUBFILE_1_OFFSET:])
    arch_patched = bytearray(size59)
    arch_patched[:len(recomp)] = recomp
    arch_patched[SUBFILE_1_OFFSET:SUBFILE_1_OFFSET + len(sub1_orig)] = sub1_orig

    # 7. 写回 ISO + 更新 codetable + 修 ECC
    print('[7/7] 写回 ISO 并修复 ECC...')
    write_sectors(ISO_PATH, block59, bytes(arch_patched))

    # 更新 codetable.json: 从 og 基线开始，叠加本次的中文分配（覆盖被替换的日文 slot）
    new_ct = dict(ct_og)
    for ch, idx in assignments.items():
        new_ct[str(idx)] = ch
    with open(CODETABLE, 'w', encoding='utf-8') as f:
        json.dump(new_ct, f, ensure_ascii=False, separators=(',', ':'))
    print(f'      codetable.json 已更新（{len(new_ct)} 条 = og {len(ct_og)} + 新中文 {len(assignments)} - 覆盖）')

    # 修 ECC
    sector_count = (size59 + BLOCK_SIZE - 1) // BLOCK_SIZE
    lba_end = block59 + sector_count - 1
    subprocess.run(['python3', FIX_ECC, str(block59), str(lba_end)], check=True)

    print(f'\n✅ 完成。{len(assignments)} 个汉字已注入文件 59 sub-file 0')
    print('下一步：python3 encode_zh.py → node apply_zh.mjs <file> <sub>')

if __name__ == '__main__':
    main()
