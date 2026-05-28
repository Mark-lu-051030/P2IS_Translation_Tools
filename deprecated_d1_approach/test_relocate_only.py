"""
最小化测试：只搬 file 59 到 ISO 末尾，**不** inject 中文字体，**不** 重压缩 sub-file 0。
完整复制 backup 的 file 59 原 archive（sub0 + padding + sub1）到新位置。

如果这个测试能进游戏（虽然没中文），说明问题在 ijc.py 的 LZSS 重压缩 / inject 流程。
如果这个测试也黑屏，说明问题在"搬位置"本身（更深层的 SLPS 假设）。

用法: python3 test_relocate_only.py
"""
import os, sys, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors, write_sectors, archive_subfile_offsets

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO_PATH   = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BACKUP_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC    = os.path.join(ROOT, 'fix_ecc.py')
FONT_FILE  = 59
TARGET_OFFSET = 61440  # SLPS 1E patch 期待 sub-file 1 在 30 sectors

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
    # 1. 从 backup 读 file 59 原 archive
    filepos = read_sectors(BACKUP_ISO, 0x17, 0x1b88)
    block59 = struct.unpack_from('<I', filepos, FONT_FILE * 8)[0]
    size59  = struct.unpack_from('<I', filepos, FONT_FILE * 8 + 4)[0]
    arch = read_sectors(BACKUP_ISO, block59, size59)
    subs = archive_subfile_offsets(arch)
    print(f'backup file 59: block={block59}, size={size59}, sub-files={len(subs)}')

    # 2. 直接保留原 sub-file 0 字节流（不 inject 不重压缩）
    sub0_off, sub0_len = subs[0]
    sub0_original = bytes(arch[sub0_off:sub0_off + sub0_len])
    print(f'sub-file 0 原大小: {sub0_len} 字节')
    if sub0_len > TARGET_OFFSET:
        print(f'错误: sub0 ({sub0_len}) > TARGET_OFFSET ({TARGET_OFFSET})')
        sys.exit(1)

    # 3. 提取 sub-file 1 原内容
    sub1_off, sub1_len = subs[1]
    sub1_original = bytes(arch[sub1_off:sub1_off + sub1_len])
    print(f'sub-file 1 原大小: {sub1_len} 字节')

    # 4. 组装新 archive: sub0 在 0~sub0_len, padding 到 0xf000, sub1 在 0xf000
    new_file59_size = TARGET_OFFSET + sub1_len
    arch_new = bytearray(new_file59_size)
    arch_new[:sub0_len] = sub0_original
    arch_new[TARGET_OFFSET:TARGET_OFFSET + sub1_len] = sub1_original
    print(f'新 archive: {new_file59_size} 字节')

    # 5. 追加到 working ISO 末尾
    with open(ISO_PATH, 'r+b') as f:
        f.seek(0, 2)
        iso_size = f.tell()
        new_lba = iso_size // 2352
        new_sector_count = (new_file59_size + 2047) // 2048
        for i in range(new_sector_count):
            f.write(create_valid_ps1_sector(new_lba + i))
    print(f'追加 LBA {new_lba}, {new_sector_count} sectors')

    write_sectors(ISO_PATH, new_lba, bytes(arch_new))

    # 6. 更新 FILEPOS.DAT[59] (跨 4 sectors)
    fp = bytearray(read_sectors(ISO_PATH, 0x17, 4 * 2048))
    struct.pack_into('<I', fp, FONT_FILE * 8, new_lba)
    struct.pack_into('<I', fp, FONT_FILE * 8 + 4, new_file59_size)
    write_sectors(ISO_PATH, 0x17, bytes(fp))

    # 7. 更新 PVD volume_space_size
    new_total = new_lba + new_sector_count
    pvd = bytearray(read_sectors(ISO_PATH, 16, 2048))
    struct.pack_into('<I', pvd, 80, new_total)
    struct.pack_into('>I', pvd, 84, new_total)
    write_sectors(ISO_PATH, 16, bytes(pvd))
    print(f'PVD volume_space_size → {new_total}')

    # 8. 修 ECC
    subprocess.run(['python3', FIX_ECC, str(new_lba), str(new_lba + new_sector_count - 1)], check=True)
    subprocess.run(['python3', FIX_ECC, '23', '26'], check=True)
    subprocess.run(['python3', FIX_ECC, '16', '16'], check=True)
    print('\n✅ 测试 ISO 已就绪。冷启动 DuckStation 看是否能进游戏。')
    print('   - 如果能进，问题在 ijc.py 的 inject/重压缩')
    print('   - 如果还黑屏，问题在"搬位置"本身')

if __name__ == '__main__':
    main()
