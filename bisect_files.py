#!/usr/bin/env python3
# 白屏二分定位工具: 把指定 FILEPOS 文件在 WORK 盘上整体还原成原版字节,或恢复成汉化版。
# 还原前自动把 WORK 当前版本快照到 out/bisect/file{id}.bin,restore 时写回,不用全量重build。
# 用法:
#   python3 bisect_files.py revert 63 69 70 71 72        # 还原这些文件为原版(自动快照)
#   python3 bisect_files.py restore 63 69                # 把快照(汉化版)写回
#   python3 bisect_files.py status 63 69 70              # 看当前是原版还是汉化版
# 自带 ECC 修复。文件 block/size 必须 WORK==原版(被 relocate 改过 FILEPOS 的会拒绝并提示)。
import json, os, struct, subprocess, sys

ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)
WORK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
ORIG = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin'
SECTOR, BO, BS = 0x930, 24, 2048
SNAP = 'out/bisect'

def rblk(f, blk, sz):
    out = bytearray()
    sec = blk * SECTOR
    while len(out) < sz:
        f.seek(sec + BO)
        out += f.read(min(BS, sz - len(out)))
        sec += SECTOR
    return bytes(out)

def wblk(f, blk, data):
    off, sec = 0, blk * SECTOR
    while off < len(data):
        c = min(BS, len(data) - off)
        f.seek(sec + BO)
        f.write(data[off:off+c])
        off += c; sec += SECTOR

def filepos(f):
    d = rblk(f, 0x17, 0x2400)
    return lambda fid: struct.unpack_from('<II', d, fid * 8)

def fix_ecc(blk, nsec):
    subprocess.run(['python3', 'fix_ecc.py', str(blk), str(blk + nsec - 1)],
                   check=True, stdout=subprocess.DEVNULL)

cmd, fids = sys.argv[1], [int(x) for x in sys.argv[2:]]
os.makedirs(SNAP, exist_ok=True)
fw = open(WORK, 'r+b'); fo = open(ORIG, 'rb')
fpW, fpO = filepos(fw), filepos(fo)

for fid in fids:
    blkW, szW = fpW(fid); blkO, szO = fpO(fid)
    if (blkW, szW) != (blkO, szO):
        print(f'✗ file{fid}: FILEPOS 不一致 W=({blkW},{szW}) O=({blkO},{szO}),跳过(被 relocate 过,需全量 build 处理)')
        continue
    snap = f'{SNAP}/file{fid}.bin'
    cur = rblk(fw, blkW, szW)
    org = rblk(fo, blkO, szO)
    if cmd == 'status':
        if cur == org: print(f'file{fid}: 原版')
        else:
            n = sum(a != b for a, b in zip(cur, org))
            print(f'file{fid}: 汉化版 (diff {n} 字节)')
        continue
    if cmd == 'revert':
        if cur == org: print(f'file{fid}: 已是原版,跳过'); continue
        if not os.path.exists(snap):
            open(snap, 'wb').write(cur)
        wblk(fw, blkW, org)
        fix_ecc(blkW, -(-szW // BS))
        print(f'✓ file{fid} → 原版 (快照存 {snap})')
    elif cmd == 'restore':
        if not os.path.exists(snap): print(f'✗ file{fid}: 无快照 {snap}'); continue
        data = open(snap, 'rb').read()
        if len(data) != szW: print(f'✗ file{fid}: 快照大小不符'); continue
        wblk(fw, blkW, data)
        fix_ecc(blkW, -(-szW // BS))
        print(f'✓ file{fid} → 汉化版(快照)')
    else:
        sys.exit(f'未知命令 {cmd}')
fw.close(); fo.close()
