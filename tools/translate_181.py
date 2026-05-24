"""
file 181 sub-file 8 全部对话的中文翻译。
风格更自然，按人物语气区分（流氓粗口 / 校长严肃 / 朋友闲聊 / Persona 觉醒古风），
专有名词使用官方/常见汉化名（反谷、般若、七姊妹、艾尔敏、冴子、副岛 等）。
"""
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JSON_PATH = os.path.join(ROOT, 'all_translatable.json')

# 说话人（meta_zh）。'???' 是主角，保持原样。
META = {
    'diag0':  '???',
    'diag1':  '小混混',
    'diag2':  '小喽啰',
    'diag3':  '小混混',
    'diag4':  '???',
    'diag5':  '小喽啰',
    'diag6':  '???',
    'diag7':  '小喽啰',
    'diag8':  '???',
    'diag9':  '???',
    'diag10': '般若校长',
    # diag11 是角色介绍框，整段是 META，没 body
    'diag11': '反谷<SURNAME/>孝志(はんや<SURNAME/>たかし)\n<SURNAME/>从艾尔敏学园调任的新校长。\n<SURNAME/>在艾尔敏外号"般若"被嫌弃，\n<SURNAME/>不知为何在七姊妹学园却很受爱戴。',
    'diag12': '小喽啰',
    'diag13': '小喽啰',
    'diag14': '般若校长',
    'diag15': '般若校长',
    'diag16': '般若校长',
    'diag17': '般若校长',
    'diag18': '般若校长',
    'diag19': '般若校长',
    'diag20': '般若校长',
    'diag21': '副岛',
    'diag22': '副岛',
    'diag23': '副岛',
    'diag24': '副岛',
    'diag25': '副岛',
    'diag26': '丽莎',
    'diag27': '丽莎',
    'diag28': '丽莎',
    'diag29': '丽莎',
}

