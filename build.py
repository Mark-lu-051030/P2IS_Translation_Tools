"""
P2IS 汉化一键打包。
读 all_translatable.json 的 zh 字段 → 产出可玩的中文 ISO。

流程：
  1. 还原 ISO 从备份（默认；--no-restore 跳过用于增量场景）
  2. 注入中文字体 → 文件 59 sub-file 0（inject_chinese_font.py）
  3. 编码 zh 翻译 → out/scripts_zh/（encode_zh.py）
  4. 把每个编码文件应用到 ISO（apply_zh.mjs，含自动 ECC）
  5. 总结

用法:
  python3 build.py                # 完整流水线
  python3 build.py --no-restore   # 跳过 ISO 还原（增量更新）
  python3 build.py --no-font      # 跳过字体注入（仅 zh 文本变化时用，risky）
  python3 build.py --only 181,3   # 只 apply 指定 file_id（逗号分隔）
"""
import argparse, json, os, re, shutil, subprocess, sys, time

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO    = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
BACKUP = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'

SCRIPTS_ZH_DIR = os.path.join(ROOT, 'out', 'scripts_zh')
REPORT_DIR     = os.path.join(ROOT, 'out', 'build_report')

# ── 工具 ────────────────────────────────────────────────────────────────────

def step(label):
    print(f'\n\033[1;36m━━━ {label} ━━━\033[0m')

def run(cmd, **kw):
    """跑子进程，失败抛异常。"""
    print(f'  $ {" ".join(cmd)}')
    subprocess.run(cmd, check=True, cwd=ROOT, **kw)

def sanity_check_no_pollution():
    """检查 all_translatable.json 的 jp 字段没有被中文污染。

    污染信号：jp 字段含有字符 c，但 c 不在 codetable_og 里（即只能由字体注入的中文 slot 产生）。
    如果发现污染，提示用户重跑 export_translatable.py 或重 extract。
    """
    transp = os.path.join(ROOT, 'all_translatable.json')
    if not os.path.exists(transp):
        return  # 还没生成，跳过
    og = json.load(open(os.path.join(ROOT, 'codetable_og.json'), encoding='utf-8'))
    og_chars = set(og.values())
    data = json.load(open(transp, encoding='utf-8'))
    bad = []
    for e in data:
        for p in e.get('pages', []):
            jp = p.get('jp', '') or ''
            for ch in jp:
                if '一' <= ch <= '鿿' and ch not in og_chars:
                    bad.append((e['id'], ch))
                    break
            if bad and bad[-1][0] == e['id']: break
        if len(bad) >= 5: break
    if bad:
        print(f'\n\033[1;31m⚠ 污染告警: all_translatable.json 的 jp 字段含非日文 codetable 字符\033[0m')
        for eid, ch in bad[:5]:
            print(f'    {eid}: 含字符 "{ch}"（不在 codetable_og 里）')
        print(f'  → 这表明数据是从被改过的 ISO 反向提取的。建议：')
        print(f'    1) node p2ep_tool.mjs extract_script 0 880 -o out/scripts')
        print(f'    2) python3 export_translatable.py')
        print(f'  继续构建可能产生错误的翻译输出。\n')

def count_zh_translations():
    """返回 (script_count, strtbl_count, battle_count) of entries with non-empty zh."""
    data = json.load(open(os.path.join(ROOT, 'all_translatable.json'), encoding='utf-8'))
    counts = {'script': 0, 'strtbl': 0, 'battle': 0, 'other': 0}
    for e in data:
        for p in e['pages']:
            if not p.get('zh', '').strip():
                continue
            kind = e['id'].split(':')[0]
            counts[kind if kind in counts else 'other'] += 1
    return counts

# ── 流水线步骤 ──────────────────────────────────────────────────────────────

def step_restore():
    step('1. 还原 ISO（从备份）')
    if not os.path.exists(BACKUP):
        print(f'  ✗ 备份不存在: {BACKUP}')
        sys.exit(1)
    t0 = time.time()
    shutil.copy(BACKUP, ISO)
    print(f'  ✓ 已还原 ({time.time()-t0:.1f}s, {os.path.getsize(ISO)//1024//1024} MB)')

def step_inject_font():
    step('2. 注入中文字体 → 文件 59 sub-file 0')
    run(['python3', 'inject_chinese_font.py'])

def step_encode_zh():
    step('3. 编码 zh 翻译 → out/scripts_zh/')
    run(['python3', 'encode_zh.py'])

def step_apply(only=None):
    """对 out/scripts_zh/ 里每个文件跑 apply_zh.mjs。
    only: set of file_id ints to filter, or None for all."""
    step('4. 把翻译应用到 ISO（含自动 ECC）')
    # 清空旧报告，避免上次跑剩的数据污染聚合
    if os.path.isdir(REPORT_DIR):
        for f in os.listdir(REPORT_DIR):
            if f.endswith('.json'):
                os.remove(os.path.join(REPORT_DIR, f))
    files = sorted(os.listdir(SCRIPTS_ZH_DIR))
    print(f'  out/scripts_zh/ 里 {len(files)} 个文件')
    applied = 0
    skipped = 0
    failed = []
    for fname in files:
        m = re.match(r'^(\d+)_(\d+)\.json$', fname)
        if not m:
            skipped += 1; continue
        file_id, sub_id = int(m.group(1)), int(m.group(2))
        if only is not None and file_id not in only:
            skipped += 1; continue
        print(f'\n  → apply file {file_id} sub {sub_id}')
        try:
            run(['node', 'apply_zh.mjs', str(file_id), str(sub_id)])
            applied += 1
        except subprocess.CalledProcessError as e:
            failed.append((file_id, sub_id, str(e)))
            print(f'  ✗ apply {file_id}_{sub_id} 失败: {e}')
    print(f'\n  Apply 总结: {applied} 成功 / {skipped} 跳过 / {len(failed)} 失败')
    if failed:
        for f, s, err in failed:
            print(f'    ✗ {f}_{s}: {err}')
        return False
    return True

