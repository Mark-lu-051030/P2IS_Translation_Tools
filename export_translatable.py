"""
统一提取所有可翻译文本，保留控制符为 tag 格式。
输出: all_translatable.json
格式:
  [{"id": "script:181_8:diag1", "pages": [{"jp": "...", "zh": ""}, ...]}, ...]
"""
import json, os, re

# 渲染 JP 必须用 codetable_og.json（原始日文映射）
# codetable.json 含字体注入后的中文覆盖，用它渲染 JP 会把日文 slot 误显示成中文
raw_table = json.load(open('codetable_og.json', encoding='utf-8'))
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

def _items_to_text(items):
    """把 items 直接渲染成一段文本（不分页），保留控制符 tag 和 char 字典查找。"""
    out = []
    for x in items:
        if isinstance(x, list):
            cmd = x[0]
            if cmd == NEWLINE:
                out.append('\n')
            elif cmd == END:
                break
            else:
                out.append(cmd_to_tag(x))
        elif isinstance(x, int):
            out.append(table.get(x, f'[?{x}]'))
        elif isinstance(x, str):
            out.append(x)
    return ''.join(out)


def split_meta_body(items):
    """把 diag items 拆成 (meta_items, body_items)。

    META 段 = 从开头到 [29, 1] 之前（[29, 1] 是 "切换到对话本体" 的分隔符）。
    body = [29, 1] 之后所有内容。
    某些 diag（如角色介绍）没有 [29, 1]，整段都是 META，body = []。
    返回的 meta_items 已剥离开头的 [29, X] 控制码（保留纯文本/字符）。
    """
    sep_idx = None
    for i, x in enumerate(items):
        if isinstance(x, list) and len(x) >= 2 and x[0] == 29 and x[1] == 1:
            sep_idx = i
            break
    if sep_idx is None:
        meta_items, body_items = list(items), []
    else:
        meta_items, body_items = items[:sep_idx], items[sep_idx+1:]
    # 剥离 META 头部的 [29, X]（"open box / set portrait" 控制码，不属于翻译内容）
    if meta_items and isinstance(meta_items[0], list) and meta_items[0][0] == 29:
        meta_items = meta_items[1:]
    return meta_items, body_items


def items_to_pages(items, has_meta=True):
    """把 items 列表转成 page 字符串列表，保留控制符为 tag。
    仅处理对话 body 段（has_meta=True 时跳过 META；strtbl/battle 整段都是 body）。"""
    if has_meta:
        _, items = split_meta_body(items)

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


def items_to_meta_text(items):
    """从 diag items 提取 META 段文本（说话人名 / 角色介绍 / 标题等）。"""
    meta_items, _ = split_meta_body(items)
    if not meta_items:
        return ''
    return _items_to_text(meta_items).strip()


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
        meta_jp = items_to_meta_text(items)
        pages   = items_to_pages(items, has_meta=True)
        if not pages and not meta_jp:
            continue
        entry = {
            'id':    f'script:{file_id}_{sub_id}:{diag_name}',
            'pages': [{'jp': p, 'zh': ''} for p in pages],
        }
        # 仅当 META 段含真实文本（不止控制码）时才加 meta 字段
        if meta_jp:
            entry['meta_jp'] = meta_jp
            entry['meta_zh'] = ''
        entries.append(entry)

# ── string_table ─────────────────────────────────────────
# 注意：文件名格式 {file}_{sub}_{table_idx}.json，同一 file/sub 下有多个 table。
# 必须把 table_idx 编进 ID，否则 strtbl:138_0:0 会出现 3 次（来自 138_0_0, 138_0_1, 138_0_2）。
st_dir = 'out/string_table'
for fname in sorted(os.listdir(st_dir), key=sort_key):
    d       = json.load(open(f'{st_dir}/{fname}', encoding='utf-8'))
    file_id = d.get('file', '?')
    sub_id  = d.get('file_num', '?')
    table_idx = fname.replace('.json', '').split('_')[-1]
    strings = d.get('strings', [])

    for idx, items in enumerate(strings):
        if not isinstance(items, list):
            continue
        pages = items_to_pages(items, has_meta=False)
        if not pages:
            continue
        entries.append({
            'id':    f'strtbl:{file_id}_{sub_id}_{table_idx}:{idx}',
            'pages': [{'jp': p, 'zh': ''} for p in pages],
        })

