"""检查 undone.json 里翻译的质量：
  1. 控制码守恒（数量+种类）
  2. 换行符 \\n 数量
  3. 空字段检测

用法:
  python3 check_undone.py                     # 报告所有问题
  python3 check_undone.py --strict-order      # 控制码顺序也要严格相同
  python3 check_undone.py --export bad.json   # 把有问题的导出
"""
import argparse
import json
import re
from pathlib import Path
from collections import Counter

UNDONE = Path(__file__).parent / "undone1.json"
TAG_RE = re.compile(r"<[^>]+>")


def check_text_pair(jp, zh, strict_order=False):
    """检查 jp 和 zh 的控制码、换行守恒，返回 list of issues。"""
    issues = []
    jp_tags = TAG_RE.findall(jp)
    zh_tags = TAG_RE.findall(zh)

    # 控制码：数量+种类
    if Counter(jp_tags) != Counter(zh_tags):
        # 找出差异
        jp_set = Counter(jp_tags)
        zh_set = Counter(zh_tags)
        only_jp = jp_set - zh_set
        only_zh = zh_set - jp_set
        if only_jp:
            issues.append(f"zh 缺: {dict(only_jp)}")
        if only_zh:
            issues.append(f"zh 多: {dict(only_zh)}")

    # 控制码：顺序（严格模式）
    if strict_order and jp_tags != zh_tags:
        issues.append(f"控制码顺序不同")

    # 换行
    jp_nl = jp.count("\n")
    zh_nl = zh.count("\n")
    if jp_nl != zh_nl:
        issues.append(f"换行: jp={jp_nl}, zh={zh_nl}")

    # 标签后空白：如果 zh 里两个 tag 紧挨着（中间无文字）但 jp 那里有文字
    # 例：jp 是 "<SURNAME/>思ってたけど<pause:10/>"，
    #     zh 变成 "<SURNAME/><pause:10/>" → SURNAME 旁边没桥接文字，渲染时突兀
    jp_adj_pairs = _adjacent_tag_pairs(jp)
    zh_adj_pairs = _adjacent_tag_pairs(zh)
    new_adjacencies = zh_adj_pairs - jp_adj_pairs
    if new_adjacencies:
        for t1, t2 in list(new_adjacencies)[:3]:
            issues.append(f"zh 出现紧挨的标签 {t1}{t2}（jp 这里有文字）")

    return issues


def _adjacent_tag_pairs(text):
    """找出所有"紧挨着"（中间只有空格/\\n）的相邻 tag 对，返回 set of (tag1, tag2)。"""
    pairs = set()
    # 用 re.split 分段：会得到 [文本, 标签, 文本, 标签, ...]
    parts = re.split(r"(<[^>]+>)", text)
    prev_tag = None
    for i, p in enumerate(parts):
        if i % 2 == 1:  # 标签
            if prev_tag is not None:
                pairs.add((prev_tag, p))
            prev_tag = p
        else:  # 文本段
            # 只有空白/换行就算 "紧挨"
            if p.strip():
                prev_tag = None  # 中间有实际文字，断开
    return pairs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict-order", action="store_true",
                    help="控制码顺序也要严格相同")
    ap.add_argument("--export", help="把有问题的条目导出到该文件")
    ap.add_argument("--quiet", "-q", action="store_true",
                    help="只显示统计，不列出每条")
    args = ap.parse_args()

    data = json.loads(UNDONE.read_text(encoding="utf-8"))

    bad_entries = []
    empty_meta = 0
    empty_pages = 0
    page_count_mismatch = 0
    issues_by_type = Counter()

    for e in data:
        entry_issues = []

        # meta 检查
        meta_jp = e.get("meta_jp", "")
        meta_zh = e.get("meta_zh", "")
        if meta_jp.strip() and not meta_zh.strip():
            entry_issues.append("meta_zh 空")
            empty_meta += 1
            issues_by_type["meta_zh 空"] += 1
        elif meta_jp.strip() and meta_zh.strip():
            for iss in check_text_pair(meta_jp, meta_zh, args.strict_order):
                entry_issues.append(f"meta: {iss}")
                issues_by_type[f"meta {iss.split(':')[0]}"] += 1

        # pages 检查
        pages = e.get("pages", [])
        for i, p in enumerate(pages):
            jp = p.get("jp", "")
            zh = p.get("zh", "")
            if jp.strip() and not zh.strip():
                entry_issues.append(f"page{i} zh 空")
                empty_pages += 1
                issues_by_type["page zh 空"] += 1
            elif jp.strip() and zh.strip():
                for iss in check_text_pair(jp, zh, args.strict_order):
                    entry_issues.append(f"page{i}: {iss}")
                    issues_by_type[f"page {iss.split(':')[0]}"] += 1

        if entry_issues:
            bad_entries.append({
                "id": e["id"],
                "meta_jp": meta_jp,
                "meta_zh": meta_zh,
                "issues": entry_issues,
            })

    print(f"扫描 {len(data)} 条 entry")
    print(f"  ⚠ 有问题: {len(bad_entries)}")
    print(f"  ✓ 完全 OK: {len(data) - len(bad_entries)}")
    print()
    print("问题分类:")
    for k, n in issues_by_type.most_common():
        print(f"  {n:4d}: {k}")

    if not args.quiet and bad_entries:
        print(f"\n前 20 条问题详情:")
        for b in bad_entries[:20]:
            print(f"\n  {b['id']}  meta_jp={b['meta_jp']!r:30s}")
            for iss in b["issues"]:
                print(f"    - {iss}")
        if len(bad_entries) > 20:
            print(f"\n  ... 还有 {len(bad_entries)-20} 条")

    if args.export:
        out_path = Path(args.export)
        out_path.write_text(
            json.dumps(bad_entries, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\n问题条目已导出 → {out_path.name}")


if __name__ == "__main__":
    main()
