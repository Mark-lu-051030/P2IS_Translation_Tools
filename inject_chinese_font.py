"""
把中文字符的 bitmap 写入 F0086.BIN 的空闲槽，并更新 codetable.json。
用法: python3 inject_chinese_font.py
"""
import json, shutil, re
from PIL import Image, ImageDraw, ImageFont

FONT_BIN   = '/home/mark/Code/ROMHacking/games/Persona2IS/extrac/D/F0086.BIN'
TTF_PATH   = '/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf'
CODETABLE  = 'codetable.json'
FIRST_SLOT = 2576   # 从这个槽开始分配

# ── 收集需要注入的汉字 ────────────────────────────────────────
data = json.load(open('all_translatable.json', encoding='utf-8'))
needed = set()
for entry in data:
    for page in entry['pages']:
        zh = page.get('zh', '')
        if not zh:
            continue
        clean = re.sub(r'<[^>]+/?>', '', zh)
        for c in clean:
            if '一' <= c <= '鿿' or '㐀' <= c <= '䶿':
                needed.add(c)

needed = sorted(needed)
print(f'需要注入 {len(needed)} 个汉字')

# ── 加载现有 codetable ────────────────────────────────────────
ct = json.load(open(CODETABLE, encoding='utf-8'))
# 反查已有分配，避免重复
existing = {v: int(k) for k, v in ct.items() if len(v) == 1}

# ── 分配槽位 ─────────────────────────────────────────────────
assignments = {}   # char → slot_index
slot = FIRST_SLOT
for ch in needed:
    if ch in existing:
        assignments[ch] = existing[ch]
    else:
        while str(slot) in ct and ct[str(slot)] and not ct[str(slot)].startswith('[?'):
            slot += 1
        assignments[ch] = slot
        slot += 1

print(f'槽位分配完成，最高槽: {max(assignments.values())}')

# ── 渲染 bitmap ───────────────────────────────────────────────
try:
    ttf = ImageFont.truetype(TTF_PATH, 11)
except:
    ttf = ImageFont.load_default()

def render_char(ch):
    img = Image.new('L', (12, 12), 0)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), ch, font=ttf)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    x = (12 - w) // 2 - bbox[0]
    y = (12 - h) // 2 - bbox[1]
    draw.text((x, y), ch, fill=255, font=ttf)
    # 转成 1-bit 列表 (144个bit，LSB-first行优先)
    pixels = list(img.getdata())
    return [1 if p > 64 else 0 for p in pixels]

def pack_bitmap(bits):
    """144 bits → 18 bytes，LSB-first"""
    result = bytearray(18)
    for i, b in enumerate(bits):
        if b:
            result[i // 8] |= (1 << (i % 8))
    return bytes(result)

# ── 写入 F0086.BIN ────────────────────────────────────────────
shutil.copy(FONT_BIN, FONT_BIN + '.bak')
font_data = bytearray(open(FONT_BIN, 'rb').read())

for ch, idx in assignments.items():
    bits = render_char(ch)
    bmp  = pack_bitmap(bits)
    off  = 0x480 + idx * 18
    font_data[off:off+18] = bmp

with open(FONT_BIN, 'wb') as f:
    f.write(font_data)
print(f'已写入 F0086.BIN（备份: F0086.BIN.bak）')

# ── 更新 codetable.json ───────────────────────────────────────
for ch, idx in assignments.items():
    ct[str(idx)] = ch

with open(CODETABLE, 'w', encoding='utf-8') as f:
    json.dump(ct, f, ensure_ascii=False, separators=(',', ':'))
print(f'已更新 codetable.json')

# ── 输出分配表供检查 ──────────────────────────────────────────
print('\n字符 → 槽位:')
for ch in needed:
    print(f'  {ch} → {assignments[ch]}')
