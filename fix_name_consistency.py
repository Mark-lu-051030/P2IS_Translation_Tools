#!/usr/bin/env python3
# 角色译名统一(术语去重)。早期按文件分批翻译无统一术语表 → 同角色多译名。
# 本次(2026-06-12, 玩家反馈):
#   噂屋パオフゥ(P2EP 反派 Baofu 在 IS 的客串身份):
#       传闻屋Pao Fu / Pao Fu / 传闻贩子帕乌夫 / 传闻屋帕乌夫 / 帕乌夫 → 统一「传闻屋Baofu」/「Baofu」
#       身份称呼 传闻贩子 → 传闻屋(玩家选定)
#   芹沢うらら(官方英文 Ulala, 舞耶闺蜜):
#       丽丽 / 乌啦啦 / 乌拉拉 / 拉拉 → 统一「丽」(玩家选定)
# 真相源: all_translatable.json(对话 script: + 字符串表 strtbl: 都从这读) + out/field_text_zh.json(field)。
# nametable「普拉拉亚」含「拉拉」是误伤, 不动; script_577「丽丽丽，丽莎同学」是结巴喊丽莎(Lisa), 受 (?<!丽)丽丽(?!丽) 保护。
# 用法: python3 fix_name_consistency.py        # DRY-RUN, 只打印 diff
#       python3 fix_name_consistency.py apply  # 落盘
import json, os, re, sys

os.chdir(os.path.dirname(os.path.abspath(__file__)))
APPLY = 'apply' in sys.argv

