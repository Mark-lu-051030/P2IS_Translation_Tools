import json
import os
from collections import defaultdict

def main():
    file_path = os.path.join(os.path.dirname(__file__), 'all_translatable.json')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 记录 日文 -> 中文 的所有对应关系
    jp_to_zh = defaultdict(set)
    # 记录 中文 -> 日文 的所有对应关系
    zh_to_jp = defaultdict(set)
    
    # 记录某个翻译对出现在哪些 ID 中，方便你回去定位
    occurrences = defaultdict(list)

    for entry in data:
        jp = entry.get('meta_jp')
        zh = entry.get('meta_zh')
        
        if jp is not None and zh is not None:
            jp_to_zh[jp].add(zh)
            zh_to_jp[zh].add(jp)
            occurrences[(jp, zh)].append(entry.get('id', '?'))

    print("=== 一个日文名对应多个中文名的角色 (可能是翻译不统一) ===")
    for jp, zh_set in jp_to_zh.items():
        if len(zh_set) > 1:
            print(f"\n[日文] {jp}")
            for zh in zh_set:
                print(f"  -> [中文] {zh} (共出现 {len(occurrences[(jp, zh)])} 次)")
                
    print("\n\n=== 一个中文名对应多个日文名的角色 (可能是把不同人翻成了同一个) ===")
    for zh, jp_set in zh_to_jp.items():
        if len(jp_set) > 1:
            print(f"\n[中文] {zh}")
            for jp in jp_set:
                print(f"  <- [日文] {jp} (共出现 {len(occurrences[(jp, zh)])} 次)")

if __name__ == '__main__':
    main()