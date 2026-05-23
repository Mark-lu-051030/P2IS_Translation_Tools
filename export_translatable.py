"""
统一提取所有可翻译文本，保留控制符为 tag 格式。
输出: all_translatable.json
格式:
  [{"id": "script:181_8:diag1", "pages": [{"jp": "...", "zh": ""}, ...]}, ...]
"""
import json, os, re

raw_table = json.load(open('codetable.json', encoding='utf-8'))
table = {int(k): v for k, v in raw_table.items()}

# 控制符 → tag 名
CMD_TAG = {
    0x05: 'pause',
    0x07: 'unk7',
    0x08: 'option',
    0x09: 'option_end',
    0x0e: 'keyitem',
    0x20: 'SURNAME',
    0x21: 'NAME',
    0x2e: 'col',
    0x35: 'item',
    0x36: 'text',
}
PAGE_BREAK = {2, 6}   # cmd_end_page, cmd_wait
NEWLINE    = 1
END        = 3

def cmd_to_tag(x):
    cmd  = x[0]
    args = x[1:]
    name = CMD_TAG.get(cmd, f'c{cmd:02x}')
    if args:
        return f'<{name}:{",".join(map(str, args))}/>'
    return f'<{name}/>'

def items_to_pages(items, has_meta=True):
    """把 items 列表转成 page 字符串列表，保留控制符为 tag。"""
    if has_meta:
        # 跳过 META 段: [29,11]...[29,1]
        text_started = False
        start = 0
        for i, x in enumerate(items):
            if isinstance(x, list) and x[0] == 29:
                if len(x) >= 2 and x[1] == 1:
                    text_started = True
                    start = i + 1
                    break
        if not text_started:
            return []
        items = items[start:]

    current = []
    pages   = []

    for x in items:
        if isinstance(x, list):
            cmd = x[0]
            if cmd == END:
                break
            elif cmd in PAGE_BREAK:
                if current:
                    pages.append(''.join(current))
                    current = []
            elif cmd == NEWLINE:
                current.append('\n')
            else:
                current.append(cmd_to_tag(x))
        elif isinstance(x, int):
            current.append(table.get(x, f'[?{x}]'))
        elif isinstance(x, str):
            current.append(x)

    if current:
        pages.append(''.join(current))

    return [p for p in pages if p.strip()]


def sort_key(fname):
    return [int(x) for x in re.findall(r'\d+', fname)]


entries = []

# ── scripts ──────────────────────────────────────────────
script_dir = 'out/scripts'
for fname in sorted(os.listdir(script_dir), key=sort_key):
    d       = json.load(open(f'{script_dir}/{fname}', encoding='utf-8'))
    file_id = d.get('file', '?')
    sub_id  = d.get('file_num', '?')
    order   = d.get('dialog_order', sorted(d.get('dialogs', {}).keys()))
    dialogs = d.get('dialogs', {})

    for diag_name in order:
        items = dialogs.get(diag_name)
        if not isinstance(items, list):
            continue
        pages = items_to_pages(items, has_meta=True)
        if not pages:
            continue
        entries.append({
            'id':    f'script:{file_id}_{sub_id}:{diag_name}',
            'pages': [{'jp': p, 'zh': ''} for p in pages],
        })

# ── string_table ─────────────────────────────────────────
st_dir = 'out/string_table'
for fname in sorted(os.listdir(st_dir), key=sort_key):
    d       = json.load(open(f'{st_dir}/{fname}', encoding='utf-8'))
    file_id = d.get('file', '?')
    sub_id  = d.get('file_num', '?')
    strings = d.get('strings', [])

    for idx, items in enumerate(strings):
        if not isinstance(items, list):
            continue
        pages = items_to_pages(items, has_meta=False)
        if not pages:
            continue
        entries.append({
            'id':    f'strtbl:{file_id}_{sub_id}:{idx}',
            'pages': [{'jp': p, 'zh': ''} for p in pages],
        })

# ── battle ───────────────────────────────────────────────
bt_dir = 'out/battle'
for fname in sorted(os.listdir(bt_dir), key=sort_key):
    d       = json.load(open(f'{bt_dir}/{fname}', encoding='utf-8'))
    file_id = d.get('file', '?')
    sub_id  = d.get('file_num', '?')
    strings = d.get('strings', [])

    for idx, items in enumerate(strings):
        if not isinstance(items, list):
            continue
        pages = items_to_pages(items, has_meta=False)
        if not pages:
            continue
        entries.append({
            'id':    f'battle:{file_id}_{sub_id}:{idx}',
            'pages': [{'jp': p, 'zh': ''} for p in pages],
        })

# 合并已有翻译（保留 zh 字段）
if os.path.exists('all_translatable.json'):
    old_data = json.load(open('all_translatable.json', encoding='utf-8'))
    old_zh = {}
    for e in old_data:
        for i, p in enumerate(e.get('pages', [])):
            if p.get('zh', '').strip():
                old_zh[(e['id'], i)] = p['zh']
    for e in entries:
        for i, p in enumerate(e.get('pages', [])):
            key = (e['id'], i)
            if key in old_zh:
                p['zh'] = old_zh[key]
    print(f'合并了 {len(old_zh)} 条已有翻译')

with open('all_translatable.json', 'w', encoding='utf-8') as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

print(f'提取完成: {len(entries)} 条 → all_translatable.json')
src = {}
for e in entries:
    s = e['id'].split(':')[0]
    src[s] = src.get(s, 0) + 1
for s, n in src.items():
    print(f'  {s}: {n} 条')
