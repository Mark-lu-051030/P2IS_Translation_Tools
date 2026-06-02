"""扫描 working ISO 某个区域/文件，列出所有还是日文的文本串。
用于"自助翻译菜单"——确认某块是否全部翻完。

用法:
  python3 scan_untranslated.py free 271864 4     # 扫游离区 sector 271864 起 4 个 sector
  python3 scan_untranslated.py file 84           # 扫 file 84 所有 sub-file
  python3 scan_untranslated.py file 0            # 扫 SLPS（大，慢）

输出：所有含日文假名的连续文本串 + 它们的 offset，让你知道还有哪些没翻。
（中文已翻的不会列出——日文假名 ぁ-ヿ 是判据，全中文则该串不显示）
"""
import sys, struct, json, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors, archive_subfile_offsets, lzss_decompress

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
ct = json.load(open(os.path.join(ROOT, 'codetable.json'), encoding='utf-8'))
# 解码用当前 codetable（含中文），但判断"是否日文"看假名
c2c = {int(k): v for k, v in ct.items() if isinstance(v, str)}

def is_kana(ch):
    return '぀' <= ch <= 'ヿ'   # 平假名+片假名

def scan_buffer(buf, label):
    """扫一段 buffer，按 0x1103 分隔，列出含假名的串。"""
    found = []
    i = 0; cur = ''; start = 0
    while i < len(buf) - 1:
        c = struct.unpack_from('<H', buf, i)[0]; i += 2
        if c == 0x1103:
            if cur.strip() and any(is_kana(x) for x in cur):
                found.append((start, cur))
            cur = ''; start = i
        elif c == 0x1101:
            cur += '\\n'
        elif 0x1100 <= c < 0x1200:
            cur += f'<c{c&0xff:02x}>'
        elif c in c2c:
            if not cur: start = i - 2
            cur += c2c[c]
        else:
            if cur.strip() and any(is_kana(x) for x in cur):
                found.append((start, cur))
            cur = ''
    return found

def main():
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(1)
    mode = sys.argv[1]

    if mode == 'free':
        sec = int(sys.argv[2])
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 2
        buf = read_sectors(ISO, sec, n * 2048)
        found = scan_buffer(buf, f'游离区 sector {sec}')
        print(f'=== 游离区 sector {sec} (+{n} sectors) 还含日文的串: {len(found)} ===')
        for off, txt in found:
            print(f'  @{off:#x}: {txt[:50]!r}')

    elif mode == 'file':
        fid = int(sys.argv[2])
        fp = read_sectors(ISO, 0x17, 4 * 2048)
        b, sz = struct.unpack_from('<II', fp, fid * 8)
        arch = read_sectors(ISO, b, sz)
        # file 0 太大特殊处理：直接扫整块
        if fid == 0:
            found = scan_buffer(arch[:200000], 'SLPS 前 200KB')
            print(f'=== file 0 (SLPS) 还含日文的串: {len(found)} (前200KB) ===')
            for off, txt in found[:60]:
                print(f'  @{off:#x}: {txt[:40]!r}')
            return
        try:
            subs = archive_subfile_offsets(arch)
        except Exception as e:
            print(f'archive 解析失败: {e}'); return
        total = 0
        for si, (o, l) in enumerate(subs):
            s = arch[o:o+l]
            if s[1] not in (1, 2):  # 非压缩 sub，直接扫
                found = scan_buffer(s, f'sub{si}')
            else:
                try:
                    tc = struct.unpack_from('<I', s, 4)[0]
                    uc = struct.unpack_from('<I', s, 8)[0]
                    d = lzss_decompress(s, 12, tc-12, uc)
                    found = scan_buffer(d, f'sub{si}')
                except Exception:
                    continue
            if found:
                total += len(found)
                print(f'  file {fid} sub {si}: {len(found)} 条日文')
                for off, txt in found[:5]:
                    print(f'    @{off:#x}: {txt[:40]!r}')
        print(f'\n=== file {fid} 共 {total} 条还含日文 ===')

if __name__ == '__main__':
    main()
