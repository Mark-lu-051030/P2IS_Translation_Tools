"""角色名一致性批量修正：按映射把所有译文里的"错写法→对写法"统一。

扫描 all_translatable.json（对话 zh + meta_zh）+ out/*_zh.json（各表 zh），
替换前先备份 *.namebak，替换后报告每项次数 + 抽样上下文供核对。

⚠️ 替换是纯文本 find-replace。名字够独特误伤风险低，但 run 完务必看抽样上下文。

用法:
  python3 name_fix.py            # 执行替换（先备份）
  python3 name_fix.py --dry      # 只报次数+样本，不改
  python3 name_fix.py --restore  # 从 .namebak 还原
"""
import json, os, glob, sys, shutil, re

ROOT = os.path.dirname(os.path.abspath(__file__))

# 错写法 → 对写法（PSP 权威 + 内部统一）。改这里加新修正。
FIXES = {
    '麻耶': '舞耶',      # 天野マヤ：PSP=舞耶
    '雪乃': '雪野',      # 黛ゆきの：PSP=雪野
    '达也': '龙也',      # 須藤龍也：PSP=龙也（达哉=主角周防，不受影响）
    '米歇尔': '米切',    # ミッシェル：统一到多数
    '银狐': '银子',      # ギンコ：统一到多数
}

SOURCES = [os.path.join(ROOT, 'all_translatable.json')] + glob.glob(os.path.join(ROOT, 'out', '*_zh.json'))

def iter_zh(obj):
    """yield (容器, key) 指向每个 zh 字符串，可读可写。"""
    if isinstance(obj, list):
        for it in obj:
            yield from iter_zh(it)
    elif isinstance(obj, dict):
        if isinstance(obj.get('zh'), str):
            yield (obj, 'zh')
        if isinstance(obj.get('meta_zh'), str):
            yield (obj, 'meta_zh')
        for v in obj.values():
            if isinstance(v, (list, dict)):
                yield from iter_zh(v)

def main():
    dry = '--dry' in sys.argv
    restore = '--restore' in sys.argv

    if restore:
        for f in SOURCES:
            bak = f + '.namebak'
            if os.path.exists(bak):
                shutil.copy(bak, f); print(f'还原 {os.path.basename(f)}')
        return

    counts = {w: 0 for w in FIXES}
    samples = {w: [] for w in FIXES}
    for f in SOURCES:
        if not os.path.exists(f): continue
        data = json.load(open(f, encoding='utf-8'))
        changed = False
        for holder, key in iter_zh(data):
            s = holder[key]
            ns = s
            for wrong, right in FIXES.items():
                if wrong in ns:
                    c = ns.count(wrong)
                    counts[wrong] += c
                    if len(samples[wrong]) < 4:
                        samples[wrong].append(s[:50])
                    ns = ns.replace(wrong, right)
            if ns != s:
                holder[key] = ns; changed = True
        if changed and not dry:
            if not os.path.exists(f + '.namebak'):
                shutil.copy(f, f + '.namebak')
            json.dump(data, open(f, 'w', encoding='utf-8'), ensure_ascii=False)

    print(('【DRY 预览】' if dry else '【已替换'+(' + 备份.namebak】')) )
    for wrong, right in FIXES.items():
        print(f'  {wrong} → {right}: {counts[wrong]} 处')
        for s in samples[wrong][:3]:
            print(f'      例: {s!r}')

if __name__ == '__main__':
    main()
