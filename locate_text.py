"""定位工具：输入一段日文，找出它在 ISO 里的位置 + 归属（哪个 file / 游离区）。

用于排查"游戏里看到没翻译的日文"——确定它在哪，才能决定用哪个 pipeline 翻。

用法:
  python3 locate_text.py 'コマンドを選択'       # 搜原版 ISO
  python3 locate_text.py 'セーブ' --working      # 搜 working ISO（看翻没翻）
"""
import sys, struct, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors

ROOT = os.path.dirname(os.path.abspath(__file__))
OG  = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print("用法: python3 locate_text.py '日文文本' [--working]")
        sys.exit(1)
    text = args[0]
    path = ISO if '--working' in sys.argv else OG
    print(f"搜索 {'working' if '--working' in sys.argv else '原版'} ISO: {text!r}\n")

    og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
    rev = {v: int(k) for k, v in og.items() if isinstance(v, str) and len(v) == 1}

    # 文本 → uint16 字节序列
    try:
        pat = b''.join(struct.pack('<H', rev[c]) for c in text)
    except KeyError as e:
        print(f"字符 {e} 不在 codetable_og，无法搜索（可能是中文或特殊符号）")
        sys.exit(1)

    with open(path, 'rb') as f:
        raw = f.read()

    # FILEPOS 文件表
    fp = read_sectors(path, 0x17, 4 * 2048)
    files = []
    for fid in range(881):
        b, sz = struct.unpack_from('<II', fp, fid * 8)
        if b and sz:
            files.append((b, b + (sz + 2047) // 2048, fid))

    # 搜索所有出现
    hits = []
    i = 0
    while True:
        p = raw.find(pat, i)
        if p == -1:
            break
        sec = p // 2352
        in_sec = p % 2352 - 24
        owner = next((fid for b, e, fid in files if b <= sec < e), None)
        hits.append((sec, in_sec, owner))
        i = p + 1

    if not hits:
        print("未找到。可能：1)文本不连续(中间有控制码) 2)是压缩数据(battle) 3)拼写不符")
        print("试试搜更短的片段，或单个词。")
        return

    print(f"找到 {len(hits)} 处：\n")
    for sec, off, owner in hits[:20]:
        if owner is None:
            loc = "游离区(无FILEPOS文件)"
            hint = "→ 用 mainmenu_strtbl/savemenu_strtbl 类 raw-sector 工具"
        elif owner == 0:
            loc = "file 0 (SLPS 可执行)"
            hint = "→ strtbl(SLUS_*) / apply_strtbl_slps"
        else:
            loc = f"file {owner}"
            hint = "→ script(对话) 或 strtbl(UI)，看 out/scripts 和 out/string_table 里有没有这个 file"
        print(f"  sector {sec}, file内offset {off:#x}: {loc}")
        print(f"    {hint}")

    # 游离区命中：给出它属于哪个已知块
    free_hits = [h for h in hits if h[2] is None]
    if free_hits:
        print(f"\n游离区命中 sector: {sorted(set(h[0] for h in free_hits))}")
        print("  已知游离区表: 271864(主菜单 mainmenu) / 273695(存档菜单 savemenu)")


if __name__ == '__main__':
    main()