# ── battle ───────────────────────────────────────────────
# 同 strtbl：文件名第 3 个数是 table_idx，避免 ID 冲突
bt_dir = 'out/battle'
for fname in sorted(os.listdir(bt_dir), key=sort_key):
    d       = json.load(open(f'{bt_dir}/{fname}', encoding='utf-8'))
    file_id = d.get('file', '?')
    sub_id  = d.get('file_num', '?')
    table_idx = fname.replace('.json', '').split('_')[-1]
    strings = d.get('strings', [])

    for idx, items in enumerate(strings):
        if not isinstance(items, list):
            continue
        pages = items_to_pages(items, has_meta=False)
        if not pages:
            continue
        entries.append({
            'id':    f'battle:{file_id}_{sub_id}_{table_idx}:{idx}',
            'pages': [{'jp': p, 'zh': ''} for p in pages],
        })

# 合并已有翻译（保留 zh / meta_zh 字段）
# 两阶段匹配：先按 (id, i) 精确匹配；不中再按 jp 内容唯一匹配（修过 ID 之后用）
if os.path.exists('all_translatable.json'):
    old_data = json.load(open('all_translatable.json', encoding='utf-8'))
    old_by_id = {}        # (id, i) → page zh
    old_by_jp = {}        # jp_text → zh
    old_meta_by_id = {}   # id → meta_zh
    old_meta_by_jp = {}   # meta_jp → meta_zh
    jp_zh_pairs = {}
    meta_pairs  = {}
    for e in old_data:
        for i, p in enumerate(e.get('pages', [])):
            zh = p.get('zh', '').strip()
            if zh:
                old_by_id[(e['id'], i)] = zh
                jp_zh_pairs.setdefault(p.get('jp', ''), set()).add(zh)
        m_zh = (e.get('meta_zh') or '').strip()
        if m_zh:
            old_meta_by_id[e['id']] = m_zh
            meta_pairs.setdefault(e.get('meta_jp', ''), set()).add(m_zh)
    for jp, zhs in jp_zh_pairs.items():
        if len(zhs) == 1: old_by_jp[jp] = next(iter(zhs))
    for jp, zhs in meta_pairs.items():
        if len(zhs) == 1: old_meta_by_jp[jp] = next(iter(zhs))

    by_id_hits, by_jp_hits = 0, 0
    meta_id_hits, meta_jp_hits = 0, 0
    for e in entries:
        for i, p in enumerate(e.get('pages', [])):
            key = (e['id'], i)
            if key in old_by_id:
                p['zh'] = old_by_id[key]; by_id_hits += 1
            elif p.get('jp', '') in old_by_jp:
                p['zh'] = old_by_jp[p['jp']]; by_jp_hits += 1
        if 'meta_jp' in e:
            if e['id'] in old_meta_by_id:
                e['meta_zh'] = old_meta_by_id[e['id']]; meta_id_hits += 1
            elif e['meta_jp'] in old_meta_by_jp:
                e['meta_zh'] = old_meta_by_jp[e['meta_jp']]; meta_jp_hits += 1
    print(f'合并 pages: {by_id_hits} 条按 ID + {by_jp_hits} 条按 jp 内容回退')
    print(f'合并 meta:  {meta_id_hits} 条按 ID + {meta_jp_hits} 条按 jp 内容回退')

with open('all_translatable.json', 'w', encoding='utf-8') as f:
    json.dump(entries, f, ensure_ascii=False, indent=2)

print(f'提取完成: {len(entries)} 条 → all_translatable.json')
src = {}
for e in entries:
    s = e['id'].split(':')[0]
    src[s] = src.get(s, 0) + 1
for s, n in src.items():
    print(f'  {s}: {n} 条')
