import os
import sys
import subprocess

# 允许传 ISO 路径作参数：python3 extander.py [iso_path]
# 不传则用 working ISO
DEFAULT_ISO = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin'
ISO_PATH = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ISO
FIX_ECC = '/home/mark/Code/RomHacking/P2IS_Translation_Tools/fix_ecc.py'

# 终极特征码：[未知2字节] [偏移22扇区] [大小28扇区] [未知2字节]
PATTERN = b'\x00\x00\x16\x00\x1C\x00\x01\x00'

# 我们要把偏移量 0x16 (22扇区) 改成 0x1E (30扇区，可容纳61440字节的中文字体)
# 注意：只改偏移量，Sub-file 1 的大小(0x1C)保持不变！
NEW_VALUE = b'\x00\x00\x1E\x00\x1C\x00\x01\x00'

def main():
    print("[-] 启动终极特征码猎杀程序...")
    
    with open(ISO_PATH, 'r+b') as f:
        raw_data = bytearray(f.read())
        
    total_sectors = len(raw_data) // 2352
    print(f"[-] 光盘总扇区: {total_sectors}，正在提取净数据...")
    
    # 逻辑扇区拼接
    logical_data = bytearray()
    for i in range(total_sectors):
        start = i * 2352 + 24
        logical_data.extend(raw_data[start:start+2048])
        
    pos = logical_data.find(PATTERN)
    
    if pos == -1:
        # 如果已经改过了，检查一下是不是已经是 1E 了
        if logical_data.find(NEW_VALUE) != -1:
            print("[✅] 扫描发现：该硬编码已经被成功修改为 1E (30扇区)！无需重复操作。")
        else:
            print("[!] 未找到特征码。请确保你使用的是未被破坏的原版 ISO。")
        return
        
    # 反推物理坐标
    sector_idx = pos // 2048
    offset_in_sector = pos % 2048
    physical_offset = (sector_idx * 2352) + 24 + offset_in_sector
    
    print(f"\n[+] 🎉 找到了！结构体藏在执行文件扇区 {sector_idx} 里。")
    print(f"[+] 物理绝对地址: 0x{physical_offset:X}")
    
    # 写入新结构体
    print(f"[-] 正在将 File 59 内部偏移量从 22 扇区扩大至 30 扇区...")
    with open(ISO_PATH, 'r+b') as f:
        f.seek(physical_offset)
        f.write(NEW_VALUE)
        
    # 修复 ECC
    print(f"[-] 正在修复执行文件扇区 {sector_idx} 的 ECC...")
    subprocess.run(['python3', FIX_ECC, str(sector_idx), str(sector_idx)], check=True)
    
    print("\n[✅] 恭喜！ISO 永久修改成功！汉化字库的 45KB 容量封印已被彻底解除！")

if __name__ == '__main__':
    main()