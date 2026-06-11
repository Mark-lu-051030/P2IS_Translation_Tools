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
| 86 | F0086.BIN | 裸未压缩字库（格式同 file 59 解压后）。**对话不读它（读 file 59）；但命名界面等非对话画面读 file 86**——`inject_font_f86.py` 同步中文字形进去 |
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
| 1 | subtype / 压缩 | **同时决定解压方式（1=RLE，2=LZSS）+ 场景脚本 subtype。⚠ 重压缩必须保留原值**：RLE 文件(byte[1]=1)被强行改成 2 → cutscene/战斗白屏（见"四、踩过的坑"） |
| 2–3 | sub_index | sub-file 序号（uint16 LE）⚠️ 重要 |
| 4–7 | total_size | 该 sub-file 总字节数（含头部） |
| 8–11 | uncomp_size | 解压后字节数 |
| 12+ | — | 压缩数据（byte[1]=2 → LZSS，=1 → RLE） |

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

> **⚠️ 重要修正**：之前以为字体在 `F0086.BIN`（文件 86），实际**对话字体在文件 59 sub-file 0**（LZSS 压缩），不是 86。详见"五、踩过的坑"中的字体定位事件。**再修正**：file 86 也不是全无用——**命名界面等非对话画面读的就是 file 86**（裸字库），所以 `inject_font_f86.py` 要把中文字形同步进去。

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
| `lzss.mjs` | LZSS 压缩 / 解压。`compress`=贪心（日常够用）；`compress_optimal`=DP 全局最优解析（比原版游戏压缩器小 12~211 字节，紧实 archive 原位改写必用，token 格式不变）；`compress_to_size(input,header_len,target_total)`=DP 压缩后用有效 token **精确填满到目标槽大小**（放不下返回 null）——给"sub 紧密排列、非扇区对齐、tc 必须=槽大小"的 map 文件原位重压用，避免补零致游戏解压垃圾黑屏 |
| `rle.mjs` | RLE 压缩 / 解压。file 3/4 等剧情/战斗脚本用 RLE；`compress`（与 decompress token 格式对应）让 RLE 文件翻译后压回 RLE、保持 `byte[1]` subtype 不变——是觉醒/战斗白屏的修复关键 |
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
| **`build.py`** | **一键完整管道**：还原 ISO → D1（patch 描述符 + 搬 file 59 + 注字体 + 同步 file 86）→ 编码 zh/strtbl → apply（脚本按 file 分组 + strtbl + SLPS + savemenu + mainmenu + nametable + freetbl 三表 + **maptbl 地图区域/房间名 + citymap 城市图地点标签 + field 字段文本**）→ 修 ECC → 报告。`SKIP_FIELD=1` 跳过字段回插（二分调试用） | ⭐ 主入口 |
| `apply_maptbl.mjs` | 翻译 map 97-136 sub0 头部的**区域名（左上角第一行）+ 房间名（第二行）**。原位等长替换 + **`compress_to_size` 精确填满原始槽重压**（tc=op 枚举/解压均正确，修了 padding 补零致进图黑屏的坑，见"四、踩过的坑"）。房间名表是 **16-uint16 固定宽记录**（名字左对齐 + `{1000}` 填充 + `·`/`」` 分隔符，在 sub0 中段与瓦片混排），用 **roomLut 查表 + 记录结构校验双重过滤** 精准定位（实测 95 处 0 瓦片误命中）。译表：`map_names_zh.json`（区域名审定）/ `strtbl 138_0_5`+`room_names_zh.json`（房间名） | ✅ |
| **`apply_citymap.mjs`** | 翻译**城市俯视图地点标签**（如 スマル・プリズン→苏摩鲁监狱、廃工場→废工厂）。标签按区分散在 **file 1113/1114/1115/1116 未压缩区**（平坂/夢崎/青華/港南区各一簇，同簇重复 2-3 份），是 og 码 + **`0x1000` 终止符**（非 RET 非字符串表 → 字段提取漏了；⚠`0x0000` 会渲染成「不能当填充）。**偶对齐滑窗逐字符匹配 + 接受一码多形**（如 ヨ=879/543，预编码取末码+indexOf 会漏匹配）+ 后跟 0x1000 → 原位换 CN+0x1000终止+填充。`LABELS` 字典可扩展 | ✅ |
| `apply_affinity.mjs` | **Persona属性抗性句**(file47/69/70/71/1109 五副本)：模板句典(ATTR×动作)+原位等长(ct码+全角空格填充),控制码/指针表零改动。`extract`/`apply` 双模式。⚠ parseEntries 条目尾 p=q-2 防隔条漏 | ✅ |
| `apply_tarot.mjs` | **塔罗/魔法卡描述**(file1105 主显示源+64-67 残留)：解析 strtbl 同构条目→查 strtbl:64_0_* 译文 LUT→逐行原位等长。幂等 | ✅ |
| `apply_battlenames.mjs` | 战斗面板名(file1129 名字簇 og码+{1000}+RAM指针表)原位翻译——数据正确但游戏不读(RAM 另有源,搁置),保留无害 | ⛔搁置 |
| **`extract_field_text.mjs`** | 提取主管道漏掉的**字段文本**（外景对话 file 1075、装备/简介/传闻 等，散在非-scene_script 自定义格式文件）。读全文件表(0x2400, 真实 1144 文件)、有界 sub 枚举、RET 定界、CJK 密度过滤、内容级去重 → `out/field_text.json` | ✅ |
| **`clean_field_text.py`** | 清洗字段文本：过滤垃圾(单字符重复噪音)、按唯一 jp 去重 → `out/field_to_translate.json`(翻译输入) + `out/field_text_clean.json`(全部出现位置) | ✅ |
| **`translatable/translate_field.py`** | 字段文本 DeepSeek-R1 批量翻译（复用角色名锁定，⚠Maya=**舞耶**非麻耶；保留 `<cXX/>`+`\n`；partial 按唯一 id 命名；`--merge` 合并 + NAME_FIX 归一化；`--retrans` 重译太长条目更短） | ✅ |
| **`apply_field.mjs`** | 字段文本回插：原位等长(zh码+**RET紧跟zh**+全角空格填到原字节数；padding必须在RET后否则游戏逐字渲染空格卡顿)，**从 WORK 读**保留前面 apply、**跳过结构性条目**、未注册表文件按jp内容重建变长(不缩短)、绕过 cdimage 881 上限直接扇区写。**含归档子文件路径**：file 1112-1117/77 多sub归档里~1013条NPC对话(解压→原位改→`compress_optimal`重压保留头tag→塞回原sub槽不移偏移)。tag比对忽略装饰码`<c20/>`(救回93条描述)；encodeText把非cXX的`<占位符>`(如`<舞耶>`)当字符。`verify`/`dry`/`apply`/`dumptoolong`(导出太长/标签不符/缺字) | ✅ |
| `shorten_toolong.py` | 把太长字段译文缩到≤budget(译者审定的等价缩写规则+逐条OVERRIDE,保意减字只裁多出部分)→合回 field_text_zh.json。太长 760→14 | ✅ |
| `fix_misschar.py` | 字库没有的罕用字(频率1被丢)在译文里换常用同义词(摩羯座→山羊座/馒头→包子/内讧→内斗)，不占字库。缺字 22→0 | ✅ |
| `patch_subfile_table.py` | **D1 扩容 Step 1**：patch SLPS sub-file 描述符表（Desc1+Desc2 22→**32** sectors，字段文本字多扩到 32；Desc1 实际由 set_subfile0_size 动态精确设） | ✅ |
| `relocate_file59.py` | **D1 扩容 Step 2**：把 file 59 搬到 ISO 末尾 + sub-file 1 在 **32** sectors offset；同时更新 FILEPOS.DAT 和 PVD | ✅ |
| `inject_chinese_font.py` | **D1 字体注入**：读 working ISO file 59 → inject 中文到 og kanji slot + 扩展 slot（从低位2575↑紧凑分配）+ og 缺的假名 → **`compress_optimal` 重压缩**(挤进 32 sectors) → 修 ECC。扫 all_translatable + map/room/**field_text_zh** + **名表/UI zh(提权,保证名字字形不被罕用对话字挤掉)**；动态 N。⚠ decompressed 仍 65520(RAM上限3575槽)，超出的极罕用字丢弃 | ✅ |
| `inject_font_f86.py` | **file 86 字体同步**：命名界面等画面读 file 86（裸未压缩字库，非 file 59）；把注入 file 59 的同批中文字形（codetable≠og 的槽）写进 file 86 | ✅ |
| `encode_zh.py` | 把 script 翻译编码成字符码 items（含 META 段处理 + 全角标点 alias），输出 `out/scripts_zh/` | ✅ |
| `encode_strtbl.py` | 把 strtbl 翻译编码成 items，输出 `out/strtbl_zh/`（文件名 regex 支持 SLUS 前缀=file 0） | ✅ |
| `apply_zh.mjs` | 把编码好的对话写回 ISO。`<file>`（不带 sub）一次处理该 file 所有 sub 合并 patch（**必须**，否则多 sub 互相覆盖）。**RLE 文件用 rle.compress 压回 RLE、保留原 byte[1] subtype**（觉醒/战斗白屏修复），LZSS 压回 LZSS，relocate 三级降级，自动 ECC | ✅ |
| `apply_strtbl.mjs` | strtbl 写回 archive 文件（**重建 count+索引表**，跳过 SLUS） | ✅ |
| `apply_strtbl_slps.py` | SLPS file 0 内 strtbl 写回（raw-sector，重建索引表） | ✅ |
| `savemenu_strtbl.py` | 存档/记忆卡菜单 extract+apply（ISO 游离区 sector 273695，保留前缀/控制码） | ✅ |
| `mainmenu_strtbl.py` | 主菜单/提示语 extract+apply（游离区 sector 271864 两个文本区，原位替换不碰指针表，短项前补全角空格居中） | ✅ |
| `nametable_strtbl.py` | 道具/Persona/技能/恶魔名主表 extract+apply（游离区 sector 200，~1639 条，原位等长替换） | ✅ |
| `freetbl.py` | **通用游离区 strtbl 引擎**（注册表 TABLES 驱动）：`names`(221) / `contactui`(271039) / `config`(271964)。原位等长替换不碰指针表；含带参控制码的条目整条 skip 防崩 | ✅ |
| `check_translation.py` | 校验翻译：进度 + hard 控制码守恒（SURNAME 软码豁免）+ codetable 缺字 | ✅ |
| `locate_text.py` | 定位工具：`'日文'` 查它在哪个 file/游离区 + 该用哪个 pipeline（`--working` 搜改后 ISO） | ✅ |
| `lookup_char.py` | 字符 ↔ slot 互查（codetable 调试） | 工具 |
| `name_fix.py` | 一次性：批量替换 all_translatable 里指定人名（对齐 PSP 译名），写 `.namebak` 备份 | 工具 |
| `audit_untranslated.py` / `scan_untranslated.py` | 游离区聚簇扫未翻文本。**实验性**：纯文本表可靠，码密集区误报多（见 memory），长尾靠玩家反馈补 | 实验 |
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
| **觉醒/战斗场景纯白屏（2026-06-01，调试最久）** | sub-file 头 `byte[1]` 是**场景脚本 subtype**（不是压缩类型）。apply 把 RLE 剧情/战斗脚本(file 3/4)重压成 LZSS 时强制 `r[1]=2`，改掉了 subtype → cutscene/战斗引擎据 byte[1] 走错处理 → 进场景 hang 纯白屏（debugger 无异常）。LZSS 文件本就 byte[1]=2 故无事，只有 RLE 文件中招 | `lib/rle.mjs` 实现 `compress`；apply 的 `compress_with_header` 对 `byte[1]==1` 的 sub 用 `rle.compress` 压回 RLE、保留原 byte[1]（不再强制 =2）。**铁证**：commit 53d3c1a(RLE 文件未翻=原版 RLE)正常 vs c408510(RLE 翻成 LZSS)白。⚠ 中途误判为"短译文 0x00 填充/改空格填充"，是弯路、已证伪 |
| **worktree build 出来整个游戏是日文** | 新建的 git worktree 没有 conf.json，apply 找不到工作 ISO 路径写不进去；step_restore 又把 ISO 还原成 backup → 整盘日文 | 在 worktree 里 build 前先 `cp 主仓/conf.json`；或直接在主仓 build。诊断时务必先验证 working ISO 真翻译了（file 181/4 解压 ≠ backup）再下结论 |
| **地图区域名原位改名重压"超容量"塞不回**（2026-06-03） | 不是名字变长——是 `lib/lzss.mjs` 贪心 `compress` 比原版游戏压缩器差 ~0.4%：原样不改重压就胀 +22~+78 字节。map 文件 5~6 sub 紧贴、文件尾 0 slack，胀 1 字节就溢出 | `lib/lzss.mjs` 加 `compress_optimal`（DP 全局最优解析），比原版小 12~211 字节 → 名字轻松塞回，不用搬文件。**先做无修改 round-trip 比原大小**就能区分"压缩器差"还是"数据变大" |
| **进外景地图黑屏死机**（廃工場/ム大陸 等外景图，2026-06-08 公测后玩家报） | `apply_maptbl` 重压地图 sub0 后把压缩头 tc（offset 4）写成 **padding 后的槽大小 `op`** 而非真实压缩长度（`compress_optimal` 压完再补零到 op）。map 文件多个 sub **紧密排列、非扇区对齐**，游戏按 tc 读进尾部零填充 → 解压出垃圾 → 进图加载即黑屏死机（BGM 还在、左上角区域名能显示、场景全黑） | 改用 `lib/lzss.mjs` 新增的 `compress_to_size(d, 0xc, op)`：DP 最优压缩后用**有效 token 精确填满到原始槽大小**（无零填充），tc=op 时归档枚举 + 解压双双正确。⚠ 不能照搬 apply_field 的"tc=真实长度 + 槽内补零"——那招要求 sub 扇区对齐（遇零枚举跳到下个扇区边界找 sub），map 文件紧密排列会丢 sub |
| **発布盘没带上修复**（v0.3.0 玩家继续报白屏，2026-06-11） | v0.3.0 的 bin 是 20:16 build 的，RLE `compress_to_size` 修复代码 20:21 才存盘——修复根本没上船 | 发版前 `stat` 比对 WORK bin mtime vs 全部 lib/apply 代码 mtime；修复后单独重跑 `apply_zh 3/4` 落盘 |
| **変異/融合白屏**（选変異→动画白屏，2026-06-11 调一整天） | P2 归档**没有偏移表，游戏按每个 sub 头的 tc 链式找下一个 sub**（组间 0x800 对齐兜底）。apply_field 归档路径重压后把 tc 写成变短的真实长度 → **同组后续 sub 全部错位** → 変異台词（file77 链条深处的小 sub）读到错位垃圾当压缩流解压 → 跳进垃圾执行白屏。RAM 取证：EPC 区域是"错位 1 字节的类 MIPS 垃圾" = 链错位指纹 | apply_field 归档重压改 `compress_to_size(dc, 12, 原tc)` **精确填满原 tc，链条逐字节不变**；写了链验证器（walk WORK vs 原版逐 sub 比对 off/tc/uc/type + 输入有界解码行为）。⚠ 三轮二分还原战斗文件全白费——変異台词在 field 管道(file77)不在战斗文件，**二分前必须列全"谁写过这个数据"** |
| **提取器吞 sub 头**（同日发现的第二颗雷） | extract_field_text 的 raw 扫描把 sub 头 8 字节吞进文本单元开头（低码渲染成「，如 `field:77:0x4552` 的 jp 前缀 `「」「r「`=风魔小太郎），翻译删了前缀，apply 原位写回时中文从头部位置盖起 → sub 头被毁、链从此断裂 | 偏移 +吞掉的字节数、jp 去前缀（0x4552→0x455c 已修）。凡归档文件上 jp 开头有「类垃圾的原位条目都是嫌疑 |
| **战斗交涉人名乱套**（リサ→雅 等，v0.3.0 玩家报，2026-06-11） | 游戏开档时把称呼字符串以**字符码**写进记忆卡，而 inject 按词频分配新字槽位、词频每版都变 → **新分配字槽位每版洗牌**（v0.2→v0.3: 丽2179→导、莎→羁、银→败、荣→卢）。og 共用字天然稳定所以 达哉/米切/舞耶 没事——乱的恰是简体专用字。盘上名字表/SLUS表/指针全是好的，锅在"存档持久化码"与"码表跨版本漂移"之间 | `codetable_pinned.json`（=git 52314b0 的 v0.2 公测码表）**钉死布局**：inject 完整复现其 slot→字，新字只进**腾退槽**（已弃用字让位），成功后演进结果写回 pinned → 永久稳定。**存档会持久化的编码空间 = ABI，必须钉版本兼容**。⚠ 队列须过滤 equiv 日文字（時/闘 由别名映射满足，不滤会挤占稀缺腾退槽） |
| **"秋"字渲染乱码**（槽 3576 越界） | `MAX_SAFE_SLOT=(65520-0x480)//18` **整除时少了 -1**：槽 s 占 `[0x480+18s, 0x480+18(s+1))`，3576 的位图落在 decompressed 65520 上限之外永远写不进去 | 公式 -1（=3575）；pinned 模式把越界槽的字转入新分配队列 |

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
- ✅ **觉醒/战斗白屏根治**（2026-06-01）：真因是 apply 把 RLE 脚本(file 3/4)重压成 LZSS 改了 `byte[1]` subtype → 引擎走错处理白屏。`lib/rle.mjs` 加 RLE `compress`，RLE 文件翻译后保持 byte[1]=1、与原版结构同构。已游戏内验证觉醒/战斗正常。详见"四、踩过的坑"+"六"bug #1
- ✅ **游离区 UI/名表**（2026-05-31）：道具/Persona/技能/恶魔名主表（sector 200，`nametable_strtbl.py`，~1639条）、角色姓名/昵称（221）、交涉动作+战斗UI（271039）、设置菜单（271964）—— `freetbl.py` 通用游离区引擎（注册表驱动），原位等长替换不碰指针表；带参控制码条目整条 skip 防崩
- ✅ **file 86 字体同步**（`inject_font_f86.py`）：命名界面等画面读的是 file 86（裸未压缩字库，非 file 59），把注入 file 59 的同批字形同步进去
- ✅ **字体动态 N + 主菜单居中**：`patch_subfile_table.set_subfile0_size` 按实际重压缩大小设 SLPS Desc1（修 UI 精灵错乱）；`mainmenu_strtbl.py` 短菜单项前补全角空格居中
- ✅ **左上角地点名（区域名+房间名）**（2026-06-03）：场景面板两行名字在 **map 文件 97-136 sub0 头部**（区域名=开头 og 码串；房间名=固定宽记录表 `[标志∅/」][名字][{1000}填充]`）。`apply_maptbl.mjs` 原位等长替换：区域名用人工审定表 `map_names_zh.json`（对齐对话正文 希巴尔巴/卡拉科尔，专名用户拍板），房间名取 `strtbl 138_0_5` 现成译法 + `room_names_zh.json` 覆盖个别超长（駐輪場→停车场、階段→楼梯）。边界规则（前∈{0,1} 后≥0x1000）防误伤瓦片数据；40 个图区域名 + 110 处房间名全写回
- ✅ **最优 LZSS 压缩器**（2026-06-03）：`lib/lzss.mjs` 的 `compress_optimal`（DP 全局最优解析，token 格式不变游戏可解）。原贪心 `compress` 比原版游戏压缩器差 ~0.4%，导致紧实 archive（map 文件 5~6 sub 紧贴、0 slack）原位改名重压必膨胀 → 装不回。最优解析比原版**小 12~211 字节**，彻底拆掉压缩墙，且对话/字体链也受益（更多 headroom）。每个 map ~50-150ms，写回前强制 round-trip 校验防损坏
- ✅ **字体槽等价兜底**（2026-06-03）：`jp_cn_equiv.json`（56 对 JP新字体→CN简体，如 姉→姐、駐→驻、階→阶）。`inject_chinese_font.py` 把这些 JP 字的 og 槽**强制渲染成 CN 简体字形**（即使该 JP 字在译文里也用了，无条件覆盖）；`encode_zh.py` 加等价别名让译文里字面的 JP 字编码到同一槽。作用：任何**漏翻的 og 汉字**（地图/未覆盖文本）优雅降级成可读简体，而非乱码
- ✅ **字段文本大批量**（2026-06-04）：发现真实文件数 **1144**（原管道 cdimage 硬编码 0x1b88 只读 881，漏 881-1143）。提取主管道漏掉的字段文本——**外景/事件对话 file 1075（6336条!）+ 装备说明 + 人物简介 + 传闻**等（非-scene_script 自定义格式）。管道：`extract_field_text.mjs`(全表+有界sub+RET定界+CJK过滤) → `clean_field_text.py`(去重→10016唯一) → `translate_field.py`(DeepSeek-R1, ~10h/$15) → `apply_field.mjs`(原位等长, 从WORK读保留前面apply, 跳过strtbl表区+结构性条目, 含file>881)。字体扩到 **32 sectors** + `compress_optimal` 装下。详见"六"
- ✅ **strtbl 带参控制码 + 终止符 bug 修复**（2026-06-03）：谣言描述等"乱码+闪一下消失"——`apply_strtbl` 的 `items_to_bytes` len nibble 写错(0x1100|cmd→`0x1000|(词数<<8)|cmd`) + `encode_strtbl` 丢了 `[6]WAIT` 终止符(硬加[1][3]→保留原 entry 尾部结构码)。游戏内确认修好
- ✅ **归档子文件对话大补漏**（2026-06-04）：file **1112-1117 + 77** 是多sub归档，里面**~1013 条市井NPC/流言/剧情对话**已翻译但 apply_field 原来只认扁平 id `field:N:0x..`、归档 sub id `field:N_Md:0x..` 全被忽略 → 整片对话保留日文。加归档路径：解压→原位等长改→`compress_optimal` 重压保留头tag→塞回原 sub 槽(不移偏移、文件大小不变)。游戏内确认市井对话中文不崩
- ✅ **字段回插 3 坑修复**（2026-06-04）：①padding 必须填 RET **后**（原来填前→游戏逐字渲染空格→对话框结束卡很久不能操作）；②tag 守恒比对忽略装饰码 `<c20/>`（DeepSeek 重组常丢，救回 93 条技能/装备描述 标签不符153→60）；③encodeText 把非 cXX 的 `<占位符>`(`<舞耶>`/`<前>`)当字符（修缺字None）
- ✅ **太长全清 + 缺字归零**（2026-06-04）：`shorten_toolong.py` 逐条审定缩写(保意减字只裁多出部分)太长 760→14(仅2条内部niche拉丁名)；`fix_misschar.py` 罕用字换常用同义词(摩羯座→山羊座/馒头→包子)缺字 22→0，不占字库。`apply_field dumptoolong` 导出太长/标签不符/缺字三类供排查
- ✅ **字体槽等价补 撃→击/闘→斗/歓→欢**：装备"攻撃力"显示日文 撃 → 加进 `jp_cn_equiv.json` og 槽渲染成 击
- ✅ **城市俯视图地点标签**（2026-06-04）：スマル・プリズン→苏摩鲁监狱。读取源在 **file 1113 未压缩区**(og码+`0x1000`终止符，⚠`0x0000`渲染成「不能当填充)。`apply_citymap.mjs` 精确匹配JP标签字节+后跟0x1000→原位换CN，集成 build(4j2)。LABELS 字典可扩展
- ✅ **进图黑屏死机修复 + 房间名 + 大地图多文件**（2026-06-09，公测后玩家反馈）：
  - **黑屏根因**：`apply_maptbl` 重压地图 sub0 时把压缩头 tc 写成 padding 后槽大小 `op` + 补零（`compress_optimal`）。map 文件多 sub **紧密排列、非扇区对齐**，游戏按 tc 读进尾部零填充 → 解压垃圾 → 进图黑屏（廃工場/ム大陸，BGM 还在、区域名能显示、场景全黑）。**改用 `compress_to_size(d,0xc,op)` 精确填满槽（无零填充）根治**，tc=op 枚举/解压均正确
  - **房间名重新启用**：之前误以为房间名原位替换的假阳性是黑屏元凶而停用，真凶是上面的 tc bug。查明房间名表是 **16-uint16 固定宽记录**（在 sub0 中段与瓦片混排），改用 **roomLut 查表 + 记录结构校验双重过滤**，95 处命中 0 瓦片误伤（駐輪場→停车场 / 階段→楼梯 / 職員室→职员室 等）
  - **大地图标签扩到多文件**：城市图标签按区分散在 **file 1113/1114/1115/1116**（之前只处理 1113）。廃工場 标签在 1116（不在 1113）。补齐 51 处（廃工場→废工厂、各区片假名地名）。修了 og 字库**一码多形**（ヨ=879/543）导致 indexOf 漏匹配 → 改字符→码集合滑窗匹配
  - ⚠️ **"废工厂" vs "废工场"**：字体等价 `場`→`场` 只能给"废工场"；"废工**厂**"是意译，进图区域名走 `map_names_zh.json`、大地图标签走 `apply_citymap` 的 LABELS，两处独立不同源

**关于 "battle string"**：⚠️ **不存在独立的 battle string**。上游 `extract_battle_strings` 是失败的半成品（条件 `f[0]==8` 在真实文件零匹配，全 false）。所谓"战斗/剧情对话没翻"实际是 **RLE 压缩的 script 文件（file 3/4 等）被 apply_zh 的 bug 坑了**，已全部修复（最后一个坑是重压缩改了 byte[1] subtype 致白屏，2026-06-01 修，见"四、踩过的坑"）。

- ✅ **战斗 UI 大扫除**（2026-06-10）：SLPS 战斗UI区(sector 29244-29268) 注册 freetbl `battleui` 表——行动提示/状态异常名/交涉性格/作战说明/错误消息/星座血型 共 201 条。⚠️ 该区内嵌 4 张 SLUS strtbl 表(0_0_0..3)由 apply_strtbl_slps 重建,battleui 必须排除其范围否则覆写坏重建表(菜单项消失事故,已修+排除140条);顺手修 strtbl 错位译文 7 条(アナライズ→分析/ギンコ→银子/ユッキー→小雪 等)
- ✅ **Persona 属性抗性句**（2026-06-10）：玩家报"火炎酱無頚"花字=「火炎糸無効」未翻+糸/効槽被占。`apply_affinity.mjs` 模板句典(属性名×动作)+原位等长,file47/69/70/71/1109 五副本共 **510 段**。⚠️ parseEntries 隔条漏一半 bug(条目尾 q 已越过 {1103},外层 p+=2 前须 p=q-2)
- ✅ **塔罗/魔法卡描述**（2026-06-10）：卡片界面读 **file1105**(strtbl 同构独立副本)而非 strtbl:64 表区 → 翻了不显示。`apply_tarot.mjs` 解析条目→查 strtbl:64_0_* 译文 LUT(216条)→逐行原位等长,1105+64-67 残留共 **343 条**;统一 65/66/67_0_2 烂译版为 64 版(368条);"Persona的魔法中"超长改"可为所持魔法"(救回97条魔法卡)
- ✅ **塔罗 Arcana 名 22 条**进 nametable（魔术师/女祭司/…/愚者,对齐卡描述译名)——但卡片列表界面读 ASCII 名表(西文字体)不读名表,该界面保留英文(见已知问题)
- ✅ **城市图扩展**（2026-06-10）：标签按区分散 5 个文件(1112街中/1113平坂/1114夢崎/1115青華/1116港南),apply_citymap 多文件+一码多形匹配+改从 WORK 读(单独跑不再误伤归档对话,幂等);区名显式翻译(青華区→青华区 修"青胶区"花字)+阿罗耶神社/希尔曼宅/莲花
- ✅ **房间名重启用+补漏**：roomLut 查表+16-uint16 记录结构双重过滤(95处 0 误伤);补 プライズマシンフロア→奖品机楼层 / ビデオゲームフロア→电子游戏楼层
- ✅ **对话卡死根治**（2026-06-10）：apply_zh 重压变短后"零 padding+tc=槽大小"被游戏输入有界解码当指令解析→溢出卡死(563_8 荣吉句后实证)。LZSS 改 `compress_to_size` 精确填满(与地图黑屏同源同修);RLE 兜底待办
- ✅ **NPC speaker 名批量修**：上班族/大叔/老爷爷/老爹/银子 65 条(DeepSeek 翻正文留了日文 speaker)
- ✅ **変異/融合白屏根治**（2026-06-11，玩家报+冷启动复现+游戏内确认修复）：双因——①v0.3.0 盘在 RLE `compress_to_size` 存盘前 build（修复没上船）；②真凶 **归档 tc 链错位**：apply_field 归档重压写短 tc → 同组后续 sub 全错位 → 変異台词（file77 deep sub）解压垃圾跳入执行。改 `compress_to_size(dc,12,原tc)` 精确填满 + 链验证器全过。破案工具链：DuckStation 即时存档 RAM 取证（DUCCS+zstd 解包、CPU 寄存器布局、EPC 反汇编"错位类 MIPS 垃圾"指纹）+ `bisect_files.py` 二分还原工具
- ✅ **战斗交涉人名乱套根治**（2026-06-11，游戏内确认）：码表跨版本漂移 vs 存档持久化字符码（详见"四"）。`codetable_pinned.json` 钉死 v0.2 布局（与 v0.2 仅 3 处差异：泷/珥 腾退给 祂/秋 + 越界槽清除），inject 演进式钉死从此布局永久稳定。⚠ 纯 v0.3.0 新开档玩家名字会反乱（一天版本，重开档即可，发布说明注明）
- ✅ **翻译平台回填管道**（2026-06-11）：`import_platform.py` 把平台校对稿 `{id,jp,translation}` 按 id 前缀路由回 11 类源文件（script/strtbl→all_translatable 按 `:pN` 页号精确定位、field、freetbl 各表、map/room_names），四道安检（jp 一致/标签⊆原文/原位等长类超长跳过/缺页号拒写），干跑报告+`--apply` 自动备份
- ✅ **file1129 战斗名字簇写入摘除**：冷启动验证游戏不读、留着是变量，已还原原版字节并从 build 注释掉
- ✅ **宝箱/效果消息补漏 12 条**（2026-06-11，玩家报"日文后跟同样的中文"）：开宝箱是两条消息——「見つけた」(发现)→「手に入れた」(获得)，file92 事件区成对存放，提取器把"発现版"连同事件代码吞成一单元被假名过滤丢弃。补 見つけた×6(个/张/日元)+已调查过+空箱+効果終了×2；顺手修 円手に入れた 译文多余 `<ce:1/>` 标签(一直被标签安检拦下没进游戏)
- ✅ **说话人单元全盘审计探测器**（2026-06-11）：`<c1d:11/>名字<c1d:1/>` 是确定性结构特征——全盘 1144 文件(raw+解压)扫此模式 + "og 解码含假名≥3 = 漏翻"判定，**误报零**。修完宝箱后复扫 = 0 条剩余，"带说话人的对话"这一整类证明全清。剩余漏网只可能在无说话人的纯 UI 串里

**发布策略（2026-06-05 决定）**：主体（剧情/对话/菜单/道具/技能/装备/简介/外景NPC/城市图，14000+条）已 100% 中文，**发公开测试版 → 随玩家反馈出补丁迭代**。剩余是散落边角，只在特定路线/界面才显示，单人审计找不全（玩家走不同路线几天能列全清单）。下列为 **v1 已知问题**，列入发布说明：

- 🚧 **部分菜单/UI 文本**（持续收口）：2026-06-10 已扫掉一大片（战斗UI区216条/属性抗性句510段/塔罗卡描述343条/塔罗Arcana名22条，见"五"），剩余散落项随玩家反馈补。`<c101>` 定界 UI 串提取扩展仍是待办
- ⛔ **战斗面板/状态页角色名**（2026-06-10 深查后搁置）：ミッシェル/ギンコ/リサ・シルバーマン 等。**数据层面已全部翻好**（SLUS_0_1 strtbl 写入验证；file1129 写入已摘除），但游戏运行时不读它们——冷启动+记忆卡+新战斗仍日文，RAM 0x8009F608 的名字数据另有初始化源。需 DuckStation 调试器断点/Ghidra 追。⚠ 别与已修复的**交涉菜单人名乱套**混淆——那是码表漂移 vs 存档持久化码（2026-06-11 钉死根治，见"四/五"），这条是"显示日文"不是"显示乱码"
- ⛔ **ASCII 西文字体类（暂不可翻）**：①命名界面（独立 JIS 原版字库 + 自有编码 overlay）②**塔罗 Arcana 名列表**（2026-06-10 查明：读 sector 198 的 11 字节定宽 ASCII 名表 `MAGICIAN∅∅∅PRIESTESS…`+ROD/CUP，渲染用 LV/EXP/NEXT 同款西文粗体美术字，**无中文字形**，改字节=乱码）③状态页全名（疑似同类）。共同点：不走 12×12 中文字库，需 Ghidra 改渲染路径才能根治。**塔罗列表保留英文**（描述栏已是【EMPEROR(皇帝)】中英对照，可接受）；nametable 的 22 条中文译名留存（若有其他界面走名表会显示中文）
- ⚠️ **个别迷宫子区域名**（如 シバルバー中心部）：像城市图标签，发现一个往字典加一个，后续补丁
- ⚠️ **标签不符残余 60 条**：多是 file-84 内部事件触发标签(獅子宮戦闘前，玩家不可见)，留日文
- ⚠️ 对话框三角 + L1/L2 图标 + HP/¥/TIME 颜色 — 非文字 UI 元素（cosmetic）
- ⚠️ 存档菜单「差込口X」插槽标签（SLPS 动态拼接，极小瑕疵）

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
   - 修复（2026-05-30）：按 `byte[1]` 选 `rle.decompress`/`lzss.decompress` 解压。⚠ 当时无 RLE 压缩器、重压缩统一 LZSS 并强制 `byte[1]=2`——**这正是后来觉醒/战斗白屏的真因**（改掉了 RLE 脚本的 subtype）。**2026-06-01 补修**：`lib/rle.mjs` 加 `compress`，RLE 文件压回 RLE、保留 `byte[1]=1`，与原版结构同构（详见"四、踩过的坑"觉醒白屏）。

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
