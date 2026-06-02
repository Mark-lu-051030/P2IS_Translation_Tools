"""通用 free-region strtbl 引擎：提取/写回 ISO 游离区里的字符串表。

适用于一类同构的游离区表（[头部/指针][字符串区]，字符串 \\n(0x1101) 分隔、夹带
<XXXX> 格式码）。原位等长替换不碰指针表 → 结构零改动、绝对安全。

已注册的表（见 TABLES）：
  contactui  sector 271039  交涉动作名 + 战斗UI + 队友关系状态
  config     sector 271964  设置菜单（サウンド/振動/壁紙… + 说明文 + 壁纸名）

新增一张表：往 TABLES 加一行 {sector, win} 即可。

用法:
  python3 freetbl.py <table> extract     # → out/<table>_zh.json（翻译填 zh，保留<XXXX>）
  python3 freetbl.py <table> apply       # 原位等长写回 working ISO
  python3 freetbl.py list
"""
import sys, os, json, struct, subprocess, re

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from pylib.p2is import read_sectors, write_sectors, BLOCK_SIZE

WK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BAK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')

TABLES = {
    'contactui': {'sector': 271039, 'win': 4},
    'config':    {'sector': 271964, 'win': 4},
    'names':     {'sector': 221,    'win': 8},   # 角色姓/名/昵称（交涉对象名）
}

NL = 0x1101
FULL_SPACE = '　'
TAG_RE = re.compile(r'<([0-9a-fA-F]{4})>')

og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
OGMAP = {int(k): v for k, v in og.items() if isinstance(v, str) and len(v) == 1}

def out_json(table):
    return os.path.join(ROOT, 'out', f'{table}_zh.json')

def decode_entry(buf, off):
    """解一条到 NL(0x1101)。按引擎规则（见 lib/msg_script.mjs）：
      (c>>12)==0  → 文字 (code<0x1000)
      (c>>12)==1  → 控制命令，参数数 = ((c>>8)&0xf)-1，后跟这么多 uint16 参数
    命令+其参数整体作为不可翻 token，emit <XXXX> 标签（参数另存，见返回值）。
    返回 (text含标签, next_off, ntext, bad, has_argcode)。
    has_argcode=True 表示含带参命令 → 该条目不安全、不可做原位文本替换，应 skip。"""
    i = off; s = ''; ntext = 0; bad = 0; has_argcode = False
    while i < len(buf) - 1:
        c = buf[i] | (buf[i + 1] << 8); i += 2
        if c == NL:
            return s, i, ntext, bad, has_argcode
        if (c >> 12) == 0:                      # 文字
            if c in OGMAP:
                s += OGMAP[c]; ntext += 1
            else:
                s += '?'; bad += 1
        else:                                    # 控制命令
            argn = max(0, ((c >> 8) & 0xf) - 1)
            if argn:
                has_argcode = True
                i += 2 * argn                    # 跳过参数（不当文字）
            s += f'<{c:04x}>'
    return s, i, ntext, bad, has_argcode

def _clean_entry(buf, off):
    """从 off 是否是一条干净条目（含文本、几乎无杂、长度合理）。"""
    s, nxt, ntext, bad, _ = decode_entry(buf, off)
    return ntext >= 1 and bad <= 1 and 2 <= (nxt - off) <= 200, nxt

def find_start(buf):
    """字符串区起点：跳过头部，找首个 0x1103 起头、且**连续两条都干净**的位置
    （单条干净可能是 header 巧合，连续两条几乎必是真字符串区）。
    兼容以 2 字短名开头的表（旧的 ≥3 连续 OG 判据会漏掉前几条）。"""
    off = 8
    while off < len(buf) - 8:
        if (buf[off] | (buf[off + 1] << 8)) == 0x1103:
            ok1, nxt1 = _clean_entry(buf, off)
            if ok1:
                ok2, _ = _clean_entry(buf, nxt1)
                if ok2:
                    return off
        off += 2
    return 8

def parse(buf, limit):
    start = find_start(buf)
    entries = []; off = start; miss = 0
    while off < min(limit, len(buf)) - 2:
        s, nxt, ntext, bad, has_arg = decode_entry(buf, off)
        blen = nxt - off
        if ntext == 0 or bad > 2 or blen < 2:
            miss += 1; off = nxt
            if miss > 25:
                break
            continue
        miss = 0
        entries.append((off, blen, s, has_arg))
        off = nxt
    return entries

