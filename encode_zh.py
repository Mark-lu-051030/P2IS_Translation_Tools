"""
把 all_translatable.json 里的 zh 翻译编码回 script items 格式，
生成更新后的脚本 JSON 到 out/scripts_zh/，供 insert_script.mjs 使用。

用法: python3 encode_zh.py
"""
import json, os, re, shutil

# ── 反向码表: 字符 → 字体索引 ─────────────────────────────────
raw_ct = json.load(open('codetable.json', encoding='utf-8'))
# 只取单字符映射，跳过待定条目
rev = {}
for k, v in raw_ct.items():
    if len(v) == 1 and not v.startswith('['):
        rev[v] = int(k)

# ── 标签解析: tag 字符串 → items 子列表 ──────────────────────
TAG_SIMPLE = {
    'NAME':    [0x21],
    'SURNAME': [0x20],
    'unk7':    [0x07],
    'option_end': [0x09],
    'text':    [0x36],
}
TAG_WITH_ARG = {
    'pause':   0x05,
    'col':     0x2e,
    'option':  0x08,
    'keyitem': 0x0e,
    'item':    0x35,
}

def tag_to_item(tag_str):
    """'<NAME/>' → [0x21],  '<pause:30/>' → [0x05, 30]"""
    inner = tag_str.strip('<>/')
    if ':' in inner:
        name, args_s = inner.split(':', 1)
        args = [int(a) for a in args_s.split(',')]
    else:
        name, args = inner, []

    if name in TAG_SIMPLE:
        return TAG_SIMPLE[name]
    # 处理 c<hex> 格式，如 c1d → cmd=0x1d
    if name.startswith('c') and re.fullmatch(r'c[0-9a-f]+', name):
        cmd = int(name[1:], 16)
        return [cmd] + args
    if name in TAG_WITH_ARG:
        return [TAG_WITH_ARG[name]] + args
    print(f'  未知 tag: {tag_str}')
    return None

def encode_page(zh_text):
    """把一个 page 的 zh 字符串编码成 items 列表（不含结尾命令）。"""
    items = []
    tokens = re.split(r'(<[^>]+/?>)', zh_text)
    for tok in tokens:
        if not tok:
            continue
        if tok.startswith('<'):
            item = tag_to_item(tok)
            if item is not None:
                items.append(item)
        else:
            for ch in tok:
                if ch == '\n':
                    items.append([1])   # CMD_NEWLINE
                elif ch in rev:
                    items.append(rev[ch])
                else:
                    print(f'  找不到字符: {repr(ch)}')
    return items

def get_meta(orig_items):
    """从原始 items 里提取 META 段（包含结尾的 [29,1]），返回 meta_list。"""
    meta = []
    if not orig_items or not (isinstance(orig_items[0], list) and orig_items[0][0] == 29):
        return []
    for i, x in enumerate(orig_items):
        meta.append(x)
        if isinstance(x, list) and x[0] == 29 and (len(x) == 1 or x[1] == 1):
            return meta
    return meta

# ── 加载翻译 ──────────────────────────────────────────────────
trans_data = json.load(open('all_translatable.json', encoding='utf-8'))
# 只处理 script 类型、有 zh 内容的
trans_map = {}  # "file_file_num:diag_name" → [zh_page, ...]
for entry in trans_data:
    if not entry['id'].startswith('script:'):
        continue
    pages = [p['zh'] for p in entry['pages'] if p.get('zh', '').strip()]
    if not pages:
        continue
    # id 格式: script:3_3:diag0
    rest = entry['id'][len('script:'):]
    trans_map[rest] = pages

print(f'有翻译的对话: {len(trans_map)} 条')

# ── 处理脚本文件 ──────────────────────────────────────────────
src_dir = 'out/scripts'
dst_dir = 'out/scripts_zh'
os.makedirs(dst_dir, exist_ok=True)

updated_files = set()

for fname in sorted(os.listdir(src_dir)):
    script = json.load(open(f'{src_dir}/{fname}', encoding='utf-8'))
    file_id = script.get('file', '?')
    sub_id  = script.get('file_num', '?')
    dialogs = script.get('dialogs', {})
    changed = False

    for diag_name, orig_items in dialogs.items():
        key = f'{file_id}_{sub_id}:{diag_name}'
        if key not in trans_map:
            continue
        zh_pages = trans_map[key]

        meta = get_meta(orig_items or [])
        new_items = list(meta)

        for page_text in zh_pages:
            new_items += encode_page(page_text)
            new_items.append([6])       # CMD_WAIT（等待按键）
            new_items.append([2])       # CMD_END_PAGE

        new_items.append([3])           # CMD_RET
        script['dialogs'][diag_name] = new_items
        changed = True
        print(f'  编码: {key}')

    if changed:
        out_path = f'{dst_dir}/{fname}'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(script, f, ensure_ascii=False, indent=4)
        updated_files.add(fname.replace('.json', ''))

print(f'\n已写入 {len(updated_files)} 个文件到 out/scripts_zh/')
print('运行插入命令:')
for name in sorted(updated_files):
    print(f'  node p2ep_tool.mjs insert_script out/scripts_zh/{name}.json')
