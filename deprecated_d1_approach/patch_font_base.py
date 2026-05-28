"""
Patch 字库目标 RAM 基址。

字库基址在 SLPS 内的 FUN_80024e78 函数里通过 lui+ori 加载到 $a2 寄存器：
  ISO sector 70 offset 0x68c-0x68f:  lui  $a2, 0x801C
  ISO sector 70 offset 0x690-0x693:  ori  $a2, $a2, 0xE800
  → 当前字库基址 = 0x801CE800

把 0x801CE800 改成 0x801A0000（往前移 186KB，给后续扩容留空间）。
RAM 0x801A0000 - 0x801CB000 内空闲（在 SLPS TEXT 之后）。

用法:
  python3 patch_font_base.py            # patch working
  python3 patch_font_base.py --target both
  python3 patch_font_base.py --verify   # 只验证当前 patch 状态
"""
import argparse, os, struct, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from pylib.p2is import read_sectors, write_sectors

ISO_WORKING = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
ISO_BACKUP  = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')

# 字库基址硬编码位置
SECTOR = 70
LUI_OFFSET = 0x68c   # lui $a2, immediate
ORI_OFFSET = 0x690   # ori $a2, $a2, immediate

# 原字库基址 0x801CE800 → 新基址 0x801A0000
OLD_LUI = b'\x1c\x80\x06\x3c'    # lui a2, 0x801C
OLD_ORI = b'\x00\xe8\xc6\x34'    # ori a2, a2, 0xE800
NEW_LUI = b'\x1a\x80\x06\x3c'    # lui a2, 0x801A
NEW_ORI = b'\x00\x00\xc6\x34'    # ori a2, a2, 0  (新基址低 16 = 0)

OLD_BASE = 0x801CE800
NEW_BASE = 0x801A0000

def patch_iso(iso_path, verify_only=False):
    print(f'\n=== {os.path.basename(iso_path)} ===')
    data = bytearray(read_sectors(iso_path, SECTOR, 2048))

    cur_lui = bytes(data[LUI_OFFSET:LUI_OFFSET+4])
    cur_ori = bytes(data[ORI_OFFSET:ORI_OFFSET+4])

    if cur_lui == OLD_LUI and cur_ori == OLD_ORI:
        state = '原版 (字库基址 0x801CE800)'
    elif cur_lui == NEW_LUI and cur_ori == NEW_ORI:
        state = f'已 patch (字库基址 0x{NEW_BASE:08X})'
    else:
        state = f'未知状态 lui={cur_lui.hex()} ori={cur_ori.hex()}'

    print(f'  当前: {state}')

    if verify_only:
        return

    if cur_lui == NEW_LUI and cur_ori == NEW_ORI:
        print(f'  ✓ 已是目标状态，无需 patch')
        return True
    if cur_lui != OLD_LUI or cur_ori != OLD_ORI:
        print(f'  ⚠ 字节不匹配原版，拒绝 patch（避免破坏未知修改）')
        return False

    data[LUI_OFFSET:LUI_OFFSET+4] = NEW_LUI
    data[ORI_OFFSET:ORI_OFFSET+4] = NEW_ORI
    write_sectors(iso_path, SECTOR, bytes(data))
    subprocess.run(['python3', FIX_ECC, str(SECTOR), str(SECTOR)], check=True)
    print(f'  ✓ Patched: 字库基址 0x{OLD_BASE:08X} → 0x{NEW_BASE:08X}')
    return True

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--target', choices=['working', 'backup', 'both'], default='working')
    ap.add_argument('--verify', action='store_true', help='只验证不改')
    args = ap.parse_args()
    targets = []
    if args.target in ('working', 'both'): targets.append(ISO_WORKING)
    if args.target in ('backup', 'both'):  targets.append(ISO_BACKUP)
    for t in targets:
        if not os.path.exists(t):
            print(f'⚠ ISO 不存在: {t}'); continue
        patch_iso(t, verify_only=args.verify)

if __name__ == '__main__':
    main()
