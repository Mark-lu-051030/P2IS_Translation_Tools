# missing_stats.py
import json, os
from collections import Counter

table = {int(k):v for k,v in json.load(open('codetable.json', encoding='utf-8')).items()}
for i in range(0, 96):
    table.setdefault(i, chr(0x20 + i))

missing = Counter()
total_chars = 0

for fn in os.listdir('out/scripts'):
    if not fn.endswith('.json'): continue
    data = json.load(open(f'out/scripts/{fn}', encoding='utf-8'))
    for diag in data.get('dialogs', {}).values():
        for x in diag:
            if isinstance(x, int):
                total_chars += 1
                if x not in table or not table[x]:
                    missing[x] += 1

print(f'总字符数: {total_chars}')
print(f'未识别字符: {sum(missing.values())} ({100*sum(missing.values())/total_chars:.1f}%)')
print(f'\n未识别索引 Top 30 (按出现频次):')
for idx, count in missing.most_common(30):
    print(f'  索引 {idx}: {count} 次')