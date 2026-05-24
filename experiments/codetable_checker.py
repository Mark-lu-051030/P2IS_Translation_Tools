import json, sys, os

FONT_PATH = '/home/mark/Code/ROMHacking/games/Persona2IS/extrac/D/F0086.BIN'
PROGRESS_FILE = 'codetable_progress.json'
font = open(FONT_PATH, 'rb').read()

def render(idx):
    off = 0x480 + idx * 18
    print('┌' + '─' * 24 + '┐')
    for row in range(12):
        line = ''
        for col in range(12):
            n = row * 12 + col
            bit = (font[off + n // 8] >> (n % 8)) & 1
            line += '██' if bit else '  '
        print('│' + line + '│')
    print('└' + '─' * 24 + '┘')

def load_progress():
    if os.path.exists(PROGRESS_FILE):
        return json.load(open(PROGRESS_FILE, encoding='utf-8')).get('last', 0)
    return 0

def save_progress(pos):
    json.dump({'last': pos}, open(PROGRESS_FILE, 'w', encoding='utf-8'))

def main_loop():
    with open('codetable.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    changed = {}
    pending_mode = len(sys.argv) > 1 and sys.argv[1] == '?'

    if pending_mode:
        queue = [int(k) for k, v in sorted(data.items(), key=lambda x: int(x[0]))
                 if isinstance(v, str) and v.startswith('[?')]
        print(f'(待定模式：共 {len(queue)} 条)')
        qi = 0
        while qi < len(queue):
            i = queue[qi]
            ch = data.get(str(i), '')
            print(f'\n索引 {i}  当前: {repr(ch)}  [{qi+1}/{len(queue)}]')
            render(i)
            action = input('ENTER=跳过  字符=改  ?=继续待定  b=后退  q=保存退出: ').strip()

            if action == 'q':
                break
            elif action == 'b':
                qi = max(0, qi - 1)
                continue
            elif action in ('', '?'):
                qi += 1
            else:
                data[str(i)] = action
                changed[i] = action
                print(f'  → 已改为 {repr(action)}')
                qi += 1
    else:
        if len(sys.argv) > 1:
            start = int(sys.argv[1])
        else:
            start = load_progress()
            print(f'(从上次进度继续: 索引 {start})')

        total = max(int(k) for k in data) + 1
        i = start
        while i < total:
            ch = data.get(str(i), '')
            print(f'\n索引 {i}  当前: {repr(ch)}')
            render(i)
            action = input('ENTER=正确  字符=改  ?=待定  b=后退  q=保存退出: ').strip()

            if action == 'q':
                break
            elif action == 'b':
                i = max(start, i - 1)
                continue
            elif action == '':
                i += 1
            elif action == '?':
                marker = f'[?{i}]'
                data[str(i)] = marker
                changed[i] = marker
                print(f'  → 已标记为待定 {marker}')
                i += 1
            else:
                data[str(i)] = action
                changed[i] = action
                print(f'  → 已改为 {repr(action)}')
                i += 1

        save_progress(i)
        print(f'(进度已保存: 索引 {i})')

    if changed:
        print(f'\n修改了 {len(changed)} 条')
        with open('codetable.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
        print('已保存')

main_loop()
