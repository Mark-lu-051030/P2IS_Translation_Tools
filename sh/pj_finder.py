# 渲染单个字符，方便和图对照
def render_char(idx):
    """渲染font索引 idx 的字符"""
    data = open("/home/mark/Code/ROMHacking/games/Persona2IS/extrac/D/F0086.BIN", "rb").read()
    if idx < 96:
        # lower段, 8x12, 12字节
        c_data = data[idx*12:(idx+1)*12]
        for row in range(12):
            line = ''
            for bit in range(8):
                line += '█' if (c_data[row] >> bit) & 1 else '·'
            print(line)
    else:
        # upper段, 12x12, 18字节
        off = 0x480 + (idx - 96) * 18
        c_data = data[off:off+18]
        bits = []
        for b in c_data:
            for i in range(8):
                bits.append((b >> i) & 1)
        for row in range(12):
            print(''.join('█' if bits[row*12+c] else '·' for c in range(12)))

render_char(96)   # 应该是空格
render_char(128)  # 你猜是"零"
render_char(139)  # 你猜是"あ"
# 试 200~300 之间几个看看
