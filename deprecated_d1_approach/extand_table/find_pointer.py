import sys, struct, os

# 直接指定项目根目录的绝对路径
ROOT = '/home/mark/Code/RomHacking/P2IS_Translation_Tools'
sys.path.insert(0, ROOT)

from pylib.p2is import read_sectors, archive_subfile_offsets

# 读取你的备份 ISO
BACKUP_ISO = os.path.join(ROOT, '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin')
FONT_FILE = 59

print("[-] 正在侦查 File 59...")

# 1. 找到 File 59 的物理位置
filepos = read_sectors(BACKUP_ISO, 0x17, 0x1b88)
block59, size59 = struct.unpack_from('<II', filepos, FONT_FILE * 8)
arch = read_sectors(BACKUP_ISO, block59, size59)

# 2. 提取 sub-file 1 的原始偏移量
subs = archive_subfile_offsets(arch)

if len(subs) < 2:
    print("[!] 严重警告：在 File 59 中没有找到 sub-file 1！")
    sys.exit(1)

sub0_off, sub0_len = subs[0]
sub1_off, sub1_len = subs[1]

print(f"[*] Sub-file 0 起始偏移 (Header 长度): {sub0_off} (0x{sub0_off:X})")
print(f"[*] Sub-file 1 起始偏移: {sub1_off} (0x{sub1_off:X})")

# 3. 提取 Header 二进制数据
header = bytearray(arch[0:sub0_off])

# 4. 在 Header 中搜索 sub1_off 的小端序字节
target_bytes = struct.pack('<I', sub1_off)
print(f"[*] 正在 Header 中搜索指针特征码: {target_bytes.hex()}")

positions = []
offset = 0
while True:
    pos = header.find(target_bytes, offset)
    if pos == -1:
        break
    positions.append(pos)
    offset = pos + 4

if not positions:
    print("[-] 未在 Header 中找到直接匹配的小端序指针。")
else:
    print(f"[+] 找到了！目标指针在 Header 的以下偏移位置：")
    for p in positions:
        print(f"    -> 0x{p:X}")
        
    print("\n[✅ 诊断完成]")
    print(f"在接下来的修改中，我们只需将 Header 偏移 0x{positions[0]:X} 处的 4 字节替换为新地址即可！")