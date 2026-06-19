#!/usr/bin/env python3
"""合并 Photoshop 编辑的 16 张 F1079 调色板预览，并可直接写入工作盘。"""

import argparse
import json
import struct
from collections import Counter
from pathlib import Path

from PIL import Image

from apply_f1079 import (
    BLOCK_SIZE,
    DEFAULT_ISO,
    DEFAULT_SOURCE,
    F1079_SIZE,
    LBA,
    fix_iso_ecc,
    parse_f1079,
    read_sectors,
    write_sectors,
)

HERE = Path(__file__).resolve().parent
DEFAULT_PAGES = HERE / "battleandmenu/tim/tim"
DEFAULT_ORIGINAL_PNGS = HERE / "battleandmenu"
DEFAULT_OUT = HERE / "out/f1079_batch"


def unpack_pixels(tim: bytes) -> tuple[list[int], int]:
    off, size = parse_f1079(tim)
    pixels = []
    for value in tim[off:off + size]:
        pixels.extend((value & 0x0F, value >> 4))
    return pixels, off


def pack_pixels(pixels: list[int]) -> bytes:
    return bytes(pixels[i] | (pixels[i + 1] << 4) for i in range(0, len(pixels), 2))


def alpha_for(info, index: int) -> int:
    trans = info.get("transparency")
    if isinstance(trans, bytes) and index < len(trans):
        return trans[index]
    if isinstance(trans, int) and trans == index:
        return 0
    return 255


def load_pages(original_pixels, original_dir: Path, edited_dir: Path):
    pages = []
    for file_number in range(1, 17):
        # Photoshop 目录顺序实际旋转了 7 页：1→p09, ..., 16→p08。
        palette_number = (file_number + 8) % 16
        original_path = original_dir / f"F1079.BIN[0]_p{palette_number:02}.png"
        edited_path = edited_dir / f"{file_number}.png"
        if not original_path.is_file() or not edited_path.is_file():
            raise FileNotFoundError(f"缺图：{original_path} 或 {edited_path}")

        with Image.open(original_path) as image:
            if image.mode != "P" or image.size != (256, 256):
                raise ValueError(f"原预览格式异常：{original_path}")
            exported_pixels = image.tobytes()
            original_rgba = list(image.convert("RGBA").getdata())
            palette = image.getpalette()
            info = image.info.copy()

        # 旧导出器会重排部分页面色号；从原图和 TIM 的位置关系恢复映射。
        export_to_tim = {}
        for exported_index in range(16):
            votes = Counter(
                original_pixels[pos]
                for pos, value in enumerate(exported_pixels)
                if value == exported_index
            )
            if not votes:
                raise ValueError(f"p{palette_number:02} 未使用色号 {exported_index}")
            export_to_tim[exported_index] = votes.most_common(1)[0][0]
        if len(set(export_to_tim.values())) != 16:
            raise ValueError(f"p{palette_number:02} 色号映射不是排列")
        tim_to_export = {value: key for key, value in export_to_tim.items()}

        colors = []
        for tim_index in range(16):
            exported_index = tim_to_export[tim_index]
            rgb = tuple(palette[exported_index * 3:exported_index * 3 + 3])
            colors.append(rgb + (alpha_for(info, exported_index),))

        with Image.open(edited_path) as image:
            if image.size != (256, 256):
                raise ValueError(f"编辑图尺寸异常：{edited_path} = {image.size}")
            target_rgba = list(image.convert("RGBA").getdata())

        # Photoshop 可以重排自己的 PNG palette，但颜色必须仍来自对应原页。
        allowed_colors = set(colors)
        unknown = set(target_rgba) - allowed_colors
        if unknown:
            raise ValueError(
                f"{edited_path} 有 {len(unknown)} 个不属于原 CLUT 的颜色：{list(unknown)[:3]}"
            )
        pages.append({
            "number": palette_number,
            "original_path": original_path,
            "edited_path": edited_path,
            "original_rgba": original_rgba,
            "target_rgba": target_rgba,
            "colors": colors,
            "tim_to_export": tim_to_export,
        })
    return pages


