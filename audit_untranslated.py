"""全盘审计：扫 working ISO，列出所有还含日文假名的文本串 + 位置。
用于"找全没翻的菜单/名字"，不靠打通关。

原理：扫已 build 的 working ISO。已翻内容用原版码表(og)解码会变成乱码汉字（无假名），
只有真·没翻的日文才含平/片假名。所以"连续 og 可解码 + 含假名 + 长度≥3"能天然
过滤掉已翻中文和二进制噪声，精准抓漏网日文。

覆盖：
  - free region（FILEPOS 未占用的扇区）→ 设置菜单/Persona名/道具名/存档主菜单等
  - 全部 881 个 FILEPOS 文件的每个 sub-file（raw / LZSS 解压；RLE 跳过并计数）

用法:
  python3 audit_untranslated.py              # 全扫，写 out/audit_untranslated.txt
  python3 audit_untranslated.py --free       # 只扫 free region（快）
  python3 audit_untranslated.py --files      # 只扫 FILEPOS 文件
"""
import sys, struct, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors, archive_subfile_offsets, lzss_decompress, BLOCK_SIZE

ROOT = os.path.dirname(os.path.abspath(__file__))
WK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
OGMAP = {int(k): v for k, v in og.items() if isinstance(v, str) and len(v) == 1}
OUT = os.path.join(ROOT, 'out', 'audit_untranslated.txt')

MIN_LEN = 3   # 文本串最少可见字符数

def is_kana(ch):
    return '぀' <= ch <= 'ヿ'   # 平假名 + 片假名

def looks_texty(s):
    """剔除填充/图形噪声：真文本字符多样，padding 是同一字符反复。"""
    clean = s.replace('\\n', '')
    if len(clean) < MIN_LEN:
        return False
    if len(set(clean)) < 3:                       # 字符种类太少
        return False
    from collections import Counter
    most = Counter(clean).most_common(1)[0][1]
    if most > len(clean) * 0.5:                   # 单字符占比 >50% = 填充噪声
        return False
    return sum(is_kana(x) for x in clean) >= 2     # 至少2个假名（1个多为二进制误报）

def scan_runs(buf):
    """扫一段 buffer，返回 [(offset, 文本)]：连续 og 可解码、含假名、长度≥MIN_LEN 的串。"""
    out = []
    i = 0; cur = ''; start = 0
    n = len(buf) - 1
    while i < n:
        c = buf[i] | (buf[i + 1] << 8); i += 2
        ch = OGMAP.get(c)
        if ch is not None:
            if not cur:
                start = i - 2
            cur += ch
        elif c == 0x1101:        # 换行，文本内部，保持连续
            cur += '\\n'
        else:
            if looks_texty(cur):
                out.append((start, cur))
            cur = ''
    if looks_texty(cur):
        out.append((start, cur))
    return out

