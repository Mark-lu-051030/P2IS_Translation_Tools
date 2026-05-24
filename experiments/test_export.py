import json, os, re
from collections import Counter

cmd_positions = Counter()   # 控制码出现在哪(句首/句中/句尾)
cmd_after_c1 = Counter()    # 哪些码紧跟在 <C1> 后

for fname in os.listdir('out/scripts'):
    d = json.load(open(f'out/scripts/{fname}', encoding='utf-8'))
    for items in d.get('dialogs', {}).values():
        if not items: continue
        # 跳过 META 区
        start = 0
        if isinstance(items[0], list) and items[0][0] == 29:
            for i in range(1, len(items)):
                if isinstance(items[i], list) and items[i][0] == 29:
                    start = i + 1; break
        body = items[start:]
        for i, x in enumerate(body):
            if isinstance(x, list):
                cmd = x[0]
                pos = 'head' if i < 2 else ('tail' if i >= len(body)-3 else 'mid')
                cmd_positions[(cmd, pos)] += 1
                if i > 0 and isinstance(body[i-1], list) and body[i-1][0] == 1:
                    cmd_after_c1[cmd] += 1

print('控制码位置分布:')
for (cmd, pos), n in sorted(cmd_positions.items(), key=lambda x: -x[1])[:20]:
    print(f'  C{cmd} @ {pos}: {n}')
print('\n紧跟 <C1> 之后的码:')
for cmd, n in cmd_after_c1.most_common(10):
    print(f'  C{cmd}: {n}')