def merge(current_pixels, original_pixels, pages):
    merged = current_pixels[:]
    touched = []
    for pos in range(256 * 256):
        if not any(p["original_rgba"][pos] != p["target_rgba"][pos] for p in pages):
            continue
        touched.append(pos)
        costs = []
        for tim_index in range(16):
            cost = 0
            for page in pages:
                actual = page["colors"][tim_index]
                target = page["target_rgba"][pos]
                cost += sum((actual[channel] - target[channel]) ** 2 for channel in range(4))
            costs.append(cost)
        best = min(costs)
        winners = [index for index, cost in enumerate(costs) if cost == best]
        merged[pos] = current_pixels[pos] if current_pixels[pos] in winners else winners[0]
    return merged, touched


def save_preview(page, pixels, output: Path):
    with Image.open(page["original_path"]) as image:
        result = image.copy()
        result.putdata([page["tim_to_export"][value] for value in pixels])
        result.save(output, bits=4)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages", type=Path, default=DEFAULT_PAGES)
    parser.add_argument("--original-pngs", type=Path, default=DEFAULT_ORIGINAL_PNGS)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--iso", type=Path, default=DEFAULT_ISO)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--apply", action="store_true", help="写入工作游戏 BIN 并修 ECC")
    parser.add_argument("--overwrite-backup", action="store_true")
    args = parser.parse_args()

    original_tim = args.source.read_bytes()
    original_pixels, original_offset = unpack_pixels(original_tim)
    current_tim = bytes(read_sectors(args.iso, LBA, F1079_SIZE))
    current_pixels, current_offset = unpack_pixels(current_tim)
    if current_offset != original_offset:
        raise ValueError("工作盘 F1079 与原版结构不一致")

    pages = load_pages(original_pixels, args.original_pngs, args.pages)
    merged, touched = merge(current_pixels, original_pixels, pages)
    result = bytearray(current_tim)
    result[current_offset:current_offset + 32768] = pack_pixels(merged)
    parse_f1079(result)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    merged_path = args.out_dir / "F1079.merged.BIN"
    merged_path.write_bytes(result)
    report = {
        "page_order": {f"{i}.png": f"p{(i + 8) % 16:02}" for i in range(1, 17)},
        "target_touched_positions": len(touched),
        "changed_pixels_vs_current": sum(a != b for a, b in zip(current_pixels, merged)),
        "pages": {},
    }
    for page in pages:
        number = page["number"]
        preview = args.out_dir / f"preview_p{number:02}.png"
        save_preview(page, merged, preview)
        mismatches = sum(
            page["colors"][merged[pos]] != page["target_rgba"][pos]
            for pos in touched
        )
        report["pages"][f"p{number:02}"] = {
            "different_target_pixels_in_touched_area": mismatches,
            "touched_area_pixels": len(touched),
        }
    (args.out_dir / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"合并完成：{merged_path}")
    print(f"目标涉及 {len(touched)} 像素，实际修改 {report['changed_pixels_vs_current']} 像素")
    print(f"预览和报告：{args.out_dir}")

    if args.apply:
        backup = args.out_dir / "F1079.before_apply.BIN"
        if backup.exists() and not args.overwrite_backup:
            raise FileExistsError(f"备份已存在：{backup}（可加 --overwrite-backup）")
        backup.write_bytes(current_tim)
        write_sectors(args.iso, LBA, result)
        last = LBA + (F1079_SIZE + BLOCK_SIZE - 1) // BLOCK_SIZE - 1
        fix_iso_ecc(args.iso, LBA, last)
        verify = bytes(read_sectors(args.iso, LBA, F1079_SIZE))
        if verify != result:
            raise RuntimeError("工作盘写后校验失败")
        print(f"已写入工作盘 LBA {LBA}-{last}，ECC/EDC 已修复")
        print(f"写入前备份：{backup}")


if __name__ == "__main__":
    main()
