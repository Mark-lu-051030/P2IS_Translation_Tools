#!/usr/bin/env python3
# 字段译文整合(安全版 merge)。
# ⚠ 背景: translate_field.py 的 do_merge 是"从 clean 重建+按 jp 回填 partials",
#   会丢掉 field_text_zh.json 里所有不来自 partials 的东西——手工新增条目(宝箱/効果終了)、
#   偏移修正(77:0x455c)、speaker 批修、布袋等直接编辑(2026-06-12 实证翻车一次)。
# 本脚本的策略: git HEAD 的 field_text_zh(含全部手工修复) 为基底
#   → 删 file61 伪文本 → 只给"空 zh"条目按 jp 回填 partials 新译文 → 写回。
# 手工编辑后务必 commit field_text_zh, 本脚本永远以 HEAD 为真相源。
# 用法: python3 field_consolidate.py
import json, os, re, subprocess, glob

os.chdir(os.path.dirname(os.path.abspath(__file__)))

base = json.loads(subprocess.run(['git', 'show', 'HEAD:out/field_text_zh.json'],
                                 capture_output=True, text=True, check=True).stdout)
print(f'基底(HEAD): {len(base)} 条')

# ① 删 file61 伪文本(命名界面 JIS 数据被误读, 回写会产生 狸数字 类损伤)
n0 = len(base)
base = [e for e in base if not re.match(r'field:61:0x', e['id'])]
print(f'① 删 file61 伪文本: {n0 - len(base)} 条')

# ② 收集全部 partials 的 jp→zh
done = {}
review = 0
for f in glob.glob('translatable/partials_field/*.json') + glob.glob('translatable/partials_field_short/*.json'):
    try:
        d = json.load(open(f, encoding='utf-8'))
    except Exception:
        continue
    for t in d.get('translations', []):
        jp, zh = t.get('jp'), t.get('zh')
        if jp and zh:
            done[jp] = zh
            if t.get('review'): review += 1
print(f'② partials 译文池: {len(done)} 条 (标记复查 {review})')

# ③ 只填空白 zh(可见字符为空才算空)
vis = lambda s: re.sub(r'<[^>]*>|\\\\n|\n', '', s or '').strip()
filled = still = 0
for e in base:
    if vis(e.get('zh')):
        continue
    zh = done.get(e.get('jp'))
    if zh and vis(zh):
        e['zh'] = zh
        filled += 1
    elif len(vis(e.get('jp'))) >= 2:
        still += 1
print(f'③ 空白回填: {filled} 条, 仍空: {still}')

json.dump(base, open('out/field_text_zh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(f'→ out/field_text_zh.json ({len(base)} 条)。下一步: node apply_field.mjs apply')
