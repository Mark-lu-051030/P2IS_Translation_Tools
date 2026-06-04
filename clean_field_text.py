"""清洗 out/field_text.json：过滤垃圾 + 按唯一 jp 统计翻译工作量。
- 垃圾过滤：剥标签后无 CJK/假名、或长度<2、或单字符重复占比>50%（如「「「噪音）
- 唯一 jp 去重：同一 jp 文本只需翻一次（如 64-67 重复装备说明），保留所有出现位置供回插
输出 out/field_text_clean.json（保留 entry + 唯一 jp 统计）。
"""
import json, re
from collections import Counter

d = json.load(open("out/field_text.json", encoding="utf-8"))
strip = lambda s: re.sub(r"<[^>]*>", "", s or "").replace("\\n", "").replace("\n", "").replace("　", "").strip()
def is_cjk_kana(c): return ("぀" <= c <= "ヿ") or ("一" <= c <= "鿿") or ("＀" <= c <= "￯")

def is_garbage(jp):
    s = strip(jp)
    if len(s) < 2: return True
    if not any(is_cjk_kana(c) for c in s): return True          # 无日文 → 符号/拉丁噪音
    top = Counter(s).most_common(1)[0][1]
    if len(s) > 4 and top / len(s) > 0.5: return True            # 单字符重复噪音(「「「)
    return False

kept, garbage = [], 0
for e in d:
    if is_garbage(e["jp"]): garbage += 1
    else: kept.append(e)

# 唯一 jp（翻译单元）
uniq = {}
for e in kept:
    uniq.setdefault(e["jp"], []).append(e["id"])

json.dump(kept, open("out/field_text_clean.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

# 单一翻译文件：所有唯一 jp 汇总到一处（同 jp 只翻一次），翻译器读这个
to_translate = [{"id": f"u{i}", "jp": jp, "zh": "", "count": len(ids)}
                for i, (jp, ids) in enumerate(uniq.items())]
json.dump(to_translate, open("out/field_to_translate.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

print(f"原始 {len(d)} 条 → 过滤垃圾 {garbage} → 保留 {len(kept)} 条")
print(f"唯一 jp（实际要翻的条数）: {len(uniq)} → 已汇总到 out/field_to_translate.json")
dup = len(kept) - len(uniq)
print(f"重复出现（翻一次用多处）: {dup}")
# 按文件分布（保留后）
c = Counter(e["id"].split(":")[1].split("_")[0] for e in kept)
print("保留后文件分布(top20):", dict(sorted(c.items(), key=lambda x: -x[1])[:20]))
# 估算字符量
chars = sum(len(strip(j)) for j in uniq)
print(f"唯一 jp 总字符数: {chars}（粗估翻译规模）")
