"""文件 183_8 翻译（七姊妹学园：华小路雅 / 丽莎 / 荣吉登场场景，32 条 diag）。
术语见 glossary.md。运行后将翻译写入 all_translatable.json。
"""
import json, os

# 翻译表：id → {zh_pages: [...], meta_zh: '...'}
T = {
    'script:183_8:diag0': {
        'meta_zh': '???',
        'zh_pages': ['\n<SURNAME/>嗝…<pause:30/>\n<SURNAME/>多谢款待。\n'],
    },
    'script:183_8:diag1': {
        # 纯 META：华小路雅角色介绍
        'meta_zh': '华小路<SURNAME/>雅\n<SURNAME/>七姊妹学园 2-C 学生。\n<SURNAME/>绰号"花姐"，新闻部部长。\n<SURNAME/>独自调查"纹章诅咒"之谜。',
        'zh_pages': [],
    },
    'script:183_8:diag2': {
        'meta_zh': '???',
        'zh_pages': ['\n<SURNAME/>・<pause:10/>・<pause:10/>・<pause:10/>哈!?\n'],
    },
    'script:183_8:diag3': {
        'meta_zh': '???',
        # 荣吉登场（粗暴）+ 第二页是他的角色介绍
        'zh_pages': [
            '\n<SURNAME/>你、你们这帮人!\n<SURNAME/>这女的，真是老子的粉丝!?<pause:30/>\n<SURNAME/>看着就不正常吧，这家伙!!\n',
            '<c1d:7/>三科<SURNAME/>荣吉\n<SURNAME/><c13/>春日山高中二年级生，紧盯着<c12/><c13/>。\n<SURNAME/>自称米切，\n<SURNAME/>身兼番长与乐队主唱的自恋狂。<c1d:1/>\n',
        ],
    },
    'script:183_8:diag4': {
        'meta_zh': '健',
        'zh_pages': ['\n<SURNAME/>冷、冷静点，米切大哥!\n'],
    },
    'script:183_8:diag5': {
        'meta_zh': '昭吾',
        'zh_pages': ['\n<SURNAME/>是、是啊。\n<SURNAME/>再等一会儿，\n<SURNAME/>七姊妹的<c12/>也会来的!\n'],
    },
    'script:183_8:diag6': {
        'meta_zh': '昭吾',
        'zh_pages': ['\n<SURNAME/>啊!?\n<SURNAME/>慌、慌、慌…!!\n'],
    },
    'script:183_8:diag7': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>喂…<pause:30/>\n<SURNAME/>什、什么<c12/>不<c12/>的，搞什么名堂?\n<SURNAME/>你们这帮家伙，在背着老子搞什么!!\n'],
    },
    'script:183_8:diag8': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>哼…<pause:30/>\n<SURNAME/>原来是这么回事啊?\n'],
    },
    'script:183_8:diag9': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/><c12/>!?\n'],
    },
    'script:183_8:diag10': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>就是你?\n<SURNAME/>什么米切荣吉?\n'],
    },
    'script:183_8:diag11': {
        'meta_zh': '荣吉',
        # ナルシスト腔调
        'zh_pages': ['\n<SURNAME/>耶~斯!\n<SURNAME/>宝贝你也是本大爷的粉丝吗~?\n'],
    },
    'script:183_8:diag12': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>向全天下的女士们挥洒爱意的天才艺术家，\n<SURNAME/>米切大人，正是在下♥\n<SURNAME/>木哦哦哦哦哦哦!!\n'],
    },
    'script:183_8:diag13': {
        'meta_zh': '丽莎',
        # ワいてんの = 脑子进水
        'zh_pages': ['\n<SURNAME/>你…<pause:30/>\n<SURNAME/>脑子进水啦?\n'],
    },
    'script:183_8:diag14': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>啊啥!?\n<SURNAME/>你这…!!\n'],
    },
    'script:183_8:diag15': {
        'meta_zh': '昭吾',
        'zh_pages': ['\n<SURNAME/>那个…实在抱歉!!<pause:30/>\n<SURNAME/>是我们把花姐当人质，\n<SURNAME/>把<c12/>给叫出来的!\n'],
    },
    'script:183_8:diag16': {
        'meta_zh': '武',
        'zh_pages': ['\n<SURNAME/>米切大哥不是吵着要组乐队吗?\n<SURNAME/>我们就在找成员。<pause:30/>\n<SURNAME/>一直就只有主唱一个人嘛…\n'],
    },
    'script:183_8:diag17': {
        'meta_zh': '健',
        'zh_pages': ['\n<SURNAME/>反正都要找，不如把<c12/>拉进来…<pause:30/>\n<SURNAME/>这样就靠谱了，\n<SURNAME/>米切大哥肯定也高兴…\n'],
    },
    'script:183_8:diag18': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>你、你们这帮…<pause:30/>\n<SURNAME/>违反帮规会怎样，知道吧…\n'],
    },
    'script:183_8:diag19': {
        'meta_zh': '昭吾<SURNAME/>健<SURNAME/>武',
        'zh_pages': ['\n<SURNAME/>是!\n<SURNAME/>"身为男人，不可使用卑鄙手段!"\n<SURNAME/>什么惩罚都愿意领!!\n'],
    },
    'script:183_8:diag20': {
        'meta_zh': '花姐',
        'zh_pages': ['\n<SURNAME/>那个…说要告诉我纹章诅咒之谜…<pause:30/>\n<SURNAME/>是骗我的吧?\n<SURNAME/>那么，我就先告辞了。\n'],
    },
    'script:183_8:diag21': {
        'meta_zh': '丽莎',
        # ア木らしくて = 真蠢得可笑
        'zh_pages': ['\n<SURNAME/>唉…<pause:30/>\n<SURNAME/>我们也回吧，<c13/>。\n<SURNAME/>蠢得我都要哭了。\n'],
    },
    'script:183_8:diag22': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>等等，<c12/>!\n'],
    },
    'script:183_8:diag23': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>用卑鄙手段，老子认错。<pause:30/>\n<SURNAME/>可是呢，为了这帮小弟，\n<SURNAME/>也不能让你们就这么走了…\n'],
    },
    'script:183_8:diag24': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>赌上死神番长的脸面，你得当!\n<SURNAME/>当乐队成员!!\n'],
    },
    'script:183_8:diag25': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>死神番长~!?\n<SURNAME/>该叫内裤番长才对吧?\n'],
    },
    'script:183_8:diag26': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>传闻我可听说啦!\n<SURNAME/>你不是靠扒人内裤扒不停，\n<SURNAME/>才当上番长的吗?\n'],
    },
    'script:183_8:diag27': {
        'meta_zh': '健',
        'zh_pages': ['\n<SURNAME/>糟、糟了，米切大哥!!\n'],
    },
    'script:183_8:diag28': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>内、内裤…\n'],
    },
    'script:183_8:diag29': {
        'meta_zh': '<c13/>',
        'zh_pages': ['\n<SURNAME/>………!?\n'],
    },
    'script:183_8:diag30': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>什、什么!?\n<SURNAME/>这种感觉…\n'],
    },
    'script:183_8:diag31': {
        'meta_zh': '荣吉',
        # 怒吼：别叫我内裤! 我叫三科 荣吉!
        'zh_pages': ['\n<SURNAME/>别叫老子内裤啊啊啊!!\n<SURNAME/>老子叫三科<SURNAME/>荣吉!!\n<SURNAME/>三科<SURNAME/>荣吉啊啊啊啊啊啊啊啊啊!!\n'],
    },
}

# 应用到 all_translatable.json
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'all_translatable.json')
data = json.load(open(PATH, encoding='utf-8'))

applied = 0
for entry in data:
    eid = entry['id']
    if eid not in T:
        continue
    tr = T[eid]
    if 'meta_zh' in tr and tr['meta_zh']:
        entry['meta_zh'] = tr['meta_zh']
    for i, zh in enumerate(tr.get('zh_pages', [])):
        if i < len(entry['pages']):
            entry['pages'][i]['zh'] = zh
    applied += 1

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f'已应用 {applied} 条翻译 → all_translatable.json')
