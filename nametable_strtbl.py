"""道具/Persona/技能名 主表 extract + apply（ISO free region，sector 200 起）。

格式（审计 + 逆向确认）：
  [0, ~0x3064) 头部/指针表（指针指向 mid-string、结构复杂）—— 不碰。
  字符串区从第一个 0x1103 开始，条目顺序排列：<0x1103>名字<0x1101换行>。
  内容 = 道具名 + Persona/恶魔名（混在一张表，~546 条）。
  杂质：未使用ID、单字(R)、ダミー(dummy 垃圾) —— extract 标 skip，apply 不动。

写回策略（关键）：**等字节长度原位替换**。中文按 uint16 编码，前缀 0x1103 + 中文 +
  全角空格补齐 + 0x1101，凑到与原条目**完全相同的字节长度**。这样每个 byte offset
  都不变 → 复杂的指针表/索引全程有效 → 结构零改动、绝对安全。中文比日文长则警告跳过
  （名字一般中文更短）。

用法:
  python3 nametable_strtbl.py extract     # → out/nametable_zh.json（翻译填 zh）
  python3 nametable_strtbl.py apply       # 读 out/nametable_zh.json 原位写回 working ISO
"""
import sys, os, json, struct, subprocess

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
from pylib.p2is import read_sectors, write_sectors, BLOCK_SIZE

WK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BAK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')
OUT_JSON = os.path.join(ROOT, 'out', 'nametable_zh.json')

SEC0 = 200          # 表所在起始扇区（free region）
WIN  = 16           # 读写窗口扇区数（覆盖整表 + 余量）
NL   = 0x1101       # 换行/条目结束
PRE  = 0x1103       # 条目前缀控制码
FULL_SPACE = '　'   # 全角空格（补齐用）

og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
OGMAP = {int(k): v for k, v in og.items() if isinstance(v, str) and len(v) == 1}

def is_skip(jp):
    """占位/垃圾/单字 → 不翻，原样保留。"""
    return (len(jp) <= 1 or 'ダミー' in jp or '未使用' in jp
            or jp.count('「') > 3)   # 大量「= dummy 垃圾条

def find_start(buf):
    """字符串区起点 = 头部之后第一个 0x1103。"""
    for off in range(0x244, len(buf) - 1, 2):
        if buf[off] | (buf[off + 1] << 8) == PRE:
            return off
    return None

def parse(buf):
    """从字符串区起点按 \\n 切条目，返回 [(off, byte_len, jp, has_pre)]。
    遇到连续非文本判定出表。"""
    start = find_start(buf)
    entries = []; off = start; miss = 0
    while off < len(buf) - 2:
        i = off; s = ''; has_pre = False; bad = 0
        while i < len(buf) - 1:
            c = buf[i] | (buf[i + 1] << 8); i += 2
            if c == NL:
                break
            if c == PRE:
                has_pre = True
            elif c in OGMAP:
                s += OGMAP[c]
            else:
                bad += 1
        blen = i - off
        if bad > 3 or blen < 2:        # 非文本 → 计入 miss
            miss += 1; off = i
            if miss > 30:
                break
            continue
        miss = 0
        entries.append((off, blen, s, has_pre))
        off = i
    return entries

def cmd_extract():
    buf = read_sectors(BAK, SEC0, WIN * 2048)   # 从 pristine backup 提取原文
    entries = parse(buf)
    out = []
    for off, blen, jp, has_pre in entries:
        out.append({'off': off, 'blen': blen, 'jp': jp, 'zh': '', 'skip': is_skip(jp)})
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    json.dump(out, open(OUT_JSON, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    n_tr = sum(1 for e in out if not e['skip'])
    print(f'提取 {len(out)} 条（{n_tr} 条可翻，{len(out)-n_tr} 条 skip）→ {OUT_JSON}')
    print('样例:')
    for e in out[:12]:
        print(f'  @{e["off"]:#x} len={e["blen"]} {"[skip]" if e["skip"] else ""} {e["jp"]!r}')

def cmd_apply():
    if not os.path.exists(OUT_JSON):
        print(f'✗ {OUT_JSON} 不存在，先 extract + 翻译'); sys.exit(1)
    data = json.load(open(OUT_JSON, encoding='utf-8'))
    ct = json.load(open(os.path.join(ROOT, 'codetable.json'), encoding='utf-8'))
    rev = {v: int(k) for k, v in ct.items() if isinstance(v, str) and len(v) == 1}
    for fw, hw in {'！':'!','？':'?','…':'.','，':'、','：':':','（':'(','）':')','·':'・'}.items():
        if hw in rev and fw not in rev: rev[fw] = rev[hw]

    pad_code = rev.get(FULL_SPACE, rev.get(' '))
    if pad_code is None:
        print('✗ 码表里找不到空格字符，无法补齐'); sys.exit(1)

    buf = bytearray(read_sectors(WK, SEC0, WIN * 2048))
    applied = skipped = toolong = 0
    for e in data:
        zh = (e.get('zh') or '').strip()
        if e.get('skip') or not zh:
            skipped += 1; continue
        miss = [c for c in zh if c not in rev]
        if miss:
            print(f'  ⚠ 缺字 {miss} in {zh!r}（@{e["off"]:#x}）跳过'); skipped += 1; continue
        # 等字节长度重建：PRE + 中文 + 全角空格补齐 + NL，凑到原 blen
        cap = e['blen'] // 2 - 1                 # uint16 槽数（减去结尾 NL）
        codes = [PRE] + [rev[c] for c in zh]
        if len(codes) > cap:
            print(f'  ⚠ 太长 {zh!r} ({len(codes)}>{cap}) @{e["off"]:#x} 跳过'); toolong += 1; continue
        codes += [pad_code] * (cap - len(codes))
        codes.append(NL)
        b = b''.join(struct.pack('<H', c) for c in codes)
        assert len(b) == e['blen'], f'长度不符 {len(b)}!={e["blen"]}'
        buf[e['off']:e['off'] + e['blen']] = b
        applied += 1
    write_sectors(WK, SEC0, bytes(buf))
    subprocess.run(['python3', FIX_ECC, str(SEC0), str(SEC0 + WIN - 1)], check=True)
    print(f'✅ 写回 {applied} 条（跳过 {skipped}，太长 {toolong}）→ working ISO sector {SEC0}+')

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] not in ('extract', 'apply'):
        print(__doc__); sys.exit(1)
    (cmd_extract if sys.argv[1] == 'extract' else cmd_apply)()
