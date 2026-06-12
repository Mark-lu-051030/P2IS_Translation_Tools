#!/usr/bin/env python3
# M4b: 往 file59 sub1(JIS 命名字库) 注入简体字形。
# 槽位分配钉死在下表(NAMING_EXT)——命名界面文本不进存档,但布局稳定省心。
# 渲染参数与 inject_chinese_font.render_char 完全一致(fusion-pixel 12px, 阈值64, LSB行优先)。
# 本脚本只产出 bitmap JSON,真正写盘(解压→改→compress_to_size→回写)由 inject_naming_glyphs.mjs 做。
# 用法: python3 subfile1/inject_naming_glyphs.py && node subfile1/inject_naming_glyphs.mjs
import json, os
from PIL import Image, ImageDraw, ImageFont

os.chdir(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
TTF = ImageFont.truetype('fusion-pixel-12px.otf', 12)

# 简体字 → sub1 槽位。压缩预算只有 ~103B(原tc 55437 - 最优重压 55334):
#   牺牲槽(有字形但 file61 全文从未引用, 字形换字形几乎不胀): 3224,2897,2896,2895,2894,2892,164
#   空白槽(全零, 每字 ~19B 压缩膨胀, 只能用 3 个): 3575,3574,3573
NAMING_EXT = {
    '为': 3224, '换': 2897, '汉': 2896, '确': 2895, '请': 2894, '输': 2892, '这': 164,
    '选': 3575, '假': 3574, '个': 3573,
}

def render_char(ch):
    img = Image.new('L', (12, 12), 0)
    draw = ImageDraw.Draw(img)
    bbox = draw.textbbox((0, 0), ch, font=TTF)
    w = bbox[2] - bbox[0]; h = bbox[3] - bbox[1]
    x = (12 - w) // 2 - bbox[0]
    y = (12 - h) // 2 - bbox[1]
    draw.text((x, y), ch, fill=255, font=TTF)
    bits = [1 if p > 64 else 0 for p in img.getdata()]
    out = bytearray(18)
    for i, b in enumerate(bits):
        if b: out[i // 8] |= (1 << (i % 8))
    return bytes(out)

payload = {str(slot): list(render_char(ch)) for ch, slot in NAMING_EXT.items()}
json.dump(payload, open('subfile1/naming_glyphs.json', 'w'))
json.dump({str(s): c for c, s in NAMING_EXT.items()},
          open('subfile1/codetable_jis_ext.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(f'✅ 渲染 {len(payload)} 字形 → naming_glyphs.json + codetable_jis_ext.json')
