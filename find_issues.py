#!/usr/bin/env python3
"""找出所有 标签不符 / 缺字 / 太长 的条目，输出到 out/fix_list.json"""
import json, re, os

ROOT = '.'
CODETABLE_PATH = 'codetable.json'

# 加载字库
ct = json.load(open(CODETABLE_PATH, encoding='utf-8'))
valid_chars = set()
for v in ct.values():
    if isinstance(v, str) and len(v) == 1:
        valid_chars.add(v)
# 也加上等价字
if os.path.exists('jp_cn_equiv.json'):
    eq = json.load(open('jp_cn_equiv.json', encoding='utf-8'))
    for k, v in eq.items():
        valid_chars.add(k)
        valid_chars.add(v)

issues = {'tag_mismatch': [], 'missing_char': [], 'too_long': []}

def check_entry(entry_id, jp, zh):
    if not zh or not zh.strip():
        return
    
    # 1. 检查缺字
    for ch in re.sub(r'<[^>]+>', '', zh):
        if '\u4e00' <= ch <= '\u9fff' or '\u3040' <= ch <= '\u30ff':
            if ch not in valid_chars:
                issues['missing_char'].append({'id': entry_id, 'char': ch, 'jp': jp[:60], 'zh': zh[:60]})
                return  # 缺字优先报
    
    # 2. 检查标签不符（简化：原文和译文的控制码数量是否匹配）
    jp_tags = re.findall(r'<[^>]+>', jp)
    zh_tags = re.findall(r'<[^>]+>', zh)
    if len(jp_tags) != len(zh_tags):
        issues['tag_mismatch'].append({'id': entry_id, 'jp_tags': jp_tags, 'zh_tags': zh_tags, 'jp': jp[:60], 'zh': zh[:60]})
        return
    
    # 3. 太长检查（粗略估计：中文全角字占2字节，控制码按实际长度）
    # 这里只能估，实际判断在 apply 阶段做；我们把所有 zh 都列出来，让人工判断
    if len(zh) > len(jp) * 1.5:  # 中文字节数通常是日文1.5倍以上
        issues['too_long'].append({'id': entry_id, 'jp_len': len(jp), 'zh_len': len(zh), 'jp': jp[:60], 'zh': zh[:60]})

# 扫描 all_translatable.json
at_path = 'all_translatable.json'
if os.path.exists(at_path):
    data = json.load(open(at_path, encoding='utf-8'))
    for item in data:
        for i, p in enumerate(item.get('pages', [])):
            check_entry(item['id'], p.get('jp', ''), p.get('zh', ''))

# 扫描 field_text_zh.json
ft_path = os.path.join('out', 'field_text_zh.json')
if os.path.exists(ft_path):
    data = json.load(open(ft_path, encoding='utf-8'))
    for item in data:
        check_entry(item.get('id', '?'), item.get('jp', ''), item.get('zh', ''))

# 保存
with open(os.path.join('out', 'fix_list.json'), 'w', encoding='utf-8') as f:
    json.dump(issues, f, ensure_ascii=False, indent=2)

print(f"标签不符: {len(issues['tag_mismatch'])} 条")
print(f"缺字: {len(issues['missing_char'])} 条")
print(f"可能太长: {len(issues['too_long'])} 条")
print(f"详细结果: out/fix_list.json")