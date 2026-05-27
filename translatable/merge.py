"""把 partials/ 里的翻译合并回 ../all_translatable.json。

跑完 translate.py 后跑这个：
  python3 merge.py             # 只合干净的 translations
  python3 merge.py --include-review  # 也合 needs_review 里的（不推荐）
"""

import argparse
import json
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT = SCRIPT_DIR.parent
SOURCE = ROOT / "all_translatable.json"
PARTIALS_DIR = SCRIPT_DIR / "partials"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-review", action="store_true",
                    help="也合 needs_review 的条目（默认跳过）")
    ap.add_argument("--dry-run", action="store_true",
                    help="只打印要合什么，不实际写入")
    args = ap.parse_args()

    # 1. 收集所有 partial 翻译
    by_id = {}
    review_count = 0
    for f in sorted(PARTIALS_DIR.glob("*.json")):
        batch = json.loads(f.read_text(encoding="utf-8"))
        for t in batch.get("translations", []):
            by_id[t["id"]] = t
        for t in batch.get("needs_review", []):
            review_count += 1
            if args.include_review:
                by_id[t["id"]] = t

    print(f"收集到 {len(by_id)} 条翻译")
    print(f"  含 needs_review: {review_count} 条 ({'合' if args.include_review else '跳过'})")

    # 2. 备份原文件
    if not args.dry_run:
        import time
        bak = SOURCE.with_suffix(f".json.bak.merge_{time.strftime('%Y%m%d_%H%M%S')}")
        bak.write_bytes(SOURCE.read_bytes())
        print(f"备份原文件 → {bak.name}")

    # 3. 合并
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    merged_pages = 0
    merged_meta = 0
    skipped = []

    for e in data:
        if e["id"] not in by_id:
            continue
        tr = by_id[e["id"]]

        # meta_zh
        if "meta_zh" in tr and tr["meta_zh"]:
            if not e.get("meta_zh", "").strip():  # 只填空缺
                e["meta_zh"] = tr["meta_zh"]
                merged_meta += 1

        # pages_zh
        pages_zh = tr.get("pages_zh", [])
        if len(pages_zh) != len(e.get("pages", [])):
            skipped.append(f"{e['id']} (pages 数不匹配 jp={len(e.get('pages', []))} zh={len(pages_zh)})")
            continue
        for i, zh in enumerate(pages_zh):
            if not e["pages"][i].get("zh", "").strip():  # 只填空缺
                e["pages"][i]["zh"] = zh
                merged_pages += 1

    print(f"\n合并结果：")
    print(f"  ✓ pages 填充: {merged_pages}")
    print(f"  ✓ meta 填充: {merged_meta}")
    if skipped:
        print(f"  ⚠ 跳过 (pages 不匹配): {len(skipped)}")
        for s in skipped[:5]:
            print(f"    - {s}")
        if len(skipped) > 5:
            print(f"    ... 还有 {len(skipped)-5} 条")

    if args.dry_run:
        print("\n[--dry-run] 未实际写入。")
        return

    # 4. 写回
    SOURCE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n已写回 {SOURCE.name}")


if __name__ == "__main__":
    main()