def aggregate_reports():
    """读 out/build_report/*.json，返回 {success: int, skipped: [{file, diag, reason, detail}], by_reason: {}}"""
    if not os.path.isdir(REPORT_DIR):
        return None
    total_success = 0
    skipped = []
    for fname in sorted(os.listdir(REPORT_DIR)):
        if not fname.endswith('.json') or fname == 'summary.json': continue
        r = json.load(open(os.path.join(REPORT_DIR, fname), encoding='utf-8'))
        total_success += len(r.get('success', []))
        for s in r.get('skipped', []):
            skipped.append({**s, 'file': r['file'], 'sub': r['sub']})
    from collections import Counter
    by_reason = Counter(s['reason'] for s in skipped)
    return {
        'success': total_success,
        'skipped': skipped,
        'by_reason': dict(by_reason),
    }

def step_summary():
    step('5. 完成')
    c = count_zh_translations()
    total = sum(c.values())
    print(f'  翻译统计（all_translatable.json 里 zh 非空）:')
    print(f'    script: {c["script"]}')
    print(f'    strtbl: {c["strtbl"]} (当前不会被 apply，pipeline 仅处理 script)')
    print(f'    battle: {c["battle"]} (当前不会被 apply)')
    print(f'    other:  {c["other"]}')
    print(f'  总计: {total} pages 已翻译')

    # 聚合 apply 报告
    rep = aggregate_reports()
    if rep:
        print(f'\n  Apply 统计（所有 file/sub）:')
        print(f'    ✓ 成功: {rep["success"]} 条对话')
        if rep['skipped']:
            print(f'    ⚠ 跳过: {len(rep["skipped"])} 条对话')
            for reason, n in rep['by_reason'].items():
                label = {
                    'no_offset':    '不在 script 指令表里',
                    'parse_failed': '原对话解析失败（可能 extract bug）',
                    'too_big':      '译文太长塞不下',
                }.get(reason, reason)
                print(f'      - {label}: {n} 条')
            print(f'\n    具体跳过的 dialog 列表:')
            for s in rep['skipped'][:20]:
                tag = f'{s["file"]}_{s["sub"]}:{s["diag"]}'
                print(f'      {tag:20s} → {s["reason"]:14s} {s["detail"]}')
            if len(rep['skipped']) > 20:
                print(f'      …还有 {len(rep["skipped"])-20} 条，见 out/build_report/')
        # 写 summary.json
        with open(os.path.join(REPORT_DIR, 'summary.json'), 'w', encoding='utf-8') as f:
            json.dump(rep, f, ensure_ascii=False, indent=2)
        print(f'\n  📄 详细报告: out/build_report/summary.json')

    if c['strtbl'] or c['battle']:
        print(f'\n  ⚠ strtbl/battle 翻译未应用（encode_zh.py 仅处理 script）')
    print(f'\n  ✅ ISO 已就绪: {ISO}')
    print(f'     冷启动 DuckStation → 加载 ISO → 从标题画面开新游戏')

# ── 主函数 ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description='P2IS 汉化一键打包')
    ap.add_argument('--no-restore', action='store_true', help='跳过 ISO 还原（增量场景）')
    ap.add_argument('--no-font',    action='store_true', help='跳过字体注入（仅 zh 文本变化时）')
    ap.add_argument('--no-encode',  action='store_true', help='跳过 encode_zh.py（用已有 out/scripts_zh/）')
    ap.add_argument('--only',       help='只 apply 指定 file_id 列表（逗号分隔，e.g. 181,3）')
    args = ap.parse_args()

    only = None
    if args.only:
        only = set(int(x) for x in args.only.split(','))
        print(f'仅处理 file_id: {sorted(only)}')

    t_start = time.time()
    try:
        sanity_check_no_pollution()
        if not args.no_restore: step_restore()
        else:                   print('\n[跳过] ISO 还原')
        if not args.no_font:    step_inject_font()
        else:                   print('\n[跳过] 字体注入')
        if not args.no_encode:  step_encode_zh()
        else:                   print('\n[跳过] 编码')
        ok = step_apply(only=only)
        step_summary()
        print(f'\n⏱  总耗时: {time.time()-t_start:.1f}s')
        sys.exit(0 if ok else 1)
    except subprocess.CalledProcessError as e:
        print(f'\n\033[1;31m✗ 流水线失败: {e}\033[0m')
        sys.exit(1)
    except KeyboardInterrupt:
        print(f'\n\033[1;33m⚠ 用户中断\033[0m')
        sys.exit(130)

if __name__ == '__main__':
    main()
