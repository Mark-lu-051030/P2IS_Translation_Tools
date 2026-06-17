#!/usr/bin/env python3
"""
apply_title.py — 把修改好的标题 PNG 重新编码并写回 WORK ISO

PNG → 8bpp/4bpp 索引 → RLE 压缩 → 写回 file 1081 对应 sub

用法:
    cd P2IS_Translation_Tools/update_title
    python3 apply_title.py

PNG 文件映射（从 title_position.txt 和 ISO 实测确认）:
  484.png  (318×140) → sub1  8bpp  vram=(480,256)  CLUT→sub2
  485.png  (302×111) → sub3  8bpp  vram=(480,396)  CLUT→sub4
  486.png  (304×179) → sub5  8bpp  vram=(768, 77)  CLUT→sub6
  487.png  (304×168) → sub7  8bpp  vram=(576, 88)  CLUT→sub8
  decode_4bpp_clut_384_480.png (304×145) → sub9 4bpp vram=(500,111) CLUT→sub10
"""

import os, struct, sys, subprocess
from pathlib import Path
from PIL import Image

# ── 路径 ────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
TOOL_DIR   = SCRIPT_DIR.parent
ISO  = TOOL_DIR.parent / 'Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
FIX_ECC = TOOL_DIR / 'fix_ecc.py'
SECTOR = 0x930; BO = 24; BS = 2048

# ── ISO 读写 ─────────────────────────────────────────────────────
def read_sectors(path, lba, n_bytes):
    buf = bytearray()
    with open(path, 'rb') as f:
        f.seek(lba * SECTOR)
        while len(buf) < n_bytes:
            s = f.read(SECTOR)
            c = min(BS, n_bytes - len(buf))
            buf += s[BO:BO + c]
    return bytes(buf)

def write_sectors(path, lba, data):
    with open(path, 'r+b') as f:
        off = 0
        sec = lba * SECTOR
        while off < len(data):
            f.seek(sec + BO)
            c = min(BS, len(data) - off)
            f.write(data[off:off + c])
            off += c; sec += SECTOR

def read_iso_file(fid):
    fpos = read_sectors(ISO, 0x17, 0x12000)
    blk  = struct.unpack_from('<I', fpos, fid * 8)[0]
    sz   = struct.unpack_from('<I', fpos, fid * 8 + 4)[0]
    return read_sectors(ISO, blk, sz), blk, sz

def write_iso_file(blk, sz, data):
    assert len(data) == sz, f'data len {len(data)} ≠ file sz {sz}'
    write_sectors(ISO, blk, data)
    n_sec = (sz + BS - 1) // BS
    subprocess.run(['python3', str(FIX_ECC), str(blk), str(blk + n_sec - 1)], check=True)
    # 也修 FILEPOS 区
    subprocess.run(['python3', str(FIX_ECC), '23', '26'], check=True)

# ── Archive 操作 ─────────────────────────────────────────────────
def walk_subs(data):
    """返回 [(idx, offset, tc, header16bytes)] 列表"""
    ptr = 0; idx = 0; result = []
    while ptr < len(data):
        b = data[ptr]
        if b == 0:
            ptr = (ptr + 0x800) & ~0x7ff
            continue
        tc = struct.unpack_from('<I', data, ptr + 4)[0]
        if tc == 0: break
        result.append((idx, ptr, tc, bytes(data[ptr:ptr + 16])))
        idx += 1
        ptr += tc
        while ptr & 3: ptr += 1
    return result

def patch_sub(archive, offset, old_tc, new_payload_bytes):
    """
    用 new_payload_bytes 替换 archive[offset] 处的 sub-file 数据部分（16字节头保留）。
    new_payload_bytes 长度必须等于 old_tc - 16，即原 payload 等长替换。
    返回新 archive bytes。
    """
    assert len(new_payload_bytes) == old_tc - 16, \
        f'payload 长度 {len(new_payload_bytes)} ≠ 原大小 {old_tc - 16}'
    result = bytearray(archive)
    result[offset + 16: offset + old_tc] = new_payload_bytes
    return bytes(result)

