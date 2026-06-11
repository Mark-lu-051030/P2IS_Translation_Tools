# P2IS 汉化 · 可翻译文档索引

本目录是《女神异闻录2 罪》PS1 汉化工程**核心可翻译数据的副本**，从 `P2IS_Translation_Tools/` 抽取，方便校对 / 协作翻译平台直接读取。
**这是副本，不是工程主数据** —— 改这里不会影响 build；真正生效要改回工程原位的同名文件再 `build.py`。

---

## 根目录

| 文件 | 条数 | 格式 | 内容 |
|------|------|------|------|
| `all_translatable.json` | 26811 | `list`，每条 `{id, pages:[{jp,zh}], meta_jp, meta_zh}` | **主翻译文件**。剧情对话(script) + 菜单/道具/技能/角色名/地点(strtbl)。`id` 前缀区分来源(`script:` / `strtbl:` 等) |
| `map_names_zh.json` | 24 | `dict {日名: 中名}` | **地图区域名**审定表(进图后左上角第一行，如 廃工場→废工厂)。约束：中文字数 ≤ 原文 |
| `room_names_zh.json` | 4 | `dict {日名: 中名}` | **房间名**覆盖表(左上角第二行，覆盖个别超长，如 駐輪場→停车场)。主译法来自 `all_translatable` 的 `strtbl:138_0_5` |
| `jp_cn_equiv.json` | 59 | `dict {日字: 中简体字}` | **字体等价表**(姉→姐、駐→驻、階→阶…)。漏翻的日文汉字靠它优雅降级成可读简体，非翻译文本但影响渲染 |

## out/ （字段文本 + 游离区 UI/菜单）

| 文件 | 格式 | 内容 |
|------|------|------|
| `field_text.json` | 提取原文 | **字段文本**(外景对话 file1075、装备说明、人物简介、传闻等，主管道漏掉的自定义格式) |
| `field_to_translate.json` | 待翻译输入 | 字段文本去重后的待翻列表 |
| `field_text_zh.json` | 译文 | 字段文本的中文译文 |
| `field_text_clean.json` | 全位置 | 字段文本每条的全部出现位置 |
| `config_zh.json` | 译文 | 设置菜单 |
| `contactui_zh.json` | 译文 | 交涉动作 + 战斗 UI |
| `mainmenu.json` / `mainmenu_zh.json` | 原文 / 译文 | 主菜单、提示语(魔法/道具/读取/保存 等) |
| `savemenu.json` / `savemenu_zh.json` | 原文 / 译文 | 存档 / 记忆卡菜单系统消息 |
| `names_zh.json` | 译文 | 角色姓名 / 昵称 |
| `nametable_zh.json` | 译文 | 道具 / Persona / 技能 / 恶魔名主表(~1639 条) |

---

## ⚠️ 不在本目录的译名（内嵌在脚本常量里）

以下译名是写死在 `.mjs` 代码的字典里、没有独立 json，如需校对要去对应脚本看：

- **大地图(城市俯视图)地点标签** → `apply_citymap.mjs` 的 `LABELS`(平坂/夢崎/青華/港南 各区，如 廃工場→废工厂、スマル・プリズン→苏摩鲁监狱)
- 区域名 / 房间名的最终采用译法 = 上面的 `map_names_zh.json` + `room_names_zh.json` + `all_translatable` 的 `strtbl:138_0_5`(房间名)/ `strtbl:138_0_7`(区域名)
