# render_font.py
data = open("/home/mark/Code/ROMHacking/games/Persona2IS/extrac/D/F0086.BIN", "rb").read()

# IS 字体结构（和EP相同）: 前0x480字节=96个8x12字符, 其余=12x12字符
LOWER_END = 0x480
CHAR_W_LO, CHAR_H_LO = 8, 12  # 每个字符12字节
CHAR_W_HI, CHAR_H_HI = 12, 12  # 每个字符18字节
COLS = 32  # 每行显示32个字符

def render_section(raw, char_w, char_h, char_bytes, cols, filename):
    count = len(raw) // char_bytes
    rows = (count + cols - 1) // cols
    # 输出 PGM 文件（不需要PIL）
    pixels = []
    for c in range(count):
        for row in range(char_h):
            byte_idx = c * char_bytes + row * (char_w // 8)
            # 可能跨多个字节
            for byte_off in range(char_w // 8):
                b = raw[byte_idx + byte_off] if byte_idx + byte_off < len(raw) else 0
                for bit in range(8):
                    pixels.append(1 if (b >> bit) & 1 else 0)

    img_w = cols * char_w
    img_h = rows * char_h
    with open(filename, "w") as f:
        f.write(f"P2\n{img_w} {img_h}\n1\n")
        idx = 0
        for c in range(count):
            cx, cy = (c % cols) * char_w, (c // cols) * char_h
            # 直接按字符写更清晰
        # 简化版：直接按行写
        grid = [[0]*img_w for _ in range(img_h)]
        for c in range(count):
            cx = (c % cols) * char_w
            cy = (c // cols) * char_h
            for row in range(char_h):
                b_start = c * char_bytes + row * (char_w // 8)
                for byte_off in range(char_w // 8):
                    if b_start + byte_off >= len(raw): break
                    b = raw[b_start + byte_off]
                    for bit in range(8):
                        if (b >> bit) & 1:
                            grid[cy + row][cx + byte_off * 8 + bit] = 1
        for row in grid:
            f.write(" ".join(map(str, row)) + "\n")

render_section(data[:LOWER_END], 8, 12, 12, COLS, "/tmp/font_lower.pgm")
render_section(data[LOWER_END:], 12, 12, 18, COLS, "/tmp/font_upper.pgm")
print(f"lower: {LOWER_END//12} chars, upper: {(len(data)-LOWER_END)//18} chars")
