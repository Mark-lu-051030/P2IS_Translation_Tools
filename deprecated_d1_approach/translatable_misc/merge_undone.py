"""把人工翻好的 undone.json 合并回 ../all_translatable.json。

用法：
  python3 merge_undone.py --dry-run    # 看会合多少
  python3 merge_undone.py              # 真合（会自动备份）

只会填空缺（zh / meta_zh 已有内容的条目不会被覆盖）。
"""
import argparse
import json
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT = SCRIPT_DIR.parent
SOURCE = ROOT / "all_translatable.json"
UNDONE = SCRIPT_DIR / "undone.json"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    undone = json.loads(UNDONE.read_text(encoding="utf-8"))
    undone_by_id = {e["id"]: e for e in undone}
    print(f"undone.json 里 {len(undone_by_id)} 条")

    if not args.dry_run:
        bak = SOURCE.with_suffix(f".json.bak.undone_{time.strftime('%Y%m%d_%H%M%S')}")
        bak.write_bytes(SOURCE.read_bytes())
        print(f"备份原文件 → {bak.name}")

    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    merged_pages = 0
    merged_meta = 0
    skipped = []

    for e in data:
        if e["id"] not in undone_by_id:
            continue
        u = undone_by_id[e["id"]]

        # meta_zh
        if u.get("meta_zh", "").strip() and not e.get("meta_zh", "").strip():
            e["meta_zh"] = u["meta_zh"]
            merged_meta += 1

        # pages zh
        u_pages = u.get("pages", [])
        if len(u_pages) != len(e.get("pages", [])):
            skipped.append(f"{e['id']} (pages 数量不匹配 jp={len(e['pages'])} undone={len(u_pages)})")
            continue
        for i, up in enumerate(u_pages):
            u_zh = up.get("zh", "").strip()
            e_zh = e["pages"][i].get("zh", "").strip()
            if u_zh and not e_zh:
                e["pages"][i]["zh"] = up["zh"]
                merged_pages += 1

    print(f"\n合并结果:")
    print(f"  ✓ pages 填充: {merged_pages}")
    print(f"  ✓ meta 填充: {merged_meta}")
    if skipped:
        print(f"  ⚠ 跳过 (pages 数量不匹配): {len(skipped)}")
        for s in skipped[:5]:
            print(f"    - {s}")

    if args.dry_run:
        print("\n[--dry-run] 未实际写入。")
        return

    SOURCE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n已写回 {SOURCE.name}")


if __name__ == "__main__":
    main()
