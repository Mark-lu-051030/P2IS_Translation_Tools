"""
测试 30-sector layout 但不 inject：
  - sub-file 0 占 30 sectors (原内容 + zero padding)
  - sub-file 1 在 30 sectors offset (原内容字节不变)
  - SLPS 描述符表已 patch 为 30/30

必须先跑 patch_subfile_table.py。
file 59 需要更大空间（58 sectors = 118784 字节），放在 ISO 末尾。

用法: python3 relocate_file59.py
"""
import os, sys, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors, write_sectors, archive_subfile_offsets

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BAK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')

TARGET_SUB1_OFFSET = 30 * 2048   # 61440 bytes

def create_valid_ps1_sector(lba):
    abs_sect = lba + 150
    m = abs_sect // 4500; s = (abs_sect % 4500) // 75; f = abs_sect % 75
    bcd = lambda v: (v // 10) * 16 + (v % 10)
    sec = bytearray(2352)
    sec[0:12] = b'\x00\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\xFF\x00'
    sec[12:15] = bytes([bcd(m), bcd(s), bcd(f)])
    sec[15] = 0x02
    sec[16:24] = b'\x00\x00\x08\x00\x00\x00\x08\x00'
    return sec

# 1. 读 backup file 59
fp = read_sectors(BAK, 0x17, 0x1b88)
b59 = struct.unpack_from('<I', fp, 59*8)[0]
s59 = struct.unpack_from('<I', fp, 59*8 + 4)[0]
arch = read_sectors(BAK, b59, s59)
subs = archive_subfile_offsets(arch)

# 2. 取原始 sub-file 0 和 sub-file 1 字节
sub0_off, sub0_len = subs[0]
sub1_off, sub1_len = subs[1]
sub0_orig = bytes(arch[sub0_off:sub0_off + sub0_len])
sub1_orig = bytes(arch[sub1_off:sub1_off + sub1_len])
print(f'原 sub-file 0: {sub0_len} 字节 ({sub0_len/2048:.1f} sectors)')
print(f'原 sub-file 1: {sub1_len} 字节 ({sub1_len/2048:.1f} sectors)')

# 3. 拼新 archive: sub-file 0 + padding + sub-file 1 (sub-file 1 在 30 sectors offset)
new_size = TARGET_SUB1_OFFSET + sub1_len
arch_new = bytearray(new_size)
arch_new[:sub0_len] = sub0_orig          # sub-file 0 原内容
arch_new[TARGET_SUB1_OFFSET:TARGET_SUB1_OFFSET + sub1_len] = sub1_orig
print(f'新 archive 总大小: {new_size} 字节 ({(new_size+2047)//2048} sectors)')

# 4. 追加到 ISO 末尾
with open(ISO, 'r+b') as f:
    f.seek(0, 2)
    new_lba = f.tell() // 2352
    nsec = (new_size + 2047) // 2048
    for i in range(nsec):
        f.write(create_valid_ps1_sector(new_lba + i))
write_sectors(ISO, new_lba, bytes(arch_new))
print(f'追加 LBA {new_lba}, {nsec} sectors')

# 5. 更新 FILEPOS.DAT[59]
fp_data = bytearray(read_sectors(ISO, 0x17, 4*2048))
struct.pack_into('<I', fp_data, 59*8, new_lba)
struct.pack_into('<I', fp_data, 59*8 + 4, new_size)
write_sectors(ISO, 0x17, bytes(fp_data))
print(f'FILEPOS.DAT[59] = ({new_lba}, {new_size})')

# 6. 更新 PVD volume_space_size
new_total = new_lba + nsec
pvd = bytearray(read_sectors(ISO, 16, 2048))
struct.pack_into('<I', pvd, 80, new_total)
struct.pack_into('>I', pvd, 84, new_total)
write_sectors(ISO, 16, bytes(pvd))
print(f'PVD volume_space_size → {new_total}')

# 7. 修 ECC
subprocess.run(['python3', FIX_ECC, str(new_lba), str(new_lba + nsec - 1)], check=True)
subprocess.run(['python3', FIX_ECC, '23', '26'], check=True)
subprocess.run(['python3', FIX_ECC, '16', '16'], check=True)

print('\n✅ 30-sector layout 部署完成（无 inject）')
print('   先确认 patch_subfile_table.py 已跑（两处都改成 30 sectors）')
print('   启动 game 测试：能跑 → D1 真正成功；崩 → 还有别的 SLPS 硬编码')
