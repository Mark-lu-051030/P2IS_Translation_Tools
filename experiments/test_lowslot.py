"""
测试脚本：把 吗 的 bitmap 注入到低编号空槽（1876），
并临时把对话中的 2602 换成 1876，验证高槽位是否是问题所在。

如果用这个测试通过了，说明游戏对槽号有上限限制。
"""
import json, struct, subprocess

FONT_BIN  = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/extrac/D/F0086.BIN'
ISO_PATH  = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
SECTOR    = 2352
BLOCK_OFF = 0x18
BLOCK_SIZE = 0x800
TEST_SLOT  = 1876   # 空槽，低于 2576 限制

# ── 读取 slot 2602 的 bitmap（已有 吗 的图案）──────────────────────
font_data = bytearray(open(FONT_BIN, 'rb').read())
src_off = 0x480 + 2602 * 18
dst_off = 0x480 + TEST_SLOT * 18
bmp = font_data[src_off:src_off+18]
print(f'Slot 2602 bitmap: {bmp.hex()}')
print(f'非零: {any(b != 0 for b in bmp)}')

# ── 把同样的 bitmap 写到 slot 1876 ────────────────────────────────
font_data[dst_off:dst_off+18] = bmp
open(FONT_BIN, 'wb').write(font_data)
print(f'已将 bitmap 复制到 slot {TEST_SLOT}')

# ── 写回 ISO ──────────────────────────────────────────────────────
def _read_sectors(f, block, size):
    out = bytearray()
    sec = block * SECTOR
    while len(out) < size:
        f.seek(sec)
        raw = f.read(SECTOR)
        chunk = min(BLOCK_SIZE, size - len(out))
        out += raw[BLOCK_OFF:BLOCK_OFF + chunk]
        sec += SECTOR
    return bytes(out)

def _write_sectors(f, block, data):
    sec = block * SECTOR
    off = 0
    while off < len(data):
        f.seek(sec)
        raw = bytearray(f.read(SECTOR))
        chunk = min(BLOCK_SIZE, len(data) - off)
        raw[BLOCK_OFF:BLOCK_OFF + chunk] = data[off:off + chunk]
        if chunk < BLOCK_SIZE:
            raw[BLOCK_OFF + chunk:BLOCK_OFF + BLOCK_SIZE] = bytes(BLOCK_SIZE - chunk)
        f.seek(sec)
        f.write(bytes(raw))
        off += chunk
        sec += SECTOR

with open(ISO_PATH, 'r+b') as iso:
    filepos = _read_sectors(iso, 0x17, 0x1b88)
    block    = struct.unpack_from('<I', filepos, 86 * 8)[0]
    orig_sz  = struct.unpack_from('<I', filepos, 86 * 8 + 4)[0]
    assert len(font_data) == orig_sz
    _write_sectors(iso, block, bytes(font_data))
ecc_end = block + (orig_sz + BLOCK_SIZE - 1) // BLOCK_SIZE - 1
subprocess.run(['python3', 'fix_ecc.py', str(block), str(ecc_end)], check=True)
print(f'字体写回 ISO，ECC 修复完成')

# ── 更新 codetable.json 让 encode_zh 知道 吗 = slot 1876 ───────────
ct = json.load(open('codetable.json', encoding='utf-8'))
# 找到 2602 的映射（吗），复制到 1876
char_2602 = ct.get('2602')
ct['1876'] = char_2602
with open('codetable.json', 'w', encoding='utf-8') as f:
    json.dump(ct, f, ensure_ascii=False, separators=(',', ':'))
print(f'codetable.json 已更新：slot {TEST_SLOT} = {char_2602}')

print('\n下一步：')
print('  1. python3 encode_zh.py        # 重新编码（吗 会被分配到 1876）')
print('  2. node apply_zh.mjs 181 8     # 写回对话')
print('  3. 启动新游戏测试')