# (正则, 替换)。顺序敏感: 长复合在前, 独立残项在后。
RULES = [
    # --- Baofu ---
    # (re.compile(r'传闻贩子帕乌夫'), '传闻屋Baofu'),
    # (re.compile(r'传闻屋帕乌夫'),   '传闻屋Baofu'),
    # (re.compile(r'传闻贩子Pao Fu'), '传闻屋Baofu'),
    # (re.compile(r'传闻屋Pao Fu'),   '传闻屋Baofu'),
    # (re.compile(r'帕乌夫'),         'Baofu'),
    # (re.compile(r'Pao Fu'),         'Baofu'),
    # (re.compile(r'传闻贩子'),       '传闻屋'),   # 散文/身份称呼
    # # --- Urara → 丽 ---
    # (re.compile(r'乌啦啦'),         '丽'),
    # (re.compile(r'乌拉拉'),         '丽'),
    # (re.compile(r'(?<!丽)丽丽(?!丽)'), '丽'),     # 保护「丽丽丽」结巴喊丽莎
    # (re.compile(r'遇到了拉拉'),     '遇到了丽'),  # field 唯一独立「拉拉」=うらら
    # # --- Lisa(リサ) → 丽莎(全作 1140:7 主流; 2026-06-12 校对批引入「莉莎」分歧, 归一) ---
    # (re.compile(r'莉莉莉'),         '丽丽丽'),     # 结巴「莉莉莉、莉莎同学」(577); 不碰莉莉丝(Lilith)/茉莉
    # (re.compile(r'莉莎'),           '丽莎'),
    # --- Michel(ミシェル) → 米歇尔 ---
    # (re.compile(r'米切'),           '米歇尔'),
    # (re.compile(r'Philemon'),         '费列蒙'),
    # (re.compile(r'菲列蒙'),        '费列蒙'),
    # (re.compile(r'菲莱蒙'),        '费列蒙'),
    # (re.compile(r'伊戈尔'),         '伊格尔'),
    # (re.compile(r'ナナシ'),         '无名'),
    # (re.compile(r'纳纳西'),         '无名'),
    # (re.compile(r'特莉丝'), '特里休'),
    # (re.compile(r'特莉修'), '特里休'),
    # (re.compile(r'翠西'), '特里休'),
    # (re.compile(r'特莉什'), '特里休'),
    # # パンツ番長 -> 内裤番长
    # (re.compile(r'胖次番长'), '内裤番长'),
    # (re.compile(r'内裤老大'), '内裤番长'),
    # (re.compile(r'裤衩番长'), '内裤番长'),
    # (re.compile(r'英理子'), '艾莉'),
    # # シルバーマン -> 希尔巴曼
    # (re.compile(r'希尔瓦曼'), '希尔巴曼'),
    # (re.compile(r'西尔弗曼'), '希尔巴曼'),
    # (re.compile(r'席尔瓦曼'), '希尔巴曼'),
    # (re.compile(r'希尔曼'),   '希尔巴曼'),   # 丽莎·希尔曼 → 丽莎·希尔巴曼
    # # ジュン -> 淳
    # (re.compile(r'(?<![亻])纯(?![\u4e00-\u9fa5])'), '淳'),  # 独立的“纯”替换
    # # パオフゥ / Baofu -> 报复（根据最终译名表）
    # (re.compile(r'Paofu'), 'Baofu'),
    # (re.compile(r'Baofu'), 'Baofu'),
    # # 黛 ゆきの -> 黛雪野
    # (re.compile(r'黛 雪乃'), '黛 雪野'),
    # # ブラウン -> 史棕
    # (re.compile(r'布朗'), '史棕'),
    # # エリー -> 艾莉（注意：原文エリー时用艾莉，英理子是本名，不能替换）
    # # 本规则仅处理错误的音译，不能将所有英理子替换
    # (re.compile(r'埃利'), '艾莉'),  # 如果还有别的错译
    # # ハナジー -> 鼻血子
    # (re.compile(r'花姐'), '鼻血子'),  # 若决定统一，否则可保留
    # # チカリン -> 小知香
    # (re.compile(r'千佳琳'), '小知香'),
    # # みーぽ -> 美宝
    # (re.compile(r'米波'), '美宝'),
    # (re.compile(r'未步'), '美宝'),
    # # あさっち -> 小朝
    # (re.compile(r'阿达'), '小朝'),   # 注意：仅在特定对话中
    # (re.compile(r'小麻'), '小朝'),
    # # 噂屋トロ -> 传言商托罗
    # (re.compile(r'传闻屋托洛'), '传言商托罗'),
    # (re.compile(r'托洛'), '托罗'),
    # # トニー -> 托尼
    # (re.compile(r'Tony'), '托尼'),
    # # イシュキック -> 伊修奇克
    # (re.compile(r'伊什基克'), '伊修奇克'),
    # (re.compile(r'伊修基克'), '伊修奇克'),
    # # レイディ・スコルピオン -> 天蝎座贵妇
    # (re.compile(r'蝎子女王'), '天蝎座贵妇'),
    # (re.compile(r'蝎子女郎'), '天蝎座贵妇'),
    # (re.compile(r'天蝎女士'), '天蝎座贵妇'),
    # # プリンス・トーラス -> 金牛座王子
    # (re.compile(r'托勒斯公子'), '金牛座王子'),
    # (re.compile(r'Prince Taurus'), '金牛座王子'),
    # # クイーン・アクエリアス -> 水瓶座女王
    # (re.compile(r'Queen Aquarius'), '水瓶座女王'),
    # (re.compile(r'水瓶女王'), '水瓶座女王'),
    # # イデアル -> 理想
    # (re.compile(r'伊迪亚老师'), '理想老师'),
    # (re.compile(r'伊甸老师'),   '理想老师'),
    # (re.compile(r'伊迪尔老师'), '理想老师'),
    # # 影人間 -> 影人类
    # (re.compile(r'影人类类类'), '影人类'),
    # # (re.compile(r'影人类类类类'),   '影人类'),
    # # 影達の宴 -> 影子舞会
    # (re.compile(r'影子们的宴席'), '影子舞会'),
    # (re.compile(r'影子们的宴会'), '影子舞会'),
    # # ノリコ -> 典子
    # (re.compile(r'纪子'),   '典子'),
    # (re.compile(r'诺里子'), '典子'),
    # # 恋する女 -> 恋中女子
    # (re.compile(r'恋爱的女人'), '恋中女子'),
    # # 渋いおじさん -> 沉稳大叔
    # (re.compile(r'酷大叔'), '沉稳大叔'),
    # # 住職 -> 方丈
    # (re.compile(r'住持'), '方丈'),
    # # 闘う浪人生 -> 奋战的复读生
    # (re.compile(r'战斗浪人'), '奋战的复读生'),
    # # ちい坊 -> 小不点
    # (re.compile(r'小坊'), '小不点'),
    # # 下町おやじ -> 市井大叔
    # (re.compile(r'老街大叔'), '市井大叔'),
    # # 若い女/若い男 -> 年轻女人/年轻男人
    # (re.compile(r'年轻女子'), '年轻女人'),
    # (re.compile(r'年轻男子'), '年轻男人'),
    # # 口裂け女/クチサケ -> 裂口女
    # (re.compile(r'口裂女'), '裂口女'),
    # # ジャンピングじじい -> 蹦跶老头
    # (re.compile(r'跳跃爷爷'), '蹦跶老头'),
    # (re.compile(r'跳跃老头'), '蹦跶老头'),
    # # クダン -> 件
    # (re.compile(r'九段'), '件'),  # 注意：只在妖怪语境下
    # # たんすババア -> 衣柜婆婆
    # (re.compile(r'衣柜老太婆'), '衣柜婆婆'),
    # (re.compile(r'柜子婆婆'),   '衣柜婆婆'),
    # (re.compile(r'橱柜婆婆'),   '衣柜婆婆'),
    # # メタル・マム -> 合金妈妈
    # (re.compile(r'金属老妈'), '合金妈妈'),
    # # ボロンティック -> 波隆提克
    # (re.compile(r'博隆提克'), '波隆提克'),
    # (re.compile(r'沃伦提克'), '波隆提克'),
    # # 男子生徒 -> 男学生
    # (re.compile(r'男同学生'), '男学生'),
    # # マスター -> 店长（如果希望统一）
    # # (re.compile(r'老板'), '店长'),  # 视情况打开
    # # トクさん -> 德叔
    # (re.compile(r'托克桑'),       '德叔'),
    # (re.compile(r'传闻屋トクさん'), '传闻屋德叔'),
    # (re.compile(r'传闻屋托克桑'),   '传闻屋德叔'),
    # # 流星野郎 -> 流星野郎
    # (re.compile(r'流星老兄'), '流星野郎'),
    # # キング・レオ -> 狮子座国王（如果想统一中文）
    # (re.compile(r'King Leo'), '狮子座国王'),
    # (re.compile(r'シャドウ'), '阴影'),
    # (re.compile(r'シャドウ'), '阴影'),
    # (re.compile(r'雪乃'), '雪野'),
    # (re.compile(r'Ishkick'), '伊修奇克'),
    # (re.compile(r'伊迪尔先生'), '理想老师'),
    # (re.compile(r'Toro'), '托罗'), 
    # (re.compile(r'トロ'), '托罗')
    (re.compile(r'男の子'), '男孩'),
]

