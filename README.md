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
| **59** | — | **对话字体（LZSS 压缩，2 个 sub-file，每个解压 65520 字节）** ⭐ |
| 86 | F0086.BIN | 字体的"参考副本"——格式相同但**游戏运行时不读取**（曾误以为是字体源） |
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

### 层级 7：字体文件（文件 59，sub-file 0）⭐

> **⚠️ 重要修正**：之前以为字体在 `F0086.BIN`（文件 86），实际**完全错了**。游戏运行时根本不读 F0086.BIN，它只是格式相同的"参考副本"。真正使用的字体在**文件 59 sub-file 0**，LZSS 压缩。详见"五、踩过的坑"中的字体定位事件。

**文件结构：**

```
文件 59（archive，2 个 sub-file）:
  sub-file 0:  LZSS 压缩，解压后 65520 字节  ← 对话字体源
  sub-file 1:  LZSS 压缩，解压后 65520 字节  ← 备用/异体字（用途待确认）
```

**解压后的格式与 F0086.BIN 完全相同：**

```
偏移 0x480 开始：字形 bitmap 数组
  字形 N 的偏移 = 0x480 + N × 18
  每个字形 = 18 字节 = 144 bits（12×12 像素，LSB 优先，行优先）
```

字符码 N → 第 N 个字形槽。原版字库共 3576 个槽（0–3575）：
- **槽 0–99**：ASCII / 标点 / 数字（保护，不能动）
- **槽 100–2574**：原版日文 kanji（可被覆盖替换成中文）
- **槽 2575–3575**：原版空槽

**D1 扩容方案**（2026-05-28 突破）：原版 SLPS 限制 sub-file 0 为 22 sectors（45056 字节 LZSS 数据），写空槽会让 LZSS 重压缩超界 → 黑屏。经过 Ghidra 反汇编追踪发现真正的限制点：

```
SLPS sub-file 描述符表 @ RAM 0x80010070-0x8001007f (ISO sector 29 offset 0x70):
  0x80010070: 00 00 00 00 16 00 01 00   ← Desc 1: sub-file 0, size=22 sectors
  0x80010078: 00 00 16 00 1C 00 01 00   ← Desc 2: sub-file 1, offset=22, size=28 sectors
```

只要 patch 这 16 字节里的两处 `0x16 → 0x1E`（22 → 30 sectors）+ 把 file 59 搬到 ISO 末尾让 sub-file 1 落到 30 sectors offset，就能扩 sub-file 0 容量到 **30 sectors = 61440 字节 LZSS**，覆盖全部 2775 个中文字。详见 `patch_subfile_table.py` + `relocate_file59.py`。

**修改流程**（D1 模式，由 `build.py` 编排）：

```bash
# 1. patch_subfile_table.py  → SLPS Desc1/Desc2 patch 22→30
# 2. relocate_file59.py      → file 59 搬 ISO 末尾 + sub-file 1 @ 30 sectors offset
# 3. inject_chinese_font.py  → 读 working ISO file 59 → 解压 sub-file 0 → 扩到 69KB
#                             → inject 字到扩展 slot → 重压缩 ≤ 30 sectors → 写回 + fix_ecc
```

**Slot 分配策略**（关键优化）：
- **优先填 og kanji slot 100-2574**：替换原日文字符 bitmap，LZSS 重压缩几乎不膨胀
- **不够再填扩展 slot 2575-3768**：bitmap 替换 0 → 每字膨胀 ~14 字节
- 实测：1498 个新字 inject 后重压缩 ~47KB（< 30 sectors 限制 61KB）

**容量上限**：
- decompressed: 65520 → **69000 字节**（RAM 上限：字库基址 0x801CE800 + 69000 < SLPS BSS 区）
- 重压缩: 45056 → **61440 字节**（SLPS Desc1=30 后 sub-file 0 容量）
- 可用 slot: 3576 → **3768**（扩展 ~200 个）

**已验证的渲染管道：**
1. SLPS 启动 → FUN_80017a9c 调用字库 loader chain → LZSS 解压到 RAM `0x801CE800`
2. 渲染对话时，从 `0x801CE800 + 0x480 + code*18` 读 18 字节 1bpp bitmap
3. 转换为 VRAM 纹理

