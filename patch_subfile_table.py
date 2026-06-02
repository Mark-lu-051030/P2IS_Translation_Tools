"""
正确的 file 59 sub-file 描述符表 patch。

在 SLPS 内 0x80010070-0x8001007f 是 sub-file 描述符表（FUN_80017a9c 通过 lwl/lwr 读取）：
  0x80010070: 00 00 00 00 16 00 01 00   ← Desc 1: sub-file 0 (size=22 sectors)
  0x80010078: 00 00 16 00 1C 00 01 00   ← Desc 2: sub-file 1 (offset=22, size=28)

之前 extander.py 只改了 Desc 2 的 sub-file 1 偏移 22→30（一半的 patch）。
真正生效需要同时改 Desc 1 的 sub-file 0 大小 22→30。

⚠️ 动态 N（根治 UI sprite 损坏）：
  Desc1.size = CD 读 sub-file 0 的扇区数（read countdown，DAT_80080da0）。
  它必须 == 压缩后 sub-file 0 实际占用的扇区数，否则 CD 多读的扇区溢出
  7-slot ring buffer（0x801CB000-0x801CE800）→ 损坏字库/相邻 RAM
  （HP/SP/¥/TIME 标签、对话续行三角标显示绿噪点）。
  本脚本静态设 30 只是 build 流程里的"上限占位"——inject_chinese_font.py
  重压缩后会调用 set_subfile0_size() 把 Desc1.size 精确改成 ceil(recomp/2048)。
  Desc2.offset（sub-file 1 位置）保持 30 不变。

ISO 上对应位置（在 SLPS BIN sector 29 user data）：
  sector 29 offset 0x74-0x77 (Desc 1 后 4 字节)
  sector 29 offset 0x78-0x7b (Desc 2 前 4 字节)

用法:
  python3 patch_subfile_table.py            # patch working
  python3 patch_subfile_table.py --target both
  python3 patch_subfile_table.py --verify
  python3 patch_subfile_table.py --revert
"""
import argparse, os, struct, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from pylib.p2is import read_sectors, write_sectors

ISO_WORKING = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
ISO_BACKUP  = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')

SECTOR = 29
# Desc 1: sub-file 0 size 字段 在 offset 0x74-0x77 (LE word = 0x00010016)
DESC1_OFFSET = 0x74
OLD_DESC1 = b'\x16\x00\x01\x00'   # sub-file 0 size = 22 sectors
NEW_DESC1 = b'\x1e\x00\x01\x00'   # sub-file 0 size = 30 sectors

# Desc 2: sub-file 1 offset 字段 在 offset 0x78-0x7b (LE word = 0x00160000)
DESC2_OFFSET = 0x78
OLD_DESC2 = b'\x00\x00\x16\x00'   # sub-file 1 offset = 22 sectors
NEW_DESC2 = b'\x00\x00\x1e\x00'   # sub-file 1 offset = 30 sectors

def set_subfile0_size(iso_path, n_sectors, fix_ecc=True):
    """动态 N 根治：把 Desc1 的 sub-file 0 size 字段设为 n_sectors（= CD 读扇区数）。

    inject_chinese_font.py 重压缩后调用此函数，n_sectors = ceil(len(recomp)/2048)。
    SIZE 精确匹配压缩大小 → CD 读的扇区数恰好等于 sub-file 0 占用扇区 → ring buffer 零溢出。
    只改 Desc1 低 16 位（保留高 16 位 type=1）；Desc2.offset 不动。"""
    if not (1 <= n_sectors <= 0xffff):
        raise ValueError(f'n_sectors 越界: {n_sectors}')
    data = bytearray(read_sectors(iso_path, SECTOR, 2048))
    old = struct.unpack_from('<H', data, DESC1_OFFSET)[0]
    struct.pack_into('<H', data, DESC1_OFFSET, n_sectors)
    write_sectors(iso_path, SECTOR, bytes(data))
    if fix_ecc:
        subprocess.run(['python3', FIX_ECC, str(SECTOR), str(SECTOR)], check=True)
    print(f'  Desc1 sub-file 0 size: {old} → {n_sectors} sectors (动态 N)')
    return old

def patch_iso(iso_path, verify_only=False, revert=False):
    print(f'\n=== {os.path.basename(iso_path)} ===')
    data = bytearray(read_sectors(iso_path, SECTOR, 2048))

    cur_d1 = bytes(data[DESC1_OFFSET:DESC1_OFFSET+4])
    cur_d2 = bytes(data[DESC2_OFFSET:DESC2_OFFSET+4])

    d1_size = struct.unpack_from('<H', cur_d1, 0)[0]
    print(f'  Desc 1 (sub-file 0 size): {cur_d1.hex()} ', end='')
    if cur_d1 == OLD_DESC1: print('(原版 22 sectors)')
    elif cur_d1 == NEW_DESC1: print('(占位上限 30 sectors，待 inject 改动态 N)')
    elif 22 < d1_size <= 30 and cur_d1[2:] == b'\x01\x00': print(f'(动态 N: {d1_size} sectors — inject 已精确设定)')
    else: print('(未知)')

    print(f'  Desc 2 (sub-file 1 offset): {cur_d2.hex()} ', end='')
    if cur_d2 == OLD_DESC2: print('(原版 22 sectors)')
    elif cur_d2 == NEW_DESC2: print('(已 patch 30 sectors / extander.py 改过)')
    else: print('(未知)')

    if verify_only:
        return

    if revert:
        target_d1, target_d2 = OLD_DESC1, OLD_DESC2
        label = '原版'
    else:
        target_d1, target_d2 = NEW_DESC1, NEW_DESC2
        label = 'D1 完整版 (30 sectors)'

    if cur_d1 == target_d1 and cur_d2 == target_d2:
        print(f'  ✓ 已是目标状态 ({label})')
        return True

    data[DESC1_OFFSET:DESC1_OFFSET+4] = target_d1
    data[DESC2_OFFSET:DESC2_OFFSET+4] = target_d2
    write_sectors(iso_path, SECTOR, bytes(data))
    subprocess.run(['python3', FIX_ECC, str(SECTOR), str(SECTOR)], check=True)
    print(f'  ✓ Patched: {label}')
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', choices=['working', 'backup', 'both'], default='working')
    ap.add_argument('--verify', action='store_true')
    ap.add_argument('--revert', action='store_true')
    args = ap.parse_args()
    targets = []
    if args.target in ('working', 'both'): targets.append(ISO_WORKING)
    if args.target in ('backup', 'both'):  targets.append(ISO_BACKUP)
    for t in targets:
        if not os.path.exists(t):
            print(f'⚠ ISO 不存在: {t}'); continue
        patch_iso(t, verify_only=args.verify, revert=args.revert)

if __name__ == '__main__':
    main()
