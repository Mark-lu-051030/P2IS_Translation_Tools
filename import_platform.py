#!/usr/bin/env python3
# 把翻译平台导出的校对稿回填到各源 _zh 文件。
# 平台格式: [{"id": "script:190_8:diag49", "jp": "...", "translation": "..."}, ...]
#   (translation 也接受 zh 键名; id 即 translatable_docs/build_merged.py 导出的 id,
#    多页条目带 :pN 后缀 → 精确写回 all_translatable 对应 page,不存在"一个id多句怎么融"的歧义)
# 路由(按 id 前缀):
#   script:/strtbl:[...][:pN] → all_translatable.json pages[N].zh
#   field:...                 → out/field_text_zh.json (id 精确匹配)
#   config/contactui/names/nametable:0xOFF → 对应 out/*_zh.json (off 匹配)
#   mainmenu/savemenu:#IDX    → out/*_zh.json strings[].idx
#   map_names/room_names:JP   → *_zh.json dict[jp]
# 校验:
#   ① jp 必须与源 jp 一致(防止平台改过原文/对错位置;尾部空白宽松)
#   ② 译文里的 <...> 标签必须是原文标签的子集(乱标签会炸 encodeText/控制码流)
#   ③ 原位等长类(field/map_names/room_names)译文可见字数 ≤ 原文 → 超长跳过并列出(写了也会被 apply 跳过,白翻)
#      freetbl 类(config 等)整窗重排,超长只警告不跳过(build 时 freetbl 会兜底报溢出)
# 用法: python3 import_platform.py 下载的文件.json          (干跑,只出报告)
#       python3 import_platform.py 下载的文件.json --apply  (写回,先备份 *.bak)
import glob as _glob
import json, re, shutil, sys, os
from collections import defaultdict

os.chdir(os.path.dirname(os.path.abspath(__file__)))
ARGS = [a for a in sys.argv[1:] if not a.startswith('--')]
APPLY = '--apply' in sys.argv
if not ARGS:
    sys.exit("用法: python3 import_platform.py <导出1.json> [导出2.json ... | 目录] [--apply]")

# 多文件/目录支持: 目录取其中全部 *.json;同一 id 多文件给出不同译文 → 后者覆盖前者并计入"文件间冲突"
srcs = []
for a in ARGS:
    if os.path.isdir(a):
        srcs += sorted(_glob.glob(os.path.join(a, '*.json')))
    else:
        srcs.append(a)
recs, seen_tr = [], {}          # seen_tr: id → (translation, 来源文件)
conflicts = []
for sf in srcs:
    d = json.load(open(sf, encoding='utf-8'))
    if isinstance(d, dict): d = d.get('items') or d.get('data') or []
    n_conf = 0
    for r in d:
        rid = r.get('id') or ''
        tr = r.get('translation') if r.get('translation') is not None else r.get('zh')
        if rid in seen_tr and seen_tr[rid][0] != tr:
            n_conf += 1
            if len(conflicts) < 10:
                conflicts.append(f"{rid}: [{seen_tr[rid][1]}]≠[{os.path.basename(sf)}] 取后者")
        seen_tr[rid] = (tr, os.path.basename(sf))
        recs.append(r)
    print(f"  + {sf}: {len(d)} 条" + (f" (与前面文件冲突 {n_conf} 条,取本文件)" if n_conf else ''))
# 同 id 去重: 保留最后一次出现(后传入的文件视为更新)
recs = list({(r.get('id') or '') + '\x00' + (r.get('jp') or ''): r for r in recs}.values())
if conflicts:
    print("  ▸ 文件间冲突示例:")
    for c in conflicts: print(f"      {c}")
print(f"平台导出合计: {len(recs)} 条(去重后)  模式: {'写回' if APPLY else '干跑(加 --apply 才写)'}\n")

def load(f): return json.load(open(f, encoding='utf-8'))
TARGETS = {  # 懒加载缓存: 路径 → (数据, 是否被改)
}
def get(path):
    if path not in TARGETS: TARGETS[path] = [load(path), False]
    return TARGETS[path][0]
def touched(path): TARGETS[path][1] = True

# ── 索引 ──
at = get('all_translatable.json')
at_idx = {e['id']: e for e in at}
ft = get('out/field_text_zh.json')
ft_idx = {e['id']: e for e in ft}
off_idx = {}
for src, path in [('config','out/config_zh.json'), ('contactui','out/contactui_zh.json'),
                  ('names','out/names_zh.json'), ('nametable','out/nametable_zh.json')]:
    off_idx[src] = (path, {e['off']: e for e in get(path)})
menu_idx = {}
for src, path in [('mainmenu','out/mainmenu_zh.json'), ('savemenu','out/savemenu_zh.json')]:
    menu_idx[src] = (path, {e['idx']: e for e in get(path)['strings']})
DICT_FILES = {'map_names': 'map_names_zh.json', 'room_names': 'room_names_zh.json'}

TAG = re.compile(r'<[^<>]*>')
strip = lambda s: TAG.sub('', s or '')
def tags_ok(jp, zh):           # 译文标签 ⊆ 原文标签(允许删,不允许造)
    have = defaultdict(int)
    for t in TAG.findall(jp or ''): have[t] += 1
    for t in TAG.findall(zh or ''):
        have[t] -= 1
        if have[t] < 0: return False
    return True
