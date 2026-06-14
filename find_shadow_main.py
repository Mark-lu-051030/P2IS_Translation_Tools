#!/usr/bin/env python3
"""终极搜索：列出所有日文原文中提到‘克哉’的句子，并显示对应的中文翻译。"""
import json, os

ROOT = '.'
files = {
    'all_translatable': 'all_translatable.json',
    'field': 'out/field_text_zh.json'
}

for kind, path in files.items():
    if not os.path.exists(path):
        continue
    data = json.load(open(path, encoding='utf-8'))
    if kind == 'all_translatable':
        for item in data:
            for p in item.get('pages', []):
                jp = p.get('jp', '')
                zh = p.get('zh', '')
                if '克哉' in jp:  # 只在日文里搜
                    print(f'[{item["id"]}]')
                    print(f'  JP: {jp[:200]}')
                    print(f'  ZH: {zh[:200]}')
                    print()
    else:
        for item in data:
            jp = item.get('jp', '')
            zh = item.get('zh', '')
            if '克哉' in jp:
                print(f'[{item["id"]}]')
                print(f'  JP: {jp[:200]}')
                print(f'  ZH: {zh[:200]}')
                print()