def fix(s, jp=''):
    if not s:
        return s, []
    orig = s
    for pat, rep in RULES:
        s = pat.sub(rep, s)
        
    # 针对日文原文进行判断替换
    if 'ギンコ' in jp:
        s = s.replace('丽莎', '银子')
    if 'ユッキー' in jp:
        s = s.replace('雪野', '小雪')

    return s, ([] if s == orig else [(orig, s)])

def process_file(path, getters):
    """getters: list of (label, get_fn, set_fn) over each entry."""
    data = json.load(open(path, encoding='utf-8'))
    diffs = []
    for e in data:
        for label, get, setv in getters:
            old = get(e)
            new, ch = fix(old, e.get('jp', ''))
            if ch:
                setv(e, new)
                diffs.append((e.get('id', '?'), label, ch[0][0], ch[0][1]))
    if APPLY:
        json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return diffs

# all_translatable.json: meta_zh + pages[].zh
def at_getters():
    gs = [('meta_zh', lambda e: e.get('meta_zh', ''),
                       lambda e, v: e.__setitem__('meta_zh', v))]
    # pages handled separately below
    return gs

def process_all_translatable():
    path = 'all_translatable.json'
    data = json.load(open(path, encoding='utf-8'))
    diffs = []
    for e in data:
        m = e.get('meta_zh', '')
        nm, ch = fix(m, e.get('meta_jp', ''))
        if ch:
            e['meta_zh'] = nm
            diffs.append((e.get('id', '?'), 'meta_zh', ch[0][0], ch[0][1]))
        for i, p in enumerate(e.get('pages', [])):
            z = p.get('zh', '')
            nz, ch = fix(z, p.get('jp', ''))
            if ch:
                p['zh'] = nz
                diffs.append((e.get('id', '?'), f'page{i}', ch[0][0], ch[0][1]))
    if APPLY:
        json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return diffs

def process_field():
    path = 'out/field_text_zh.json'
    data = json.load(open(path, encoding='utf-8'))
    diffs = []
    for e in data:
        z = e.get('zh', '')
        nz, ch = fix(z, e.get('jp', ''))
        if ch:
            e['zh'] = nz
            diffs.append((e.get('id', '?'), 'zh', ch[0][0], ch[0][1]))
    if APPLY:
        json.dump(data, open(path, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    return diffs

def show(title, diffs):
    print(f'\n===== {title}: {len(diffs)} 处 =====')
    for id_, label, o, n in diffs:
        # 只显示变化片段的紧凑形式
        print(f'  [{id_} {label}]')
        print(f'    - {o[:90].replace(chr(10), "/")}')
        print(f'    + {n[:90].replace(chr(10), "/")}')

d1 = process_all_translatable()
d2 = process_field()
show('all_translatable.json (对话+strtbl)', d1)
show('out/field_text_zh.json (field)', d2)
print(f'\n总计 {len(d1)+len(d2)} 处。', '已落盘。' if APPLY else 'DRY-RUN(未落盘)。加 apply 落盘。')
