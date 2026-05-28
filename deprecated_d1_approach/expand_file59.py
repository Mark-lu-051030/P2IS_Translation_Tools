"""扩展 file 59 容量（D1 方案）：把 file 59 搬到 ISO 末尾，扩到 100 sector。

原理：
  1. 原 file 59 在扇区 66625-66674（50 sector, 102400 字节）
  2. 把 file 59 archive 内容（含 sub-file 0/1 原样）复制到 ISO 末尾空白扇区
  3. 更新 FILEPOS.DAT[59] = (new_block, 204800)
  4. 修 ECC
  5. 原扇区 66625-66674 保留不动（如果新位置出问题，rollback 极快）

效果：
  - sub-file 0 现在最多可扩到 ~100KB（之前 45KB）
  - sub-file 1 内容不变（避免之前 minimize 导致游戏崩的问题）
  - 后续 inject_chinese_font.py 可以装下全部 2775+ 汉字，未来 strtbl/battle 也有余地

用法:
  python3 expand_file59.py --dry-run        # 看会怎么改，不实际写
  python3 expand_file59.py                  # 真改（同时备份 backup ISO）
  python3 expand_file59.py --rollback       # FILEPOS.DAT[59] 改回原位置
  python3 expand_file59.py --target backup  # 只改 backup ISO（默认是 both）
  python3 expand_file59.py --target working # 只改 working ISO
"""

import argparse
import os
import shutil
import struct
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from pylib.p2is import read_sectors, write_sectors

# ── 路径 ──────────────────────────────────────────────────
GAME_DIR = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd"
BACKUP_ISO = f"{GAME_DIR}/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin"
WORKING_ISO = f"{GAME_DIR}/Persona 2 - Tsumi - Innocent Sin (Japan).bin"

# ── 参数 ──────────────────────────────────────────────────
FILE_NUM       = 59
ORIG_BLOCK     = 66625
ORIG_SIZE      = 102400         # 50 sector
NEW_SIZE       = 204800         # 100 sector = 200KB
NEW_SECTORS    = NEW_SIZE // 2048
FILEPOS_BLOCK  = 0x17
FILEPOS_SIZE   = 0x1b88
NEW_BLOCK_DEFAULT = 264891      # ISO 末尾空白起始（由用户提供的 ls 结果）

FIX_ECC = str(Path(__file__).parent / "fix_ecc.py")


def find_free_block(iso_path):
    """扫 FILEPOS.DAT 找所有文件末尾，返回最大 end_sector 作为新空白起点。"""
    filepos = read_sectors(iso_path, FILEPOS_BLOCK, FILEPOS_SIZE)
    max_end = 0
    for i in range(881):
        block, size = struct.unpack_from("<II", filepos, i * 8)
        if block > 0 and size > 0:
            sectors = (size + 2047) // 2048
            end = block + sectors
            if end > max_end:
                max_end = end
    return max_end


def get_filepos_entry(iso_path, file_num):
    """读 FILEPOS.DAT 里 file_num 的 (block, size)。"""
    filepos = read_sectors(iso_path, FILEPOS_BLOCK, FILEPOS_SIZE)
    block, size = struct.unpack_from("<II", filepos, file_num * 8)
    return block, size


def set_filepos_entry(iso_path, file_num, block, size):
    """更新 FILEPOS.DAT 里 file_num 的 (block, size)，写回 ISO 同时修 ECC。"""
    filepos = bytearray(read_sectors(iso_path, FILEPOS_BLOCK, FILEPOS_SIZE))
    struct.pack_into("<II", filepos, file_num * 8, block, size)
    write_sectors(iso_path, FILEPOS_BLOCK, bytes(filepos))
    # 修 ECC: FILEPOS.DAT 占 4 sectors（0x1b88 / 2048 = 3.4 → 4 sector）
    sector_count = (FILEPOS_SIZE + 2047) // 2048
    subprocess.run(
        ["python3", FIX_ECC, str(FILEPOS_BLOCK), str(FILEPOS_BLOCK + sector_count - 1)],
        check=True,
    )


