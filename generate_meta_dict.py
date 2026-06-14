import json
import os
from collections import defaultdict, Counter

def main():
    file_path = os.path.join(os.path.dirname(__file__), 'all_translatable.json')
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 记录 日文 -> 中文 的所有对应关系及其出现次数
    jp_to_zh_counts = defaultdict(Counter)

    for entry in data:
        jp = entry.get('meta_jp')
        zh = entry.get('meta_zh')
        
        if jp and zh:
            jp_to_zh_counts[jp][zh] += 1

    result_dict = {}
    for jp in sorted(jp_to_zh_counts.keys()):
        # 自动选出出现次数最多的中文翻译作为默认值
        best_zh = jp_to_zh_counts[jp].most_common(1)[0][0]
        result_dict[jp] = best_zh

    out_path = os.path.join(os.path.dirname(__file__), 'meta_dict.json')
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=4)
    print(f"✅ 提取完毕！已生成 {out_path}，快去编辑它吧。")

if __name__ == '__main__':
    main()
