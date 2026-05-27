"""手动把 undone.json 里所有缺失的 meta_zh 翻好。

策略：只有 54 个 unique meta_jp（覆盖 194 条 entry），手填一份映射表批处理。
名字用「百度百科/wiki」规范（黑须淳、舞耶、雪野、莉莎…）。

用法:
  python3 manual_translation.py --dry-run    # 看会填多少 + 列出未覆盖的
  python3 manual_translation.py              # 真填写
"""
import argparse
import json
from pathlib import Path

UNDONE = Path(__file__).parent / "undone.json"

# meta_jp → meta_zh 翻译表（统一用百度百科规范）
META_TRANSLATIONS = {
    # ── 主要角色 ──────────────────────────────────────
    "リサ":                 "莉莎",
    "ギンコ":               "银子",       # 丽莎绰号 Ginko
    "ゆきの":               "雪野",       # 雪野（不是雪乃）
    "淳":                  "淳",         # 黑须淳
    "栄吉<SURNAME/>ギンコ":  "荣吉<SURNAME/>银子",
    "シャドウ栄吉":          "影子荣吉",
    "栄吉の声":             "荣吉的声音",

    # ── 重要 NPC / 反派 ──────────────────────────────
    "フィレモン":           "费列蒙",     # Philemon
    "ベラドンナ":           "贝拉冬娜",   # Belladonna（蓝色房间歌姬）
    "イゴール":             "伊格尔",     # Igor
    "ナナシ":               "无名氏",     # Nanashi = "无名"
    "エリー":               "艾莉",
    "黒須<SURNAME/>純子":   "黑须<SURNAME/>纯子",

    # ── 传闻屋系列（P2 标志性 NPC）─────────────────
    "噂屋珠閒瑠ジプシー":    "传闻屋 珠閒瑠吉普赛",
    "噂屋チカリン":          "传闻屋 千咔铃",
    "噂屋トロ":              "传闻屋 托罗",
    "噂屋トクさん":          "传闻屋 阿德",

    # ── 一般 NPC（路人）─────────────────────────────
    "太った男":             "胖男人",
    "やる気のないボーイ":    "没干劲的男生",
    "店員":                 "店员",
    "寿司貴族":             "寿司贵族",
    "レリーフ":             "浮雕",
    "トニー":               "托尼",
    "香さん":               "阿香",
    "おばちゃん":           "阿姨",
    "PTAのおばさん":        "PTA 大妈",
    "若い男":               "年轻男人",
    "あんちゃん":           "大哥",
    "ブラウン":             "布朗",
    "秘密の箱":             "秘密之箱",
    "本丸公園":             "本丸公园",
    "暇な大学生":           "闲着的大学生",
    "おじいさん":           "老爷爷",
    "仮面党員":             "假面党员",
    "ちい坊":               "小坊",
    "初老の画家":           "中年画家",
    "テイラー":             "泰勒",
    "若い女":               "年轻女人",
    "たまきちゃん":         "玉树酱",
    "サチコ":               "幸子",
    "カズヤ":               "一也",
    "マヌカン":             "模特",
    "オバサン・長女":       "阿姨·长女",
    "飄々とした男":         "飘逸的男人",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    data = json.loads(UNDONE.read_text(encoding="utf-8"))

    filled = 0
    skipped_unknown = []
    for e in data:
        meta_jp = e.get("meta_jp", "").strip()
        if not meta_jp:
            continue
        if e.get("meta_zh", "").strip():
            continue
        if meta_jp in META_TRANSLATIONS:
            if not args.dry_run:
                e["meta_zh"] = META_TRANSLATIONS[meta_jp]
            filled += 1
        else:
            skipped_unknown.append((e["id"], meta_jp))

    print(f"已填充 meta_zh: {filled} 条")
    if skipped_unknown:
        print(f"\n未覆盖的 meta_jp（脚本里需要补 mapping）: {len(skipped_unknown)} 条")
        seen = set()
        for eid, m in skipped_unknown:
            if m not in seen:
                seen.add(m)
                print(f"  {m!r}  (例: {eid})")

    if not args.dry_run:
        UNDONE.write_text(
            json.dumps(data, ensure_ascii=False, indent=4),
            encoding="utf-8",
        )
        print(f"\n已写回 {UNDONE.name}")


if __name__ == "__main__":
    main()