# ── RLE 压缩 ─────────────────────────────────────────────────────
def rle_compress(data: bytes) -> bytes:
    """贪心 RLE：run [0x80|(n-3)][byte] / literal [n-1][...bytes]"""
    out = bytearray()
    i = 0; n = len(data)
    while i < n:
        run = 1
        while i + run < n and data[i + run] == data[i] and run < 130:
            run += 1
        if run >= 3:
            out.append((run - 3) | 0x80)
            out.append(data[i])
            i += run
        else:
            ln = 0
            while i + ln < n and ln < 128:
                if i + ln + 2 < n and data[i + ln] == data[i + ln + 1] == data[i + ln + 2]:
                    break
                ln += 1
            out.append(ln - 1)
            out += data[i:i + ln]
            i += ln
    return bytes(out)

def rle_compress_to_size(data: bytes, target_payload: int) -> bytes | None:
    """
    压缩后精确填满 target_payload 字节。
    先贪心压缩，若比 target 小则膨胀（run→literal，literal 拆分）；
    若比 target 大返回 None。
    """
    n = len(data)
    # 贪心 token 化
    tokens = []
    i = 0
    while i < n:
        run = 1
        while i + run < n and data[i + run] == data[i] and run < 130:
            run += 1
        if run >= 3:
            tokens.append(('R', i, run)); i += run
        else:
            ln = 0
            while i + ln < n and ln < 128:
                if i + ln + 2 < n and data[i + ln] == data[i + ln + 1] == data[i + ln + 2]:
                    break
                ln += 1
            tokens.append(('L', i, ln)); i += ln

    def lit_cost(k):
        return -(-k // 128) + k  # ceil(k/128) + k

    def cost(ts):
        return sum(2 if t == 'R' else lit_cost(k) for t, _, k in ts)

    gap = target_payload - cost(tokens)
    if gap < 0:
        return None  # 已超目标，装不下

    # Phase1: run → literal（膨胀 lit_cost(n)-2），从 extra 小的先换
    runs = sorted(
        [(i, lit_cost(k) - 2) for i, (t, _, k) in enumerate(tokens) if t == 'R'],
        key=lambda x: x[1]
    )
    for idx, extra in runs:
        if gap <= 0: break
        if extra <= gap:
            t, s, k = tokens[idx]; tokens[idx] = ('L', s, k); gap -= extra

    # Phase2: literal 拆分（每次 +1B）
    final_tokens = []
    for t, s, k in tokens:
        if gap > 0 and t == 'L' and k >= 2:
            splits = min(gap, k - 1)
            for j in range(splits):
                final_tokens.append(('L', s + j, 1))
            final_tokens.append(('L', s + splits, k - splits))
            gap -= splits
        else:
            final_tokens.append((t, s, k))

    if gap != 0:
        return None

    # 序列化
    out = bytearray()
    for t, s, k in final_tokens:
        if t == 'R':
            out.append((k - 3) | 0x80); out.append(data[s])
        else:
            done = 0
            while done < k:
                chunk = min(128, k - done)
                out.append(chunk - 1)
                out += data[s + done: s + done + chunk]
                done += chunk
    assert len(out) == target_payload, f'序列化后 {len(out)} ≠ {target_payload}'
    return bytes(out)

# ── 图像转换 ──────────────────────────────────────────────────────
def rgba_to_psx15(r, g, b, transparent=False):
    # index0(透明)=0x0000；不透明色一律置 STP 位(bit15)，与原版日文 CLUT 完全一致。
    # 标题精灵以 PSX 半透明模式(ABE)绘制：STP=1 让每个像素与背景混合，
    # 这正是标题"飞入淡入 + 玻璃质感"效果的来源。
    # 试过给红字单独清 STP(实心)，反而更糟：飞入阶段背景是亮白光爆，
    # 不透明的深红盖上去显示成黑、且失去淡入→显得位置硬跳、像卡顿。故全部 STP=1。
    if transparent:
        return 0x0000
    c = (r >> 3) | ((g >> 3) << 5) | ((b >> 3) << 10)
    return c | 0x8000  # 置 STP；纯黑不透明像素→0x8000(保持不透明,不会误判为透明)

def png_to_indexed(png_path: Path, pixel_w: int, pixel_h: int, bpp: int, dx: int = 0, dy: int = 0):
    """
    把 PNG 转为 bpp 位索引图 + PSX15bit 调色板。
    dx/dy: 编码前对图像内容做整体平移(正=右/下)，空出的区域填透明。
           用于对齐——某些帧的编辑稿相对其它帧/原版有几像素偏移。
    返回 (indexed_bytes, psx_palette_uint16_list)
    indexed_bytes:
      8bpp: pixel_w × pixel_h bytes（每字节=1索引）
      4bpp: (pixel_w/2) × pixel_h bytes（每字节两个4bit索引，低nibble=左像素）
    psx_palette:
      8bpp: 256 个 uint16
      4bpp:  16 个 uint16
    """
    n_colors = 256 if bpp == 8 else 16

    img = Image.open(png_path).convert('RGBA')
    if img.size != (pixel_w, pixel_h):
        print(f'  ⚠ 尺寸不符: PNG={img.size} 期望=({pixel_w},{pixel_h})，缩放…')
        img = img.resize((pixel_w, pixel_h), Image.LANCZOS)

    if dx or dy:  # 整体平移对齐，空出区域填透明
        shifted = Image.new('RGBA', (pixel_w, pixel_h), (0, 0, 0, 0))
        shifted.paste(img, (dx, dy))
        img = shifted
        print(f'    对齐平移: dx={dx:+d} dy={dy:+d}')

    rgba_data = list(img.getdata())

    # 区分透明/不透明像素
    transparent_mask = [p[3] < 128 for p in rgba_data]

    # 用不透明像素量化
    # 把透明像素临时替换成黑色，避免影响色彩分布
    rgb_img = Image.new('RGB', img.size, (0, 0, 0))
    for idx2, (r, g, b, a) in enumerate(rgba_data):
        if a >= 128:
            x = idx2 % pixel_w; y = idx2 // pixel_w
            rgb_img.putpixel((x, y), (r, g, b))

    # 量化到 n_colors-1 个非透明色（保留 index 0 给透明）
    quantized = rgb_img.quantize(colors=n_colors - 1, method=Image.Quantize.MEDIANCUT)
    palette_rgb = quantized.getpalette()  # R,G,B,...（768 or 48 bytes）
    q_data = list(quantized.getdata())   # 0‥n_colors-2 per pixel

    # 重建 index（透明 → 0，不透明 → q_index+1）
    indices = []
    for i, is_t in enumerate(transparent_mask):
        indices.append(0 if is_t else q_data[i] + 1)

    # PSX 调色板：所有非透明色置 STP(半透明)，与原版日文 CLUT 一致
    psx_pal = [0x0000]  # index 0 = 透明
    for ci in range(n_colors - 1):
        r = palette_rgb[ci * 3]
        g = palette_rgb[ci * 3 + 1]
        b = palette_rgb[ci * 3 + 2]
        psx_pal.append(rgba_to_psx15(r, g, b))

    # 打包 indexed bytes
    if bpp == 8:
        indexed_bytes = bytes(indices)
    else:  # 4bpp: 每字节低nibble=偶列，高nibble=奇列
        packed = bytearray()
        for y in range(pixel_h):
            for x in range(0, pixel_w, 2):
                lo = indices[y * pixel_w + x] & 0xf
                hi = indices[y * pixel_w + x + 1] & 0xf if x + 1 < pixel_w else 0
                packed.append(lo | (hi << 4))
        indexed_bytes = bytes(packed)

    return indexed_bytes, psx_pal

# ── 配置表 ────────────────────────────────────────────────────────
# (png_file, sub_img, sub_clut, bpp, pixel_w, pixel_h, dx, dy)
# dx/dy: 编码前对齐平移(正=右/下)。484 的编辑稿整张比其余三帧左移了 6px,
#        +6 修正后它的卡片对齐原版、文字也与 485/486/487 一致(消除帧间跳动)。
IMAGES = [
    ('484.png',                       1, 2,  8, 318, 140,  6, 0),
    ('485.png',                       3, 4,  8, 302, 111,  0, 0),
    ('486.png',                       5, 6,  8, 304, 179,  0, 0),
    ('487.png',                       7, 8,  8, 304, 168,  0, 0),
    # ('decode_4bpp_clut_384_480.png',  9, 10, 4, 304, 145,  0, 0),
]

# ── 主流程 ────────────────────────────────────────────────────────
def main():
    print(f'读取 file 1081 …')
    archive, blk, total_sz = read_iso_file(1081)
    print(f'  archive size = {len(archive)} bytes')

    subs = walk_subs(archive)
    sub_map = {idx: (offset, tc, hdr) for idx, offset, tc, hdr in subs}

    new_archive = bytearray(archive)

    for png_name, sub_img, sub_clut, bpp, pixel_w, pixel_h, dx, dy in IMAGES:
        png_path = SCRIPT_DIR / png_name
        if not png_path.exists():
            print(f'跳过 {png_name}（文件不存在）')
            continue

        print(f'\n─── {png_name} → sub{sub_img} ({bpp}bpp {pixel_w}×{pixel_h}) + CLUT sub{sub_clut} ───')

        # 1. 转换图像
        indexed, psx_pal = png_to_indexed(png_path, pixel_w, pixel_h, bpp, dx, dy)
        print(f'  索引数据: {len(indexed)} bytes  调色板: {len(psx_pal)} 色')

        # 2. RLE 压缩图像
        img_off, img_tc, img_hdr = sub_map[sub_img]
        target_payload = img_tc - 16
        compressed = rle_compress(indexed)
        if len(compressed) > target_payload:
            print(f'  ❌ 压缩后 {len(compressed)} > 槽大小 {target_payload}，尝试更优压缩…')
            compressed = rle_compress_to_size(indexed, target_payload)
            if compressed is None:
                print(f'  ❌ 图像太大，无法装入原 slot，跳过')
                continue
        elif len(compressed) < target_payload:
            print(f'  压缩后 {len(compressed)} < 目标 {target_payload}，膨胀填满…')
            compressed = rle_compress_to_size(indexed, target_payload)
            if compressed is None:
                print(f'  ❌ 无法精确填满，跳过')
                continue

        print(f'  压缩大小: {len(compressed)} / {target_payload} 字节')

        # 3. 写入图像 sub-file（保留原 16 字节头，只换 payload）
        new_archive[img_off + 16: img_off + img_tc] = compressed

        # 4. 更新 CLUT sub-file
        clut_off, clut_tc, clut_hdr = sub_map[sub_clut]
        n_colors = 256 if bpp == 8 else 16
        clut_payload_expected = clut_tc - 16
        clut_bytes = struct.pack(f'<{n_colors}H', *psx_pal[:n_colors])
        if len(clut_bytes) != clut_payload_expected:
            print(f'  ⚠ CLUT 大小不符: {len(clut_bytes)} vs {clut_payload_expected}，用零填充…')
            clut_bytes = clut_bytes.ljust(clut_payload_expected, b'\x00')
        new_archive[clut_off + 16: clut_off + clut_tc] = clut_bytes
        print(f'  CLUT sub{sub_clut}: {n_colors} 色写入完成')

    # 5. 写回 ISO
    print(f'\n写回 ISO file 1081 @ LBA {blk} …')
    write_iso_file(blk, total_sz, bytes(new_archive))
    print('✓ 完成，ECC 已修复')

if __name__ == '__main__':
    main()
