"""把 partials_strtbl/ 里的 strtbl 翻译合并回 ../all_translatable.json。

跑完 translate_strtbl.py 后跑这个：
  python3 merge_strtbl.py
  python3 merge_strtbl.py --include-review   # 也合 needs_review（不推荐）
  python3 merge_strtbl.py --dry-run
"""

import argparse
import json
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT = SCRIPT_DIR.parent
SOURCE = ROOT / "all_translatable.json"
PARTIALS_DIR = SCRIPT_DIR / "partials_strtbl"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--include-review", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

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

    print(f"收集到 {len(by_id)} 条 strtbl 翻译")
    print(f"  含 needs_review: {review_count} 条 ({'合' if args.include_review else '跳过'})")

    if not args.dry_run:
        bak = SOURCE.with_suffix(f".json.bak.strtbl_{time.strftime('%Y%m%d_%H%M%S')}")
        bak.write_bytes(SOURCE.read_bytes())
        print(f"备份原文件 → {bak.name}")

    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    merged = 0
    for e in data:
        if e["id"] not in by_id:
            continue
        tr = by_id[e["id"]]
        zh = tr.get("zh", "")
        if not zh:
            continue
        if not e.get("pages"):
            e["pages"] = [{"jp": "", "zh": ""}]
        if not e["pages"][0].get("zh", "").strip():   # 只填空缺
            e["pages"][0]["zh"] = zh
            merged += 1

    print(f"\n合并结果：✓ {merged} 条 strtbl zh 填充")
    if not args.dry_run:
        SOURCE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"已写回 {SOURCE.name}")
    else:
        print("(dry-run，未写入)")


if __name__ == "__main__":
    main()