**LZSS bug 修复**（2026-05-23）：
- 原 `find_backref` 贪心匹配越过数据末尾，产生越界 backref
- 游戏的 PS1 解码器宽容（写越界静默忽略）；JS Buffer 也宽容；**Python 严格 → IndexError**
- 修复：`max_len = min(128, n - iptr)` 不让匹配越界（`pylib/p2is.py` 和 `lib/lzss.mjs` 都改了）

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

### 目录结构

```
P2IS_Translation_Tools/
├── README.md
├── (日常使用的入口脚本和数据文件，见下表)
├── lib/          ← 核心库（archive.mjs, lzss.mjs, cdimage.mjs, msg_script.mjs 等）
├── cmd/          ← 原 p2ep_tool 的子命令（extract.mjs, insert.mjs 等）
├── sh/           ← Python 辅助脚本（build_codetable.py 等）
├── out/          ← 生成的输出（scripts/, scripts_zh/, battle/, f35/, string_table/）
├── verify/       ← 验证/调试脚本
├── tools/        ← 一次性工具（restore, 单字注入示例等）
├── experiments/  ← 历史实验脚本（已知坏的/过时的，留作教训）
└── artifacts/    ← 生成的产物（PNG 预览、提取的 bin），gitignored
```

### 根目录：日常管道脚本

