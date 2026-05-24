"""
P2IS 工具的共享 Python 助手：扇区 IO、LZSS、Archive 解析。

修过的 bug：
  - lzss_compress 的 find_backref 之前贪心匹配 "data + 隐式零" → 产生越界 backref
    游戏解压器宽容（写越界静默忽略）但我们的 Python 严格（IndexError）
    现在限制 max_len = n - iptr，不让 backref 越过数据末尾。
  - lzss_decompress 内层循环加防御性 bounds check，遇到越界 backref 时
    （来自其他工具产生的旧文件）能安全降级而非崩溃。
"""
import struct

SECTOR = 2352
BLOCK_OFF = 0x18
BLOCK_SIZE = 0x800


# ── 扇区读写 ────────────────────────────────────────────────────────────────

def read_sectors(path, block, size):
    """从 PS1 ISO 读 `size` 字节有效数据，从扇区 `block` 开始（跳过扇区头 0x18）。"""
    data = bytearray()
    sec = block * SECTOR
    with open(path, 'rb') as f:
        while len(data) < size:
            f.seek(sec)
            raw = f.read(SECTOR)
            chunk = min(BLOCK_SIZE, size - len(data))
            data += raw[BLOCK_OFF:BLOCK_OFF + chunk]
            sec += SECTOR
    return bytearray(data[:size])


def write_sectors(path, block, data):
    """把 `data` 写回 ISO 扇区数据区（保留扇区头/ECC，后续要跑 fix_ecc.py）。"""
    sec = block * SECTOR
    off = 0
    with open(path, 'r+b') as f:
        while off < len(data):
            f.seek(sec)
            raw = bytearray(f.read(SECTOR))
            chunk = min(BLOCK_SIZE, len(data) - off)
            raw[BLOCK_OFF:BLOCK_OFF + chunk] = data[off:off + chunk]
            if chunk < BLOCK_SIZE:
                raw[BLOCK_OFF + chunk:BLOCK_OFF + BLOCK_SIZE] = bytes(BLOCK_SIZE - chunk)
            f.seek(sec)
            f.write(bytes(raw))
            off += chunk
            sec += SECTOR


# ── LZSS ────────────────────────────────────────────────────────────────────

def lzss_decompress(data, ptr, comp_size, uncomp_size):
    """游戏自定义 LZSS：高位=1 是 backref（count, offset 各 1 字节），高位=0 是字面量。

    防御性 bounds check：遇到越界 backref（旧工具产物）时在 uncomp_size 截断而非崩溃。
    """
    out = bytearray(uncomp_size)
    optr = 0
    while optr < uncomp_size:
        b = data[ptr]; ptr += 1
        if b & 0x80:
            count = (b & 0x7f) + 3
            offset = data[ptr] + 1; ptr += 1
            s = optr - offset
            if s < 0:
                # 越过头部：先填零（bytearray 默认就是 0，只前进指针）
                c = min(-s, count); optr += c; count -= c; s += c
            if count:
                # bounds: 不超过 uncomp_size
                count = min(count, uncomp_size - optr)
                if count <= 0:
                    continue
                if s + count <= optr:
                    out[optr:optr+count] = out[s:s+count]
                    optr += count
                else:
                    while count > 0:
                        out[optr] = out[s]; optr += 1; s += 1; count -= 1
        else:
            count = b + 1
            count = min(count, uncomp_size - optr, len(data) - ptr)
            out[optr:optr+count] = data[ptr:ptr+count]
            optr += count; ptr += count
    return bytes(out)


def _find_backref(data, iptr, n):
    """在 [iptr-256, iptr) 范围找最长匹配。长度上限 min(128, n - iptr)。"""
    best_off = 0; best_len = 1
    c = data[iptr]
    max_len = min(128, n - iptr)   # ⭐ 关键修复：不匹配越过数据末尾
    if max_len < 2:
        return best_off, best_len
    lo = max(-1, iptr - 256)
    for s in range(iptr - 1, lo, -1):
        if data[s] == c:
            i = 1
            while i < max_len:
                if data[s + i] != data[iptr + i]:
                    break
                i += 1
            if i > 2 and i > best_len:
                best_off = iptr - s
                best_len = i
                if best_len == max_len:
                    break  # 不可能更好，提前停
    return best_off, best_len


def lzss_compress(data, header_len):
    """LZSS 压缩。前 `header_len` 字节保留给调用方写头部（tag, sizes）。"""
    n = len(data)
    out = bytearray(n + header_len + 16)
    optr = header_len
    iptr = 0
    while iptr < n:
        off, length = _find_backref(data, iptr, n)
        if length == 1:
            # 字面量：找下一个非匹配的连续段
            run = 1
            while iptr + run < n and run < 128:
                _, l2 = _find_backref(data, iptr + run, n)
                if l2 > 1:
                    break
                run += 1
            out[optr] = run - 1; optr += 1
            out[optr:optr+run] = data[iptr:iptr+run]
            optr += run; iptr += run
        else:
            out[optr] = ((length - 3) | 0x80) & 0xff; optr += 1
            out[optr] = off - 1; optr += 1
            iptr += length
    return bytes(out[:optr])


# ── Archive 解析 ────────────────────────────────────────────────────────────

def archive_subfile_offsets(arch):
    """解析 archive 结构，返回 [(offset, length), ...]，按 sub-file 顺序。

    跳过扇区对齐填充（type 字节为 0 表示扇区填零，跳到下一扇区边界）。
    """
    ptr = 0; results = []
    while ptr < len(arch):
        typ = arch[ptr]
        if typ == 0:
            ptr = (ptr + 0x7ff) & ~0x7ff if ptr & 0x7ff else ptr + 0x800
            continue
        length = struct.unpack_from('<I', arch, ptr + 4)[0]
        if length == 0:
            break
        results.append((ptr, length))
        ptr += length
        while ptr & 3:
            ptr += 1
        if ptr < len(arch) and arch[ptr] == 0:
            ptr = (ptr + 0x7ff) & ~0x7ff
    return results


# ── FILEPOS.DAT 助手 ────────────────────────────────────────────────────────

def read_filepos(iso_path):
    """读取 ISO 扇区 0x17 的 FILEPOS.DAT（0x1b88 字节）。"""
    return read_sectors(iso_path, 0x17, 0x1b88)


def get_file_entry(fileposdat, filenum):
    """返回 (block, size) 给定文件号。"""
    return (
        struct.unpack_from('<I', fileposdat, filenum * 8)[0],
        struct.unpack_from('<I', fileposdat, filenum * 8 + 4)[0],
    )
