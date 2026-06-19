#!/usr/bin/env python3
"""把 256x256、4bpp 索引 PNG 安全写回 P2IS 的 F1079.BIN。

F1079 是一个标准 PS1 TIM：一份共享像素 + 16 行 CLUT。脚本只替换像素 payload，
保留原 TIM 头、VRAM 坐标和全部 16 套调色板。
"""

import argparse
import hashlib
import sys
from pathlib import Path
import struct

from PIL import Image

TOOL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TOOL_ROOT))

from fix_ecc import fix_sector  # noqa: E402
from pylib.p2is import BLOCK_SIZE, SECTOR, read_sectors, write_sectors  # noqa: E402

LBA = 271477
F1079_SIZE = 33312
DEFAULT_SOURCE = Path(
    "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/extrac/D/F1079.BIN"
)
DEFAULT_ISO = Path(
    "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/"
    "Persona 2 - Tsumi - Innocent Sin (Japan).bin"
)


def parse_f1079(data: bytes) -> tuple[int, int]:
    if len(data) != F1079_SIZE:
        raise ValueError(f"F1079 大小应为 {F1079_SIZE}，实际为 {len(data)}")
    magic, flags = struct.unpack_from("<II", data, 0)
    if (magic, flags) != (0x10, 0x08):
        raise ValueError(f"不是预期的 4bpp+CLUT TIM：magic={magic:#x}, flags={flags:#x}")

    clut_size, cx, cy, cw, ch = struct.unpack_from("<IHHHH", data, 8)
    image_header = 8 + clut_size
    image_size, ix, iy, words_w, height = struct.unpack_from(
        "<IHHHH", data, image_header
    )
    expected = (524, 0, 480, 16, 16, 32780, 768, 0, 64, 256)
    actual = (clut_size, cx, cy, cw, ch, image_size, ix, iy, words_w, height)
    if actual != expected:
        raise ValueError(f"F1079 TIM 结构不符：\n预期 {expected}\n实际 {actual}")
    if image_header + image_size != len(data):
        raise ValueError("TIM 块长度与文件大小不一致")
    return image_header + 12, image_size - 12


def pack_png(path: Path) -> bytes:
    with Image.open(path) as im:
        if im.mode != "P" or im.size != (256, 256):
            raise ValueError(f"PNG 必须是 256x256 的索引图(P)，实际为 {im.size} {im.mode}")
        pixels = im.tobytes()
    highest = max(pixels)
    if highest > 15:
        raise ValueError(f"PNG 使用了 16 色范围外的索引：最大 index={highest}")
    return bytes(
        (pixels[i] & 0x0F) | ((pixels[i + 1] & 0x0F) << 4)
        for i in range(0, len(pixels), 2)
    )


def patch_tim(source: bytes, png: Path, allow_large_change: bool = False) -> tuple[bytes, int]:
    pixel_offset, pixel_size = parse_f1079(source)
    packed = pack_png(png)
    if len(packed) != pixel_size:
        raise ValueError(f"像素应为 {pixel_size} 字节，实际为 {len(packed)}")
    old = source[pixel_offset:pixel_offset + pixel_size]
    changed = sum(a != b for a, b in zip(old, packed))
    if changed > 4096 and not allow_large_change:
        raise ValueError(
            f"PNG 会改动 {changed}/{pixel_size} 个像素字节，疑似导出时索引被重排；"
            "确认是大面积改图时才加 --allow-large-change"
        )
    result = bytearray(source)
    result[pixel_offset:pixel_offset + pixel_size] = packed
    # 再解析一次，防止任何长度/头部意外变化。
    parse_f1079(result)
    return bytes(result), changed


def fix_iso_ecc(iso: Path, first: int, last: int) -> None:
    with iso.open("r+b") as f:
        for lba in range(first, last + 1):
            f.seek(lba * SECTOR)
            raw = f.read(SECTOR)
            if len(raw) != SECTOR or raw[15] != 2:
                raise ValueError(f"LBA {lba} 不是完整的 Mode 2 扇区")
            f.seek(lba * SECTOR)
            f.write(fix_sector(raw))


def cmd_build(args) -> None:
    source = args.source.read_bytes()
    result, changed = patch_tim(source, args.png, args.allow_large_change)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(result)
    print(f"生成 {args.out}（{len(result)} bytes，像素区改动 {changed} bytes）")
    print(f"SHA-256 {hashlib.sha256(result).hexdigest()}")


def cmd_apply(args) -> None:
    current = bytes(read_sectors(args.iso, LBA, F1079_SIZE))
    result, changed = patch_tim(current, args.png, args.allow_large_change)
    if changed == 0:
        print("工作盘中的 F1079 已与该 PNG 一致，无需写入。")
        return

    args.backup.parent.mkdir(parents=True, exist_ok=True)
    if args.backup.exists() and not args.overwrite_backup:
        raise FileExistsError(
            f"备份已存在：{args.backup}；请移走它或加 --overwrite-backup"
        )
    args.backup.write_bytes(current)
    write_sectors(args.iso, LBA, result)
    last = LBA + (F1079_SIZE + BLOCK_SIZE - 1) // BLOCK_SIZE - 1
    fix_iso_ecc(args.iso, LBA, last)

    verify = bytes(read_sectors(args.iso, LBA, F1079_SIZE))
    if verify != result:
        raise RuntimeError("写回后的逐字节校验失败")
    print(f"已写回 {args.iso}")
    print(f"LBA {LBA}-{last}，像素区改动 {changed} bytes，ECC/EDC 已修复")
    print(f"原文件备份：{args.backup}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="只生成修改后的 F1079.BIN，不碰光盘镜像")
    build.add_argument("png", type=Path)
    build.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    build.add_argument("--out", type=Path, default=Path("out/F1079.zh.BIN"))
    build.add_argument("--allow-large-change", action="store_true")
    build.set_defaults(func=cmd_build)

    apply = sub.add_parser("apply", help="写入工作 BIN 镜像并修复 ECC/EDC")
    apply.add_argument("png", type=Path)
    apply.add_argument("--iso", type=Path, default=DEFAULT_ISO)
    apply.add_argument("--backup", type=Path, default=Path("out/F1079.before_apply.BIN"))
    apply.add_argument("--overwrite-backup", action="store_true")
    apply.add_argument("--allow-large-change", action="store_true")
    apply.set_defaults(func=cmd_apply)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
