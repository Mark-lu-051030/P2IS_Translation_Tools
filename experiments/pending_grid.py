"""生成所有待定字符([?N])的预览大图"""
import json
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = '/home/mark/Code/ROMHacking/games/Persona2IS/extrac/D/F0086.BIN'
CODETABLE  = 'codetable.json'
OUT_IMAGE  = 'pending_grid.png'

SCALE      = 6       # 12×12 → 72×72
COLS       = 16      # 每行几个
PAD        = 4       # 格子内边距
LABEL_H    = 0       # 标签高度（显示索引）
BG         = (20, 20, 20)
FG         = (220, 220, 220)
BORDER     = (60, 60, 60)

font_data = open(FONT_PATH, 'rb').read()

def get_bitmap(idx):
    off = 0x480 + idx * 18
    bits = []
    for row in range(12):
        for col in range(12):
            n = row * 12 + col
            bits.append((font_data[off + n // 8] >> (n % 8)) & 1)
    return bits

data = json.load(open(CODETABLE, encoding='utf-8'))
pending = [(int(k), v) for k, v in data.items()
           if isinstance(v, str) and v.startswith('[?')]
pending.sort()

if not pending:
    print('没有待定条目')
    exit()

print(f'找到 {len(pending)} 个待定字符')

CELL_W = 12 * SCALE + PAD * 2
CELL_H = 12 * SCALE + PAD * 2 + LABEL_H
rows = (len(pending) + COLS - 1) // COLS

img_w = CELL_W * COLS
img_h = CELL_H * rows
img = Image.new('RGB', (img_w, img_h), BG)
draw = ImageDraw.Draw(img)

try:
    label_font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf', 11)
except:
    label_font = ImageFont.load_default()

for qi, (idx, _) in enumerate(pending):
    col = qi % COLS
    row = qi // COLS
    ox = col * CELL_W
    oy = row * CELL_H

    draw.rectangle([ox, oy, ox + CELL_W - 1, oy + CELL_H - 1], outline=BORDER)

    bits = get_bitmap(idx)
    for r in range(12):
        for c in range(12):
            if bits[r * 12 + c]:
                px = ox + PAD + c * SCALE
                py = oy + PAD + r * SCALE
                draw.rectangle([px, py, px + SCALE - 1, py + SCALE - 1], fill=FG)


img.save(OUT_IMAGE)
print(f'已保存 → {OUT_IMAGE}  ({img_w}×{img_h})')
