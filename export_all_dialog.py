import json, os, re

# 加载码表
raw_table = json.load(open('codetable.json', encoding='utf-8'))
table = {int(k): v for k, v in raw_table.items()}

def decode_items(items):
    """把对话item列表解码成纯文本，去掉控制命令"""
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
            if cmd == 1:
                if current_page:
                    pages.append(''.join(current_page))
                    current_page = []
            elif cmd in (2, 3, 6):
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

entries = []

for fname in files:
    d = json.load(open(f'{script_dir}/{fname}', encoding='utf-8'))
    file_id = d.get('file', '?')
    sub_id  = d.get('file_num', '?')
    order   = d.get('dialog_order', sorted(d.get('dialogs', {}).keys()))
    dialogs = d.get('dialogs', {})

    for diag_name in order:
        items = dialogs.get(diag_name)
        if not items:
            continue
        text = decode_items(items)
        if not text:
            continue

        entries.append({
            "id": f'{file_id}_{sub_id}:{diag_name}',
            "jp": text,
            "zh": ""
        })

with open('all_dialog.json', 'w', encoding='utf-8') as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

print(f'导出完成：{len(entries)} 条对话 → all_dialog.json')
