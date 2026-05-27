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
# 槽位分配策略：从 ALLOC_TOP 往下替换已有日文槽位（避免压缩膨胀）
# 替换现有 bitmap 几乎不增加压缩大小；写入空槽（>2575）会使 LZSS 失去大段零的 backref
# 副作用：被覆盖的日文字符在未翻译的对话里会显示成对应中文（属正常 trade-off）
ALLOC_TOP    = 3575     # 字库共有 0-3575 槽，2694-3575 是空槽（写它会让 LZSS 压缩膨胀但能扩容量）
ALLOC_BOTTOM = 100      # 不低于这里（保护常用标点和 UI 字符）

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
    # 1. 收集需要注入的汉字
    print('[1/7] 扫描 all_translatable.json 中的汉字...')
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
    print(f'      需要 {len(needed)} 个汉字')

    if not needed:
        print('没有汉字需要注入，退出。')
        return

    # 2. 分配槽位（3 层优先级，省 slot）：
    #   优先级 1: 复用 codetable_og 里已有的同字符（CJK 共用字，~1277 字可省）
    #   优先级 2: 复用上次 inject 的 CN 分配（避免槽号每次重排）
    #   优先级 3: 新分配（从 ALLOC_TOP 往下）
    print('[2/7] 分配槽位（替换高位日文 kanji）...')
    ct_og = json.load(open(CODETABLE_OG, encoding='utf-8'))
    needed_set = set(needed)

    # 优先级 1: og 里同字复用（不渲染，不写 bitmap，只是更新 codetable mapping）
    og_reused = {}
    for k, v in ct_og.items():
        if isinstance(v, str) and len(v) == 1 and v in needed_set:
            og_reused[v] = int(k)
    print(f'      og 共用字复用: {len(og_reused)} 字（不需要 inject bitmap）')

    # 优先级 2: 复用上次 CN inject
    ct_existing = {}
    try:
        ct_cur = json.load(open(CODETABLE, encoding='utf-8'))
        ct_existing = {v: int(k) for k, v in ct_cur.items()
                       if isinstance(v, str) and len(v) == 1
                       and v in needed_set and int(k) <= ALLOC_TOP
                       and v not in og_reused
                       and (k not in ct_og or ct_og[k] != v)}
    except Exception:
        pass

    assignments = {}   # char → slot
    used_slots = set(og_reused.values()) | set(ct_existing.values())
    for ch, slot in og_reused.items():
        assignments[ch] = slot
    for ch, slot in ct_existing.items():
        assignments[ch] = slot

    # 优先级 3: 新分配
    slot = ALLOC_TOP
    new_alloc_count = 0
    for ch in needed:
        if ch in assignments:
            continue
        while slot in used_slots:
            slot -= 1
        if slot < ALLOC_BOTTOM:
            print(f'错误：槽位用到 {ALLOC_BOTTOM} 以下了（已分配 {len(assignments)} 字），')
            print(f'      调整 ALLOC_BOTTOM 或减少汉字数量。')
            sys.exit(1)
        assignments[ch] = slot
        used_slots.add(slot)
        new_alloc_count += 1
        slot -= 1

    # 只对【真正需要写 bitmap 的字】生成渲染列表 = og 没有的
    inject_chars = {ch: slot for ch, slot in assignments.items() if ch not in og_reused}
    used_in_run = set(assignments.values())
    print(f'      槽位范围: {min(used_in_run)} ~ {max(used_in_run)}（{len(used_in_run)} 个 mapping）')
    print(f'      og 复用 {len(og_reused)} + 旧 CN 复用 {len(ct_existing)} + 新分配 {new_alloc_count}')
    print(f'      实际需要 inject bitmap 的字: {len(inject_chars)}')

    # 3. 读取文件 59 archive
    print('[3/7] 读取文件 59 archive...')
    filepos = read_sectors(BACKUP_ISO, 0x17, 0x1b88)
    block59 = struct.unpack_from('<I', filepos, FONT_FILE * 8)[0]
    size59  = struct.unpack_from('<I', filepos, FONT_FILE * 8 + 4)[0]
    arch = read_sectors(BACKUP_ISO, block59, size59)
    subs = archive_subfile_offsets(arch)
    print(f'      文件 59: block={block59}, size={size59}, sub-files={len(subs)}')

    # 4. 提取并解压 sub-file 0
    print('[4/7] 解压 sub-file 0...')
    sub0_off, sub0_len = subs[FONT_SUB]
    sub0 = arch[sub0_off:sub0_off + sub0_len]
    tag_bytes = bytes(sub0[0:4])
    total_comp  = struct.unpack_from('<I', sub0, 4)[0]
    uncomp_size = struct.unpack_from('<I', sub0, 8)[0]
    decompressed = bytearray(lzss_decompress(sub0, 12, total_comp - 12, uncomp_size))
    print(f'      tag={tag_bytes.hex()}, {sub0_len} → {len(decompressed)} 字节')
    assert len(decompressed) == 65520, f'解压大小异常: {len(decompressed)}'

    # 5. 渲染并写入需要注入的字（og 共用字不动）
    print(f'[5/7] 渲染并注入 {len(inject_chars)} 个汉字 bitmap...')
    for ch, idx in inject_chars.items():
        bmp = render_char(ch)
        off = 0x480 + idx * 18
        decompressed[off:off + 18] = bmp

    # 6. 重压缩 sub-file 0
    print('[6/7] LZSS 重压缩...')
    recomp = bytearray(lzss_compress(bytes(decompressed), 12))
    recomp[0:4] = tag_bytes  # 保留原始 tag（关键！否则游戏崩溃）
    struct.pack_into('<I', recomp, 4, len(recomp))
    struct.pack_into('<I', recomp, 8, len(decompressed))
    print(f'      重压缩 sub-file 0: {len(recomp)} 字节 (原 {sub0_len})')

    # === 检查能否在原位置直接放下 ===
    in_place_available = subs[1][0] - sub0_off if len(subs) > 1 else size59 - sub0_off
    if len(recomp) <= in_place_available:
        # 简单情况：sub-file 0 没爆，原位写回，sub-file 1 不动
        print(f'      sub-file 0 容量 OK ({len(recomp)} ≤ {in_place_available})，sub-file 1 保持原样')
        arch_patched = bytearray(arch)
        arch_patched[sub0_off:sub0_off + in_place_available] = bytes(in_place_available)
        arch_patched[sub0_off:sub0_off + len(recomp)] = recomp
        assert len(arch_patched) == size59
    else:
        # === 扩容方案：把 sub-file 1 压成最小（全零）腾出空间给 sub-file 0 ===
        print(f'      ⚠ sub-file 0 超原槽 ({len(recomp)} > {in_place_available})，启用 sub-file 1 最小化')
        sub1_off, sub1_len = subs[1]
        sub1 = arch[sub1_off:sub1_off + sub1_len]
        sub1_tag = bytes(sub1[0:4])
        sub1_uncomp = struct.unpack_from('<I', sub1, 8)[0]
        print(f'      sub-file 1 原: tag={sub1_tag.hex()}, uncomp={sub1_uncomp}, comp={sub1_len}')

        # 生成最小 sub-file 1：保留 tag 和 uncomp_size，body 是 LZSS 压缩的全零
        sub1_min_body = bytearray(lzss_compress(bytes(sub1_uncomp), 12))
        sub1_min_body[0:4] = sub1_tag
        struct.pack_into('<I', sub1_min_body, 4, len(sub1_min_body))
        struct.pack_into('<I', sub1_min_body, 8, sub1_uncomp)
        sub1_min = bytes(sub1_min_body)
        print(f'      sub-file 1 最小化: {sub1_len} → {len(sub1_min)} 字节')

        # 重排 archive: [sub0][padding 到 2KB][sub1_min][padding 到 archive end]
        # sub-file 0 起始位置不变（0）
        sub1_new_off = (len(recomp) + 0x7ff) & ~0x7ff   # 下一个 2KB 边界
        if sub1_new_off + len(sub1_min) > size59:
            print(f'错误：即使最小化 sub-file 1 也塞不下 (sub1_new_off={sub1_new_off} + min={len(sub1_min)} > {size59})')
            sys.exit(1)

        arch_patched = bytearray(size59)  # 全零
        arch_patched[sub0_off:sub0_off + len(recomp)] = recomp
        arch_patched[sub1_new_off:sub1_new_off + len(sub1_min)] = sub1_min
        print(f'      新布局: sub0=[0, {len(recomp)}), sub1=[{sub1_new_off}, {sub1_new_off + len(sub1_min)})')
        print(f'      ⚠️ 测试时验证：游戏所有场景渲染正常，否则 sub-file 1 不能 minimize')

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
