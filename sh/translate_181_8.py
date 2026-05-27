"""文件 181_8 翻译（开场霸凌+般若校长登场场景，29 条 diag）。
术语见 glossary.md。运行后将翻译写入 all_translatable.json。
"""
import json, os

# 翻译表：id → {zh_pages: [...], meta_zh: '...'}
# zh_pages 顺序对应原 entry.pages
T = {
    # 【测试 RELOCATE】下面 3 条故意加长，触发追加到 script 末尾的路径
    'script:181_8:diag0': {
        'meta_zh': '???',
        'zh_pages': ['\n<SURNAME/>嗯……发生什么了…？'],
    },
    'script:181_8:diag1': {
        'meta_zh': '不良学生',
        'zh_pages': ['\n<SURNAME/>哟，你好啊…\n<SURNAME/>这就准备回家了吗？小子？\n'],
    },
    'script:181_8:diag2': {
        'meta_zh': '混混跟班',
        'zh_pages': ['\n<SURNAME/>嘿嘿嘿嘿嘿嘿嘿嘿嘿嘿嘿～！！哈哈哈哈\n<SURNAME/>那破破破破车，再也跑不动跑不动咯啊～\n<SURNAME/>因为这家伙真的真的没啦哦～哈哈哈哈哈\n'],
    },
    'script:181_8:diag3': {
        'meta_zh': '不良学生',
        'zh_pages': ['\n<SURNAME/>装作没听见啊…<pause:30/>\n<SURNAME/>看你那副得意的脸，就让人来气。\n<SURNAME/>少在那儿翘尾巴，小子…\n'],
    },
    'script:181_8:diag4': {
        'meta_zh': '???',
        'zh_pages': ['\n<SURNAME/>………！？\n'],
    },
    'script:181_8:diag5': {
        'meta_zh': '不良学生',
        'zh_pages': ['\n<SURNAME/>喂、喂…\n<SURNAME/>怎么搞的啊！？\n'],
    },
    'script:181_8:diag6': {
        'meta_zh': '神秘之声',
        # 古风保留（Persona 觉醒前奏）
        'zh_pages': ['\n<SURNAME/>握住…<pause:30/>\n<SURNAME/>吾…<pause:30/>\n<SURNAME/>之手…\n'],
    },
    'script:181_8:diag7': {
        'meta_zh': '混混跟班',
        'zh_pages': ['\n<SURNAME/>那、那家伙样子怪怪的吧？\n<SURNAME/>这小子，浑身在冒汗…\n'],
    },
    'script:181_8:diag8': {
        'meta_zh': '神秘之声',
        # 经典 Persona 觉醒台词（"I am thou, thou art I"）
        'zh_pages': ['\n<SURNAME/>勿惧…<pause:45/>\n<SURNAME/>吾即汝…<pause:45/>\n<SURNAME/>汝即…\n'],
    },
    'script:181_8:diag9': {
        'meta_zh': '???',
        'zh_pages': ['\n<SURNAME/>………！！\n'],
    },
    'script:181_8:diag10': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>喂！那边的！\n<SURNAME/>到底在干什么，你们这些小笨蛋！！\n<SURNAME/>放学时间早就过了，知道吗！\n'],
    },
    'script:181_8:diag11': {
        # 纯 META（角色介绍画面，无 body pages）
        'meta_zh': '反谷<SURNAME/>孝志\n<SURNAME/>从艾尔敏学园转任而来的新校长。\n<SURNAME/>在艾尔敏因绰号"般若"而被讨厌，\n<SURNAME/>却莫名在七姊妹学园广受欢迎。',
        'zh_pages': [],
    },
    'script:181_8:diag12': {
        'meta_zh': '不良学生',
        'zh_pages': ['\n<SURNAME/>反、反谷校长！？\n<SURNAME/>是、是的！！<SURNAME/>这就回家预习去！\n<SURNAME/>喂！<SURNAME/>快、快走！！\n'],
    },
    'script:181_8:diag13': {
        'meta_zh': '混混跟班',
        'zh_pages': ['\n<SURNAME/>这、这个还给你！！\n<SURNAME/>告辞～！！\n'],
    },
    'script:181_8:diag14': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>明白就好，明白就好。\n<SURNAME/>哈哈哈哈！\n<SURNAME/>真是心情愉快！！\n'],
    },
    'script:181_8:diag15': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>你也一样！！\n<SURNAME/>没听见我说话吗！？\n'],
    },
    'script:181_8:diag16': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>为什么不听话！？\n<SURNAME/>岂有此理！！\n'],
    },
    'script:181_8:diag17': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>你！<SURNAME/>几年几班，叫什么名字！？\n<SURNAME/>报上姓名和班级！！\n<SURNAME/>还不快说！？\n'],
    },
    'script:181_8:diag18': {
        'meta_zh': '般若校长',
        # <c12/> 黄字开始, <c13/> 黄字结束（颜色复位）
        'zh_pages': ['\n<SURNAME/>哦，难怪…<pause:30/>\n<SURNAME/>你就是那个传闻中的<c12/><SURNAME/><c13/>啊。\n'],
    },
    'script:181_8:diag19': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>刚才在走廊感到的那阵不快共鸣，\n<SURNAME/>原来源头是你，倒说得通了…<pause:30/>\n<SURNAME/>看来传闻中的问题学生果然名不虚传。\n'],
    },
    'script:181_8:diag20': {
        'meta_zh': '般若校长',
        # 「あの方」= 那位大人（反派 BOSS 的代称，保留引号梗）；古风风味轻微保留
        'zh_pages': ['\n<SURNAME/>呵呵呵…也罢。\n<SURNAME/>你呀，「那位大人」会亲自来调教你。\n<SURNAME/>所剩无几的青春，就尽情挥洒吧。\n'],
    },
    'script:181_8:diag21': {
        'meta_zh': '男学生',
        'zh_pages': ['\n<SURNAME/>哟，挺惨的啊。\n<SURNAME/>不过反谷校长其实人很好的。\n<SURNAME/>他的话还是听一听吧。\n'],
    },
    'script:181_8:diag22': {
        'meta_zh': '男学生',
        'zh_pages': ['\n<SURNAME/>别瞪我嘛。\n<SURNAME/>我只是来通知你一声，\n<SURNAME/>冴子老师在找你。\n'],
    },
    'script:181_8:diag23': {
        'meta_zh': '男学生',
        'zh_pages': ['\n<SURNAME/>你一直在躲升学指导吧？\n<SURNAME/>看那架势她都快冲到你家了，\n<SURNAME/>我看你还是去见一面好。\n'],
    },
    'script:181_8:diag24': {
        'meta_zh': '绷带男生',
        'zh_pages': ['\n<SURNAME/>唉…终于连我也发病了。\n<SURNAME/>早上一觉醒来，脸肿了，头也秃了。\n<SURNAME/>哼，要笑就笑吧。\n'],
    },
    'script:181_8:diag25': {
        'meta_zh': '绷带男生',
        'zh_pages': ['\n<SURNAME/>切，你那头长发也没什么好羡慕的。\n<SURNAME/>反正再过几十年，大家都要秃。<pause:30/>\n<SURNAME/>哼…<pause:30/>等着你哦，<c12/>。\n'],
    },
    'script:181_8:diag26': {
        'meta_zh': '绷带女生',
        'zh_pages': ['\n<SURNAME/>真是倒霉啊，<c12/>学长。\n<SURNAME/>不过反谷校长莫名地受欢迎呢。<pause:30/>\n<SURNAME/>我也是，明明很气他却又有点喜欢…为什么呢？\n'],
    },
    'script:181_8:diag27': {
        'meta_zh': '男学生',
        'zh_pages': ['\n<SURNAME/>这副岛的摩托，\n<SURNAME/>是<c12/>你<c13/>自己保养的吧？\n<SURNAME/>看来你擅长机械的传闻是真的。\n'],
    },
    'script:181_8:diag28': {
        'meta_zh': '女学生',
        # 误会喜剧：女生把主角搭话当成告白
        'zh_pages': ['\n<SURNAME/><c12/>学长！？<SURNAME/>诶！？<SURNAME/>讨厌啦，这么突然…<pause:30/>\n<SURNAME/>人家还没经验…心理准备也没…<pause:30/>\n<SURNAME/>不、不过，如果是学长的话也…\n'],
    },
    'script:181_8:diag29': {
        'meta_zh': '女学生',
        'zh_pages': ['\n<SURNAME/>诶？<SURNAME/>冴子老师吗？<pause:30/>\n<SURNAME/>嗯…应该在 2 楼的教员室吧…<pause:30/>\n<SURNAME/>唉…也是啦，我这种人…\n'],
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