def free_ranges():
    """返回 FILEPOS 未占用的扇区区间 [(lba_start, lba_end_exclusive)]（跳过前 200 系统区）。"""
    fp = read_sectors(WK, 0x17, 4 * 2048)
    covered = set()
    for i in range(881):
        b, s = struct.unpack_from('<II', fp, i * 8)
        if s > 0:
            for k in range((s + BLOCK_SIZE - 1) // BLOCK_SIZE):
                covered.add(b + k)
    tot = os.path.getsize(WK) // 2352
    ranges = []; run_start = None
    for lba in range(200, tot):
        if lba not in covered:
            if run_start is None: run_start = lba
        else:
            if run_start is not None: ranges.append((run_start, lba)); run_start = None
    if run_start is not None: ranges.append((run_start, tot))
    return ranges

NOISE_FREQ = 8   # 同一串出现 > 此次数 = 结构化二进制噪声，剔除

def dedup_filter(items):
    """items=[(loc, txt)]；剔除高频重复（结构噪声），返回 [(loc, txt, count)] 唯一串。"""
    from collections import Counter
    freq = Counter(t for _, t in items)
    seen = set(); out = []
    for loc, txt in items:
        if freq[txt] > NOISE_FREQ:    # 重复太多次 = 噪声
            continue
        if txt in seen:
            continue
        seen.add(txt)
        out.append((loc, txt, freq[txt]))
    return out

def cluster(found, gap=2, min_size=6):
    """把按 offset 排序的命中聚成簇（相邻命中所在扇区间隔 ≤ gap）。
    只保留 ≥min_size 的簇 = 密集文本表；散落的二进制噪声被丢弃。
    found=[(abs_off, sec, txt)] 已排序。返回 [(sec0, sec1, [txt...])]。"""
    clusters = []; cur = []
    last_sec = None
    for off, sec, txt in found:
        if last_sec is None or sec - last_sec <= gap:
            cur.append((sec, txt))
        else:
            if len(cur) >= min_size: clusters.append(cur)
            cur = [(sec, txt)]
        last_sec = sec
    if len(cur) >= min_size: clusters.append(cur)
    return clusters

def audit_free(w):
    print('=== 扫 free region（按文本簇聚合）===')
    w.write('=== FREE REGION (clusters) ===\n')
    total = 0
    for lo, hi in free_ranges():
        if hi - lo < 1: continue
        buf = read_sectors(WK, lo, (hi - lo) * BLOCK_SIZE)
        raw = scan_runs(buf)
        if not raw: continue
        # 去重 + 高频噪声剔除，保留绝对 offset 以便聚簇
        from collections import Counter
        freq = Counter(t for _, t in raw)
        seen = set(); pts = []
        for off, txt in raw:
            if freq[txt] > NOISE_FREQ or txt in seen: continue
            seen.add(txt); pts.append((off, lo + off // BLOCK_SIZE, txt))
        for cl in cluster(pts):
            s0, s1 = cl[0][0], cl[-1][0]
            line = f'\n[簇] 扇区 {s0}-{s1}  {len(cl)} 条日文'
            print(line); w.write(line + '\n')
            total += len(cl)
            for sec, txt in cl:
                w.write(f'  扇区{sec}: {txt[:60]!r}\n')
            for sec, txt in cl[:10]:
                print(f'    扇区{sec}: {txt[:40]!r}')
    print(f'\nfree region 文本簇共 {total} 条日文')
    w.write(f'\nfree region 簇合计: {total} 条\n')
    return total

def audit_files(w):
    print('\n=== 扫 FILEPOS 全部文件 ===')
    w.write('\n=== FILEPOS FILES ===\n')
    fp = read_sectors(WK, 0x17, 4 * 2048)
    total = 0; rle_skip = 0; hit_files = 0
    for fid in range(881):
        b, sz = struct.unpack_from('<II', fp, fid * 8)
        if sz == 0: continue
        try:
            arch = read_sectors(WK, b, sz)
        except Exception:
            continue
        try:
            subs = archive_subfile_offsets(arch)
        except Exception:
            subs = [(0, len(arch))]
        file_found = []
        for si, (o, l) in enumerate(subs):
            s = arch[o:o + l]
            comp = s[1] if len(s) > 1 else 0
            try:
                if comp == 2:
                    tc = struct.unpack_from('<I', s, 4)[0]
                    uc = struct.unpack_from('<I', s, 8)[0]
                    data = lzss_decompress(s, 12, tc - 12, uc)
                elif comp == 1:
                    rle_skip += 1
                    continue   # RLE = 已翻剧情脚本，跳过
                else:
                    data = s
            except Exception:
                continue
            for off, txt in scan_runs(bytes(data)):
                file_found.append((si, off, txt))
        if file_found:
            hit_files += 1; total += len(file_found)
            line = f'\n[file {fid}] block={b} {len(file_found)} 条日文'
            print(line); w.write(line + '\n')
            for si, off, txt in file_found:
                w.write(f'  sub{si} @{off:#x}: {txt[:60]!r}\n')
            for si, off, txt in file_found[:5]:
                print(f'    sub{si} @{off:#x}: {txt[:40]!r}')
    print(f'\nFILEPOS 文件：{hit_files} 个文件含日文，共 {total} 条（跳过 {rle_skip} 个 RLE 脚本 sub）')
    w.write(f'\nFILEPOS 合计: {total} 条, {hit_files} 文件, 跳过 {rle_skip} RLE\n')
    return total

def main():
    only_free = '--free' in sys.argv
    only_files = '--files' in sys.argv
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as w:
        t = 0
        if not only_files: t += audit_free(w)
        if not only_free:  t += audit_files(w)
        print(f'\n✅ 共 {t} 条漏网日文，完整列表: {OUT}')

if __name__ == '__main__':
    main()
