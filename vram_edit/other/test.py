from capstone import Cs, CS_ARCH_MIPS, CS_MODE_MIPS32, CS_MODE_LITTLE_ENDIAN

with open('SLPS_021.00', 'rb') as f:
    body = f.read()[0x800:] 

BASE = 0x80010000
md = Cs(CS_ARCH_MIPS, CS_MODE_MIPS32 + CS_MODE_LITTLE_ENDIAN)

print("🕵️‍♂️ 开启全范围魔法数字 (0x480 与 18) 暴搜...")

for ins in md.disasm(body, BASE):
    # 把操作数拆开，防止匹配到无关字符串
    parts = [x.strip() for x in ins.op_str.split(',')]
    
    for p in parts:
        # 寻找字库头部跳过量: 0x480 (十进制 1152)
        if p in ['0x480', '1152']:
            print(f"[⭐ 极高概率: 字库偏移 0x480] @ 0x{ins.address:08x}: {ins.mnemonic:7} {ins.op_str}")
        
        # 寻找字模乘数: 0x12 (十进制 18)
        if p in ['0x12', '18']:
            # 只抓有算术或加载意义的 18，排除毫无关联的寄存器操作
            if ins.mnemonic in ['li', 'addiu', 'mulu', 'mul']:
                print(f"[🔍 疑似字模大小 18] @ 0x{ins.address:08x}: {ins.mnemonic:7} {ins.op_str}")