def cmd_extract(table, cfg):
    sec, win = cfg['sector'], cfg['win']
    buf = read_sectors(BAK, sec, win * 2048)
    entries = parse(buf, win * 2048)
    # 保留已有翻译（按 off 匹配），避免重提取丢失用户译文
    prev = {}
    p = out_json(table)
    if os.path.exists(p):
        for e in json.load(open(p, encoding='utf-8')):
            prev[e['off']] = e.get('zh', '') or ''
    out = []
    for o, b, t, has_arg in entries:
        # 含带参控制码的条目（关系状态/说明文/占位标签）不安全 → skip 不翻，保留日文
        zh = '' if has_arg else prev.get(o, '')
        out.append({'off': o, 'blen': b, 'jp': t, 'zh': zh, 'skip': bool(has_arg)})
    os.makedirs(os.path.join(ROOT, 'out'), exist_ok=True)
    json.dump(out, open(out_json(table), 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    skipn = sum(1 for e in out if e['skip'])
    print(f'[{table}] 提取 {len(out)} 条（{skipn} 条含带参码→skip保留日文）→ out/{table}_zh.json (sector {sec})')
    for e in out[:25]:
        tag = '[skip]' if e['skip'] else ''
        print(f'  @{e["off"]:#x} len={e["blen"]} {tag} {e["jp"][:42]!r}')

def encode_text(zh, rev):
    codes = []
    for tok in re.split(r'(<[0-9a-fA-F]{4}>)', zh):
        if not tok:
            continue
        m = TAG_RE.fullmatch(tok)
        if m:
            codes.append(int(m.group(1), 16))
        else:
            for ch in tok:
                if ch not in rev:
                    return None, ch
                codes.append(rev[ch])
    return codes, None

def cmd_apply(table, cfg):
    p = out_json(table)
    if not os.path.exists(p):
        print(f'✗ {p} 不存在，先 extract + 翻译'); sys.exit(1)
    data = json.load(open(p, encoding='utf-8'))
    ct = json.load(open(os.path.join(ROOT, 'codetable.json'), encoding='utf-8'))
    rev = {v: int(k) for k, v in ct.items() if isinstance(v, str) and len(v) == 1}
    for fw, hw in {'！':'!','？':'?','…':'.','，':'、','：':':','（':'(','）':')','·':'・'}.items():
        if hw in rev and fw not in rev:
            rev[fw] = rev[hw]
    pad = rev.get(FULL_SPACE, rev.get(' '))
    if pad is None:
        print('✗ 码表无空格字符'); sys.exit(1)

    sec, win = cfg['sector'], cfg['win']
    buf = bytearray(read_sectors(WK, sec, win * 2048))
    applied = skipped = toolong = 0
    for e in data:
        zh = (e.get('zh') or '').strip()
        if e.get('skip') or not zh:        # 含带参码的条目绝不写回（防止参数错乱崩溃）
            skipped += 1; continue
        if sorted(TAG_RE.findall(zh)) != sorted(TAG_RE.findall(e['jp'])):
            print(f'  ⚠ 格式码不匹配 @{e["off"]:#x} 跳过'); skipped += 1; continue
        codes, miss = encode_text(zh, rev)
        if codes is None:
            print(f'  ⚠ 缺字 {miss!r} in {zh!r} @{e["off"]:#x} 跳过'); skipped += 1; continue
        cap = e['blen'] // 2 - 1
        if len(codes) > cap:
            print(f'  ⚠ 太长 {zh!r} ({len(codes)}>{cap}) @{e["off"]:#x} 跳过'); toolong += 1; continue
        codes += [pad] * (cap - len(codes))
        codes.append(NL)
        b = b''.join(struct.pack('<H', c) for c in codes)
        assert len(b) == e['blen']
        buf[e['off']:e['off'] + e['blen']] = b
        applied += 1
    write_sectors(WK, sec, bytes(buf))
    subprocess.run(['python3', FIX_ECC, str(sec), str(sec + win - 1)], check=True)
    print(f'[{table}] ✅ 写回 {applied} 条（跳过 {skipped}，太长 {toolong}）→ sector {sec}')

def main():
    if len(sys.argv) >= 2 and sys.argv[1] == 'list':
        for t, c in TABLES.items():
            print(f'  {t}: sector {c["sector"]}')
        return
    if len(sys.argv) < 3 or sys.argv[1] not in TABLES or sys.argv[2] not in ('extract', 'apply'):
        print(__doc__); sys.exit(1)
    table, action = sys.argv[1], sys.argv[2]
    (cmd_extract if action == 'extract' else cmd_apply)(table, TABLES[table])

if __name__ == '__main__':
    main()
