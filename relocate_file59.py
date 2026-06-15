"""
file 59 重定位 + 32-sector layout 部署（不 inject）。

file 59 sub-file 0 扩容（字库），archive 总 ~60 sectors，原版槽位
（22 sectors @ LBA 66625）装不下，必须重定位。

【2026-06-15 改：放进 DUMMY.DAT，不再追加到 ISO 末尾】
  旧做法把扩容 archive 追加到盘尾，FILEPOS 指过去 + 改 PVD 卷大小。
  问题：盘尾那块在 ISO9660 目录里【没有文件名】——镜像工具无法解析（"隐含文件"），
        按 ISO9660 校验/严格读盘的模拟器、真机可能读不到 → 兼容性隐患。
  新做法：写进 DUMMY.DAT 占用的扇区。
    - DUMMY.DAT 是盘上的大填充文件（游戏从不读），有 ~32MB 余量。
    - archive 覆盖 DUMMY.DAT 起始扇区（填充数据被覆盖，无害）。
    - 只改 FILEPOS.DAT[59] 指过去；盘大小 / PVD 不变，数据全部落在卷内。
  layout 与位置无关：inject_chinese_font.py 仍按 FILEPOS[59] 定位 archive，
  patch_subfile_table.py 改的是 SLPS 描述符表（与位置无关）。

必须先跑 patch_subfile_table.py。
用法:
  python3 relocate_file59.py                       # 改工作盘
  python3 relocate_file59.py --iso A.bin --bak B.bin  # 改指定盘（验证用，B 提供原版 file59）
"""
import argparse, os, sys, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors, write_sectors, archive_subfile_offsets

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO_DEFAULT = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BAK_DEFAULT = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')

TARGET_SUB1_OFFSET = 32 * 2048   # 65536 bytes (sub-file 0 扩到 32 sectors)


def iso9660_find(iso, name):
    """在 ISO9660 根目录及其一级子目录里按名字找文件，返回 (lba, size_bytes)。name 不含 ';1'。"""
    def scan_dir(dir_lba, dir_len):
        d = read_sectors(iso, dir_lba, dir_len)
        i, out = 0, []
        while i < len(d):
            L = d[i]
            if L == 0:                                  # 记录不跨扇区，0 = 本扇区结束
                nxt = ((i // 2048) + 1) * 2048
                if nxt >= len(d):
                    break
                i = nxt
                continue
            lba = struct.unpack_from('<I', d, i + 2)[0]
            ln = struct.unpack_from('<I', d, i + 10)[0]
            flags = d[i + 25]
            nl = d[i + 32]
            nm = d[i + 33:i + 33 + nl].decode('latin1', 'replace')
            if not (nl == 1 and nm in ('\x00', '\x01')):   # 跳过 . 和 ..
                out.append((nm, lba, ln, flags))
            i += L
        return out

    pvd = read_sectors(iso, 16, 2048)
    root_lba = struct.unpack_from('<I', pvd, 156 + 2)[0]
    root_len = struct.unpack_from('<I', pvd, 156 + 10)[0]
    root = scan_dir(root_lba, root_len)
    for nm, lba, ln, _ in root:
        if nm.split(';')[0] == name:
            return lba, ln
    for nm, lba, ln, flags in root:
        if flags & 0x02:                                 # 子目录
            for nm2, lba2, ln2, _ in scan_dir(lba, ln):
                if nm2.split(';')[0] == name:
                    return lba2, ln2
    raise SystemExit(f'ISO9660 找不到 {name}')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--iso', default=ISO_DEFAULT, help='目标盘（被修改）')
    ap.add_argument('--bak', default=BAK_DEFAULT, help='原版盘（提供原始 file 59 字节）')
    args = ap.parse_args()
    ISO, BAK = args.iso, args.bak

    # 1. 从原版盘读 file 59 archive
    fp = read_sectors(BAK, 0x17, 0x1b88)
    b59 = struct.unpack_from('<I', fp, 59 * 8)[0]
    s59 = struct.unpack_from('<I', fp, 59 * 8 + 4)[0]
    arch = read_sectors(BAK, b59, s59)
    subs = archive_subfile_offsets(arch)

    # 2. 取原始 sub-file 0 / sub-file 1
    sub0_off, sub0_len = subs[0]
    sub1_off, sub1_len = subs[1]
    sub0_orig = bytes(arch[sub0_off:sub0_off + sub0_len])
    sub1_orig = bytes(arch[sub1_off:sub1_off + sub1_len])
    print(f'原 sub-file 0: {sub0_len} 字节 ({sub0_len/2048:.1f} sectors)')
    print(f'原 sub-file 1: {sub1_len} 字节 ({sub1_len/2048:.1f} sectors)')

    # 3. 拼新 archive: sub0 原内容 + padding 到 32 sectors + sub1 原内容
    new_size = TARGET_SUB1_OFFSET + sub1_len
    arch_new = bytearray(new_size)
    arch_new[:sub0_len] = sub0_orig
    arch_new[TARGET_SUB1_OFFSET:TARGET_SUB1_OFFSET + sub1_len] = sub1_orig
    nsec = (new_size + 2047) // 2048
    print(f'新 archive 总大小: {new_size} 字节 ({nsec} sectors)')

    # 4. 找 DUMMY.DAT，把 archive 写进它的起始扇区（覆盖填充，盘大小不变）
    dummy_lba, dummy_size = iso9660_find(ISO, 'DUMMY.DAT')
    dummy_secs = (dummy_size + 2047) // 2048
    if nsec > dummy_secs:
        raise SystemExit(f'DUMMY.DAT 只有 {dummy_secs} sectors，装不下 {nsec} sectors')
    new_lba = dummy_lba
    write_sectors(ISO, new_lba, bytes(arch_new))         # 写进现有扇区的数据区（保留扇区头）
    print(f'F0059 → DUMMY.DAT 起始 LBA {new_lba}, 占 {nsec}/{dummy_secs} sectors')

    # 5. 更新 FILEPOS.DAT[59] → 新位置
    fp_data = bytearray(read_sectors(ISO, 0x17, 4 * 2048))
    struct.pack_into('<I', fp_data, 59 * 8, new_lba)
    struct.pack_into('<I', fp_data, 59 * 8 + 4, new_size)
    write_sectors(ISO, 0x17, bytes(fp_data))
    print(f'FILEPOS.DAT[59] = ({new_lba}, {new_size})')

    # 6. 修 ECC：写过的 F0059 扇区 + FILEPOS 扇区（PVD / 盘大小不变，无需动）
    subprocess.run(['python3', FIX_ECC, str(new_lba), str(new_lba + nsec - 1)], check=True)
    subprocess.run(['python3', FIX_ECC, '23', '26'], check=True)

    print('\n✅ file 59 已重定位到 DUMMY.DAT（盘大小不变，无隐含文件）')
    print('   下一步: inject_chinese_font.py（按 FILEPOS[59] 定位，位置无关）')


if __name__ == '__main__':
    main()
