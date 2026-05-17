"""
查找所有包含待定字符 [?N] 的对话，按索引分组显示上下文。
用法:
  python3 unknown_in_context.py          # 所有待定字符
  python3 unknown_in_context.py 523      # 只看 [?523]
"""
import json, os, re, sys

raw_table = json.load(open('codetable.json', encoding='utf-8'))
table = {int(k): v for k, v in raw_table.items()}

def decode_items(items):
    if not isinstance(items, list):
        return None
    text_started = False
    current_page = []
    pages = []
    for x in items:
        if isinstance(x, list) and x[0] == 29:
            if len(x) >= 2 and x[1] == 1:
                text_started = True
            continue
        if not text_started:
            continue
        if isinstance(x, list):
            cmd = x[0]
            if cmd in (1, 2, 3, 6):
                if current_page:
                    pages.append(''.join(current_page))
                    current_page = []
        elif isinstance(x, int):
            ch = table.get(x)
            current_page.append(ch if ch else f'[?{x}]')
    if current_page:
        pages.append(''.join(current_page))
    result = '\n'.join(p for p in pages if p.strip())
    return result if result.strip() else None

script_dir = 'out/scripts'
files = sorted(os.listdir(script_dir),
               key=lambda f: [int(x) for x in re.findall(r'\d+', f)])

# target: None = all unknowns, int = specific index
target = int(sys.argv[1]) if len(sys.argv) > 1 else None

# unknown_idx -> [(dialog_id, decoded_text), ...]
hits = {}

for fname in files:
    d = json.load(open(f'{script_dir}/{fname}', encoding='utf-8'))
    file_id = d.get('file', '?')
    sub_id  = d.get('file_num', '?')
    dialogs = d.get('dialogs', {})
    order   = d.get('dialog_order', sorted(dialogs.keys()))

    for diag_name in order:
        items = dialogs.get(diag_name)
        if not items:
            continue
        text = decode_items(items)
        if not text:
            continue

        unknowns = set(int(m) for m in re.findall(r'\[\?(\d+)\]', text))
        if not unknowns:
            continue
        if target is not None and target not in unknowns:
            continue

        dialog_id = f'{file_id}_{sub_id}:{diag_name}'
        for idx in unknowns:
            if target is None or idx == target:
                hits.setdefault(idx, []).append((dialog_id, text))

if not hits:
    print('没有找到待定字符出现在对话中')
else:
    for idx in sorted(hits):
        entries = hits[idx]
        print(f'\n{"="*60}')
        print(f'[?{idx}]  共出现在 {len(entries)} 条对话中')
        print('='*60)
        for dialog_id, text in entries[:10]:  # 最多显示10条
            print(f'\n  [{dialog_id}]')
            for line in text.splitlines():
                print(f'    {line}')
        if len(entries) > 10:
            print(f'\n  ... 还有 {len(entries)-10} 条省略')
