#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
edit_png.py — 对索引(4bpp/调色板)PNG做矩形涂改 / 植入 fusion-pixel 字体。
支持一次批量改多张图,每张图用各自的「主色/描边色」色号。

为什么用它:battleandmenu/ 里的 F1079.BIN[0]_pNN.png 是 256x256、4bpp、16色
索引图。它们像素内容大体一样,只是 16 张各用一套调色板(颜色不同)。要塞回 ROM
必须始终保持「索引模式 + 原调色板 + 4bpp」。本脚本只在原调色板的 16 个槽里写
索引号,不碰调色板,存盘锁死 bits=4 并保留透明块,逐像素可回插。

子命令:
  info     看尺寸/模式/位深
  palette  列出 16 个调色板槽 (index -> RGB),用来挑主色/描边色号
  rect     用某个色号填一个矩形 (擦掉旧日文)
  text     单张图:用 fusion-pixel 写字,可主色+描边
  batch    多张图一次写同样的字,但每张用各自的 (主色, 描边) 色号

batch 的颜色用「一个列表,每项是对应那张图的元组」:
  --colors "[(3,5),(6,1),(14,0), ...]"     # 第N个元组配排序后第N张图
  --colors-file colors.txt                  # 同样内容写在文件里
  元组 = (主色号, 描边色号);只给一个数或长度1的元组 = 无描边。
  只给一个元组/数 = 所有图共用。

例子:
  python3 edit_png.py palette "battleandmenu/F1079.BIN[0]_p00.png"
  python3 edit_png.py batch --glob "battleandmenu/F1079.BIN[0]_p*.png" \
      --xy 6,18 --text 传闻屋 --erase-box 4,16,64,30 --bg 0 \
      --colors "[(3,5),(6,1),(3,0),(14,8),(2,0),(6,5),(3,0),(7,0),(10,2),(3,0),(3,0),(1,6),(14,0),(3,0),(3,0),(3,0)]"

