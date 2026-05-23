# P2IS PS1 汉化工程技术文档

> 基于 [cmccord-dev/p2ep_tool](https://github.com/cmccord-dev/p2ep_tool)，目标是把 PS1 游戏《女神异闻录 2 罪》的日文对话替换为中文。感谢 cmccord-dev 的逆向工程基础工作。

---

## 一、游戏文件结构（从外到内）

### 层级 1：ISO 文件（CD 镜像）

```
Persona 2 - Tsumi.bin   ← 整个光盘镜像，约 650MB
```

PS1 光盘每个扇区（sector）= **2352 字节**，结构如下：

| 偏移 | 大小 | 内容 |
|------|------|------|
| 0 | 12 B | 同步头 |
| 12 | 4 B | 地址 + 模式 |
| 16 | 8 B | 子头 |
| **24** | **2048 B** | **有效数据** |
| 2072 | 280 B | ECC 纠错码 |

只有中间 2048 字节是有效数据（偏移 `0x18` 开始）。**修改数据后必须重新计算 ECC**，否则模拟器/光驱报读取错误。`fix_ecc.py` 负责这一步：

```bash
python3 fix_ecc.py <起始扇区LBA> <结束扇区LBA>
```

---

### 层级 2：FILEPOS.DAT（文件索引）

位于 ISO 扇区 `0x17`，大小 `0x1b88` 字节（881 个文件）。

每条记录 **8 字节**：

```
[起始扇区号 uint32 LE][文件字节数 uint32 LE]
```

读取示例：
```js
const block = fileposdat.readUInt32LE(N * 8);      // 起始扇区
const size  = fileposdat.readUInt32LE(N * 8 + 4);  // 字节数
```

已知重要文件：

| 文件号 | 文件名 | 内容 |
|--------|--------|------|
| 86 | F0086.BIN | 字体数据 |
| 181 | — | 开头霸凌场景脚本 |
| 3 | — | 学校走廊场景脚本 |

---

### 层级 3：Archive（归档文件）

大多数文件是 archive 格式，把多个 sub-file 打包在一起：

```
[sub-file 0][sub-file 1]...[sub-file N][填充零到扇区边界]
```

**Sub-file 头部（12 字节）：**

| 字节 | 字段 | 说明 |
|------|------|------|
| 0 | type | 类型（1 = LZSS 压缩脚本） |
| 1 | subtype | 子类型（2 = 场景脚本） |
| 2–3 | sub_index | sub-file 序号（uint16 LE）⚠️ 重要 |
| 4–7 | total_size | 该 sub-file 总字节数（含头部） |
| 8–11 | uncomp_size | 解压后字节数 |
| 12+ | — | LZSS 压缩数据 |

`lib/archive.mjs` 处理 archive 的读写：
- `extract_files(buff)` → 返回 sub-file Buffer 数组
- `patch_archive_inplace(original, {sub_id: new_buf})` → 替换指定 sub-file，保持总大小不变

---

### 层级 4：LZSS 压缩

游戏使用自定义 LZSS 变体，`lib/lzss.mjs` 处理：

```
字节最高位 = 1：回引（back-reference）
  count = (byte & 0x7F) + 3
  offset = next_byte + 1
  复制 count 字节，从当前位置往前 offset 处

字节最高位 = 0：字面量
  count = byte + 1
  接下来 count 字节原样输出
```

用法：
```js
const decompressed = lzss.decompress(sub, 12, total_comp - 12, uncomp_size);
const recompressed = lzss.compress(modified, 0xc, true);

// 写回头部时必须保留原始 tag（含 sub-file 序号）：
recomp.writeUInt32LE(sub.readUInt32LE(0), 0);  // ← 不能 hardcode！
recomp.writeUInt32LE(recomp.byteLength, 4);
recomp.writeUInt32LE(modified.byteLength, 8);
```

> ⚠️ **曾踩的坑**：之前把第一行 hardcode 为 `0x101`，把子类型字段和 sub-file 序号都写成了 0，导致游戏加载时字体渲染器崩溃（`0x831BA92F`）。必须用 `sub.readUInt32LE(0)` 保留原始值。

---

### 层级 5：场景脚本（解压后）

解压后的数据是场景脚本，头部 24 字节存各段指针：

| 偏移 | 字段 | 说明 |
|------|------|------|
| 0 | START 指针 | START 函数偏移 |
| 4 | func_table | 函数表起始偏移 |
| 8 | func_count | 函数数量 |
| 12 | script_ptr | 指令区起始偏移 |
| 16 | arg_ptr | 参数区起始偏移 |
| 20 | diag_ptr | 对话区起始偏移 |

**指令结构（每条 8 字节）：**

| 字节 | 字段 | 说明 |
|------|------|------|
| 0–1 | op | 操作码（uint16 LE） |
| 2–3 | imm | 立即数（uint16 LE） |
| 4–7 | arg_section_ptr | **指向参数区内的指针**，需再解引用一次 |

关键操作码：

| 操作码 | 作用 |
|--------|------|
| `0x13` | 显示对话框，`args[0]` = 对话偏移（相对 diag_ptr） |
| `0x10f` | 同上（另一种对话显示指令） |
| `0x0e` | 函数返回 |
| `0x56` | 等待按键 |

扫描对话偏移的正确写法：
```js
const arg_section_ptr = orig.readUInt32LE(instr_ptr + 4);  // 先读指针
const diag_off        = orig.readUInt32LE(arg_section_ptr); // 再解引用
```

> ⚠️ **曾踩的坑**：直接把 `instr_ptr + 4` 处的值当作对话偏移，漏掉了一次解引用，导致所有对话解析失败。

> ⚠️ **`compile_script` 不可用**：原版二进制使用"广播编码"（如值 `0x12` 存成 `12 12 12 12`），`compile_script` 未实现此格式，写回后会损坏脚本。**只能用二进制补丁方式**（只改对话字节，指令和参数区保持原样）。

---

### 层级 6：对话数据（Dialog）

对话区从 `diag_ptr` 开始，多个对话连续存储。每个对话是 **uint16 流**：

| 数值范围 | 含义 |
|----------|------|
| `0x0001`–`0x0FFF` | 字符码（查字体表得到字形） |
| `0x1101` | `CMD_NEWLINE` 换行 |
| `0x1102` | `CMD_END_PAGE` 翻页 |
| `0x1103` | `CMD_RET` 对话结束（终止符） |
| `0x1106` | `CMD_WAIT` 等待按键 |
| `0x1120` | `CMD_TATSUYA_SURNAME` 主角姓氏（动态插入） |
| `0x1121` | `CMD_TATSUYA` 主角名字 |
| `0x1D12` + arg | 未知命令（设置说话人/立绘） |

`lib/msg_script.mjs` 处理：
- `parse(data, offset)` → 解析为 items 数组
- `calculate_dialog_length(items)` → 计算字节数
- `compile_msg(items, buffer, offset)` → 写回 buffer

Items 格式：
```js
// 数字 → 字符码
63        // → writeUInt16LE(63)
2602      // → writeUInt16LE(2602)  ← 注入的中文字符

// 数组 → 控制码
[6]       // → 0x1106（CMD_WAIT）
[2]       // → 0x1102（CMD_END_PAGE）
[3]       // → 0x1103（CMD_RET）
[29, 11]  // → 0x1D12, 0x000B（立绘命令，arg=11）
[32]      // → 0x1120（CMD_TATSUYA_SURNAME）
```

---

### 层级 7：字体文件（F0086.BIN，文件 86）

**平铺二进制，不是 archive 格式**，直接存于 ISO 扇区，可以直接用 `_write_sectors` 写回，不需要打包。

```
偏移 0x480 开始：字形 bitmap 数组
  字形 N 的偏移 = 0x480 + N × 18
  每个字形 = 18 字节 = 144 bits（12×12 像素，LSB 优先，行优先）
```

字符码 N → 第 N 个字形槽。文件共有 3576 个槽（0–3575）：
- **槽 0–2575**：原版日文字形（其中 27 个空槽）
- **槽 2576–2693**：我们注入的中文字形（共 304 个汉字）
- **槽 2694–3575**：未使用

---

## 二、文件说明

### `lib/` 核心库

| 文件 | 作用 |
|------|------|
| `archive.mjs` | Archive 解包 / 打包 |
| `lzss.mjs` | LZSS 压缩 / 解压 |
| `cdimage.mjs` | ISO 扇区读写，管理 FILEPOS.DAT |
| `msg_script.mjs` | 对话解析 / 编译（唯一可靠的对话工具） |
| `msg_commands.mjs` | 控制码常量定义 |
| `scene_script.mjs` | 场景脚本解析（`parse_script` 可用，`compile_script` 有 broadcast bug 不可用） |

### 根目录工具脚本

| 文件 | 作用 | 状态 |
|------|------|------|
| `fix_ecc.py` | 修复 ISO ECC 校验码，每次写 ISO 后必须运行 | ✅ |
| `inject_chinese_font.py` | 收集汉字 → 渲染 bitmap → 写入字体 → 写回 ISO → 修 ECC | ✅ |
| `encode_zh.py` | 把翻译文本编码成字符码 items，输出到 `out/scripts_zh/` | ✅ |
| `apply_zh.mjs` | 把编码好的对话用二进制补丁写回 ISO（核心写回工具） | ✅ |
| `export_all_dialog.py` | 提取全部日文对话到 `all_dialog.json` | ✅ |
| `export_translatable.py` | 生成 `all_translatable.json`（含 jp / zh 字段） | ✅ |
| `restore_all.mjs` | 从备份 ISO 还原文件 3 和 181（出问题时用） | ✅ |
| `codetable.json` | 字符码 → 字符 的完整映射（2694 条） | ✅ |
| `all_translatable.json` | 翻译主文件，每条有 jp / zh 字段 | 翻译中 |

### 诊断 / 验证脚本

| 文件 | 作用 |
|------|------|
| `verify_injection.mjs` | 读取主 ISO，验证对话字节和字体 bitmap 是否正确写入 |
| `verify_full.mjs` | 对比主 ISO vs 备份 ISO 的 diag0，确认写入生效 |
| `test_lowslot.py` | 把中文字形复制到低编号空槽（1876）测试游戏是否有槽号上限 |
| `patch_dialog_181.mjs` | 测试用：把 file 181 diag0 全改为字符码 16（已验证管道可用） |

---

## 三、完整工作流

### 阶段 A：准备工作（只做一次）

```bash
# 1. 备份原始 ISO（出问题时用 restore_all.mjs 恢复）

# 2. 提取日文脚本
node p2ep_tool.mjs extract_script
# → 生成 out/scripts/ 下的 JSON 文件
# → 确保每个 JSON 有 "file": N, "file_num": M 字段

# 3. 生成可翻译列表
python3 export_translatable.py
# → 生成 all_translatable.json
```

### 阶段 B：翻译

编辑 `all_translatable.json`，给每个条目的 `zh` 字段填入中文翻译：

```json
{
  "id": "script:181_8:diag0",
  "pages": [
    {
      "jp": "\n<SURNAME/>………?",
      "zh": "\n<SURNAME/>……吗？"
    }
  ]
}
```

控制码标签：`<SURNAME/>` `<NAME/>` 等（与日文原文保持一致）。  
标点 `… ？ ！ ， 。` 等会自动映射到已有字符码。

### 阶段 C：注入字体

```bash
python3 inject_chinese_font.py
```

自动完成：扫描 `zh` 字段中的汉字 → 渲染 12×12 bitmap → 写入 F0086.BIN → 写回 ISO → 运行 `fix_ecc.py`。

> ⚠️ 每次新增汉字后都要重新运行，保证字形和编码表同步。

### 阶段 D：编码对话

```bash
python3 encode_zh.py
# → 输出 out/scripts_zh/{file}_{sub}.json
```

输出格式示例（`181_8.json`）：
```json
{
  "dialogs": {
    "diag0": [[29,11], 63, 63, 63, [29,1], [1], [32], 215, 215, 2602, 63, [6], [2], [3]]
  }
}
```

### 阶段 E：写回 ISO

```bash
node apply_zh.mjs 181 8    # file 181, sub-file 8
node apply_zh.mjs 3 6      # file 3, sub-file 6
# 脚本会输出对应的 ECC 修复命令，按提示执行即可
```

`apply_zh.mjs` 工作原理：
1. 从**备份** ISO 读取原始 archive
2. 提取 sub-file → LZSS 解压
3. 扫描指令区，建立 `diag名称 → 偏移` 映射
4. 对每个有变化的 diag：检查字节长度是否相同，相同则用 `compile_msg` 写入新字节
5. LZSS 重压缩（保留原始 tag 头）
6. `patch_archive_inplace` 替换 sub-file
7. `write_file` 写回主 ISO
8. 输出 ECC 修复命令

### 阶段 F：测试

> ⚠️ **必须从标题画面开始新游戏**，不能加载存档（save state）。PS1 存档会把已解压的场景数据保存在 RAM 里，加载存档后游戏不会重新从 ISO 读取对话，修改不会生效。

```bash
# 可选：验证数据是否正确写入
node verify_full.mjs
```

---

## 四、踩过的坑

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 崩溃 `0x831BA92F`（char=300） | 游戏启动场景时预加载字体，300 不在原始对话里 | 实际翻译时新字符码会出现在新对话里，会被正常预加载 |
| 崩溃 `0x831BA92F`（char=16 及其他所有码） | sub-file 头部 tag hardcode 为 `0x101`，破坏了子类型和序号字段 | 改为 `sub.readUInt32LE(0)` 保留原始 4 字节 |
| `compile_script` 写回后游戏出错 | 原版用"广播编码"（`0x12` 存成 `12 12 12 12`），我们的实现不兼容 | 改为二进制补丁：只改对话字节，其余保持原样 |
| `encode_zh.py` 不处理 181_8 | `out/scripts/181_8.json` 缺少 `file` 和 `file_num` 字段（均为 null） | 手动补充：`"file": 181, "file_num": 8` |
| `apply_zh.mjs` 所有对话解析失败 | 读 `instr_ptr + 4` 处的值当作对话偏移，漏掉一次解引用 | 改为先读 `arg_section_ptr`，再 `readUInt32LE(arg_section_ptr)` |
| 修改后游戏仍显示日文 | 从游戏中途的存档加载，场景数据已在 RAM 中，ISO 修改无效 | 从标题画面开始新游戏 |

---

## 五、当前状态

**已完成：**
- ✅ 完整二进制补丁管道（已在游戏内验证）
- ✅ 中文字体注入（304 个汉字，字符码 2576–2693）
- ✅ `apply_zh.mjs`：自动从 `scripts_zh/` 写回 ISO
- ✅ 翻译主文件 `all_translatable.json`（含测试译文）
- ✅ 字符码表 `codetable.json`（2694 条）

**待解决：**
- ⚠️ 验证游戏是否支持字符码 ≥ 2576（需从新游戏测试；若不支持，改用空闲低编号槽）
- ⚠️ `apply_zh.mjs` 目前只支持**长度不变**的替换（中文字数 ≠ 日文字数时需要额外处理）
- ⚠️ 大量翻译工作（25000+ 条目）

---

## 六、日常工作流（快速参考）

```bash
# 1. 编辑翻译
#    编辑 all_translatable.json，填写 zh 字段

# 2. 注入字体（有新汉字时才需要）
python3 inject_chinese_font.py

# 3. 编码
python3 encode_zh.py

# 4. 写回 ISO（按提示执行 ECC 命令）
node apply_zh.mjs 181 8

# 5. 启动模拟器，从新游戏开始测试
```
