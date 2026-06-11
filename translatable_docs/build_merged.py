#!/usr/bin/env python3
# 把本目录(translatable_docs)里所有「成品」可翻译文档合并成一个文件,
# 每条 {src, id, speaker_jp, speaker_zh, jp, zh}。
#   src        = 出处分类(script/strtbl/field_text/config/contactui/names/nametable/mainmenu/savemenu/map_names/room_names)
#   id         = 原始精确定位(如 script:3_0:diag0、field:1:0x58380、config:0x25c);多页条目加 :p0/:p1
#   speaker_*  = 说话人(来自 all_translatable 的 meta_jp/meta_zh,只有剧情对话有;其余留空)
# 不去重(重复保留)。字段文本只取成品 field_text_zh,不放 field_text/clean/to_translate。jp_cn_equiv 不并入。
# 用法: cd translatable_docs && python3 build_merged.py
import json, os
from collections import defaultdict

os.chdir(os.path.dirname(os.path.abspath(__file__)))
def load(f): return json.load(open(f, encoding='utf-8'))

records = []        # {src, id, speaker_jp, speaker_zh, jp, zh}
stats = defaultdict(int)

def add(jp, zh, sp_jp, sp_zh, src, rid):
    if jp is None or zh is None: return
    if not str(jp).strip() or not str(zh).strip(): return
    records.append({'src': src, 'id': rid, 'speaker_jp': (sp_jp or '').strip(),
                    'speaker_zh': (sp_zh or '').strip(), 'jp': jp, 'zh': zh})
    stats[src] += 1

# 1) 主翻译文件。id=原始 e['id'](多页加 :p{i});src 按前缀分 script/strtbl;meta_* = 说话人
for e in load('all_translatable.json'):
    src = e['id'].split(':')[0]               # 'script' 或 'strtbl'
    sj = e.get('meta_jp') or ''               # 说话人日文(条目级)
    sz = e.get('meta_zh') or ''               # 说话人中文
    pages = e.get('pages', [])
    for i, p in enumerate(pages):
        rid = e['id'] if len(pages) == 1 else f"{e['id']}:p{i}"
        add(p.get('jp'), p.get('zh'), sj, sz, src, rid)

# 2) 字段文本:只取成品 field_text_zh。id 形如 field:1:0x58380。无说话人
for e in load('out/field_text_zh.json'):
    add(e.get('jp'), e.get('zh'), '', '', 'field_text', e.get('id'))

# 3) 游离区 UI/菜单(list 形式,有 off)。id=f"{src}:0x{off:x}"。无说话人
for f, src in [('out/config_zh.json','config'), ('out/contactui_zh.json','contactui'),
               ('out/names_zh.json','names'), ('out/nametable_zh.json','nametable')]:
    for e in load(f):
        add(e.get('jp'), e.get('zh'), '', '', src, f"{src}:0x{e.get('off',0):x}")

# 4) mainmenu/savemenu(_zh 版,strings[] 含 idx+jp+zh)。id=f"{src}:#{idx}"。无说话人
for f, src in [('out/mainmenu_zh.json','mainmenu'), ('out/savemenu_zh.json','savemenu')]:
    for e in load(f).get('strings', []):
        add(e.get('jp'), e.get('zh'), '', '', src, f"{src}:#{e.get('idx')}")

# 5) 地图名/房间名审定表(dict {jp:zh},跳过 _ 注释键)。id=f"{src}:{jp}"。无说话人
for f, src in [('map_names_zh.json','map_names'), ('room_names_zh.json','room_names')]:
    for jp, zh in load(f).items():
        if jp.startswith('_'): continue
        add(jp, zh, '', '', src, f"{src}:{jp}")

# ── 报告(不去重,全保留) ──
print('各来源贡献:')
for s, n in sorted(stats.items(), key=lambda x: -x[1]):
    print(f'  {s:16} {n}')
print(f'\n总条数(不去重) : {len(records)}')
dup = len(records) - len({(r['id'], r['jp'], r['zh']) for r in records})
with_sp = sum(1 for r in records if r['speaker_zh'] or r['speaker_jp'])
print(f'  其中 id+jp+zh 完全相同: {dup}  ← 按你要求保留')
print(f'带说话人的条目(剧情对话): {with_sp}')

json.dump(records, open('merged_jp_zh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'\n→ 已写 merged_jp_zh.json  ({len(records)} 条 {{src, id, speaker_jp, speaker_zh, jp, zh}})')
