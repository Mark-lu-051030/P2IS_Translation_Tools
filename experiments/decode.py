# decode_v3.py
# Dialog character index N -> codetable key N (keys now start from 0)
import json, sys

raw_table = json.load(open('codetable.json', encoding='utf-8'))
table = {int(k): v for k, v in raw_table.items()}

def fmt_meta(items):
    """元数据区,保留原始数字便于查阅"""
    return '[META:' + ','.join(str(x) if isinstance(x, int) else f'C{x[0]}' for x in items) + ']'

def fmt_text(items):
    """实际文本区"""
    out = []
    for x in items:
        if isinstance(x, list):
            out.append(f'<C{x[0]}>' if len(x) == 1 else f'<C{x[0]}:{",".join(map(str, x[1:]))}>')
        elif isinstance(x, int):
            out.append(table[x] if x in table and table[x] else f'[?{x}]')
    return ''.join(out)

def decode(items):
    # 找 <C29:11> ... <C29:1> 这段元数据
    if items and isinstance(items[0], list) and items[0][0] == 29:
        # 找到 <C29:1> 结束位置
        end = next((i for i in range(1, len(items)) 
                   if isinstance(items[i], list) and items[i][0] == 29 and (len(items[i]) == 1 or items[i][1] == 1)), 
                   None)
        if end:
            meta = items[1:end]
            text = items[end+1:]
            return fmt_meta(meta) + '\n' + fmt_text(text)
    return fmt_text(items)

data = json.load(open(sys.argv[1], encoding='utf-8'))
print(f'=== File {data.get("file","?")} Sub {data.get("file_num","?")} ===')
for name in sorted(data.get('dialogs', {})):
    diag = data['dialogs'][name]
    if diag:
        print(f'\n--- {name} ---')
        print(decode(diag))