jp_eq = lambda a, b: (a or '') == (b or '') or (a or '').strip() == (b or '').strip()

stats = defaultdict(int)
problems = defaultdict(list)   # 类别 → [示例行]
def prob(kind, rid, detail=''):
    stats[kind] += 1
    if len(problems[kind]) < 15: problems[kind].append(f"{rid}  {detail}")

def put(obj, key, path, rid, jp_src, zh_new, len_strict=False):
    """通用写入: jp 校验→标签校验→(可选)长度校验→比对旧值→写"""
    if not jp_eq(jp_src, r_jp):
        prob('jp不匹配', rid, f"源[{(jp_src or '')[:25]!r}] 平台[{(r_jp or '')[:25]!r}]"); return
    if not tags_ok(jp_src, zh_new):
        prob('标签非法(译文有原文没有的标签)', rid, zh_new[:40]); return
    # 换行检查(告警不拦截): 游戏不自动换行,一行约24全角字,超出画到框外。
    # jp 多行而译文无 \n、或译文有超长单行 → 提醒人工检查
    jp_nl = (jp_src or '').count('\\n') + (jp_src or '').count('\n')
    zh_nl = zh_new.count('\\n') + zh_new.count('\n')
    if jp_nl >= 1 and zh_nl == 0:
        prob('⚠告警:jp有换行而译文无\\n(已写入,检查是否画出框外)', rid, strip(zh_new)[:30])
    elif max((len(strip(l)) for l in re.split(r'\\\\n|\n', zh_new)), default=0) > 24:
        prob('⚠告警:译文存在超24字单行(已写入,可能画出框外)', rid, strip(zh_new)[:30])
    if len_strict and len(strip(zh_new)) > len(strip(jp_src)):
        prob('超长跳过(原位等长类,写了也白翻)', rid,
             f"{len(strip(zh_new))}>{len(strip(jp_src))} {strip(zh_new)[:30]}"); return
    old = obj[key] if not isinstance(obj, dict) or key in obj else None
    if old == zh_new: stats['相同未动'] += 1; return
    if APPLY: obj[key] = zh_new; touched(path)
    stats['更新'] += 1

for r in recs:
    rid = r.get('id') or ''
    r_jp = r.get('jp')
    zh = r.get('translation') if r.get('translation') is not None else r.get('zh')
    if not rid or zh is None: prob('缺id或译文', rid or '<空>'); continue
    zh = str(zh)

    if rid.startswith(('script:', 'strtbl:')):
        m = re.search(r':p(\d+)$', rid)
        base, pi = (rid[:m.start()], int(m.group(1))) if m else (rid, 0)
        e = at_idx.get(base)
        if not e or pi >= len(e.get('pages', [])):
            prob('未知id', rid); continue
        # 无 :pN 后缀但源是多页 → 导出时必带后缀,说明 id 被平台截断/改动
        if not m and len(e['pages']) > 1:
            prob('多页条目缺:pN后缀', rid, f"源有{len(e['pages'])}页,无法定位"); continue
        put(e['pages'][pi], 'zh', 'all_translatable.json', rid, e['pages'][pi].get('jp'), zh)
    elif rid.startswith('field:'):
        e = ft_idx.get(rid)
        if not e: prob('未知id', rid); continue
        put(e, 'zh', 'out/field_text_zh.json', rid, e.get('jp'), zh, len_strict=True)
    elif rid.split(':')[0] in off_idx:
        src = rid.split(':')[0]
        path, idx = off_idx[src]
        try: off = int(rid.split(':0x')[1], 16)
        except (IndexError, ValueError): prob('id格式错', rid); continue
        e = idx.get(off)
        if not e: prob('未知id', rid); continue
        if len(strip(zh)) > len(strip(e.get('jp') or '')):
            prob('freetbl超长(警告,整窗重排或许能装)', rid, strip(zh)[:30])
        put(e, 'zh', path, rid, e.get('jp'), zh)
    elif rid.split(':')[0] in menu_idx:
        src = rid.split(':')[0]
        path, idx = menu_idx[src]
        try: i = int(rid.split('#')[1])
        except (IndexError, ValueError): prob('id格式错', rid); continue
        e = idx.get(i)
        if not e: prob('未知id', rid); continue
        put(e, 'zh', path, rid, e.get('jp'), zh)
    elif rid.split(':')[0] in DICT_FILES:
        src = rid.split(':')[0]
        path = DICT_FILES[src]
        jp_key = rid[len(src) + 1:]
        d = get(path)
        if jp_key not in d: prob('未知id', rid); continue
        put(d, jp_key, path, rid, jp_key, zh, len_strict=True)
    else:
        prob('未知id前缀', rid)

# ── 写盘 ──
if APPLY:
    for path, (data, dirty) in TARGETS.items():
        if not dirty: continue
        shutil.copy2(path, path + '.bak')
        json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f"✍ {path} (备份 → {path}.bak)")

print('\n══ 报告 ══')
for k in sorted(stats, key=lambda k: -stats[k]):
    print(f"  {k:32} {stats[k]}")
for kind, rows in problems.items():
    print(f"\n▸ {kind} (前{len(rows)}例):")
    for row in rows: print(f"    {row}")
if APPLY and stats['更新']:
    print("\n下一步: python3 build.py  (全量重建,字形注入会自动收新字)")
elif not APPLY:
    print("\n干跑完成,确认无误后加 --apply 写回。")
