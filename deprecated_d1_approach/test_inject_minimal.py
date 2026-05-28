"""
最最小化测试：搬位置 + 重压缩 + 只 inject 1 个汉字。
如果还崩 → 任何 inject 都崩，问题在 slot 元数据 / 字符宽度。
如果不崩 → 量的问题（某些 slot 触发崩溃，需要进一步缩小范围）。

用法: python3 test_inject_minimal.py
"""
import os, sys, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw, ImageFont
from pylib.p2is import (
    read_sectors, write_sectors,
    lzss_decompress, lzss_compress,
    archive_subfile_offsets,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO_PATH   = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BACKUP_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
TTF_PATH   = os.path.join(ROOT, 'fusion-pixel-12px.otf')
FIX_ECC    = os.path.join(ROOT, 'fix_ecc.py')
FONT_FILE  = 59
TARGET_OFFSET = 61440

TTF = ImageFont.truetype(TTF_PATH, 12)

def render_char_12x11(ch):
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

def main():
    # 1. 读 backup file 59
    filepos = read_sectors(BACKUP_ISO, 0x17, 0x1b88)
    block59 = struct.unpack_from('<I', filepos, FONT_FILE * 8)[0]
    size59  = struct.unpack_from('<I', filepos, FONT_FILE * 8 + 4)[0]
    arch = read_sectors(BACKUP_ISO, block59, size59)
    subs = archive_subfile_offsets(arch)

    # 2. 解压 sub0
    sub0_off, sub0_len = subs[0]
    sub0 = arch[sub0_off:sub0_off + sub0_len]
    tag_bytes = bytes(sub0[0:4])
    total_comp  = struct.unpack_from('<I', sub0, 4)[0]
    uncomp_size = struct.unpack_from('<I', sub0, 8)[0]
    decompressed = bytearray(lzss_decompress(sub0, 12, total_comp - 12, uncomp_size))

    # 3. 只 inject 1 个字符到 slot 3575（最高位，最不可能被引擎读到）
    test_slot = 3575
    test_char = '汉'
    bmp = render_char_12x11(test_char)
    off = 0x480 + test_slot * 18
    print(f'inject {test_char} 到 slot {test_slot} offset {off:#x}: {bmp.hex()}')
    decompressed[off:off + 18] = bmp

    # 4. 重压缩
    recomp = bytearray(lzss_compress(bytes(decompressed), 12))
    recomp[0:4] = tag_bytes
    struct.pack_into('<I', recomp, 4, len(recomp))
    struct.pack_into('<I', recomp, 8, len(decompressed))
    print(f'重压缩: {len(recomp)} 字节')

    # 5. 拼新 archive
    sub1_off, sub1_len = subs[1]
    sub1_original = bytes(arch[sub1_off:sub1_off + sub1_len])
    new_size = TARGET_OFFSET + sub1_len
    arch_new = bytearray(new_size)
    arch_new[:len(recomp)] = recomp
    arch_new[TARGET_OFFSET:TARGET_OFFSET + sub1_len] = sub1_original

    # 6. 追加 ISO 末尾
    with open(ISO_PATH, 'r+b') as f:
        f.seek(0, 2)
        new_lba = f.tell() // 2352
        new_sector_count = (new_size + 2047) // 2048
        for i in range(new_sector_count):
            f.write(create_valid_ps1_sector(new_lba + i))
    write_sectors(ISO_PATH, new_lba, bytes(arch_new))

    # 7. 更新 FILEPOS.DAT
    fp = bytearray(read_sectors(ISO_PATH, 0x17, 4 * 2048))
    struct.pack_into('<I', fp, FONT_FILE * 8, new_lba)
    struct.pack_into('<I', fp, FONT_FILE * 8 + 4, new_size)
    write_sectors(ISO_PATH, 0x17, bytes(fp))

    # 8. 更新 PVD
    new_total = new_lba + new_sector_count
    pvd = bytearray(read_sectors(ISO_PATH, 16, 2048))
    struct.pack_into('<I', pvd, 80, new_total)
    struct.pack_into('>I', pvd, 84, new_total)
    write_sectors(ISO_PATH, 16, bytes(pvd))

    # 9. 修 ECC
    subprocess.run(['python3', FIX_ECC, str(new_lba), str(new_lba + new_sector_count - 1)], check=True)
    subprocess.run(['python3', FIX_ECC, '23', '26'], check=True)
    subprocess.run(['python3', FIX_ECC, '16', '16'], check=True)
    print(f'\n✅ 测试 ISO 就绪。只 inject 1 个字 (汉) 到 slot 3575')
    print('   - 能进游戏 → 量级问题（多个 inject 之一会触发 bug）')
    print('   - 还黑屏 → 任何 inject 都崩，问题在 LZSS 重压缩 + 修改后字节流不被 PS1 接受')

if __name__ == '__main__':
    main()
