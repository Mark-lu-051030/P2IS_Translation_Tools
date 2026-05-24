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

# 全角标点 → 复用已有半角/日文槽位
FULLWIDTH_ALIASES = {
    '！': '!', '？': '?', '…': '.',
    '，': '、', '。': '。',
    '：': ':', '；': ';',
    '（': '(', '）': ')',
    '　': ' ',   # 全角空格
}
for fw, hw in FULLWIDTH_ALIASES.items():
    if hw in rev and fw not in rev:
        rev[fw] = rev[hw]

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


def get_meta_parts(orig_items):
    """把 META 段拆成 (open_ctrl, body_items, close_ctrl, tail_items)。
    open_ctrl  = 开头的 [29, X]（保持原 portrait/box-type 不变）
    body_items = META 文本内容（chars + 内部控制码）
    close_ctrl = 结尾的 [29, 1]（如果有）或 None
    tail_items = close_ctrl 之后到 [3] 之前的所有 items（含可能的 [1]/[6]/[2]），用于纯 META diag
    """
    if not orig_items or not (isinstance(orig_items[0], list) and orig_items[0][0] == 29):
        return None, [], None, []
    open_ctrl = orig_items[0]
    end_idx = None
    for i in range(1, len(orig_items)):
        x = orig_items[i]
        if isinstance(x, list) and len(x) >= 2 and x[0] == 29 and x[1] == 1:
            end_idx = i
            break
    if end_idx is None:
        return open_ctrl, list(orig_items[1:]), None, []
    # tail: close_ctrl 之后到结尾的 [3] 之前
    tail = []
    for x in orig_items[end_idx + 1:]:
        if isinstance(x, list) and len(x) >= 1 and x[0] == 3:
            break
        tail.append(x)
    return open_ctrl, list(orig_items[1:end_idx]), orig_items[end_idx], tail


def encode_meta(meta_zh):
    """把 meta_zh 文本编码成 items（chars + tags），不含两端的 [29, X] 控制码。"""
    # 复用 encode_page 但不要它的结尾 wait/end_page 处理
    items = []
    tokens = re.split(r'(<[^>]+/?>)', meta_zh)
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
                    items.append([1])
                elif ch in rev:
                    items.append(rev[ch])
                else:
                    print(f'  meta 找不到字符: {repr(ch)}')
    return items

# ── 加载翻译 ──────────────────────────────────────────────────
trans_data = json.load(open('all_translatable.json', encoding='utf-8'))
# trans_map: "file_sub:diag" → {pages: [...], meta_zh: str or None}
trans_map = {}
for entry in trans_data:
    if not entry['id'].startswith('script:'):
        continue
    pages = [p['zh'] for p in entry['pages'] if p.get('zh', '').strip()]
    meta_zh = (entry.get('meta_zh') or '').strip()
    if not pages and not meta_zh:
        continue
    rest = entry['id'][len('script:'):]
    trans_map[rest] = {'pages': pages, 'meta_zh': meta_zh}

n_pages = sum(1 for v in trans_map.values() if v['pages'])
n_meta  = sum(1 for v in trans_map.values() if v['meta_zh'])
print(f'有翻译的对话: {len(trans_map)} 条（含 body: {n_pages}，含 meta: {n_meta}）')

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
        if not isinstance(orig_items, list):
            print(f'  跳过 {key}: 原 items 不是 list')
            continue
        tr = trans_map[key]
        zh_pages = tr['pages']
        meta_zh  = tr['meta_zh']

        # 解析原 META 四段：open_ctrl + body + close_ctrl + tail（close/tail 可能为空）
        open_ctrl, orig_meta_body, close_ctrl, meta_tail = get_meta_parts(orig_items)

        new_items = []
        if open_ctrl is not None:
            new_items.append(open_ctrl)
            # META body：有 meta_zh 就用译文，没有就保留原日文 chars
            new_items += encode_meta(meta_zh) if meta_zh else orig_meta_body
            if close_ctrl is not None:
                new_items.append(close_ctrl)

        # 对话本体
        if zh_pages:
            for page_text in zh_pages:
                new_items += encode_page(page_text)
                new_items.append([6])       # CMD_WAIT
                new_items.append([2])       # CMD_END_PAGE
        elif open_ctrl is not None and meta_tail:
            # 纯 META（角色介绍类）：没有 body pages，保留原始 tail（含 [6] CMD_WAIT 等）
            new_items += meta_tail

        new_items.append([3])           # CMD_RET
        script['dialogs'][diag_name] = new_items
        changed = True
        tags = []
        if meta_zh: tags.append('+meta')
        if zh_pages: tags.append(f'+{len(zh_pages)}p')
        print(f'  编码: {key} ({" ".join(tags)})')

    if changed:
        out_path = f'{dst_dir}/{fname}'
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(script, f, ensure_ascii=False, indent=4)
        updated_files.add(fname.replace('.json', ''))

print(f'\n已写入 {len(updated_files)} 个文件到 out/scripts_zh/')
print('运行插入命令:')
for name in sorted(updated_files):
    print(f'  node p2ep_tool.mjs insert_script out/scripts_zh/{name}.json')
