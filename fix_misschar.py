"""把字库没有的罕用字(频率1被丢)在译文里换成常用同义词短语(CN→CN, 不占字库)。
作用于 out/field_text_zh.json 的 zh。运行后重 build 即生效。
"""
import json

# 罕用字短语 → 常用同义短语(保意)。长键优先。
REPL = {
    '摩羯座': '山羊座', '脚镣': '锁链', '迷途的羔羊': '迷途的羊', '低贱': '卑劣',
    '糠酱': '浆糊', '长蘑菇': '长霉', '谄媚': '奉承', '陈腐': '老套', '生蛆': '长虫',
    '艰险': '坎坷', '脾气': '性子', '内讧': '内斗', '金鱼缸': '金鱼盆', '馒头': '包子',
    '怒不可遏': '怒火中烧', '舔尽': '吞尽', '苟活': '活命', '苟且': '将就', '苟延残喘': '勉强维持',
}


def main():
    fz = json.load(open('out/field_text_zh.json', encoding='utf-8'))
    n = 0
    hit = {}
    for it in fz:
        z = it.get('zh') or ''
        if not z:
            continue
        z2 = z
        for a, b in sorted(REPL.items(), key=lambda x: -len(x[0])):
            if a in z2:
                z2 = z2.replace(a, b); hit[a] = hit.get(a, 0) + 1
        if z2 != z:
            it['zh'] = z2; n += 1
    json.dump(fz, open('out/field_text_zh.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print(f'换字 {n} 处 → out/field_text_zh.json')
    print('命中:', hit)


if __name__ == '__main__':
    main()
