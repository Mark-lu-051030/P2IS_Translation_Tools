# render_upper_v2.py
data = open("/home/mark/Code/ROMHacking/games/Persona2IS/extrac/D/F0086.BIN", "rb").read()
LOWER_END = 0x480
upper = data[LOWER_END:]
CHAR_W, CHAR_H, CHAR_BYTES = 12, 12, 18
COLS = 32  # 每行32个字符，方便数

count = len(upper) // CHAR_BYTES
rows_count = (count + COLS - 1) // COLS
img_w, img_h = COLS * CHAR_W, rows_count * CHAR_H
grid = [[0]*img_w for _ in range(img_h)]

for c in range(count):
    # 读取这个字符的所有位（LSB优先）
    bits = []
    for b_off in range(CHAR_BYTES):
        b = upper[c * CHAR_BYTES + b_off]
        for bit in range(8):
            bits.append((b >> bit) & 1)
    # bits按行优先排列: pixel(col, row) = bits[row * 12 + col]
    cx = (c % COLS) * CHAR_W
    cy = (c // COLS) * CHAR_H
    for row in range(CHAR_H):
        for col in range(CHAR_W):
            if bits[row * CHAR_W + col]:
                grid[cy + row][cx + col] = 1

with open("/tmp/font_upper.pgm", "w") as f:
    f.write(f"P2\n{img_w} {img_h}\n1\n")
    for row in grid:
        f.write(" ".join(map(str, row)) + "\n")
print(f"chars: {count}, grid: {COLS}×{rows_count}")