def expand_one_iso(iso_path, dry_run=False):
    """对一个 ISO 应用 expand。"""
    print(f"\n=== 处理 {os.path.basename(iso_path)} ===")
    # 1. 读当前 FILEPOS.DAT[59]
    cur_block, cur_size = get_filepos_entry(iso_path, FILE_NUM)
    print(f"  当前 FILEPOS.DAT[{FILE_NUM}]: block={cur_block}, size={cur_size}")
    if cur_block != ORIG_BLOCK or cur_size != ORIG_SIZE:
        print(f"  ⚠ 看起来已经修改过（期望 block={ORIG_BLOCK}, size={ORIG_SIZE}）")
        print(f"     如果想 rollback 用 --rollback")
        return False

    # 2. 找空白位置
    last_end = find_free_block(iso_path)
    new_block = last_end if last_end > NEW_BLOCK_DEFAULT - 100 else NEW_BLOCK_DEFAULT
    # 留一点 safety margin
    new_block = (new_block + 7) & ~7  # 8-sector align (不必须但好看)
    print(f"  最后文件 end sector: {last_end}")
    print(f"  新 file 59 位置: block {new_block} (占 {NEW_SECTORS} sectors, 到 {new_block + NEW_SECTORS - 1})")

    # 3. 读原 file 59 内容
    orig_content = read_sectors(iso_path, cur_block, cur_size)
    print(f"  读取原 file 59: {len(orig_content)} 字节")

    # 4. 准备新位置的内容 = 原内容 + 零 padding 到 NEW_SIZE
    new_content = bytearray(NEW_SIZE)
    new_content[:len(orig_content)] = orig_content

    if dry_run:
        print(f"  [DRY RUN] 会做:")
        print(f"    a. write_sectors({iso_path}, {new_block}, <new_content {NEW_SIZE}B>)")
        print(f"    b. set_filepos_entry({iso_path}, {FILE_NUM}, {new_block}, {NEW_SIZE})")
        print(f"    c. fix_ecc({new_block}-{new_block + NEW_SECTORS - 1})")
        print(f"    d. 原扇区 {ORIG_BLOCK}-{ORIG_BLOCK + ORIG_SIZE // 2048 - 1} 保留不动（备份）")
        return True

    # 5. 写新位置
    write_sectors(iso_path, new_block, bytes(new_content))
    print(f"  ✓ 写入 sector {new_block}-{new_block + NEW_SECTORS - 1}")

    # 6. 更新 FILEPOS.DAT
    set_filepos_entry(iso_path, FILE_NUM, new_block, NEW_SIZE)
    print(f"  ✓ FILEPOS.DAT[{FILE_NUM}] = ({new_block}, {NEW_SIZE})")

    # 7. 修 ECC for new file 59
    subprocess.run(
        ["python3", FIX_ECC, str(new_block), str(new_block + NEW_SECTORS - 1)],
        check=True,
    )
    print(f"  ✓ ECC 修复完成")
    return True


def rollback_one_iso(iso_path, dry_run=False):
    """rollback：把 FILEPOS.DAT[59] 改回原位置。原扇区还在，所以指回去就行。"""
    print(f"\n=== Rollback {os.path.basename(iso_path)} ===")
    cur_block, cur_size = get_filepos_entry(iso_path, FILE_NUM)
    if cur_block == ORIG_BLOCK and cur_size == ORIG_SIZE:
        print(f"  已经是原位置，无需 rollback")
        return True
    print(f"  当前: block={cur_block}, size={cur_size}")
    print(f"  Rollback 后: block={ORIG_BLOCK}, size={ORIG_SIZE}")

    if dry_run:
        print(f"  [DRY RUN] 会改 FILEPOS.DAT[{FILE_NUM}] 回 ({ORIG_BLOCK}, {ORIG_SIZE})")
        return True

    set_filepos_entry(iso_path, FILE_NUM, ORIG_BLOCK, ORIG_SIZE)
    print(f"  ✓ 已 rollback")
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rollback", action="store_true")
    ap.add_argument("--target", choices=["backup", "working", "both"], default="both",
                    help="改哪个 ISO（默认 both，因为 build.py 会从 backup 还原）")
    args = ap.parse_args()

    targets = []
    if args.target in ("backup", "both"):
        targets.append(BACKUP_ISO)
    if args.target in ("working", "both"):
        targets.append(WORKING_ISO)

    # 安全备份（只在真改时）
    if not args.dry_run and not args.rollback:
        for t in targets:
            safety = t + ".before_expand"
            if not os.path.exists(safety):
                print(f"安全备份: {os.path.basename(t)} → {os.path.basename(safety)}")
                shutil.copy(t, safety)
            else:
                print(f"安全备份已存在: {os.path.basename(safety)}（不覆盖）")

    op = rollback_one_iso if args.rollback else expand_one_iso
    for t in targets:
        if not os.path.exists(t):
            print(f"⚠ ISO 不存在: {t}")
            continue
        op(t, dry_run=args.dry_run)

    print("\n完成。")
    if not args.dry_run and not args.rollback:
        print("下一步:")
        print("  1. 试着启动游戏（DuckStation 冷启动加载 working ISO）→ 没黑屏说明 D1 成功")
        print("  2. python3 build.py → 用扩容后的 file 59 重新注入字体（容量充足）")
        print("  3. 测试翻译后的 ISO")
        print("\n如果游戏不启动:")
        print("  python3 expand_file59.py --rollback")


if __name__ == "__main__":
    main()
