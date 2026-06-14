#!/usr/bin/env python3
"""修复所有 meta_jp=うらら 但 meta_zh 误为鼻血子的条目"""
import json, sys

ROOT = '.'
APPLY = 'apply' in sys.argv

with open('all_translatable.json', encoding='utf-8') as f:
    data = json.load(f)

count = 0
for item in data:
    if item.get('meta_jp') == 'うらら' and '鼻血子' in item.get('meta_zh', ''):
        item['meta_zh'] = '丽'
        count += 1
        print(f"修正: {item['id']}  meta_zh: 鼻血子 → 丽")

if APPLY:
    with open('all_translatable.json', 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    print(f'已落盘，修正 {count} 处。')
else:
    print(f'DRY-RUN 发现 {count} 处需要修正，加 apply 参数落盘。')