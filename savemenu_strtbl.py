"""存档/记忆卡菜单 string table 处理（ISO 游离区 sector 273695）。

这块是标准 string table（[count u32][ptr u32...][string数据]），30 条系统消息，
但不在 FILEPOS 任何文件里——在 ISO 末尾游离区（264891~294186）。游戏按绝对 LBA 读。

3 个子命令：
  extract  → 解析 sector 273695 → out/savemenu.json (jp 文本 + items)
  apply    → 读 out/savemenu_zh.json → raw-sector 写回 working ISO (重建索引表)

用法:
  python3 savemenu_strtbl.py extract
  python3 savemenu_strtbl.py apply
"""
import sys, json, os, struct, subprocess
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors, write_sectors

ROOT = os.path.dirname(os.path.abspath(__file__))
OG  = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')
SECTOR = 273695   # 存档菜单 table 起始 sector（游离区）
OUT_JSON = os.path.join(ROOT, 'out', 'savemenu.json')

def parse_items(data, ptr, s2c):
    """从 ptr 解析一条 string 成 items（uint16 流到 0x1103 结束）。"""
    items = []
    text = ''
    i = ptr
    while i < len(data) - 1:
        c = struct.unpack_from('<H', data, i)[0]; i += 2
        if c == 0x1103:
            items.append([3]); break
        elif 0x1100 <= c < 0x1200:
            items.append([c & 0xff]); text += f'<c{c&0xff:02x}>' if c != 0x1101 else '\n'
        else:
            items.append(c); text += s2c.get(c, f'?{c}')
    return items, text

def cmd_extract():
    og_ct = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
    s2c = {int(k): v for k, v in og_ct.items() if isinstance(v, str)}
    data = read_sectors(OG, SECTOR, 4 * 2048)
    count = struct.unpack_from('<I', data, 0)[0]
    ptrs = [struct.unpack_from('<I', data, 4 + i*4)[0] for i in range(count)]
    # table 总大小 = 最后 string 的 [END] 之后
    last = max(ptrs); i = last
    while i < len(data)-1 and struct.unpack_from('<H', data, i)[0] != 0x1103: i += 2
    table_total = i + 2

    strings = []
    for idx, p in enumerate(ptrs):
        items, text = parse_items(data, p, s2c)
        strings.append({'idx': idx, 'jp': text, 'items': items, 'zh': ''})

    out = {'sector': SECTOR, 'count': count, 'table_total': table_total, 'strings': strings}
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(out, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✓ extract {count} 条存档菜单 string → {OUT_JSON}')
    print(f'  table 总大小 {table_total} 字节')
    for s in strings:
        print(f'  [{s["idx"]}] {s["jp"][:50]!r}')

def cmd_apply():
    zh_path = os.path.join(ROOT, 'out', 'savemenu_zh.json')
    if not os.path.exists(zh_path):
        print(f'✗ {zh_path} 不存在，先 extract + 翻译')
        sys.exit(1)
    data = json.load(open(zh_path, encoding='utf-8'))
    ct = json.load(open(os.path.join(ROOT, 'codetable.json'), encoding='utf-8'))
    rev = {v: int(k) for k, v in ct.items() if isinstance(v, str) and len(v) == 1}
    # 全角标点 alias（跟 encode_zh 一致）
    for fw, hw in {'！':'!','？':'?','…':'.','，':'、','。':'。','：':':','；':';','（':'(','）':')','　':' ','~':'〜','—':'-'}.items():
        if hw in rev and fw not in rev: rev[fw] = rev[hw]

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
                    else: print(f'  ⚠ 找不到字符: {ch!r}')
        return items

    def items_bytes(items):
        out = bytearray()
        for x in items:
            if isinstance(x, list):
                out += struct.pack('<H', 0x1100 | x[0])
                for a in x[1:]: out += struct.pack('<H', a)
            else:
                out += struct.pack('<H', x)
        return bytes(out)

    def split_prefix_suffix(orig):
        """从原 items 拆出 [前缀] [正文] [尾部]。
        前缀 = 开头连续的 special码(>=0x1200) / 「(code 0) / 控制码，直到第一个真正文字。
        尾部 = 结尾连续的控制码([list])。
        正文 = 中间，用中文替换。"""
        # 前缀：开头的 special(>=0x1200) 和紧跟的 「(0)
        pre = 0
        while pre < len(orig):
            x = orig[pre]
            if (isinstance(x, int) and (x >= 0x1200 or x == 0)):
                pre += 1
            else:
                break
        # 尾部：结尾的控制码 [list]
        suf = len(orig)
        while suf > pre and isinstance(orig[suf-1], list):
            suf -= 1
        return orig[:pre], orig[suf:]

    count = data['count']
    table_total = data['table_total']
    # 重建 table: [count][ptrs][strings]
    new = bytearray(table_total)
    struct.pack_into('<I', new, 0, count)
    ind = 4
    sp = 4 + count * 4
    seen = {}
    for s in data['strings']:
        zh = s.get('zh', '').strip()
        if zh:
            # 保留原前缀(图标/「) + 尾部控制码，只换中间正文
            prefix, suffix = split_prefix_suffix(s['items'])
            items = prefix + encode(zh) + suffix
        else:
            items = s['items']  # 没翻译保留原文
        b = items_bytes(items)
        key = b.hex()
        if key in seen:
            struct.pack_into('<I', new, ind, seen[key])
        else:
            if sp + len(b) > table_total:
                print(f'  ❌ string [{s["idx"]}] 超容量（{sp+len(b)} > {table_total}），用原文')
                items = s['items']; b = items_bytes(items); key = b.hex()
                if key in seen:
                    struct.pack_into('<I', new, ind, seen[key]); ind += 4; continue
            struct.pack_into('<I', new, ind, sp)
            new[sp:sp+len(b)] = b
            seen[key] = sp
            sp += len(b)
        ind += 4
    print(f'重建 table: {sp} / {table_total} 字节')

    # raw-sector 写回（table 可能跨 2 sectors）
    nsec = (table_total + 2047) // 2048
    user = bytearray(read_sectors(ISO, SECTOR, nsec * 2048))
    user[:table_total] = bytes(new)
    write_sectors(ISO, SECTOR, bytes(user))
    subprocess.run(['python3', FIX_ECC, str(SECTOR), str(SECTOR + nsec - 1)], check=True)
    print(f'✓ 写回 sector {SECTOR}~{SECTOR+nsec-1} + ECC')

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('extract', 'apply'):
        print('用法: python3 savemenu_strtbl.py extract|apply'); sys.exit(1)
    (cmd_extract if sys.argv[1] == 'extract' else cmd_apply)()
