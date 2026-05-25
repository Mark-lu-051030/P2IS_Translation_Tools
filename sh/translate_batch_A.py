# translate_batch_A.py 完整内容
import json, os
T = {
    # ===== 90_65 南条 =====
    'script:90_65:diag0': {
        'meta_zh': '背上写着 1 的男人',
        'zh_pages': ['\n<SURNAME/>喂你，是 Persona 使者吧…?<pause:20/>\n<SURNAME/>嗯…不是敌人。<pause:15/>\n<SURNAME/>我的 Persona 这么告诉我的…'],
    },
    'script:90_65:diag1': {
        'meta_zh': '背上写着 1 的男人',
        'zh_pages': ['\n<SURNAME/>能来到这种地方，看来你知道不少内情。\n<SURNAME/>方便的话，可不可以告诉我，\n<SURNAME/>这条街到底发生了什么?'],
    },
    'script:90_65:diag2': {
        'meta_zh': '<SURNAME/>这条街到底发生了什么?\n<option:2/>说\n不说\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_65:diag3': {
        'meta_zh': '背上写着 1 的男人',
        'zh_pages': ['\n<SURNAME/>哼…谨慎的家伙。<pause:15/>\n<SURNAME/>罢了，不勉强你。<pause:15/>\n<SURNAME/>那么，告辞了…'],
    },
    'script:90_65:diag4': {
        'meta_zh': '背上写着 1 的男人',
        'zh_pages': ['\n<SURNAME/>这样啊…<pause:30/>\n<SURNAME/>如果看到「黑西装的男人」，\n<SURNAME/>别靠近。'],
    },
    'script:90_65:diag5': {
        'meta_zh': '背上写着 1 的男人',
        'zh_pages': ['\n<SURNAME/>根据传闻和我的直觉，\n<SURNAME/>那家伙就是叫神取的危险男人…<pause:30/>\n<SURNAME/>我可警告过你了。'],
    },
    'script:90_65:diag6': {
        'meta_zh': '背上写着 1 的男人',
        'zh_pages': ['\n<SURNAME/>这样吗…黛啊…<pause:30/>\n<SURNAME/>看来我那挚友承蒙照顾了。<pause:15/>\n<SURNAME/>我谢谢你…'],
    },
    'script:90_65:diag7': {
        'meta_zh': '南条',
        'zh_pages': ['\n<SURNAME/>我是南条<SURNAME/>圭。\n<SURNAME/>过去与黛并肩作战的伙伴。'],
    },
    'script:90_65:diag8': {
        'meta_zh': '南条<SURNAME/>圭(なんじょう<SURNAME/>けい)\n<SURNAME/>从英国留学暂时回国，雪乃的挚友。\n<SURNAME/>目前正以成为日本第一男子为目标修行中。\n<SURNAME/>高中时代以 Persona 使者觉醒。',
        'zh_pages': [],
    },
    'script:90_65:diag9': {
        'meta_zh': '南条',
        'zh_pages': ['\n<SURNAME/>听说这条街上有我以前的伙伴…<pause:30/>\n<SURNAME/>久违地来看看，没想到是这副景象。<pause:15/>\n<SURNAME/>竟然发生了这种事件…'],
    },
    'script:90_65:diag10': {
        'meta_zh': '南条',
        'zh_pages': ['\n<SURNAME/>其实我来这里，\n<SURNAME/>是因为听到传闻说有人见到了…<pause:15/>\n<SURNAME/>本该被我们打倒的敌人——神取的相似者。'],
    },
    'script:90_65:diag11': {
        'meta_zh': '南条',
        'zh_pages': ['\n<SURNAME/>如果那家伙还活着，\n<SURNAME/>就不能置之不理…<pause:30/>\n<SURNAME/>抱歉，我先告辞了。'],
    },
    'script:90_65:diag12': {
        'meta_zh': '南条',
        'zh_pages': ['\n<SURNAME/>对了…这是我爱用的日本刀。<pause:15/>\n<SURNAME/>就当是对黛的谢礼…拿去吧。\n<SURNAME/>那么…有缘再会。'],
    },

    # ===== 90_66 城户 玲司 =====
    'script:90_66:diag0': {
        'meta_zh': '黑西装的男人',
        'zh_pages': ['\n<SURNAME/>啥啊你们…<pause:10/>不对，你们这些孩子?<pause:15/>\n<SURNAME/>在这种地方很危险…<pause:10/>\n<SURNAME/>不对啊…<pause:15/>因为危险啊…'],
    },
    'script:90_66:diag1': {
        'meta_zh': '黑西装的男人',
        'zh_pages': ['\n<SURNAME/>啧!<pause:15/>\n<SURNAME/>老子说不出这种黏糊糊的话啊!'],
    },
    'script:90_66:diag2': {
        'meta_zh': '黑西装的男人',
        'zh_pages': ['\n<SURNAME/>这里不是小屁孩该来的地方…<pause:30/>\n<SURNAME/>快滚回去…会死的哦…?'],
    },
    'script:90_66:diag3': {
        'meta_zh': '<SURNAME/>快滚回去…会死的哦…?\n<option:2/>你是神取吗?\n就这么办\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_66:diag4': {
        'meta_zh': '黑西装的男人',
        'zh_pages': ['\n<SURNAME/>你说什么…?<pause:15/>\n<SURNAME/>老子叫城户<SURNAME/>玲司!!<pause:15/>\n<SURNAME/>别把老子和那家伙…扯到一起!!'],
    },
    'script:90_66:diag5': {
        'meta_zh': '玲司',
        'zh_pages': ['\n<SURNAME/>啥?<SURNAME/>背上写着 1 的男人说的?\n<SURNAME/>难道是南条?<SURNAME/>那家伙也来这儿了!?\n<SURNAME/>…那家伙是老子的兄弟…说说看怎么回事'],
    },
    'script:90_66:diag6': {
        'meta_zh': '黑西装的男人',
        'zh_pages': ['\n<SURNAME/>你说什么…?<pause:15/>\n<SURNAME/>老子叫城户<SURNAME/>玲司!!<pause:15/>\n<SURNAME/>别把老子和那家伙…扯到一起!!'],
    },
    'script:90_66:diag7': {
        'meta_zh': '玲司',
        'zh_pages': ['\n<SURNAME/>啥?<pause:15/><SURNAME/>南条这么说的?\n<SURNAME/>喂，那家伙也来这儿了!?\n<SURNAME/>那家伙是老子的兄弟…说说看怎么回事。'],
    },
    'script:90_66:diag8': {
        'meta_zh': '玲司',
        'zh_pages': ['\n<SURNAME/>瓜、瓜娃子!<SURNAME/>大大的误会…<pause:30/>\n<SURNAME/>老子是听说这儿会出恶魔，\n<SURNAME/>来这儿压压心头那股热血罢了…'],
    },
    'script:90_66:diag9': {
        'meta_zh': '城户<SURNAME/>玲司(きど<SURNAME/>れいじ)\n<SURNAME/>雪乃的挚友，推销员。\n<SURNAME/>跟托罗在同一家公司，似乎为业绩烦恼。\n<SURNAME/>高中时代以 Persona 使者觉醒。',
        'zh_pages': [],
    },
    'script:90_66:diag10': {
        'meta_zh': '玲司',
        'zh_pages': ['\n<SURNAME/>偏偏把老子认成那混蛋，\n<SURNAME/>就算是兄弟也不能忍…<pause:30/>\n<SURNAME/>老子也是…一直在介意这事…'],
    },
    'script:90_66:diag11': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>瞅瞅瞅瞅瞅…<pause:15/>\n<SURNAME/>啊，哎呀!!(アイヤー)\n<SURNAME/>果然，这是传说中的美利坚拳套!'],
    },
    'script:90_66:diag12': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>以前御影町有个传说中的裸番长，\n<SURNAME/>他戴的那副拳套，\n<SURNAME/>能一击粉碎飞奔的卡车!!'],
    },
    'script:90_66:diag13': {
        'meta_zh': '玲司',
        'zh_pages': ['\n<SURNAME/>哈?<pause:15/>\n<SURNAME/>再夸张也得有个度…'],
    },
    'script:90_66:diag14': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>瞅瞅瞅瞅瞅…'],
    },
    'script:90_66:diag15': {
        'meta_zh': '玲司',
        'zh_pages': ['\n<SURNAME/>什、什么?<pause:15/>\n<SURNAME/>这玩意儿不行!!<pause:15/>\n<SURNAME/>这是老子的…'],
    },
    'script:90_66:diag16': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>瞅瞅瞅瞅瞅瞅瞅瞅瞅瞅瞅瞅瞅瞅…'],
    },
    'script:90_66:diag17': {
        'meta_zh': '玲司',
        'zh_pages': ['\n<SURNAME/>啧…<pause:15/>该卖的卖不出去，\n<SURNAME/>偏偏宝贝东西被人盯上…<pause:30/>\n<SURNAME/>没办法，拿走吧…'],
    },
    'script:90_66:diag18': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>诶!<SURNAME/>真的吗?(係咩!ハイメ)真!<pause:15/>\n<SURNAME/>太开心啦!!(開心囉!ホィサムロ)<pause:15/>\n<SURNAME/>万岁——!'],
    },
    'script:90_66:diag19': {
        'meta_zh': '玲司',
        'zh_pages': ['\n<SURNAME/>就当是对黛的谢礼，便宜了你们…<pause:30/>\n<SURNAME/>那么，别让自己后悔，好好干吧。'],
    },
    'script:90_66:diag20': {
        'meta_zh': '黑西装的男人',
        'zh_pages': ['\n<SURNAME/>传闻中的怪物，\n<SURNAME/>老子会一只不剩地宰光…<pause:30/>\n<SURNAME/>别再靠近这里了。'],
    },

    # ===== 90_74 CD 店 =====
    'script:90_74:diag0': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>嗨~欢迎光临~<pause:15/>\n<SURNAME/>这里是 CD 商店，\n<SURNAME/>吉佳·马齐欧!'],
    },
    'script:90_74:diag1': {
        'meta_zh': '<SURNAME/>来，要点啥米索~\n<option:3/>买 CD\n聊聊天\n没事\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag2': {
        'meta_zh': '<SURNAME/>还有别的事吗?\n<option:3/>买 CD\n聊聊天\n没事\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag3': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>抱歉啦~CD 现在卖光啦~<pause:15/>\n<SURNAME/>啥?<SURNAME/>周围架子上不是一堆?<pause:15/>\n<SURNAME/>那都是摆设。所以抱歉啦~!!'],
    },
    'script:90_74:diag4': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>你真是太厉害啦米索~<pause:15/>\n<SURNAME/>把这里的 CD 全都买走了。\n<SURNAME/>感谢之至。万分感谢呢~'],
    },
    'script:90_74:diag5': {
        'meta_zh': '<SURNAME/>选个专区吧~\n<option:6/><c10:1130/>Primo\n<c10:1131/>Secondo\n<c10:1132/>Terzo\n<c10:1133/>Quarto\n<c10:1134/>Quinto\n算了\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag6': {
        'meta_zh': '<SURNAME/>那就选 CD 米索~\n<option:6/><c11:1033/>CD1\n<c11:1034/>CD2\n<c11:1035/>CD3\n<c11:1036/>CD4\n<c11:1037/>CD5\n算了\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag7': {
        'meta_zh': '<SURNAME/>那就选 CD 米索~\n<option:6/><c11:1038/>CD6\n<c11:1039/>CD7\n<c11:1040/>CD8\n<c11:1041/>CD9\n<c11:1042/>CD10\n算了\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag8': {
        'meta_zh': '<SURNAME/>那就选 CD 米索~\n<option:6/><c11:1043/>CD11\n<c11:1044/>CD12\n<c11:1045/>CD13\n<c11:1046/>CD14\n<c11:1047/>CD15\n算了\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag9': {
        'meta_zh': '<SURNAME/>那就选 CD 米索~\n<option:6/><c11:1048/>CD16\n<c11:1049/>CD17\n<c11:1050/>CD18\n<c11:1051/>CD19\n<c11:1013/>隐藏 CD\n算了\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag10': {
        'meta_zh': '<SURNAME/>那就选 CD 米索~\n<option:6/><c11:1053/>CD21\n<c11:1054/>CD22\n<c11:1055/>CD23\n<c11:1056/>CD24\n<c11:1057/>CD25\n算了\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag11': {
        'meta_zh': '<SURNAME/>这张 CD 要<keyitem:0/>圆，要买吗?\n<option:2/>买\n不买\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:90_74:diag12': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>咦?<pause:15/><SURNAME/>咦咦?<pause:15/>\n<SURNAME/>是只有我觉得钱不够吗?<pause:15/>\n<SURNAME/>啊~真遗憾。'],
    },
    'script:90_74:diag13': {
        'meta_zh': '错误。没找到。',
        'zh_pages': [],
    },
    'script:90_74:diag14': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>是~的。\n<SURNAME/>谢谢你哦~<pause:15/>\n<SURNAME/>感谢，感谢。'],
    },
    'script:90_74:diag15': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>哇哦，Primo 专区这下卖光啦!!\n<SURNAME/>多多承蒙惠顾哦~!\n<SURNAME/>今后也请多多关照~♥'],
    },
    'script:90_74:diag16': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>恭喜——!<SURNAME/>我自己恭喜自己——!\n<SURNAME/>Secondo 专区也顺利完售啦~!\n<SURNAME/>呜~呜，真是感激涕零呢。'],
    },
    'script:90_74:diag17': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>不会吧!<SURNAME/>Terzo 专区也卖光了!\n<SURNAME/>真开心呐~，我超开心呐!\n<SURNAME/>谢谢你哦~'],
    },
    'script:90_74:diag18': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>咦咦?<pause:15/><SURNAME/>Quarto 专区完售?<pause:15/>\n<SURNAME/>感觉怎么有点太简单了…<pause:15/>\n<SURNAME/>不过还是好开心米索~♥'],
    },
    'script:90_74:diag19': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>呵呵呵——!<SURNAME/>Quarto 专区，\n<SURNAME/>居然完售了——!\n<SURNAME/>真开心米索~♥'],
    },
    'script:90_74:diag20': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>哎呀呀!<SURNAME/>Quinto 专区也卖光啦!?\n<SURNAME/>这可是壮举呢~，简直壮举~\n<SURNAME/>多亏了你!<SURNAME/>谢谢你米索~'],
    },
    'script:90_74:diag21': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>刚才呢，刚才呢，\n<SURNAME/>我亲眼见到了佐佐木<SURNAME/>银次先生本人!\n<SURNAME/>呜呼呼，有点感动呢米索~'],
    },
    'script:90_74:diag22': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>喂喂，跟你在一起的金发女孩，\n<SURNAME/>该不会是 MUSES 的丽莎吧?<pause:15/>\n<SURNAME/>哇~是本尊，本尊!'],
    },
    'script:90_74:diag23': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>咦?<SURNAME/>不过其他人呢?<pause:15/>\n<SURNAME/>没有那种人吧?<pause:15/>\n<SURNAME/>咦…想不起来了~'],
    },
    'script:90_74:diag24': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>唉…<pause:15/>因为那连续恐袭事件，\n<SURNAME/>客人越来越少了…<pause:15/>\n<SURNAME/>这算妨碍营业吧~'],
    },
    'script:90_74:diag25': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>新开了 Secondo 专区哦。\n<SURNAME/>嘛，世道虽然乱糟糟的~\n<SURNAME/>偶尔听听音乐放松一下嘛~'],
    },
    'script:90_74:diag26': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>喂，你觉得"In Lak\'ech"怎么样?\n<SURNAME/>那个是真的吗~<pause:15/>\n<SURNAME/>嘛，我倒是无所谓啦~'],
    },
    'script:90_74:diag27': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>客人，你来的真是时候呢。\n<SURNAME/>正好新曲到货了。这次是 Terzo。<pause:15/>\n<SURNAME/>来嘛，瞅一眼米索。'],
    },
    'script:90_74:diag28': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>虽然街上这么乱，\n<SURNAME/>又有新曲到货啦~<pause:15/>\n<SURNAME/>终于连 Quarto 专区都开张啦~'],
    },
    'script:90_74:diag29': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>哎呀，最近新曲不停往店里寄，\n<SURNAME/>盘点都好辛苦。<pause:15/>…总之又有新曲到货!<pause:15/>\n<SURNAME/>Quinto 专区终于登场啦米索—'],
    },
    'script:90_74:diag30': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>真奇怪呢~<pause:15/>\n<SURNAME/>我们家有过隐藏 CD 吗~?<pause:15/>\n<SURNAME/>不过实际上有就是有了…就是有呢~'],
    },
    'script:90_74:diag31': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>感觉怪怪的，不过算啦。<pause:15/>\n<SURNAME/>…总之放进 Quarto 专区了，\n<SURNAME/>请务必买走哦~'],
    },
    'script:90_74:diag32': {
        'meta_zh': '店员',
        'zh_pages': ['\n<SURNAME/>多谢光临~<pause:15/>\n<SURNAME/>再来玩米索~'],
    },

    # ===== 185_8 小丑登场 =====
    'script:185_8:diag0': {
        'meta_zh': '花姐',
        'zh_pages': ['\n<SURNAME/>荣吉君…<pause:30/>\n<SURNAME/>不对，番长先生!!\n<SURNAME/>振作点!!\n'],
    },
    'script:185_8:diag1': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>该不会…<pause:30/>\n<SURNAME/>不是…在做梦吧…?\n'],
    },
    'script:185_8:diag2': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>果然…<pause:30/>\n<SURNAME/>我也看见了。\n<SURNAME/>那个，就叫 Persona 是吧?\n'],
    },
    'script:185_8:diag3': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>传闻成真啦、\n<SURNAME/>预言未来啥的…那玩意儿也是?<pause:30/>\n<SURNAME/>就算是偶然，也太巧得过分了…\n'],
    },
    'script:185_8:diag4': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>呐…<pause:30/>\n<SURNAME/>要不要试试小丑大人…?\n'],
    },
    'script:185_8:diag5': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>就是用自己的手机打给自己手机，\n<SURNAME/>就会接通的那个吗?<pause:30/>\n<SURNAME/>为啥要做那种…\n'],
    },
    'script:185_8:diag6': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>我想确认刚才那个是不是只是梦…<pause:30/>\n<SURNAME/>如果传闻真的成真，\n<SURNAME/>就说明不是单纯的梦了…\n'],
    },
    'script:185_8:diag7': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>老子不干了…<pause:30/>\n<SURNAME/>这种事，绝对不可能…\n'],
    },
    'script:185_8:diag8': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>所以才能拿来证明啊…<pause:30/>\n<SURNAME/>难道…<pause:30/>\n<SURNAME/>你怕了…?\n'],
    },
    'script:185_8:diag9': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>知道了…<pause:30/>\n<SURNAME/>确实，就那么做完那种梦走人，心里不痛快。\n<SURNAME/>就当辟邪，试试看吧。\n'],
    },
    'script:185_8:diag10': {
        'meta_zh': '健',
        'zh_pages': ['\n<SURNAME/>呜…<pause:30/>\n<SURNAME/>为啥我们也…\n'],
    },
    'script:185_8:diag11': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>那么，要打了哦…?<pause:30/>\n<SURNAME/>小丑大人，小丑大人，\n<SURNAME/>请您降临…\n'],
    },
    'script:185_8:diag12': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>骗…人?\n'],
    },
    'script:185_8:diag13': {
        'meta_zh': '健<SURNAME/>昭吾<SURNAME/>武',
        'zh_pages': ['\n<SURNAME/>刚才…\n'],
    },
    'script:185_8:diag14': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>哪位…?\n'],
    },
    'script:185_8:diag15': {
        'meta_zh': '???',
        'zh_pages': ['\n<SURNAME/>在汝身后…\n'],
    },
    'script:185_8:diag16': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>吾即小丑…<pause:30/>\n<SURNAME/>烦于梦境之汝所抽出的，最后王牌。\n'],
    },
    'script:185_8:diag17': {
        'meta_zh': '小丑',
        'zh_pages': [
            '\n<SURNAME/>汝，述其理想…\n',
            '<c1d:11/>小丑\n<SURNAME/>传闻能实现理想的，戴面具的怪人。\n<SURNAME/>为何要实现理想，其真身是谁，\n<SURNAME/>一切皆笼罩在谜团之中。<c1d:1/>\n',
        ],
    },
    'script:185_8:diag18': {
        'meta_zh': '花姐',
        'zh_pages': ['\n<SURNAME/>不行!<SURNAME/>快说出理想!!\n<SURNAME/>传闻说，没向小丑大人说出理想的人，\n<SURNAME/>会被变成「影子人」!!\n'],
    },
    'script:185_8:diag19': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>王牌已遭废弃…\n'],
    },
    'script:185_8:diag20': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>汝所押注的是「逐梦之心」…<pause:30/>\n<SURNAME/>依仪式之规，我便收下。\n'],
    },
    'script:185_8:diag21': {
        'meta_zh': '健',
        'zh_pages': ['\n<SURNAME/>啊，啊啊啊啊啊…\n'],
    },
    'script:185_8:diag22': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>健、健!\n<SURNAME/>昭吾!!\n<SURNAME/>武!!!\n'],
    },
    'script:185_8:diag23': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>你、你这家伙…<pause:30/>\n<SURNAME/>到底干了啥!?\n'],
    },
    'script:185_8:diag24': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>理想，于无力者而言只是苦痛。\n<SURNAME/>我不过将其从苦痛中解放罢了…<pause:30/>\n<SURNAME/>无法实现的梦，不如不做…\n'],
    },
    'script:185_8:diag25': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>他们已成梦的空壳…<pause:30/>\n<SURNAME/>看似可见，实则不见。\n<SURNAME/>将被世人遗忘，终将化为真正的影子。\n'],
    },
    'script:185_8:diag26': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>戏言到此为止。\n<SURNAME/>对你们，我另有事要办…\n'],
    },
    'script:185_8:diag27': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>动不…了!<pause:30/>\n<SURNAME/>是害怕…!?\n'],
    },
    'script:185_8:diag28': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>等候多时了，<c12/><SURNAME/><c13/>…<pause:30/>\n<SURNAME/>我一直在等…<pause:30/>\n<SURNAME/>等你们呼唤出我的这一刻!!\n'],
    },

    # ===== 188_8 钟楼传闻 =====
    'script:188_8:diag0': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>大伙儿都怎么了?\n<SURNAME/>不就是大钟动了，至于这么大惊小怪…'],
    },
    'script:188_8:diag1': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>这座钟楼有好多吓人的传闻呢!\n<SURNAME/>说会闹鬼，还说只要大钟一动，\n<SURNAME/>就一定会出坏事。'],
    },
    'script:188_8:diag2': {
        'meta_zh': '校工',
        'zh_pages': ['\n<SURNAME/>哎哟…这下糟啦…\n<SURNAME/>南无阿弥陀，南无阿弥陀…'],
    },
    'script:188_8:diag3': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>嘿嘿，老爷子!\n<SURNAME/>别那么害怕嘛，没事的。\n<SURNAME/>只要本大爷在，一切 no program~!'],
    },
    'script:188_8:diag4': {
        'meta_zh': '校工',
        'zh_pages': ['\n<SURNAME/>不——!!<SURNAME/>一定会出大事!\n<SURNAME/>那位老师临死前说过…\n<SURNAME/>「不停下时间，世界就会毁灭」。'],
    },
    'script:188_8:diag5': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>那莫非是…<pause:20/>\n<SURNAME/>在钟楼里死去的那位老师?'],
    },
    'script:188_8:diag6': {
        'meta_zh': '校工',
        'zh_pages': ['\n<SURNAME/>啊…正是。\n<SURNAME/>那位老师为了守护孩子们与世界的和平，\n<SURNAME/>献出了宝贵的生命!'],
    },
    'script:188_8:diag7': {
        'meta_zh': '伊迪雅老师',
        'zh_pages': ['\n<SURNAME/>…不会吧，怎么会!\n<SURNAME/>「天空闪耀的昴星，唤动停滞的时间…」<pause:30/>\n<SURNAME/>已经开始了!?'],
    },
    'script:188_8:diag8': {
        'meta_zh': '伊迪雅老师',
        'zh_pages': ['\n<SURNAME/>啊!?<pause:20/>\n<SURNAME/>鸣罗门石!!<SURNAME/>鸣罗门石呢!?'],
    },
    'script:188_8:diag9': {
        'meta_zh': '男学生',
        'zh_pages': ['\n<SURNAME/>伊迪雅老师怎么了?\n<SURNAME/>还能再出什么事啊!?'],
    },
    'script:188_8:diag10': {
        'meta_zh': '男学生',
        'zh_pages': ['\n<SURNAME/>毕竟大钟都动了…\n<SURNAME/>肯定会出更厉害的事!'],
    },
    'script:188_8:diag11': {
        'meta_zh': '女学生',
        'zh_pages': ['\n<SURNAME/>只是把校服上的徽章取下来，\n<SURNAME/>真的能挡住诅咒吗!?'],
    },
    'script:188_8:diag12': {
        'meta_zh': '女学生',
        'zh_pages': ['\n<SURNAME/>呀!!\n'],
    },
    'script:188_8:diag13': {
        'meta_zh': '男学生',
        'zh_pages': ['\n<SURNAME/>哇!\n<SURNAME/>她、她、她那张脸…'],
    },
    'script:188_8:diag14': {
        'meta_zh': '女学生',
        'zh_pages': ['\n<SURNAME/>是诅咒!\n<SURNAME/>是纹章诅咒啊!!'],
    },
    'script:188_8:diag15': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>喂喂，玩真的吗!?\n<SURNAME/>刚才那女孩的脸真的一瞬间…'],
    },
    'script:188_8:diag16': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>不会吧!?(激氣!?ケッヘイ)到底咋回事!?\n<SURNAME/>就算把校服上的徽章取下来，\n<SURNAME/>诅咒已经挡不住了吗!?'],
    },
    'script:188_8:diag17': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>快去找般若校长!!\n<SURNAME/>趁我和<c13/>的脸还没变成一团烂泥之前\n<SURNAME/>得找出解除这诅咒的方法!'],
    },

    # ===== 192_8 找钥匙 =====
    'script:192_8:diag0': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>请——问!\n<SURNAME/>稍微打扰一下~\n'],
    },
    'script:192_8:diag1': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>那个，我想借一下钟楼的钥匙。\n'],
    },
    'script:192_8:diag2': {
        'meta_zh': '校工',
        'zh_pages': ['\n<SURNAME/>嗯?<SURNAME/>钥匙?\n'],
    },
    'script:192_8:diag3': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>对~(係,ハイ)就是钟楼的钥——匙!\n<SURNAME/>是老爷爷你拿着对吧?\n'],
    },
    'script:192_8:diag4': {
        'meta_zh': '校工',
        'zh_pages': ['\n<SURNAME/>钟楼的钥匙…<pause:30/>\n<SURNAME/>咦，到底放哪儿去了呢?\n'],
    },
    'script:192_8:diag5': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>好，老爷爷!\n<SURNAME/>别急别慌，跟本大爷一起，\n<SURNAME/>慢——慢回忆一下吧。\n'],
    },
    'script:192_8:diag6': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>这样下去不知道猴年马月才能找到钥匙。\n<SURNAME/>我们自己找还快些。\n'],
    },
    'script:192_8:diag7': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>真讨厌!\n<SURNAME/>哪儿都没钥匙啊~'],
    },
    'script:192_8:diag8': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>真伤脑筋…\n<SURNAME/>那么，该怎么办?'],
    },
    'script:192_8:diag9': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>说起来，老爷爷。\n<SURNAME/>我刚才就好奇了…\n<SURNAME/>那玩意儿，是什么?\n'],
    },
    'script:192_8:diag10': {
        'meta_zh': '校工',
        'zh_pages': ['\n<SURNAME/>嗯?\n<SURNAME/>这是钥匙啊。\n'],
    },
    'script:192_8:diag11': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>标签上写着…\n<SURNAME/>「钟·<pause:10/>楼·<pause:10/>之·<pause:10/>钥·<pause:10/>匙」\n'],
    },
    'script:192_8:diag12': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>OK!!\n<SURNAME/>钥匙被本大爷找出来啦。\n<SURNAME/>来，向钟楼出发，Let\'s go!'],
    },
    'script:192_8:diag13': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>干嘛啊，<c12/>?\n<SURNAME/>本大爷正忙着跟老爷爷探讨男子汉之道，\n<SURNAME/>别打扰啊。\n'],
    },
    'script:192_8:diag14': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>哎呀(アイヤー)好一股霉味!!\n'],
    },
    'script:192_8:diag15': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>真是的!!\n<SURNAME/>到底有没有好好晒被子啊!?\n<SURNAME/>这壁柜里也没有钥匙呢~\n'],
    },
    'script:192_8:diag16': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>哇!!<pause:30/>\n'],
    },
    'script:192_8:diag17': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>这衣柜里面，\n<SURNAME/>全是吉川小百合的剪报和写真照…\n'],
    },
    'script:192_8:diag18': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>虽然没找到钥匙，但找到下饭菜了。<pause:30/>\n<SURNAME/>那位阿姨嘴上抱怨，\n<SURNAME/>还是有好好照顾老爷子的嘛。'],
    },
    'script:192_8:diag19': {
        'meta_zh': '校医阿姨',
        'zh_pages': ['\n<SURNAME/>呵呵呵。\n<SURNAME/>老头儿啊，什么东西都立马就丢——\n<SURNAME/>人老了，真是辛苦呢——\n'],
    },
    'script:192_8:diag20': {
        'meta_zh': '校工',
        'zh_pages': ['\n<SURNAME/>钥匙…钥匙啊…\n<SURNAME/>总觉得每天都能看到呢…\n<SURNAME/>嘛，先吃饭吧。'],
    },
    'script:192_8:diag21': {
        'meta_zh': '海报',
        'zh_pages': ['\n<SURNAME/>传说中的女演员，吉川小百合的海报。\n<SURNAME/>嘴唇部分，不知为何湿乎乎的…'],
    },
    'script:192_8:diag22': {
        'meta_zh': '日历',
        'zh_pages': ['\n<SURNAME/>传说中的女演员，吉川小百合的日历。\n<SURNAME/>仔细一看，竟是 30 年前的!!\n<SURNAME/>嘴唇部分，不知为何湿乎乎的…'],
    },
    'script:192_8:diag23': {
        'meta_zh': '纸箱',
        'zh_pages': ['\n<SURNAME/>箱里不知为何放着粗麻绳和蜡烛…\n<SURNAME/>但愿是应急用的…'],
    },
    'script:192_8:diag24': {
        'meta_zh': '纸箱',
        'zh_pages': ['\n<SURNAME/>箱里不知为何放着粗麻绳和蜡烛…\n<SURNAME/>但愿是应急用的…'],
    },
    'script:192_8:diag25': {
        'meta_zh': '电视',
        'zh_pages': ['\n<SURNAME/>旧电视。<pause:30/>\n<SURNAME/>频道竟然是旋钮式的。'],
    },
    'script:192_8:diag26': {
        'meta_zh': '衣柜',
        'zh_pages': ['\n<SURNAME/>夹在吉川小百合的写真照中间…<pause:60/>\n<SURNAME/>找到了吉川小百合的剪报…'],
    },
    'script:192_8:diag27': {
        'meta_zh': '冰箱',
        'zh_pages': ['\n<SURNAME/>放着保鲜膜包好的下饭菜。'],
    },
    'script:192_8:diag28': {
        'meta_zh': '水槽',
        'zh_pages': ['\n<SURNAME/>里面什么都没有。'],
    },
    'script:192_8:diag29': {
        'meta_zh': '壁柜',
        'zh_pages': ['\n<SURNAME/>收着被子。'],
    },
    'script:192_8:diag30': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/><c12/>怎么了?\n<SURNAME/>找不到钥匙，钟楼可进不去哦。'],
    },

    # ===== 193_8 钟楼内部 =====
    'script:193_8:diag0': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>咳!\n<SURNAME/>感觉好脏哦…<pause:30/>\n<SURNAME/>本大爷完美的发型要被弄脏了。\n'],
    },
    'script:193_8:diag1': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>般若先生似乎也不在，\n<SURNAME/>赶紧把大钟砸了，\n<SURNAME/>从这种地方告别吧。\n'],
    },
    'script:193_8:diag2': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>那么，刚才那股感觉…<pause:30/>\n<SURNAME/>到底是怎么回事呢…?\n'],
    },
    'script:193_8:diag3': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>内、内、内裤番长!\n<SURNAME/>呜呜，后面，后面后面啊!!\n'],
    },
    'script:193_8:diag4': {
        'meta_zh': '教师之灵',
        'zh_pages': ['\n<SURNAME/>…告诉过…\n'],
    },
    'script:193_8:diag5': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>…诶?\n'],
    },
    'script:193_8:diag6': {
        'meta_zh': '教师之灵',
        'zh_pages': ['\n<SURNAME/>…时间<pause:30/>…不可<pause:30/>…再动…<pause:30/>\n<SURNAME/>…我已<pause:30/>…千叮万嘱…\n'],
    },
    'script:193_8:diag7': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>消失了…<pause:30/>\n<SURNAME/>不过，刚才那人好像在哪儿…\n'],
    },
    'script:193_8:diag8': {
        'meta_zh': '荣吉<SURNAME/>丽莎',
        'zh_pages': ['\n<SURNAME/>…见过!!\n'],
    },
    'script:193_8:diag9': {
        'meta_zh': '???',
        'zh_pages': ['\n<SURNAME/>哈哈哈哈!\n<SURNAME/>\n'],
    },
    'script:193_8:diag10': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>这声音…是般若!?\n<SURNAME/>在上面!\n'],
    },
    'script:193_8:diag11': {
        'meta_zh': '<c13/><SURNAME/>荣吉<SURNAME/>丽莎',
        'zh_pages': ['\n<SURNAME/>小丑!!\n'],
    },
    'script:193_8:diag12': {
        'meta_zh': '麻耶<SURNAME/>雪乃',
        'zh_pages': ['\n<SURNAME/>那就是…小丑!?\n'],
    },
    'script:193_8:diag13': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>般若校长!!\n<SURNAME/>果然你跟小丑勾结上了!\n'],
    },
    'script:193_8:diag14': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>纹章诅咒，还有大家变得不正常，\n<SURNAME/>都是你跟小丑搞的鬼对吧!?\n<SURNAME/>从实招来!!\n'],
    },
    'script:193_8:diag15': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>你说什么呢，臭丫头!!\n<SURNAME/>「纹章诅咒」乃是学生品行招致的\n<SURNAME/>天罚!\n'],
    },
    'script:193_8:diag16': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>你们这帮家伙，忘了学生本分，\n<SURNAME/>整日浑浑噩噩，\n<SURNAME/>满脑子只装着异性和外表!\n'],
    },
    'script:193_8:diag17': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>中了诅咒，也是自作自受!\n<SURNAME/>不过呢，渣校生因嫉妒而起的传闻，\n<SURNAME/>居然真的成真，倒是我没料到的…\n'],
    },
    'script:193_8:diag18': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>但只要拜托小丑大人，\n<SURNAME/>学生们的脸瞬间就能恢复如初。\n'],
    },
    'script:193_8:diag19': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>不仅如此，只要追随小丑大人，\n<SURNAME/>就能拥有更有意义的人生!\n'],
    },
    'script:193_8:diag20': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>那你呢，靠小丑的力量\n<SURNAME/>得到了什么!?\n'],
    },
    'script:193_8:diag21': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>哈哈哈!<SURNAME/>我?\n<SURNAME/>成为受学生爱戴的校长，还有…<pause:30/>\n<SURNAME/>这一头浓密的头发!!\n'],
    },
    'script:193_8:diag22': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>小丑!!\n<SURNAME/>你的目的，\n<SURNAME/>不是对我们复仇吗!?\n'],
    },
    'script:193_8:diag23': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>实现这么个蠢老头的理想，\n<SURNAME/>到底有啥意思!?\n'],
    },
    'script:193_8:diag24': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>天空闪耀的<SURNAME/>昴之星，\n<SURNAME/>唤动了<SURNAME/>停滞的时间…\n'],
    },
    'script:193_8:diag25': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>我的目的，不仅仅是复仇。\n'],
    },
    'script:193_8:diag26': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>这是身为「赐予者」的我，\n<SURNAME/>与身为「祈求者」的你…<pause:30/>\n<SURNAME/><c12/><SURNAME/><c13/>之间，为梦境一战!\n'],
    },
    'script:193_8:diag27': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>绝不让你再夺走我的梦…<pause:30/>\n<SURNAME/>绝不让同样的错误再次重演!\n'],
    },
    'script:193_8:diag28': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>那孩子，在哭…?\n'],
    },
    'script:193_8:diag29': {
        'meta_zh': '小丑',
        'zh_pages': ['\n<SURNAME/>时间已再度开始流动…<pause:30/>\n<SURNAME/>聆听昭示梦境的钟声吧!\n'],
    },
    'script:193_8:diag30': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>该死!!\n<SURNAME/>休想让你逃了!\n'],
    },
    'script:193_8:diag31': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>嘿，那边的!\n<SURNAME/>训导处分啊啊!!\n'],
    },
    'script:193_8:diag32': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>啊呀!\n<SURNAME/>别挡道啊!!\n'],
    },
    'script:193_8:diag33': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>来吧，臭小子们!\n<SURNAME/>此处就是你们的训导室!\n<SURNAME/>耶尔·卡梅恩!!\n'],
    },
    'script:193_8:diag34': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>What?<NAME/><NAME/>怎么了，everybody?\n<SURNAME/>本大爷脸上沾了什么…\n'],
    },

    # ===== 194_8 战后 =====
    'script:194_8:diag0': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>是我们赢啦!\n<SURNAME/>关于小丑你知道的事，\n<SURNAME/>就——全部告诉我们吧!\n'],
    },
    'script:194_8:diag1': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>啥、啥情况!?\n'],
    },
    'script:194_8:diag2': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>大家小心!\n<SURNAME/>要塌了!!\n'],
    },
    'script:194_8:diag3': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>哎哟哟…\n<SURNAME/>大家没事吧?\n'],
    },
    'script:194_8:diag4': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>啊!!\n<SURNAME/>臭小子，给我等等!\n'],
    },
    'script:194_8:diag5': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>今天的训导到此为止!\n<SURNAME/>不过只要你们违抗小丑大人，\n<SURNAME/>就别想有安宁!\n'],
    },
    'script:194_8:diag6': {
        'meta_zh': '般若校长',
        'zh_pages': ['\n<SURNAME/>哇啊啊————!!!\n'],
    },
    'script:194_8:diag7': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>这可是 4 楼啊!?\n<SURNAME/>嘛…<pause:30/>那老头看起来死不了。\n'],
    },
    'script:194_8:diag8': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>小丑…<pause:30/>\n<SURNAME/>痛苦地孤独着，\n<SURNAME/>心底深处怀着深深的罪恶感…\n'],
    },
    'script:194_8:diag9': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>那孩子，总觉得有点像<c13/>君…<pause:30/>\n<SURNAME/>我好像在哪儿见过他。\n'],
    },
    'script:194_8:diag10': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>「见此身姿<SURNAME/>吾心战栗\n<SURNAME/><SURNAME/>月影所映<SURNAME/>乃吾<SURNAME/>己身\n<SURNAME/><SURNAME/>汝<SURNAME/>吾之分身<SURNAME/>苍白之人」\n'],
    },
    'script:194_8:diag11': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>「何故<SURNAME/>汝<SURNAME/>过往之日\n<SURNAME/><SURNAME/>多少夜晚<SURNAME/>困于此地\n<SURNAME/><SURNAME/>吾之苦恼<SURNAME/>汝竟重演」\n'],
    },
    'script:194_8:diag12': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>这是首叫「二重身」的诗哦。\n<SURNAME/><c13/>君知道吗?\n'],
    },
    'script:194_8:diag13': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>麻耶姐…<pause:30/>该不会，\n<SURNAME/>你想说小丑是<c12/>的二重身吧?\n'],
    },
    'script:194_8:diag14': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>怎么会!!\n<SURNAME/>只是觉得有点像而已!\n<SURNAME/>别在意哦，<c13/>君。\n'],
    },
    'script:194_8:diag15': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>喂!(ワーイ)接下来咋办?\n<SURNAME/>般若也逃了，\n<SURNAME/>找小丑的线索也没了。\n'],
    },
    'script:194_8:diag16': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>Let\'s positive thinking!\n<SURNAME/>越是这种时候越要积极乐观，对吧?\n<SURNAME/>线索还没归零哦。\n'],
    },
    'script:194_8:diag17': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>顺着传闻追下去!\n<SURNAME/>传闻一定能把我们\n<SURNAME/>带到小丑那里。\n'],
    },
    'script:194_8:diag18': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>有道理，是个好主意!\n<SURNAME/>般若说过，「纹章诅咒」的传闻源头\n<SURNAME/>是渣校的学生嘛。\n'],
    },
    'script:194_8:diag19': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>姐姐，等等啊!\n<SURNAME/>本米切大人当番长的春日山高中里，\n<SURNAME/>没一个人会散布那种传闻!\n'],
    },
    'script:194_8:diag20': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>去查也是浪费时间。\n<SURNAME/>要查就去别的地方查吧。\n'],
    },
    'script:194_8:diag21': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>关于小丑和传闻的事，\n<SURNAME/>本校新闻部部长也在调查呢。\n<SURNAME/>差不多该查出点东西了吧?\n'],
    },
    'script:194_8:diag22': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>花姐的话，\n<SURNAME/>去梦崎区的和平餐厅应该能见到她。\n<SURNAME/>总之先去和平餐厅看看?\n'],
    },
    'script:194_8:diag23': {
        'meta_zh': '女学生',
        'zh_pages': ['\n<SURNAME/>听说校长为了解开纹章诅咒\n<SURNAME/>去了钟楼…\n<SURNAME/>呐，你们看到校长了吗?\n'],
    },
    'script:194_8:diag24': {
        'meta_zh': '女学生',
        'zh_pages': ['\n<SURNAME/>难、难道…<pause:30/>\n<SURNAME/>校长被钟楼倒塌卷进去了?\n<SURNAME/>不会吧…<pause:30/>他不会就这么死了吧!?\n'],
    },
    'script:194_8:diag25': {
        'meta_zh': '<SURNAME/>他不会就这么死了吧!?\n<option:2/>死了\n还活着\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:194_8:diag26': {
        'meta_zh': '女学生',
        'zh_pages': ['\n<SURNAME/>怎么会!\n<SURNAME/>为了守护我们，居然就这么走了…<pause:30/>\n<SURNAME/>谢谢您校长…<pause:30/>再见了…\n'],
    },
    'script:194_8:diag27': {
        'meta_zh': '女学生',
        'zh_pages': ['\n<SURNAME/>就是嘛!<SURNAME/>校长可是不死之身!\n<SURNAME/>等学校危急的时候，\n<SURNAME/>一定会再次现身守护我们的!!\n'],
    },
    'script:194_8:diag28': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>那家伙一个人嗨得很哪。\n<SURNAME/>但愿别又传出什么怪传闻…<pause:30/>\n<SURNAME/>那么，咱们去和平餐厅吧。\n'],
    },

    # ===== 197_8 集会 =====
    'script:197_8:diag0': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>那个笨蛋番长，这里也没有!?\n<SURNAME/>真有这种乱搞团体行动的家伙呢。\n<SURNAME/>真是的，自私自利!!\n'],
    },
    'script:197_8:diag1': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>女士?<SURNAME/>面具?<SURNAME/>卡片?\n<SURNAME/>有猫腻，绝对有猫腻!\n<SURNAME/>这里头肯定藏着什么!\n'],
    },
    'script:197_8:diag2': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>嗯—荣吉君的事也让人担心，\n<SURNAME/>得想办法混进那个秘密俱乐部里去\n<SURNAME/>才行…\n'],
    },
    'script:197_8:diag3': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/><c12/>，\n<SURNAME/>你这刀法可不一般呢。\n'],
    },
    'script:197_8:diag4': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>以前我那伙伴里也有个用刀的，\n<SURNAME/>你跟他不相上下。\n<SURNAME/>徒手功夫也很自信吧?\n'],
    },
    'script:197_8:diag5': {
        'meta_zh': '<SURNAME/>徒手功夫也很自信吧?\n<option:2/>是的\n没有\n<option_end/><c02/>',
        'zh_pages': [],
    },
    'script:197_8:diag6': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>嗯，果然如此。\n<SURNAME/>怎么样?\n<SURNAME/>下次跟我一起谈判试试?\n'],
    },
    'script:197_8:diag7': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>啊，是这样吗?\n<SURNAME/>嘛，刀使得那么好就没问题。\n<SURNAME/>就靠你了，<c12/>。\n'],
    },
    'script:197_8:diag8': {
        'meta_zh': '戴面具的青年',
        'zh_pages': ['\n<SURNAME/>你们也是头一次来「集会」吧?\n<SURNAME/>听说今天被叫来的家伙们，\n<SURNAME/>都是新来的呢。\n'],
    },
    'script:197_8:diag9': {
        'meta_zh': '戴面具的青年',
        'zh_pages': ['\n<SURNAME/>女士寄来卡片，让带面具来参加吧?\n<SURNAME/>没面具的话可进不去秘密俱乐部哦?\n'],
    },
    'script:197_8:diag10': {
        'meta_zh': '戴面具的女高中生',
        'zh_pages': ['\n<SURNAME/>集会什么的有点土，\n<SURNAME/>就当白拿了张派对入场券嘛。\n<SURNAME/>烦恼很久的大嘴还帮我缩小了呢。\n'],
    },
    'script:197_8:diag11': {
        'meta_zh': '戴面具的高中生',
        'zh_pages': ['\n<SURNAME/>哎呀，我啊，把发的面具给忘了!\n<SURNAME/>当时想完了完了，\n<SURNAME/>结果那边纸箱里有，得救啦!!\n'],
    },
    'script:197_8:diag12': {
        'meta_zh': '纸箱',
        'zh_pages': ['\n<SURNAME/>得到了<c1d:9/>谜之面具<c1d:1/>。\n'],
    },
    'script:197_8:diag13': {
        'meta_zh': '纸箱',
        'zh_pages': ['\n<SURNAME/><c1d:9/>里面什么也没有。<c1d:1/>\n'],
    },

    # ===== 200_8 拷问头目 =====
    'script:200_8:diag0': {
        'meta_zh': '头目',
        'zh_pages': ['\n<SURNAME/>呜!\n<SURNAME/>饶、饶了我…<pause:30/>\n<SURNAME/>就、就别把内裤扒下来啊啊!!\n'],
    },
    'script:200_8:diag1': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>老子没资格指责杉本。\n<SURNAME/>老子过去干的事，跟他一个样。\n'],
    },
    'script:200_8:diag2': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>嘴上说着「不能欺负弱小」，\n<SURNAME/>装出一副正义伙伴的派头…\n<SURNAME/>那不过是借口罢了。\n'],
    },
    'script:200_8:diag3': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>用 Persona 揍别人，\n<SURNAME/>把它当正当理由的借口…<pause:30/>\n<SURNAME/>那种玩意儿，根本算不上男子汉气概!\n'],
    },
    'script:200_8:diag4': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>哎呀!?(アイヤー)\n<SURNAME/>平时那个嘚瑟自恋的你\n<SURNAME/>哪里去啦?'],
    },
    'script:200_8:diag5': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>至少刚才的你…<pause:30/>\n<SURNAME/>呃…\n<SURNAME/>还、还挺帅气的哦!\n'],
    },
    'script:200_8:diag6': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>嗯嗯。\n<SURNAME/>就算没有 Persona，\n<SURNAME/>荣吉君也是个堂堂的男子汉哦!\n'],
    },
    'script:200_8:diag7': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>抱歉啊，让你们费心了…<pause:30/>\n<SURNAME/>总之，今天起老子不当番长了。\n'],
    },
    'script:200_8:diag8': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>呃那个，华小路同学。\n<SURNAME/>你、你没事…才怪呢，对吧?\n'],
    },
    'script:200_8:diag9': {
        'meta_zh': '雅',
        'zh_pages': ['\n<SURNAME/>对不起，荣吉君!\n<SURNAME/>给你添麻烦了…<pause:30/>\n<SURNAME/>真的对不起!!\n'],
    },
    'script:200_8:diag10': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>老子的事无所谓。\n<SURNAME/>比起这个，你脸上的伤…\n'],
    },
    'script:200_8:diag11': {
        'meta_zh': '雅',
        'zh_pages': ['\n<SURNAME/>不要!\n<SURNAME/>别看我，荣吉君…<pause:30/>\n<SURNAME/>对不起!!\n'],
    },
    'script:200_8:diag12': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>华小路同学!?\n'],
    },
    'script:200_8:diag13': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>来，老老实实全招了吧。\n<SURNAME/>不然，可不只是扒内裤那么简单了。\n'],
    },
    'script:200_8:diag14': {
        'meta_zh': '头目',
        'zh_pages': ['\n<SURNAME/>呜!\n<SURNAME/>我、我说，我说!\n<SURNAME/>什么都说，什么都说!\n'],
    },
    'script:200_8:diag15': {
        'meta_zh': '雪乃',
        'zh_pages': ['\n<SURNAME/>你为何要指使渣校的学生们，\n<SURNAME/>散布七姊妹纹章\n<SURNAME/>被诅咒的传闻?\n'],
    },
    'script:200_8:diag16': {
        'meta_zh': '头目',
        'zh_pages': ['\n<SURNAME/>是、是学生会长拜托的!!\n<SURNAME/>他说只要搞砸看不顺眼的七姊妹的名声，\n<SURNAME/>就用小丑大人的力量让我当头目!\n'],
    },
    'script:200_8:diag17': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>康夫那家伙…<pause:30/>\n<SURNAME/>被老子甩了之后，\n<SURNAME/>就把杉本当下家盯上了啊!\n'],
    },
    'script:200_8:diag18': {
        'meta_zh': '麻耶',
        'zh_pages': ['\n<SURNAME/>刚才在场的那帮人，说今天是来这里\n<SURNAME/>参加「集会」的吧?\n<SURNAME/>到底是什么「集会」?\n'],
    },
    'script:200_8:diag19': {
        'meta_zh': '头目',
        'zh_pages': ['\n<SURNAME/>被小丑大人实现理想的家伙，\n<SURNAME/>都得加入一个组织。\n<SURNAME/>今天的集会就是入党仪式，我听说的。\n'],
    },
    'script:200_8:diag20': {
        'meta_zh': '头目',
        'zh_pages': ['\n<SURNAME/>对、对了…<pause:30/>\n<SURNAME/>还听说集会上「蝎子女郎」这个\n<SURNAME/>组织的干部会来。\n'],
    },
    'script:200_8:diag21': {
        'meta_zh': '头目',
        'zh_pages': ['\n<SURNAME/>我、我今天也是头一回参加，\n<SURNAME/>再多的真的不知道了!\n<SURNAME/>求求你饶了我吧…\n'],
    },
    'script:200_8:diag22': {
        'meta_zh': '荣吉',
        'zh_pages': ['\n<SURNAME/>看来没撒谎…<pause:30/>\n<SURNAME/>好，就饶了你这一回。\n<SURNAME/>以后再敢靠近小丑，就别怪老子!\n'],
    },
    'script:200_8:diag23': {
        'meta_zh': '丽莎',
        'zh_pages': ['\n<SURNAME/>这下传闻幕后黑手清楚了。\n<SURNAME/>目标，渣校学生会长!!\n<SURNAME/>抓住他，狠狠揍一顿!\n'],
    },
}
PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'all_translatable.json')
data = json.load(open(PATH, encoding='utf-8'))
applied = 0
for entry in data:
    eid = entry['id']
    if eid not in T: continue
    tr = T[eid]
    if 'meta_zh' in tr and tr['meta_zh']:
        entry['meta_zh'] = tr['meta_zh']
    for i, zh in enumerate(tr.get('zh_pages', [])):
        if i < len(entry['pages']):
            entry['pages'][i]['zh'] = zh
    applied += 1
with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f'已应用 {applied} 条翻译')