不写 --out/--out-dir/--inplace 默认每张存成 <名字>.edit.png,绝不覆盖原图。
"""
import argparse, ast, glob, os, sys
from PIL import Image, ImageDraw, ImageFont, ImageChops

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_FONTS = [
    os.path.join(HERE, "..", "fusion-pixel-12px.otf"),
    os.path.join(HERE, "..", "artifacts", "fusion-pixel",
                 "fusion-pixel-12px-monospaced-zh_hant.otf"),
]


# ---------- 索引图 IO ----------

def load_indexed(path):
    im = Image.open(path)
    if im.mode != "P":
        sys.exit(f"✗ {path} 不是索引(P)模式,而是 {im.mode},拒绝处理。")
    im.load()
    return im, im.getpalette()


def save_indexed(im, pal, out):
    im.putpalette(pal)                       # 锁死原调色板,顺序不变
    im.save(out, format="PNG", bits=4)       # 强制 4bpp;透明块由 im.info 自动带出


# ---------- 解析 ----------

def parse_box(s):
    v = [int(x) for x in s.split(",")]
    if len(v) != 4:
        sys.exit("box 需要 x0,y0,x1,y1 四个数")
    return v


def parse_xy(s):
    v = [int(x) for x in s.split(",")]
    if len(v) != 2:
        sys.exit("--xy 需要 x,y 两个数")
    return v


def _i(v):
    return None if v is None else int(v)


def norm_color(entry):
    """把一项归一成 (字身, 描边, 高光, 阴影),缺的为 None。按元组长度区分模式:
        N 或 (N,)        -> 纯填充
        (身, 描边)        -> 描边模式
        (身, 高, 阴)      -> 浮雕模式 (顶高光/底阴影)
        (身, 描边, 高, 阴) -> 描边+浮雕
    """
    if isinstance(entry, int):
        return (entry, None, None, None)
    if isinstance(entry, (tuple, list)):
        e = [None if v is None else int(v) for v in entry]
        if len(e) == 1:
            return (e[0], None, None, None)
        if len(e) == 2:
            return (e[0], e[1], None, None)
        if len(e) == 3:
            return (e[0], None, e[1], e[2])
        if len(e) == 4:
            return (e[0], e[1], e[2], e[3])
    sys.exit(f"颜色项 {entry!r} 非法。应为 N / (身,描边) / (身,高,阴) / (身,描边,高,阴)")


def parse_colors(spec, n_files):
    """spec 可以是 Python 字面量字符串。返回长度 == n_files 的 [(主,描边)...]。"""
    val = ast.literal_eval(spec)
    # 单个数,或第一项不是元组 = 单个颜色项 -> 广播给所有图
    if isinstance(val, int) or (isinstance(val, (tuple, list))
                                and val and not isinstance(val[0], (tuple, list))):
        return [norm_color(val)] * n_files
    cols = [norm_color(e) for e in val]
    if len(cols) == 1:
        cols *= n_files
    if len(cols) != n_files:
        sys.exit(f"✗ 颜色元组数 {len(cols)} 与图片数 {n_files} 不符。"
                 f"要么给 1 组(全部共用),要么给 {n_files} 组。")
    return cols


def find_font(font_arg):
    for f in ([font_arg] if font_arg else []) + DEFAULT_FONTS:
        if f and os.path.exists(f):
            return f
    sys.exit("✗ 找不到字体")


def pick_out(path, args):
    if getattr(args, "inplace", False):
        return path
    if getattr(args, "out", None):
        return args.out
    root, ext = os.path.splitext(path)
    return root + ".edit" + ext


# ---------- 核心绘制 ----------

def _mask(size, xy, text, font, spacing, stroke_width, stroke):
    """渲染一张二值蒙版 (L 模式, 0/255)。stroke=True 时含描边外扩。"""
    m = Image.new("L", size, 0)
    d = ImageDraw.Draw(m)
    if stroke and stroke_width > 0:
        d.text(xy, text, font=font, fill=255, spacing=spacing,
               stroke_width=stroke_width, stroke_fill=255)
    else:
        d.text(xy, text, font=font, fill=255, spacing=spacing)
    return m.point(lambda v: 255 if v >= 128 else 0)


def _edge(mask, dy):
    """取边缘:dy=1 -> 顶边(上方是空的那圈像素);dy=-1 -> 底边。"""
    return ImageChops.subtract(mask, ImageChops.offset(mask, 0, dy))


def draw_text(im, xy, text, font, fg, outline, hi, sh, stroke_width, spacing):
    """像素字体写字。叠加顺序:描边(外圈) -> 字身 -> 底阴影 -> 顶高光。
    只写调色板索引,不碰调色板。hi/sh 给了就是浮雕模式。"""
    body = _mask(im.size, xy, text, font, spacing, 0, stroke=False)
    if outline is not None and stroke_width > 0:
        im.paste(outline, (0, 0), _mask(im.size, xy, text, font, spacing,
                                        stroke_width, stroke=True))
    im.paste(fg, (0, 0), body)
    if sh is not None:
        im.paste(sh, (0, 0), _edge(body, -1))    # 底边
    if hi is not None:
        im.paste(hi, (0, 0), _edge(body, 1))     # 顶边 (最后画,最显眼)


# ---------- 子命令 ----------

def cmd_info(args):
    im = Image.open(args.png)
    pal = im.getpalette() or []
    print(f"{args.png}\n  size={im.size} mode={im.mode} 调色板色数={len(pal)//3}")


def cmd_palette(args):
    im, pal = load_indexed(args.png)
    n = min(16, len(pal) // 3)
    print(f"{args.png} 调色板 (前 {n} 槽):")
    for i in range(n):
        r, g, b = pal[i*3:i*3+3]
        print(f"  index {i:2d} = ({r:3d},{g:3d},{b:3d}){'  ██' if r+g+b else '  ··'}")


def cmd_rect(args):
    im, pal = load_indexed(args.png)
    box = parse_box(args.box)
    ImageDraw.Draw(im).rectangle(box, fill=args.index)
    out = pick_out(args.png, args)
    save_indexed(im, pal, out)
    print(f"✓ 矩形 {box} 填色号 {args.index} -> {out}")


def cmd_text(args):
    im, pal = load_indexed(args.png)
    x, y = parse_xy(args.xy)
    if args.erase_box:
        ImageDraw.Draw(im).rectangle(parse_box(args.erase_box), fill=args.bg)
    font = ImageFont.truetype(find_font(args.font), args.size)
    draw_text(im, (x, y), args.text, font, args.fg, args.outline,
              args.hi, args.sh, args.stroke_width, args.spacing)
    out = pick_out(args.png, args)
    save_indexed(im, pal, out)
    print(f"✓ 写「{args.text}」身{args.fg} 描边{args.outline} 高光{args.hi} "
          f"阴影{args.sh} @({x},{y}) -> {out}")


def glob_files(pattern):
    """匹配文件。文件名里的字面 [ ] (如 F1079.BIN[0]) 会被转义,* ? 仍是通配。"""
    esc = pattern.replace("[", "\0L").replace("]", "\0R")
    esc = esc.replace("\0L", "[[]").replace("\0R", "[]]")
    files = glob.glob(esc)
    return files if files else glob.glob(pattern)  # 回退:允许有意的字符类


def cmd_batch(args):
    files = sorted(glob_files(args.glob))
    if not files:
        sys.exit(f"✗ glob 没匹配到文件: {args.glob}")
    spec = open(args.colors_file, encoding="utf-8").read() if args.colors_file else args.colors
    if not spec:
        sys.exit("✗ batch 需要 --colors 或 --colors-file")
    colors = parse_colors(spec, len(files))

    x, y = parse_xy(args.xy)
    box = parse_box(args.erase_box) if args.erase_box else None
    font = ImageFont.truetype(find_font(args.font), args.size)
    if args.out_dir:
        os.makedirs(args.out_dir, exist_ok=True)

    print(f"批量处理 {len(files)} 张图,写「{args.text}」@({x},{y}):")
    for path, (fg, outline, hi, sh) in zip(files, colors):
        im, pal = load_indexed(path)
        if box:
            ImageDraw.Draw(im).rectangle(box, fill=args.bg)
        draw_text(im, (x, y), args.text, font, fg, outline, hi, sh,
                  args.stroke_width, args.spacing)
        if args.inplace:
            out = path
        elif args.out_dir:
            out = os.path.join(args.out_dir, os.path.basename(path))
        else:
            root, ext = os.path.splitext(path)
            out = root + ".edit" + ext
        save_indexed(im, pal, out)
        print(f"  {os.path.basename(path):32s} 身{fg} 描边{outline} 高{hi} 阴{sh} -> {out}")


# ---------- CLI ----------

def add_text_opts(p):
    p.add_argument("--xy", required=True, help="文字左上角 x,y")
    p.add_argument("--text", required=True)
    p.add_argument("--size", type=int, default=12, help="字号,像素字体设计值=12 (用12/24..)")
    p.add_argument("--font", help="覆盖字体路径")
    p.add_argument("--stroke-width", type=int, default=1, help="描边粗细(px),0=不描边")
    p.add_argument("--spacing", type=int, default=0, help="行间距")
    p.add_argument("--erase-box", help="画字前先擦这个框 x0,y0,x1,y1")
    p.add_argument("--bg", type=int, default=0, help="擦框/背景用的色号(默认0=透明槽)")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("info"); p.add_argument("png"); p.set_defaults(fn=cmd_info)
    p = sub.add_parser("palette"); p.add_argument("png"); p.set_defaults(fn=cmd_palette)

    p = sub.add_parser("rect")
    p.add_argument("png"); p.add_argument("--box", required=True)
    p.add_argument("--index", type=int, required=True)
    p.add_argument("--out"); p.add_argument("--inplace", action="store_true")
    p.set_defaults(fn=cmd_rect)

    p = sub.add_parser("text")
    p.add_argument("png"); add_text_opts(p)
    p.add_argument("--fg", type=int, required=True, help="字身色号")
    p.add_argument("--outline", type=int, default=None, help="描边色号(外圈,不给=无)")
    p.add_argument("--hi", type=int, default=None, help="顶边高光色号(浮雕用)")
    p.add_argument("--sh", type=int, default=None, help="底边阴影色号(浮雕用)")
    p.add_argument("--out"); p.add_argument("--inplace", action="store_true")
    p.set_defaults(fn=cmd_text)

    p = sub.add_parser("batch")
    p.add_argument("--glob", required=True, help="匹配多张图,如 'dir/*.png'")
    add_text_opts(p)
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--colors", help="Python字面量: [(主,描边),...] 每图一项")
    g.add_argument("--colors-file", help="同上内容放在文件里")
    p.add_argument("--out-dir", help="输出目录(默认原地生成 .edit.png)")
    p.add_argument("--inplace", action="store_true", help="直接覆盖原图")
    p.set_defaults(fn=cmd_batch)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
