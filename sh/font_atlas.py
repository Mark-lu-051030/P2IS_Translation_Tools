# font_atlas.py - 生成带索引标号的字符总览
from PIL import Image, ImageDraw, ImageFont

data = open("/home/mark/Code/ROMHacking/games/Persona2IS/extrac/D/F0086.BIN", "rb").read()

CHAR_W, CHAR_H, CHAR_BYTES = 12, 12, 18
SCALE = 3              # 放大3倍方便看
LABEL_H = 14           # 标号区高度
COLS = 16              # 每行16个字符
START_IDX = 96         # 从upper段开始
TOTAL = 3576

cell_w = CHAR_W * SCALE + 4
cell_h = CHAR_H * SCALE + LABEL_H + 4
rows = (TOTAL + COLS - 1) // COLS

img = Image.new('RGB', (COLS * cell_w, rows * cell_h), 'white')
draw = ImageDraw.Draw(img)

try:
    label_font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
except:
    label_font = ImageFont.load_default()

for c in range(TOTAL):
    idx = START_IDX + c
    cx = (c % COLS) * cell_w + 2
    cy = (c // COLS) * cell_h + LABEL_H

    # 标号
    draw.text((cx, cy - LABEL_H), str(idx), fill='blue', font=label_font)

    # 读字符位
    off = 0x480 + c * CHAR_BYTES
    bits = []
    for b in data[off:off + CHAR_BYTES]:
        for bit in range(8):
            bits.append((b >> bit) & 1)
    
    # 画字符
    for row in range(CHAR_H):
        for col in range(CHAR_W):
            if bits[row * CHAR_W + col]:
                x0 = cx + col * SCALE
                y0 = cy + row * SCALE
                draw.rectangle([x0, y0, x0 + SCALE - 1, y0 + SCALE - 1], fill='black')

img.save('/tmp/font_atlas.png')
print(f"已生成 {TOTAL} 个字符的图册: /tmp/font_atlas.png")
print(f"图片尺寸: {img.size}, 行数: {rows}")
