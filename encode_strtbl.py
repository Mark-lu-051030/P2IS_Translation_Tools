"""
把 all_translatable.json 里的 strtbl 翻译编码成 items 格式，生成 out/strtbl_zh/。
跟 encode_zh.py 类似，但处理 strtbl 而不是 script。

每个 strtbl entry 是个 string list（fixed-byte 区，max_len 限制）。

用法: python3 encode_strtbl.py
"""
import json, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 复用 encode_zh.py 的字符码映射 + tag 解析
from encode_zh import rev, tag_to_item, encode_page

SRC_DIR = 'out/string_table'
DST_DIR = 'out/strtbl_zh'
os.makedirs(DST_DIR, exist_ok=True)

# 加载翻译
data = json.load(open('all_translatable.json', encoding='utf-8'))
# trans_map: "file_sub_table:str_idx" → zh
trans_map = {}
for entry in data:
    if not entry['id'].startswith('strtbl:'):
        continue
    pages = entry.get('pages', [])
    if not pages:
        continue
    zh = pages[0].get('zh', '').strip()
    if not zh:
        continue
    # 检查所有字符都在 codetable，没有就跳过（避免缺字渲染问题，类似 encode_zh fallback）
    cleaned = re.sub(r'<[^>]+/?>', '', zh)
    if any(c != '\n' and c not in rev for c in cleaned):
        continue
    rest = entry['id'][len('strtbl:'):]
    trans_map[rest] = zh

print(f'有翻译的 strtbl 条目: {len(trans_map)}')

updated_files = 0
total_translated = 0

for fname in sorted(os.listdir(SRC_DIR)):
    if not fname.endswith('.json'): continue
    src = json.load(open(f'{SRC_DIR}/{fname}', encoding='utf-8'))
    file_id = src['file']
    sub_id  = src['file_num']
    # 文件名: {file}_{sub}_{table}.json  或  SLUS_{sub}_{table}.json (file 0 = SLPS)
    # ⚠ file_id/sub_id 用 src json 里的（可靠）；只 table_idx 靠文件名解析。
    #   SLUS 前缀必须匹配，否则 table_idx fallback=0 → 翻译张冠李戴（角色名表写成菜单词）。
    m = re.match(r'^(?:\d+|SLUS)_(\d+)_(\d+)\.json$', fname)
    if not m:
        print(f'  ⚠ 文件名无法解析 table_idx: {fname}，跳过')
        continue
    table_idx = int(m.group(2))

    changed = False
    new_strings = []
    for idx, orig_items in enumerate(src['strings']):
        key = f'{file_id}_{sub_id}_{table_idx}:{idx}'
        if key in trans_map:
            zh = trans_map[key]
            # 编码 zh 文本成 items（复用 encode_page，包含 tag 解析）
            new_items = encode_page(zh)
            # 末尾加 [1] (CMD_NEWLINE) + [3] (CMD_RET) — 跟原版每个 string 一致
            new_items.append([1])
            new_items.append([3])
            new_strings.append(new_items)
            total_translated += 1
            changed = True
        else:
            # 没翻译，保留原 items
            new_strings.append(orig_items)

    if changed:
        out = dict(src)
        out['strings'] = new_strings
        with open(f'{DST_DIR}/{fname}', 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        updated_files += 1

print(f'已写入 {updated_files} 个文件到 {DST_DIR}/')
print(f'编码了 {total_translated} 条 strtbl')
