#!/usr/bin/env python3
# 命名界面 UI 文本汉化(零字形注入版)。
# 字源: file59 sub1 = 独立 JIS 序字库(哨兵实验实锤, 2026-06-11);
# 文本: file61 偏移 20480 = 盘扇区 66686, 未压缩, u16LE JIS 槽号序列 → 原位等长替换即可。
# 槽号 = codetable_jis.json(位图匹配) + 一水准公式 170+(区-16)*94+(点-1)。
# 译文只用 JIS 字库已有字(平仮名/確定/輸入…), 不动字库一个字节。
# 垫片 = 槽 0(全零字形, 渲染空白)。写前校验原文(可解码位须等于预期 jp), 自动备份扇区。
# 用法: python3 subfile1/apply_naming.py [restore]
import json, os, struct, subprocess, sys

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
WORK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
SECTOR, BO = 0x930, 24
SEC = 66686                      # file61 (block 66676) + 10, 命名界面字符串页
BAK = 'subfile1/naming_sector66686.bak'
PAD = 0                          # 槽 0 = 全零字形(空白)

jis = json.load(open('codetable_jis.json', encoding='utf-8'))
slot2ch = {int(k): v for k, v in jis.items()}
ch2slot = {v: int(k) for k, v in jis.items()}
# M4b: 注入的简体字扩展槽(inject_naming_glyphs 产出, 须先跑注入再跑本脚本)
EXT = 'subfile1/codetable_jis_ext.json'
if os.path.exists(EXT):
    for k, v in json.load(open(EXT, encoding='utf-8')).items():
        slot2ch[int(k)] = v
        ch2slot[v] = int(k)
def slot_of(ch):
    if ch in ch2slot: return ch2slot[ch]
    b = ch.encode('euc_jp', errors='ignore')
    if len(b) == 2 and b[0] - 0xA0 >= 16:
        s = 170 + (b[0] - 0xA0 - 16) * 94 + (b[1] - 0xA0 - 1)
        if s < 3576: return s
    return None

# (扇区内字节偏移, 预期原文, 译文)。译文 ≤ 原文长, 余位垫 PAD。
PAIRS = [   # M4b 简体版(10个简体字形注入 sub1, 其余用 JIS 已有字; 吗/昵/结/项/择 措辞绕开)
    (0x4dc, 'ひらがな',               '平假名'),
    (0x4e8, 'カタカナ',               '片假名'),
    (0x4f4, '漢字',                   '汉字'),
    (0x506, '終了',                   '完成'),
    (0x51e, 'これでよろしいですか?',   '确定使用这个名字?'),
    (0x59a, '入力する文字をひらがなに切り替えます', '切换为平假名输入'),
    (0x5c2, '入力する文字をカタカナに切り替えます', '切换为片假名输入'),
    (0x5ea, '入力する文字を漢字に切り替えます',     '切换为汉字输入'),
    (0x60e, '入力する文字を英数字に切り替えます',   '切换为英数字输入'),
    (0x634, '通称(ニックネーム)の入力に移ります',   '移至通称(別名)输入'),
    (0x65c, '姓名の入力に移ります',     '移至姓名输入'),
    (0x674, '名前の入力を終了します',   '完成名字输入'),
    (0x68e, '入力する文字を選択してください', '请选取要输入的文字'),
    (0x6b0, '全ての項目を入力してください',   '请输入全部内容'),
    (0x538, 'はい',                   '是'),
    (0x540, 'いいえ',                 '否'),
]

f = open(WORK, 'r+b')
f.seek(SEC * SECTOR + BO)
sec = bytearray(f.read(2048))

if 'restore' in sys.argv:
    if not os.path.exists(BAK): sys.exit('无备份可还原')
    sec[:] = open(BAK, 'rb').read()
    f.seek(SEC * SECTOR + BO); f.write(sec); f.close()
    subprocess.run(['python3', 'fix_ecc.py', str(SEC), str(SEC)], check=True, stdout=subprocess.DEVNULL)
    sys.exit('✅ 已还原原文')

if not os.path.exists(BAK):
    open(BAK, 'wb').write(bytes(sec))

wrote = 0
for off, jp, zh in PAIRS:
    # 写前校验: 可解码的位必须与预期 jp 一致(が/い 等未映射假名按通配跳过)
    bad = []
    for i, ch in enumerate(jp):
        v = struct.unpack_from('<H', sec, off + i * 2)[0]
        got = slot2ch.get(v)
        if got is not None and got != ch:
            bad.append((i, ch, got))
    if bad:
        print(f'✗ 0x{off:x} 原文校验失败 {bad[:3]} — 跳过(可能已翻或偏移错)')
        continue
    codes = [slot_of(c) for c in zh]
    if None in codes or len(zh) > len(jp):
        print(f'✗ 0x{off:x} 译文缺字/超长 — 跳过'); continue
    for i, c in enumerate(codes):
        struct.pack_into('<H', sec, off + i * 2, c)
    M, L = len(zh), len(jp)
    if M < L:
        # 早终止: 紧跟文本写 0x1101 0x1103(原条目结尾同款) → UI 按真实长度居中。
        # 字符串经 file61@0x3384 指针表寻址, 终止符后的残留字节不会被读。
        struct.pack_into('<H', sec, off + M * 2, 0x1101)
        struct.pack_into('<H', sec, off + (M + 1) * 2, 0x1103)
        for i in range(M + 2, L):
            struct.pack_into('<H', sec, off + i * 2, PAD)
    wrote += 1
    print(f'✓ 0x{off:x} {jp[:10]}… → {zh}')

f.seek(SEC * SECTOR + BO); f.write(sec); f.close()
subprocess.run(['python3', 'fix_ecc.py', str(SEC), str(SEC)], check=True, stdout=subprocess.DEVNULL)
print(f'✅ 写回 {wrote}/{len(PAIRS)} 条 + ECC 已修 (备份: {BAK}; 还原: python3 subfile1/apply_naming.py restore)')