# 对话本体翻译。空字符串表示该 diag 没有 body（如角色介绍 diag11）。
BODY = {
    'diag0':  '\n<SURNAME/>……？',
    'diag1':  '\n<SURNAME/>哟～\n<SURNAME/>这就回家啦？\n',
    'diag2':  '\n<SURNAME/>嘿嘿～！！\n<SURNAME/>你这破车，再也跑不了喽～\n<SURNAME/>因为这玩意儿没啦～\n',
    'diag3':  '\n<SURNAME/>装聋作哑啊…<pause:30/>\n<SURNAME/>看你那副得意的样子，老子就来气。\n<SURNAME/>少在那儿摆谱，臭小子…\n',
    'diag4':  '\n<SURNAME/>………！？\n',
    'diag5':  '\n<SURNAME/>喂、喂…\n<SURNAME/>你这是怎么了！？\n',
    'diag6':  '\n<SURNAME/>吾之…<pause:30/>\n<SURNAME/>手…<pause:30/>\n<SURNAME/>取之…\n',
    'diag7':  '\n<SURNAME/>…他、他不太对劲啊？\n<SURNAME/>这家伙，浑身都是汗…\n',
    'diag8':  '\n<SURNAME/>勿惧…<pause:45/>\n<SURNAME/>吾即汝身…<pause:45/>\n<SURNAME/>汝即…\n',
    'diag9':  '\n<SURNAME/>………！！',
    'diag10': '\n<SURNAME/>喂！那边的！\n<SURNAME/>到底在搞什么名堂，一群笨蛋！！\n<SURNAME/>都过放学时间了知道吗？\n',
    # diag11 没 body
    'diag11': '',
    'diag12': '\n<SURNAME/>反、反谷校长！？\n<SURNAME/>是、是！！<SURNAME/>这就回家预习！\n<SURNAME/>喂！<SURNAME/>快、快走！\n',
    'diag13': '\n<SURNAME/>这、这个还你！\n<SURNAME/>告辞～！！\n',
    'diag14': '\n<SURNAME/>明白就好嘛，明白就好。\n<SURNAME/>哈哈哈哈！\n<SURNAME/>心情真不错！！\n',
    'diag15': '\n<SURNAME/>你也是！\n<SURNAME/>没听见我说话吗！？\n',
    'diag16': '\n<SURNAME/>为何不听本校长的话！？\n<SURNAME/>岂有此理！！\n',
    'diag17': '\n<SURNAME/>你！<SURNAME/>几年几班，叫什么名字！？\n<SURNAME/>报上班级姓名！！\n<SURNAME/>还不快说！？\n',
    'diag18': '\n<SURNAME/>哦，难怪…<pause:30/>\n<SURNAME/>你就是传闻中的<c12/><SURNAME/><c13/>啊。\n',
    'diag19': '\n<SURNAME/>方才在走廊上感到的那股不快共鸣，\n<SURNAME/>原来是你引起的，难怪……<pause:30/>\n<SURNAME/>果然名不虚传，是个问题学生。\n',
    'diag20': '\n<SURNAME/>哼哼…也罢。\n<SURNAME/>"那位大人"会亲自来调教你。\n<SURNAME/>洗干净脖子等着吧。',
    'diag21': '\n<SURNAME/>哟，刚才挺惨的啊。\n<SURNAME/>不过反谷校长其实人挺好。\n<SURNAME/>他的话还是听着点吧。\n',
    'diag22': '\n<SURNAME/>别这么瞪我嘛。\n<SURNAME/>我就是来传个话，\n<SURNAME/>冴子老师在找你呢。\n',
    'diag23': '\n<SURNAME/>你一直在躲升学辅导吧？\n<SURNAME/>她那架势怕是要杀到你家来，\n<SURNAME/>还是见一面比较好。\n',
    'diag24': '\n<SURNAME/>呜呜…连我也发病了。\n<SURNAME/>今早起来，脸全肿了，头也秃光了。\n<SURNAME/>哼，想笑你就笑吧。',
    'diag25': '\n<SURNAME/>哼，谁稀罕你那一头长发啊。\n<SURNAME/>反正再过几十年大家都得秃。<pause:30/>\n<SURNAME/>嘿…<pause:30/>等着你哦，<c12/>。',
    'diag26': '\n<SURNAME/>真倒霉啊，<c12/>前辈。\n<SURNAME/>不过反谷校长莫名其妙地受欢迎呢。<pause:30/>\n<SURNAME/>我也是，嘴上嫌烦心里却挺喜欢…为啥呢？',
    'diag27': '\n<SURNAME/>副岛这辆摩托，\n<SURNAME/>是<c12/>你自己保养的吧？\n<SURNAME/>看来你会修机械的传闻是真的。',
    'diag28': '\n<SURNAME/><c12/>前辈！？<SURNAME/>诶！？<SURNAME/>不要嘛，这么突然…<pause:30/>\n<SURNAME/>人家还没经验…心理准备…<pause:30/>\n<SURNAME/>不、不过，是前辈的话也…',
    'diag29': '\n<SURNAME/>诶？<SURNAME/>冴子老师吗？<pause:30/>\n<SURNAME/>嗯…应该在二楼教员室…<pause:30/>\n<SURNAME/>唉…也是啦，我这种人嘛…',
}

def main():
    data = json.load(open(JSON_PATH, encoding='utf-8'))
    body_updated = 0
    meta_updated = 0
    for entry in data:
        if not entry['id'].startswith('script:181_8:'):
            continue
        diag_id = entry['id'].split(':')[-1]
        if diag_id in BODY:
            body_text = BODY[diag_id]
            for page in entry['pages']:
                page['zh'] = body_text
            if body_text:
                body_updated += 1
        if diag_id in META and 'meta_jp' in entry:
            entry['meta_zh'] = META[diag_id]
            meta_updated += 1
    print(f'body 译文: {body_updated} 条')
    print(f'meta 译文: {meta_updated} 条')
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'写回 {JSON_PATH}')

if __name__ == '__main__':
    main()
