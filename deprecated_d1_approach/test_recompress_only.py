"""
测试 B：重压缩 sub-file 0 但不 inject 中文。
搬位置 + LZSS 解→重压缩（内容字节不变）+ 不动 sub1。

对比：
  - test_relocate_only.py（A）：不重压缩 → 能跑 ✓
  - 本脚本（B）：重压缩但不 inject → ?
  - ijc.py（C）：重压缩 + inject → 黑屏 ✗

A vs B 隔离"LZSS 重压缩"变量。
B vs C 隔离"inject bitmap 内容"变量。

用法: python3 test_recompress_only.py
"""
import os, sys, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import (
    read_sectors, write_sectors,
    lzss_decompress, lzss_compress,
    archive_subfile_offsets,
)

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO_PATH   = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BACKUP_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC    = os.path.join(ROOT, 'fix_ecc.py')
FONT_FILE  = 59
TARGET_OFFSET = 61440

def create_valid_ps1_sector(lba):
    abs_sect = lba + 150
    m = abs_sect // 4500
    s = (abs_sect % 4500) // 75
    f = abs_sect % 75
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

    # 2. 解压 sub-file 0，**不改 bitmap**，重压缩
    sub0_off, sub0_len = subs[0]
    sub0 = arch[sub0_off:sub0_off + sub0_len]
    tag_bytes = bytes(sub0[0:4])
    total_comp  = struct.unpack_from('<I', sub0, 4)[0]
    uncomp_size = struct.unpack_from('<I', sub0, 8)[0]
    decompressed = lzss_decompress(sub0, 12, total_comp - 12, uncomp_size)
    print(f'解压 sub0: {sub0_len} → {len(decompressed)} 字节')

    recomp = bytearray(lzss_compress(bytes(decompressed), 12))
    recomp[0:4] = tag_bytes
    struct.pack_into('<I', recomp, 4, len(recomp))
    struct.pack_into('<I', recomp, 8, len(decompressed))
    print(f'重压缩: {len(recomp)} 字节')

    if len(recomp) > TARGET_OFFSET:
        print(f'错误: recomp 太大: {len(recomp)} > {TARGET_OFFSET}')
        sys.exit(1)

    # 3. 取 sub1 原样
    sub1_off, sub1_len = subs[1]
    sub1_original = bytes(arch[sub1_off:sub1_off + sub1_len])

    # 4. 拼新 archive
    new_size = TARGET_OFFSET + sub1_len
    arch_new = bytearray(new_size)
    arch_new[:len(recomp)] = recomp
    arch_new[TARGET_OFFSET:TARGET_OFFSET + sub1_len] = sub1_original

    # 5. 追加到 ISO 末尾
    with open(ISO_PATH, 'r+b') as f:
        f.seek(0, 2)
        new_lba = f.tell() // 2352
        new_sector_count = (new_size + 2047) // 2048
        for i in range(new_sector_count):
            f.write(create_valid_ps1_sector(new_lba + i))
    write_sectors(ISO_PATH, new_lba, bytes(arch_new))

    # 6. 更新 FILEPOS.DAT[59] (4 sectors)
    fp = bytearray(read_sectors(ISO_PATH, 0x17, 4 * 2048))
    struct.pack_into('<I', fp, FONT_FILE * 8, new_lba)
    struct.pack_into('<I', fp, FONT_FILE * 8 + 4, new_size)
    write_sectors(ISO_PATH, 0x17, bytes(fp))

    # 7. 更新 PVD
    new_total = new_lba + new_sector_count
    pvd = bytearray(read_sectors(ISO_PATH, 16, 2048))
    struct.pack_into('<I', pvd, 80, new_total)
    struct.pack_into('>I', pvd, 84, new_total)
    write_sectors(ISO_PATH, 16, bytes(pvd))

    # 8. 修 ECC
    subprocess.run(['python3', FIX_ECC, str(new_lba), str(new_lba + new_sector_count - 1)], check=True)
    subprocess.run(['python3', FIX_ECC, '23', '26'], check=True)
    subprocess.run(['python3', FIX_ECC, '16', '16'], check=True)
    print(f'\n✅ B 测试 ISO 就绪。LBA {new_lba}, sub0 重压缩 {len(recomp)}B (无 inject)')
    print('   - 能进游戏 → 重压缩本身 ok，问题在 inject bitmap 内容')
    print('   - 还黑屏 → LZSS 重压缩字节流和 PS1 解码器不兼容')

if __name__ == '__main__':
    main()
