#!/usr/bin/env python3
# 校对平台导出的 done_translate/* 把原文每行开头的 \n<SURNAME/> 压成了空格(' <SURNAME/>'),
# 译文丢了断行。游戏不自动换行 → 直接 import 会画出对话框外。
# 本脚本按 all_translatable.json 里对应 jp 的 <SURNAME/> 行首结构, 精确给译文还原 \n,
# 输出到 <目录>_fixed/, 再交给 import_platform.py 走正常 jp/标签校验+回填。
# 638/644(2026-06-12 6_12批) 能 jp 定位精确还原; 少数 SURNAME 数不符/裸换行的回退到"空格→\n"启发式并列出。
# 用法: python3 fix_platform_newlines.py done_translate/6_12          # → done_translate/6_12_fixed/
#       python3 fix_platform_newlines.py done_translate/6_12 -o 其他输出目录
import json, os, re, sys, glob

os.chdir(os.path.dirname(os.path.abspath(__file__)))
args = [a for a in sys.argv[1:] if not a.startswith('-')]
if not args:
    sys.exit("用法: python3 fix_platform_newlines.py <done_translate/批次目录> [-o 输出目录]")
SRC_DIR = args[0].rstrip('/')
OUT_DIR = sys.argv[sys.argv.index('-o')+1] if '-o' in sys.argv else SRC_DIR + '_fixed'

at = {e['id']: e for e in json.load(open('all_translatable.json', encoding='utf-8'))}
norm = lambda s: (s or '').replace('\\n', '\n')

def jp_pattern(jp):
    """每个 <SURNAME/> 前是否行首(\n 或串首); 段内部是否还有裸 \n。"""
    s = norm(jp); parts = s.split('<SURNAME/>')
    pat = [parts[i-1].endswith('\n') or (i == 1 and parts[i-1].strip() == '')
           for i in range(1, len(parts))]
    bare = any('\n' in p.strip('\n') for p in parts)
    return pat, len(parts) - 1, bare

def reconstruct(jp, tr):
    pat, jn, bare = jp_pattern(jp)
    t = norm(tr); tn = t.count('<SURNAME/>')
    if tn == jn and not bare:                       # jp 定位: 用原文行首模式
        segs = t.split('<SURNAME/>'); out = segs[0]
        for i in range(1, len(segs)):               # 按 jp 行首模式补 \n(段内已有的 \n 由下面合并)
            out += ('\n<SURNAME/>' if pat[i-1] else '<SURNAME/>') + segs[i]
        fb = None
    else:                                           # 回退: 空格→\n
        out = re.sub(r' +<SURNAME/>', '\n<SURNAME/>', t)
        fb = ('SURNAME数 %d→%d' % (jn, tn) if tn != jn else '裸换行')
    # 合并连续 \n(去两侧空格): 平台保留的 \n + 这里补的 \n 会叠成 \n\n, 统一压回单 \n。
    # 行边界恒为 \n<SURNAME/>(行间夹非空白), 不会误并两行。
    out = re.sub(r'[ \t]*\n[ \t\n]*', '\n', out)
    nj = norm(jp)                                   # 与 jp 一致地保留首/尾 \n(否则行数虚假不符)
    if nj.startswith('\n') and not out.startswith('\n'): out = '\n' + out
    if nj.endswith('\n') and not out.endswith('\n'): out = out + '\n'
    return out, fb

os.makedirs(OUT_DIR, exist_ok=True)
n_exact = n_fb = n_nojp = 0
fallbacks = []
for f in sorted(glob.glob(os.path.join(SRC_DIR, '*.json'))):
    data = json.load(open(f, encoding='utf-8'))
    for r in data:
        rid = r.get('id') or ''
        tr = r.get('translation') if r.get('translation') is not None else r.get('zh')
        m = re.search(r':p(\d+)$', rid)              # 多页条目带 :pN 后缀, base 去后缀找 page N
        base, pi = (rid[:m.start()], int(m.group(1))) if m else (rid, 0)
        e = at.get(base)
        if e is None or tr is None or pi >= len(e.get('pages', [])):
            n_nojp += 1; continue                    # 未知 id 不动, 留给 import_platform 报
        tr = re.sub(r'(?<!<)SURNAME/>', '<SURNAME/>', tr)  # 修源数据畸形: 丢<的标签(校对稿偶发)
        new, fb = reconstruct(e['pages'][pi]['jp'], tr)
        # 写回 translation 键(import_platform 两种键都吃)
        if 'translation' in r: r['translation'] = new
        else: r['zh'] = new
        if fb: n_fb += 1; fallbacks.append((rid, fb))
        else: n_exact += 1
    json.dump(data, open(os.path.join(OUT_DIR, os.path.basename(f)), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)

print(f"输出 → {OUT_DIR}/")
print(f"jp 定位精确还原 {n_exact}, 回退(空格启发式) {n_fb}, 跳过(多页/未知,原样输出) {n_nojp}")
if fallbacks:
    print("回退条目(请人工瞄一眼断行):")
    for rid, why in fallbacks: print(f"  {rid}  [{why}]")
print(f"\n下一步: python3 import_platform.py {OUT_DIR}        # 干跑确认")
print(f"        python3 import_platform.py {OUT_DIR} --apply  # 写回")