| 文件 | 作用 | 状态 |
|------|------|------|
| **`build.py`** | **一键完整管道**：还原 ISO → D1 patch → file 59 搬末尾 → 注字体 → 编码 zh → 写回 ISO → 修 ECC → 报告 | ⭐ 主入口 |
| `patch_subfile_table.py` | **D1 扩容 Step 1**：patch SLPS sub-file 描述符表（Desc1+Desc2 22→30 sectors） | ✅ |
| `relocate_file59.py` | **D1 扩容 Step 2**：把 file 59 搬到 ISO 末尾 + sub-file 1 在 30 sectors offset；同时更新 FILEPOS.DAT 和 PVD | ✅ |
| `inject_chinese_font.py` | **D1 字体注入**：读 working ISO file 59 → 扩 decompressed → inject 中文到 og kanji slot + 扩展 slot（从低位2575↑紧凑分配，避免覆盖 UI 数据）+ og 缺的假名 → LZSS 重压缩 → 修 ECC | ✅ |
| `encode_zh.py` | 把 script 翻译编码成字符码 items（含 META 段处理 + 全角标点 alias），输出 `out/scripts_zh/` | ✅ |
| `encode_strtbl.py` | 把 strtbl 翻译编码成 items，输出 `out/strtbl_zh/`（文件名 regex 支持 SLUS 前缀=file 0） | ✅ |
| `apply_zh.mjs` | 把编码好的对话写回 ISO。`<file>`（不带 sub）一次处理该 file 所有 sub 合并 patch（**必须**，否则多 sub 互相覆盖）。支持 RLE/LZSS、relocate 三级降级、自动 ECC | ✅ |
| `apply_strtbl.mjs` | strtbl 写回 archive 文件（**重建 count+索引表**，跳过 SLUS） | ✅ |
| `apply_strtbl_slps.py` | SLPS file 0 内 strtbl 写回（raw-sector，重建索引表） | ✅ |
| `savemenu_strtbl.py` | 存档/记忆卡菜单 extract+apply（ISO 游离区 sector 273695，保留前缀/控制码） | ✅ |
| `mainmenu_strtbl.py` | 主菜单/提示语 extract+apply（游离区 sector 271864 两个文本区，原位替换不碰指针表） | ✅ |
| `check_translation.py` | 校验翻译：进度 + hard 控制码守恒（SURNAME 软码豁免）+ codetable 缺字 | ✅ |
| `locate_text.py` | 定位工具：`'日文'` 查它在哪个 file/游离区 + 该用哪个 pipeline（`--working` 搜改后 ISO） | ✅ |
| `fix_ecc.py` | 修复 ISO ECC 校验码（各 apply 内部已调用） | ✅ |
| `export_translatable.py` | 生成 `all_translatable.json`（含 jp / zh / meta_jp / meta_zh 字段）。**用 codetable_og.json 渲染 JP** 防止被字体注入后的中文 slot 污染 | ✅ |
| `export_all_dialog.py` | （历史）纯文本对话提取；已不在主管道里 | 备用 |
| `p2ep_tool.mjs` | 原 p2ep_tool 入口，调用 `cmd/` 子命令（extract_script 等都走只读 ISO） | ✅ |
| `codetable.json` | 字符码 → 字符 映射（每次 inject 字体后会更新，含中文覆写） | ✅ |
| `codetable_og.json` | 原版日文 codetable 基线（用于 JP 渲染、防污染） | ✅ |
| `all_translatable.json` | 翻译主文件，每条有 id / pages[jp,zh] / meta_jp / meta_zh | ✅ 翻译完成 |
| `conf.json` | 本地配置（**gitignored**）。复制 `conf.json.example` 起步，必须填 `iso` 和 `iso_backup` | 本地配置 |
| `fusion-pixel-12px.otf` | 像素中文字体（OFL-1.1，[TakWolf/fusion-pixel-font](https://github.com/TakWolf/fusion-pixel-font)），用于渲染 12×12 bitmap | ✅ |

### `pylib/` Python 共享助手

| 文件 | 作用 |
|------|------|
| `pylib/p2is.py` | ISO 扇区读写、LZSS 编解码、archive 解析（Python 端字体注入用） |

### `verify/` 诊断 / 验证

| 文件 | 作用 |
|------|------|
| `verify_injection.mjs` | 读取主 ISO，验证对话字节和字体 bitmap 是否正确写入 |
| `verify_full.mjs` | 对比主 ISO vs 备份 ISO 的 diag0，确认写入生效 |
| `verify_diag0.mjs` | 验证 file 3 diag0（早期诊断用） |
| `debug_sub8.mjs` | 检查 file 181 sub-file 8 结构 |

### `tools/` 一次性工具

| 文件 | 作用 |
|------|------|
| `inject_grass_into_file59.py` | 字体注入的最小验证示例（只注入一个 草 到 slot 16） |
| `fix_diag0_safe.py` | 修改 file 181 diag0 单个字符码的安全模板（保留 LZSS tag） |
| `restore_all.mjs` | 从备份 ISO 还原所有写过的文件 |
| `restore_file3.mjs` | 单独还原 file 3 |
| `font_extractor.mjs` | 旧字体提取（基于 F0086.BIN 的误解，已无用但留作参考） |
| `compare_binary.mjs` | 比较两个 ISO 的差异 |
| `fix_archive.mjs` | archive 结构修复尝试（实验性） |
| `extract_font_candidates.py` | 从 ISO 提取 F0086.BIN 和 F0140（调试用） |

### `experiments/` 历史实验（**勿用，留作教训**）

| 文件 | 为什么不该用 |
|------|--------------|
| `patch_dialog_181.mjs` | LZSS tag byte 2 没保留，导致游戏崩溃 |
| `patch_dialog_test.mjs`、`patch_dialog_binary.mjs` | 早期试错版本 |
| `test_lowslot.py` | 测试槽号上限的假设（结论：F0086.BIN 根本不被读取） |
| `test_passthrough.mjs`、`test_export.py` | 早期管道验证 |
| `codetable_checker.py`、`pending_grid.py`、`missing_stats.py`、`unknown_in_context.py`、`decode.py` | 一次性数据分析脚本 |

### `deprecated_d1_approach/` 字库扩容研究历史

D1 方案最终落地前的探索性脚本（保留为历史参考，不在主管道里）：

| 文件 | 作用 |
|------|------|
| `extand_table/extander.py` | 早期只 patch Desc2 的尝试（只改了一半，atlus 后崩） |
| `expand_file59.py` | 扩 file 59 容量的早期尝试 |
| `patch_font_base.py` | 误以为字库基址撞堆栈，尝试搬基址（基于 Gemini 误判，已弃） |
| `ijc.py` | inject_chinese_font.py 的实验性分叉版本 |
| `test_d1_full.py` | D1 完整测试脚本（参数化 inject 数量/uncomp_size） |
| `test_expand_subfile0.py` | 测试 sub-file 0 解压上限（找到 ~69KB 临界值） |
| `test_inject_*.py`、`test_recompress_only.py`、`test_relocate_only.py` | 各种 D1 子方案的隔离测试 |
| `analyze_lzss*.py`、`analyze_16_vs_17.py` | LZSS 字节流模式分析 |

---

## 三、完整工作流

### 阶段 A：准备工作（只做一次）

```bash
# 1. 复制 conf.json.example → conf.json，填入：
#    "iso"        = 工作 ISO（会被 build.py 修改）
#    "iso_backup" = 干净原版 ISO（只读，用于 extract / restore；不允许被任何工具改写）

# 2. 提取日文脚本（强制从 iso_backup 读，防止从被改的 live ISO 反向污染）
node p2ep_tool.mjs extract_script 0 880
# → 生成 out/scripts/ 下的 JSON 文件

# 3. 提取 string_table / battle
node p2ep_tool.mjs extract_string_tables 0 880
node p2ep_tool.mjs extract_battle_strings 0 880

# 4. 生成可翻译列表
python3 export_translatable.py
# → 生成 all_translatable.json
```

> ⚠️ **污染预防**：所有 `extract_*` 命令都走 `cdimage.init_readonly()`，**只读 iso_backup**。
> 如果手工或第三方脚本从 live ISO 重新提取，会把已翻译的中文 item codes 写回 `out/scripts/`，
> 之后 `export_translatable.py` 渲染出来的 jp 字段就是中文 → 数据污染。
> `build.py` 启动时会跑 sanity check 检测这种污染。

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

### 阶段 C：D1 扩容 + 注入字体

`build.py` 会自动按顺序跑这三步：

```bash
python3 patch_subfile_table.py    # D1 Step 1: SLPS 描述符表 22→30
python3 relocate_file59.py        # D1 Step 2: file 59 搬末尾 + 30-sector layout
python3 inject_chinese_font.py    # D1 Step 3: inject 中文到 og kanji + 扩展 slot
```

**Slot 分配优化**：先填 og 已用 kanji slot（替换 bitmap，LZSS 几乎不膨胀），再填扩展 slot 2575+（每字膨胀 ~14 字节）。这让 1498 个新中文字 inject 后 LZSS 重压缩 ~47KB，稳稳低于 30 sectors 限制（61440 字节）。

被覆盖的日文 kanji 在未翻译对话里会显示成中文（属正常 trade-off，最终目标就是全中文）。

> ⚠️ 每次新增汉字后都要重新运行，保证字形和编码表同步。  
> ⚠️ codetable.json 会被重建，跑前会自动从 codetable_og.json 作基线。
> ⚠️ codetable.json 不复用上次 inject 的 mapping（避免污染传染），所以每次 slot 编号会变。

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

> ⚠️ **DuckStation 必须开 tab 加速**。PSX LZSS decode 慢 + cdrom 流式加载耗时。Game 启动期间常常看起来"黑屏"几秒到几十秒，实际在等 CD/decoder。**没加速 == 等不够 == 误以为崩溃**。这是排查 D1 路上几次最大误判的根因。

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
| **修改字体后游戏渲染不变** | **以为 F0086.BIN 是字体源，实际游戏完全不读取它！真正的字体在文件 59 sub-file 0（LZSS 压缩）** | 改写所有字体注入工具到文件 59；F0086.BIN 是无用的"参考副本" |
| 改 file 181 sub-file 8 后游戏黑屏崩溃 | `patch_dialog_181.mjs` 重压缩时用 `Buffer.allocUnsafe` 留下未初始化字节，把 sub-file tag 字节 2（sub-file 序号 0x08）变成 0x00，游戏无法识别 sub-file 8 | 显式保留原 tag：`recomp[0:4] = sub.readUInt32LE(0)`，并在 Python 中直接覆盖 `recomp[0:4] = tag_bytes` |
| `patch_dialog_181.mjs` 把所有字符码改成 16 导致脚本损坏 | `diag.map(item => typeof item === "number" ? 16 : item)` 把控制码参数（独立 number）和真字符码混淆了 | 只改特定位置的字符码，控制码参数（虽是 number）必须保持原值 |
| **写空 slot 区（>2574）触发 45056 字节边界 bug** | SLPS 内部限制 sub-file 0 读 22 sectors = 45056 字节。空 slot 区原本压缩成大段零 backref，inject 中文 bitmap 破坏这个压缩 → 重压缩字节流膨胀 → 超 22 sectors → 数据被截断 → 字库错乱 → 黑屏 | D1 方案：patch SLPS Desc1/Desc2 让它读 30 sectors |
| **以为字库基址撞堆栈（Gemini 误判）** | Gemini 看 FUN_80026c50 反编译猜字库在 0x801F0000 撞堆栈。实际字库基址是 0x801CE800（FUN_80024e78 内 lui+ori 加载），离堆栈 ~134KB 远 | 自己用 Ghidra 追代码，不信表面诊断 |
| **以为 atlus 前总是崩** | 所有"atlus 前黑屏"测试都没等够时间！PSX LZSS decode 很慢 + cdrom 流式加载，game 在 loading 状态 | DuckStation 按 tab 加速验证 ROM hack 必备 |
| **D1 patch Desc1+Desc2 atlus 前崩** | 实际并没崩——只是 LZSS decode + cdrom 加载慢，没等够时间误以为黑屏 | 同上：DuckStation tab 加速 |
| **MIPS unaligned access 在 Ghidra Decompile 里很乱** | `lwl/lwr` 配对在反编译里看着像奇怪的 bit-shift 写操作 | 切到 Listing 视图看实际指令；References 标记的 R/W 是可信的 |

---

## 五、当前状态

**已完成：**
- ✅ 完整二进制补丁管道（已在游戏内验证）
- ✅ **字体源定位**：确认对话字体在**文件 59 sub-file 0**（不是 F0086.BIN！）
- ✅ **字体注入**：`inject_chinese_font.py` 批量注入（扫 zh + meta_zh + 假名缺字，含 LZSS 重压缩+保留 tag）
- ✅ **D1 字库扩容**（2026-05-28）：突破 SLPS 22 sectors 限制扩到 30 sectors。可装全部中文字（含 strtbl 用字共 ~2900 unique）
- ✅ **script 剧情对话 100%**（11445/11445 页）：DeepSeek-R1 批量翻译（11h/~CA$15）+ 手工补 199 条控制码密集对话
- ✅ **strtbl UI/菜单 100%**（2939 条）：菜单/系统提示/技能说明/地点名/角色名。`encode_strtbl.py` + `apply_strtbl.mjs`(archive) + `apply_strtbl_slps.py`(SLPS file 0)，含索引表重建
- ✅ **存档/记忆卡菜单**：`savemenu_strtbl.py` 处理 ISO 游离区 sector 273695（30 条系统消息）
- ✅ **主菜单/提示语**：`mainmenu_strtbl.py` 处理游离区 sector 271864（魔法/道具/读取/保存 + "请选择指令"等提示，111 条，原位替换不碰指针表）
- ✅ **apply_zh 4 大 bug 全修**（2026-05-30）：详见"六、apply_zh 写回的连环 bug"。11670+ 条对话全部 apply，含 RLE 剧情文件 + 140 条 relocate 长译文
- ✅ **控制码守恒校验**：`check_translation.py`（SURNAME 软码可增减，其他 hard 码强制守恒）
- ✅ **定位工具**：`locate_text.py '日文'` 查任意日文在哪个 file/游离区，决定用哪个 pipeline
- ✅ **一键管道**：`build.py` 整合 还原→D1→字体→encode(script+strtbl)→apply(script按file分组+strtbl+SLPS+savemenu+mainmenu)→ECC
- ✅ **污染防御**（2026-05-24）：extract 只读 iso_backup；export 用 codetable_og 渲染 JP；build sanity check
- ✅ **end-to-end 验证**：游戏从启动到主菜单到剧情/战斗全程中文（DuckStation tab 加速）

**关于 "battle string"**：⚠️ **不存在独立的 battle string**。上游 `extract_battle_strings` 是失败的半成品（条件 `f[0]==8` 在真实文件零匹配，全 false）。所谓"战斗/剧情对话没翻"实际是 **RLE 压缩的 script 文件（file 3/4 等）被 apply_zh 的 bug 坑了**，已全部修复。

**待解决（niche，v2）：**
- ⚠️ 设置菜单（CONFIGURATION MENU：サウンド/振動/マップ回転方向...）— 在 file 84 offset 135168 + 游离区 271964，特殊格式表，extract_string_tables 没识别
- ⚠️ 命名界面（ひらがな/カタカナ/漢字 + 假名表）— 特殊格式
- ⚠️ Persona/恶魔名（游离区 sec 210）、道具名（sec 200）— 系统数据表
- ⚠️ 对话框三角 + L1/L2 图标 + HP/¥/TIME 颜色 — 非文字 UI 元素（cosmetic）
- ⚠️ 存档菜单「差込口X」插槽标签（SLPS 动态拼接，极小瑕疵）
- ⚠️ 人名一致性校对（可选润色）

### D1 字库扩容方案（2026-05-28 突破）

**问题**：原版字库 2575 个 slot，1277 个中日共用字可复用，剩余 1298 个可覆盖 og 日文 kanji slot。需要 inject 1498 个新中文字，**差 200 个字**。试图写 og 空 slot（>2574）时，LZSS 重压缩字节数膨胀超过 22 sectors（45056 字节）→ 字库 LZSS 数据被 SLPS 读取截断 → 黑屏。

**Ghidra 反汇编关键发现**：

1. **字库基址 0x801CE800**（在 FUN_80024e78 函数内 lui $a2, 0x801C + ori $a2, $a2, 0xe800 加载，位于 ISO sector 70 offset 0x68c）
2. **字库加载链**：
   ```
   FUN_8002166c (启动 init)
   └─ FUN_80017a9c(0)          ← 加载 sub-file 0
       └─ FUN_80024f00          ← dispatch wrapper
           └─ FUN_80024e78      ← LZSS state setup
               └─ FUN_80026a10   ← state machine init
               └─ FUN_80024c78   ← CD-ROM DMA 注册 (DsPacket callback)
   ```
3. **Sub-file 描述符表** @ RAM 0x80010070-0x8001007f（ISO sector 29 offset 0x70）：
   ```
   0x80010070: 00 00 00 00 16 00 01 00   ← Desc 1: sub-file 0 size=22 sectors
   0x80010078: 00 00 16 00 1C 00 01 00   ← Desc 2: sub-file 1 offset=22, size=28
   ```
4. **7-slot CD ring buffer** @ 0x801CB000-0x801CE800（紧贴字库基址，环形索引）

**D1 修改方案**：

| Step | 修改 | 作用 |
|------|------|------|
| 1 | ISO sector 29 offset 0x74-0x77: `16 00 01 00 → 1e 00 01 00` | Desc 1 short[2]: sub-file 0 size 22 → 30 sectors |
| 2 | ISO sector 29 offset 0x78-0x7b: `00 00 16 00 → 00 00 1e 00` | Desc 2 short[1]: sub-file 1 offset 22 → 30 sectors |
| 3 | 把 file 59 搬到 ISO 末尾（sector 294186），更新 FILEPOS.DAT[59] 和 PVD volume_space_size | 给 sub-file 0 留 30 sectors（61440 字节）空间 |
| 4 | inject 中文 bitmap：先填 og kanji slot（不膨胀），再填扩展 slot 2575-3768（每字 ~14 字节膨胀） | 用 1298 + 200 = 1498 个 slot 装下所有新中文字 |

**容量数据**：
- LZSS 重压缩字节数：44782 → 47590（< 30 sectors = 61440 ✓）
- decompressed 字节数：65520 → 69000（RAM 0x801CE800+69000 < BSS 区起点）
- 可用 slot 数：3576 → 3768（扩展 192 个新 slot）
- 实际 inject 1498 个新中文字 = needed_new 全部覆盖

**实现**：`patch_subfile_table.py` + `relocate_file59.py` + `inject_chinese_font.py`（三步由 `build.py` 编排）

---

### 字体定位事件回顾（2026-05-23）

为了排查"修改字体后游戏渲染不变"的问题，我们做了一系列实验：
1. 把 F0086.BIN slot 16（い）改成 草 → 游戏仍显示 い
2. 把 F0086.BIN slot 63（？）改成全 0xFF（实心黑块）→ 游戏仍正常显示 ？
3. 验证 ISO 字节、ECC、扇区读取都没问题
4. 在 DuckStation 中 RAM 搜索 草 字节 `88 E0 7F 88 C0 1F FC 41` → **完全没找到**
5. 在整个 ISO 中搜索 RAM `0x001EF5A0` 看到的字节 `81 10 10 01 11 20 01 12` → 出现在 **3 个位置**：
   - F0086.BIN 文件 86（slot 16，已知）
   - **文件 59 sub-file 0**（解压后 offset 0x5A2）⭐
   - **文件 59 sub-file 1**（解压后 offset 0x4A6）
6. 文件 59 sub-file 0 解压后正好 65520 字节，与 F0086.BIN 完全相同
7. 修改文件 59 sub-file 0 的 slot 16 → 游戏成功显示 草 ✅

**教训：以后排查"修改无效"问题，第一步永远是验证 RAM/VRAM 实际是否包含修改后的数据。**

---

### apply_zh 写回的连环 bug（2026-05-30 全修）

症状：游戏里大量剧情/战斗对话显示日文（甚至乱码），但 `all_translatable.json` 里明明有译文。根因是 `apply_zh.mjs` 写回阶段**4 个叠加的 bug**：

**1. RLE vs LZSS 压缩**：file 3/4 等剧情脚本用 **RLE** 压缩（sub-file `byte[1]==1`），不是 LZSS（`byte[1]==2`）。apply 硬编码 LZSS 解压 → 解出垃圾 → 头部全乱 → **197 条对话判 no_offset 跳过**。
   - 修复：按 `byte[1]` 选 `rle.decompress`/`lzss.decompress`；重压缩统一 LZSS 并强制 `byte[1]=2`（无 RLE 压缩器）。

**2. 多 sub 互相覆盖**：一个 file 有多个 sub-file（file 90 有 160 个），都在同一 archive。旧 apply 每个 sub 从 backup 读整个 archive、只改 1 个、全量写 working → **后一个 sub 把前一个的中文覆盖回日文**，最终只剩最后 apply 的 sub。
   - 修复：`apply_zh.mjs <file>`（不带 sub）**一次处理整个 file 的所有 sub**，合并成一次 `patch_archive_inplace`。`build.py` 按 file_id 分组调用。

**3. archive padding 损坏**：紧排 archive（sub 间无 sector padding，如 file 90）里，sub 重压缩变短，留下的 0 被 `extract_files` 误判为 sector padding → 后续 sub 错位、archive 损坏（"Unexpected data at end of sector"）。
   - 修复：`compress_with_header` 把 recomp 补齐到原 sub 的 4 字节对齐长度，len 字段写补齐后长度（解压看 uncomp_size 停，多余字节无害）。

**4. relocate（append 重定位）被无条件回退**：译文比原文长的对话（**140 条**）会追加到 script 末尾 + 改 arg 指针重定向。但合并 patch 时，主流程 step1 **无条件把所有有 append 的 sub 回退成 in-place**（误以为 append 总超容量），丢弃全部 relocate → 长译文对话保留日文，但报告假报 `relocated:true success`。
   - 修复：改成**三级降级**——先全用 append 版（保留 relocate）；某 sub 超容量才回退 in-place（放弃该 sub 的 append diag）；in-place 仍超才 drop（整 sub 保留原文）。

**结果**：11670+ 条对话全部 apply，0 no_offset，relocate 长译文全恢复，只剩个别真超容量的保留原文。

**经验**：
- 验证翻译是否生效要看 **working ISO 实际解压字节**（用 `lib/archive.mjs` 的 `extract_files` + 解压 + 按指令表算 diag offset），不能只信 build 报告的 "success"（旧 apply 报 success 但被覆盖/回退）。
- Python `pylib/p2is.py` 的 archive 解析器在改过的 archive 上可能报错/死循环；用 JS `lib/archive.mjs extract_files` 验证更可靠。
- 看到没翻的日文，先 `python3 locate_text.py '日文'` 定位它在哪个 file/游离区，再决定 pipeline。

---

## 六、日常工作流（快速参考）

```bash
# 1. 编辑 all_translatable.json：填写 zh / meta_zh 字段

# 2. 一键完整管道（推荐，~2-30s 完成）
python3 build.py
# 等价于：还原 ISO → 注字体 → encode → apply（每个 file/sub）→ 修 ECC → 报告

# 常用参数：
python3 build.py --no-restore   # 增量构建，不还原 ISO
python3 build.py --no-font      # 跳过字体注入（仅 zh 文本变了）
python3 build.py --only 181,3   # 只 apply 指定 file_id

# 3. 启动模拟器，从标题画面开新游戏（不能加载存档！）
```

### 手动单步（高级用法）

```bash
python3 inject_chinese_font.py          # 仅注字体
python3 encode_zh.py                    # 仅 encode
node apply_zh.mjs 181 8                 # 仅 apply 单个 file/sub
```

### 污染检测 & 恢复

```bash
# 自动告警：build.py 启动会扫 all_translatable.json 的 jp 字段
# 如果发现非日文 codetable 的字符（中文混入）→ 红字告警

# 人工恢复：从 backup ISO 重新提取 + 重生成
node p2ep_tool.mjs extract_script 0 880 -o out/scripts
python3 export_translatable.py   # 旧 zh 自动按 id 回灌
```
