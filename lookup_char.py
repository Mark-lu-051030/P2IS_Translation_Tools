"""查字工具：输入你在游戏画面里看到的字，告诉你它在字库的哪个 slot、
我们有没有改过、改成了什么。用于核对命名界面/菜单等画面读的是哪份字库。

用法:
  python3 lookup_char.py 課 過 価       # 查这几个字
  python3 lookup_char.py 課過価暇階貝     # 连写也行
  python3 lookup_char.py --slot 138      # 反查：slot 138 现在/原本是什么字
"""
import json, sys, os

ROOT = os.path.dirname(os.path.abspath(__file__))
og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
ct = json.load(open(os.path.join(ROOT, 'codetable.json'), encoding='utf-8'))
rev_og = {v: int(k) for k, v in og.items() if isinstance(v, str) and len(v) == 1}

def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__); return

    if args[0] == '--slot':
        for s in args[1:]:
            k = str(int(s))
            print(f'slot {k}: 原版 {og.get(k)!r} → 现在 {ct.get(k)!r}'
                  + ('  ★已改' if og.get(k) != ct.get(k) else ''))
        return

    chars = ''.join(args)
    for ch in chars:
        slot = rev_og.get(ch)
        if slot is None:
            print(f'{ch!r}: 不在原版字库（可能是我们新增的简体字，或符号）')
            continue
        cur = ct.get(str(slot))
        if cur == ch:
            print(f'{ch!r}: slot {slot} — 没改，命名界面读 86 也应显示 {ch!r}')
        else:
            print(f'{ch!r}: slot {slot} — ★我们改成了 {cur!r}（命名界面若读 file 59/已 sync 的 86 应显示 {cur!r}）')

if __name__ == '__main__':
    main()
