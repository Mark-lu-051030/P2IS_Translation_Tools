"""主菜单 string table 处理（ISO 游离区 sector 271864）。

这块是主菜单/系统 UI 文字表（魔法/道具/个人数据/卡片列表/存档/读取/装备/攻击...等 85 条），
在游离区（不在 FILEPOS）。结构特殊：头部 [count][size] + 指针表(0x8~0x16a, 88指针) + string 数据(0x16a~0x548)。

⚠ 指针表格式诡异（base 不统一），所以**不碰指针表**，用"原位等长/缩短替换"：
  每条中文写在原 string 的 offset，字节数 ≤ 原长，末尾 0x1103，剩余补 0（在本条范围内）。
  这样每条起始 offset 不变 → 指针表仍有效。

3 个子命令：
  extract  → 解析 0x16a 起的 85 条 → out/mainmenu.json
  apply    → 读 out/mainmenu_zh.json → 原位 raw-sector 写回

用法:
  python3 mainmenu_strtbl.py extract
  python3 mainmenu_strtbl.py apply
"""
import sys, json, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors, write_sectors

ROOT = os.path.dirname(os.path.abspath(__file__))
OG  = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')
SECTOR = 271864
# 主菜单这块有两个文本区（中间 0x548~0x87e 是非文本数据，跳过）：
#   区1: 0x16a~0x548  菜单项（魔法/道具/...85条）
#   区2: 0x87e~0xba6  提示语（コマンドを選択して下さい/魔法を使用する...26条）
REGIONS = [(0x16a, 0x548), (0x87e, 0xba6)]
OUT_JSON = os.path.join(ROOT, 'out', 'mainmenu.json')


def parse_one(data, ptr, s2c):
    """从 ptr 解析一条 string 到 0x1103，返回 (items, text, byte_len)。"""
    items = []; text = ''; i = ptr
    while i < len(data) - 1:
        c = struct.unpack_from('<H', data, i)[0]; i += 2
        if c == 0x1103:
            items.append([3]); break
        elif c == 0x1101:
            items.append([1]); text += '\n'
        elif 0x1100 <= c < 0x1200:
            items.append([c & 0xff]); text += f'<c{c&0xff:02x}>'
        else:
            items.append(c); text += s2c.get(c, f'?{c}')
    return items, text, i - ptr


def cmd_extract():
    og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
    s2c = {int(k): v for k, v in og.items() if isinstance(v, str)}
    data = read_sectors(OG, SECTOR, 4 * 2048)
    strings = []
    idx = 0
    for r_start, r_end in REGIONS:
        off = r_start
        while off < r_end:
            items, text, blen = parse_one(data, off, s2c)
            if blen <= 0:
                break
            strings.append({'idx': idx, 'offset': off, 'byte_len': blen, 'jp': text, 'items': items, 'zh': ''})
            off += blen
            idx += 1
    out = {'sector': SECTOR, 'regions': REGIONS, 'strings': strings}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(out, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✓ extract {len(strings)} 条主菜单 string → {OUT_JSON}')
    for s in strings:
        print(f'  [{s["idx"]}] @{s["offset"]:#x} ({s["byte_len"]}B): {s["jp"]!r}')


def cmd_apply():
    zh_path = os.path.join(ROOT, 'out', 'mainmenu_zh.json')
    if not os.path.exists(zh_path):
        print(f'✗ {zh_path} 不存在，先 extract + 翻译'); sys.exit(1)
    data_zh = json.load(open(zh_path, encoding='utf-8'))
    ct = json.load(open(os.path.join(ROOT, 'codetable.json'), encoding='utf-8'))
    rev = {v: int(k) for k, v in ct.items() if isinstance(v, str) and len(v) == 1}
    for fw, hw in {'！':'!','？':'?','…':'.','，':'、','。':'。','：':':','；':';','（':'(','）':')','　':' ','~':'〜','—':'-','·':'・','《':'「','》':'」'}.items():
        if hw in rev and fw not in rev: rev[fw] = rev[hw]

    pad_code = rev.get('　', rev.get(' '))   # 全角空格码（居中用）

    import re
    def encode(text):
        items = []
        for tok in re.split(r'(<[^>]+/?>)', text):
            if not tok: continue
            if tok.startswith('<'):
                m = re.match(r'<c([0-9a-f]+)/?>', tok)
                if m: items.append([int(m.group(1), 16)])
            else:
                for ch in tok:
                    if ch == '\n': items.append([1])
                    elif ch in rev: items.append(rev[ch])
                    else: print(f'  ⚠ 缺字: {ch!r}'); return None
        return items

    def items_bytes(items):
        out = bytearray()
        for x in items:
            if isinstance(x, list):
                out += struct.pack('<H', 0x1100 | x[0])
            else:
                out += struct.pack('<H', x)
        return bytes(out)

    # 读游离区，原位替换
    max_end = max(r[1] for r in REGIONS)
    nsec = (max_end + 2047) // 2048
    user = bytearray(read_sectors(ISO, SECTOR, nsec * 2048))
    applied = skipped = 0
    for s in data_zh['strings']:
        zh = s.get('zh', '').strip()
        if not zh:
            continue
        items = encode(zh)
        if items is None:
            print(f'  [{s["idx"]}] 缺字跳过: {zh!r}')
            skipped += 1; continue
        # 居中：原槽位宽度内，文本前补一半全角空格（游戏读到 0x1103 停，前导空格把字推到中间）
        # 长句 zh≈原长 → leading≈0 自然不受影响，只有短菜单项会居中
        slot_u16 = s['byte_len'] // 2
        body = len(items) + 1

        if pad_code is not None:
            if 'pad' in s:
                leading = max(0, int(s['pad']))
            else:
                leading = max(0, (slot_u16 - body) // 2)
        else:
            leading = 0

        items = [pad_code] * leading + items + [[3]]
        b = items_bytes(items)
        if len(b) > s['byte_len']:
            print(f'  [{s["idx"]}] 太长跳过: {zh!r} ({len(b)}B > 原 {s["byte_len"]}B)')
            skipped += 1; continue
        off = s['offset']
        # 原位写入 + 不足部分填 0x1103(终止符重复, 安全) 到原长
        user[off:off+len(b)] = b
        for j in range(off+len(b), off+s['byte_len'], 2):
            struct.pack_into('<H', user, j, 0x1103)
        applied += 1
    write_sectors(ISO, SECTOR, bytes(user))
    subprocess.run(['python3', FIX_ECC, str(SECTOR), str(SECTOR + nsec - 1)], check=True)
    print(f'✓ 主菜单 apply: {applied} 条写入, {skipped} 跳过. 写 sector {SECTOR}~{SECTOR+nsec-1}')


if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('extract', 'apply'):
        print('用法: python3 mainmenu_strtbl.py extract|apply'); sys.exit(1)
    (cmd_extract if sys.argv[1] == 'extract' else cmd_apply)()
