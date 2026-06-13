#!/usr/bin/env python3
# 校对批人工复核报告: 把 平台jp / 项目jp / 还原后译文 并排, 断行渲染成真实换行。
# 用于合并前肉眼核对 ① 平台日文是否与项目原文一致 ② \n 还原落点是否对。
# 读 原始批次目录(平台jp) + _fixed目录(还原译文) + all_translatable.json(项目jp+旧译)。
# 用法: python3 review_batch.py done_translate/6_12   [-o out/review_6_12.md]
import json, os, re, sys, glob

os.chdir(os.path.dirname(os.path.abspath(__file__)))
RAW = sys.argv[1].rstrip('/')
FIXED = RAW + '_fixed'
OUT = sys.argv[sys.argv.index('-o')+1] if '-o' in sys.argv else 'out/review_' + os.path.basename(RAW) + '.md'

at = {e['id']: e for e in json.load(open('all_translatable.json', encoding='utf-8'))}
norm = lambda s: (s or '').replace('\\n', '\n')
def page(rid):
    m = re.search(r':p(\d+)$', rid); base, pi = (rid[:m.start()], int(m.group(1))) if m else (rid, 0)
    e = at.get(base)
    return (e['pages'][pi] if e and pi < len(e.get('pages', [])) else None)

# 收集 平台jp / 项目jp / 还原译文 / 旧译
raw_jp = {}
for f in glob.glob(os.path.join(RAW, '*.json')):
    for r in json.load(open(f, encoding='utf-8')):
        raw_jp[r.get('id')] = r.get('jp')
recs = {}
for f in sorted(glob.glob(os.path.join(FIXED, '*.json'))):
    for r in json.load(open(f, encoding='utf-8')):
        rid = r.get('id'); recs[rid] = r.get('translation') if r.get('translation') is not None else r.get('zh')

def render(s):                       # 渲染断行: \n → 换行, 每行前加缩进
    s = norm(s)
    return '\n'.join('    │ ' + ln for ln in s.split('\n'))

mismatch_jp, count_diff, fallback_ids, normal = [], [], [], []
FB = {'script:183_8:diag3:p1','script:194_8:diag13','script:248_8:diag25',
      'script:4_12:diag0','script:4_12:diag1'}        # fix_platform_newlines 报的回退条目
for rid in sorted(recs):
    p = page(rid)
    if p is None:
        continue
    src_jp = norm(p.get('jp')); plat_jp = norm(raw_jp.get(rid))
    zh = norm(recs[rid])
    rec = (rid, src_jp, plat_jp, zh)
    if plat_jp.strip() != src_jp.strip():
        mismatch_jp.append(rec)
    elif rid in FB:
        fallback_ids.append(rec)
    elif src_jp.count('\n') != zh.count('\n'):
        count_diff.append(rec)
    else:
        normal.append(rec)

def block(rec):
    rid, sj, pj, zh = rec
    out = [f"### {rid}   (jp行数 {sj.count(chr(10))} / 译文行数 {zh.count(chr(10))})"]
    if pj.strip() != sj.strip():
        out.append("⚠ 平台jp ≠ 项目jp")
        out.append("─ 平台jp ─\n" + render(pj))
        out.append("─ 项目jp ─\n" + render(sj))
    else:
        out.append("─ 原文jp ─\n" + render(sj))
    out.append("─ 译文(还原后) ─\n" + render(zh))
    return '\n'.join(out)

L = []
L.append(f"# 校对批 {os.path.basename(RAW)} 人工复核  (共 {len(recs)} 条)\n")
L.append(f"- ⚠ 平台jp≠项目jp: **{len(mismatch_jp)}**  | 断行回退(重点看): **{len(fallback_ids)}**  | jp/译文行数不一致: **{len(count_diff)}**  | 正常: {len(normal)}\n")
L.append("> │ 开头的是渲染出的每一行；对照 原文jp 与 译文 的行数和断点是否一致。\n")
for title, group in [("## ① ⚠ 平台日文与项目原文不一致(最该查)", mismatch_jp),
                     ("## ② 断行回退条目(空格启发式, 重点看)", fallback_ids),
                     ("## ③ jp与译文行数不一致(断点可能偏)", count_diff),
                     ("## ④ 其余(jp定位精确还原, 抽查即可)", normal)]:
    L.append(f"\n{title}  ({len(group)} 条)\n")
    for rec in group:
        L.append(block(rec) + "\n")

os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write('\n'.join(L))
print(f"复核报告 → {OUT}")
print(f"  ⚠平台jp≠项目jp {len(mismatch_jp)}  | 回退 {len(fallback_ids)}  | 行数不一致 {len(count_diff)}  | 正常 {len(normal)}")
