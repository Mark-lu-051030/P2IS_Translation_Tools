"""
把 out/strtbl_zh/SLUS_*.json 写回 ISO。
SLPS executable (file 0) 不是 archive 格式，用 raw sector IO 直接覆写。

策略：
  - SLPS 在 ISO 上从 sector FILEPOS[0].block 开始（一般是 949）
  - 每个 SLUS_*.json 的 offset 字段 = 该 string table 在 file 0 内的字节 offset
  - 算 ISO 绝对 sector + within-sector offset，覆写 max_len 字节，修 ECC

用法: python3 apply_strtbl_slps.py
"""
import json, os, struct, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pylib.p2is import read_sectors, write_sectors

ROOT = os.path.dirname(os.path.abspath(__file__))
ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
FIX_ECC = os.path.join(ROOT, 'fix_ecc.py')
STRTBL_ZH = os.path.join(ROOT, 'out', 'strtbl_zh')
REPORT_DIR = os.path.join(ROOT, 'out', 'build_report')

# 读 FILEPOS[0] 得 SLPS 起始 sector
fp = read_sectors(ISO, 0x17, 4 * 2048)
SLPS_BLOCK = struct.unpack_from('<I', fp, 0)[0]
SLPS_SIZE  = struct.unpack_from('<I', fp, 4)[0]
print(f'SLPS file 0: block={SLPS_BLOCK}, size={SLPS_SIZE} bytes')


def items_to_bytes(items):
    """items 数组 → uint16 LE 字节流（同 apply_strtbl.mjs 的 items_to_bytes）"""
    out = bytearray()
    for item in items:
        if isinstance(item, list):
            cmd = item[0]
            val = 0x1100 | cmd
            out.append(val & 0xff)
            out.append((val >> 8) & 0xff)
            for arg in item[1:]:
                out.append(arg & 0xff)
                out.append((arg >> 8) & 0xff)
        else:
            out.append(item & 0xff)
            out.append((item >> 8) & 0xff)
    return bytes(out)


def apply_one(fname):
    data = json.load(open(os.path.join(STRTBL_ZH, fname), encoding='utf-8'))
    offset_in_file = data['offset']
    max_len = data['max_len']
    strings = data['strings']

    print(f'\n=== {fname} (offset_in_slps={offset_in_file}, max_len={max_len}) ===')

    # 重建 string table 结构（关键！游戏靠索引表指针定位每个 string）：
    #   [count u32][ptr0 u32]...[ptrN u32][string0][string1]...  (ptr = 相对 table 起点字节偏移)
    import struct as _st
    N = len(strings)
    new_table = bytearray(max_len)
    _st.pack_into('<I', new_table, 0, N)         # count
    ind_ptr = 4
    str_ptr = N * 4 + 4
    seen = {}
    for items in strings:
        b = items_to_bytes(items)
        key = b.hex()
        if key in seen:
            _st.pack_into('<I', new_table, ind_ptr, seen[key])
        else:
            if str_ptr + len(b) > max_len:
                print(f'  ❌ too_big（需 {str_ptr+len(b)} > {max_len}）')
                return {'ok': False, 'reason': 'too_big', 'detail': f'{str_ptr+len(b)} > {max_len}'}
            _st.pack_into('<I', new_table, ind_ptr, str_ptr)
            new_table[str_ptr:str_ptr+len(b)] = b
            seen[key] = str_ptr
            str_ptr += len(b)
        ind_ptr += 4
    total = str_ptr
    print(f'  {N} strings → 索引表+数据 {total} 字节 (max {max_len}, 余 {max_len-total})')

    # 算 ISO 上的绝对位置
    abs_byte_offset = SLPS_BLOCK * 2048 + offset_in_file
    start_sector = abs_byte_offset // 2048
    in_sector_off = abs_byte_offset % 2048
    end_byte = abs_byte_offset + max_len
    end_sector = (end_byte + 2047) // 2048
    sector_count = end_sector - start_sector

    # 读相关 sectors 的 user data，覆写 max_len 字节，写回
    user_data = bytearray(read_sectors(ISO, start_sector, sector_count * 2048))
    user_data[in_sector_off:in_sector_off + max_len] = bytes(new_table)
    write_sectors(ISO, start_sector, bytes(user_data))

    # 修 ECC
    subprocess.run(['python3', FIX_ECC, str(start_sector), str(end_sector - 1)], check=True)
    print(f'  ✓ 写 sector {start_sector}-{end_sector - 1}（覆盖 in-sector offset {in_sector_off}+{max_len}B）')

    return {'ok': True, 'bytes': total, 'max': max_len}


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    if not os.path.isdir(STRTBL_ZH):
        print('out/strtbl_zh/ 不存在，跳过')
        return
    files = sorted(f for f in os.listdir(STRTBL_ZH) if f.startswith('SLUS_'))
    if not files:
        print('没有 SLUS_*.json 文件，跳过')
        return

    success = 0
    skipped = []
    for fname in files:
        try:
            r = apply_one(fname)
            if r['ok']:
                success += 1
            else:
                skipped.append({'file': fname, **r})
        except Exception as e:
            print(f'  ✗ {fname}: {e}')
            skipped.append({'file': fname, 'reason': 'error', 'detail': str(e)})

    print(f'\n=== SLPS strtbl 总结 ===')
    print(f'  成功: {success}')
    print(f'  跳过: {len(skipped)}')
    with open(os.path.join(REPORT_DIR, 'strtbl_slps_summary.json'), 'w', encoding='utf-8') as f:
        json.dump({'success': success, 'skipped': skipped}, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()
