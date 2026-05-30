"""校验翻译质量：控制码守恒 + codetable 缺字 + 漏翻统计。
随时跑，检查手翻进度和错误。

用法: python3 check_translation.py
"""
import json, re, os

ROOT = os.path.dirname(os.path.abspath(__file__))
TAG = re.compile(r'<[^>]+>')

data = json.load(open(os.path.join(ROOT, 'all_translatable.json'), encoding='utf-8'))
ct = json.load(open(os.path.join(ROOT, 'codetable.json'), encoding='utf-8'))
rev = {v: int(k) for k, v in ct.items() if isinstance(v, str) and len(v) == 1}
# 跟 encode_zh.py FULLWIDTH_ALIASES 完全一致，否则误报缺字
ALIASES = {'！':'!','？':'?','…':'.','，':'、','。':'。','：':':','；':';','（':'(','）':')','　':' ',
           '~':'〜','～':'〜','—':'-','–':'-','―':'-','《':'「','》':'」','‘':"'",'’':"'",'“':'"','”':'"','·':'・','ó':'o'}
for fw, hw in ALIASES.items():
    if hw in rev: rev[fw] = rev[hw]

script_total = script_done = 0
ctrl_mismatch = []
missing_char = []

for e in data:
    if not e['id'].startswith('script:') or not e.get('pages'):
        continue
    for i, p in enumerate(e['pages']):
        jp = p.get('jp', '').strip()
        zh = p.get('zh', '').strip()
        if not jp:
            continue
        script_total += 1
        if not zh:
            continue
        script_done += 1
        # 控制码守恒检查 —— 区分两类：
        #   <SURNAME/> = 说话人前缀，数量可随断行增减（不强制守恒，游戏宽容）
        #   其他控制码 (<NAME/> <c1d:N/> <pause:N/> <option/> 等) = 逻辑码，必须守恒！
        SOFT = {'<SURNAME/>'}   # 允许数量不同的"软"控制码
        jp_hard = sorted(t for t in TAG.findall(jp) if t not in SOFT)
        zh_hard = sorted(t for t in TAG.findall(zh) if t not in SOFT)
        if jp_hard != zh_hard:
            ctrl_mismatch.append((e['id'], i, jp_hard, zh_hard))
        # 缺字
        miss = [c for c in TAG.sub('', zh) if c != '\n' and c not in rev]
        if miss:
            missing_char.append((e['id'], i, miss))

print(f'script 翻译进度: {script_done}/{script_total} ({script_done/script_total*100:.1f}%)')
print(f'  未翻: {script_total - script_done}')
print()
print(f'⚠ 控制码不守恒: {len(ctrl_mismatch)} 条')
for eid, i, jt, zt in ctrl_mismatch[:15]:
    print(f'  {eid} p{i}: jp={jt} zh={zt}')
if len(ctrl_mismatch) > 15:
    print(f'  ...还有 {len(ctrl_mismatch)-15} 条')
print()
print(f'⚠ codetable 缺字: {len(missing_char)} 条')
miss_chars = set()
for eid, i, m in missing_char[:15]:
    print(f'  {eid} p{i}: 缺 {m}')
    miss_chars.update(m)
if missing_char:
    all_miss = set()
    for _, _, m in missing_char: all_miss.update(m)
    print(f'  所有缺字: {sorted(all_miss)}')
