# 此项目is forked from cmccord-dev/p2ep_tool， 感谢cmccord-dev大佬的贡献
# 文件总览
## JS 主入口
- p2ep_tool.mjs — CLI 入口，注册所有子命令
- cmd/ — 提取与写回命令
- 文件	用途
- extract_script.mjs	提取对话脚本 → out/scripts/
- extract_battle_strings.mjs	提取战斗字符串 → out/battle/
- extract_string_tables.mjs	提取 UI/菜单字符串
- insert_script.mjs	把修改后的脚本写回 ISO
- insert_battle_strings.mjs	写回战斗字符串
- insert_font.mjs	写回字体文件
- apply_font_patch.mjs 等	各类已有补丁
## lib/ — JS 底层库
文件	用途
- cdimage.mjs	PS1 ISO 扇区读写
- archive.mjs	子文件包提取
- file.mjs	文件头解析、LZSS/RLE 解压
- msg_script.mjs	对话脚本解析与生成（核心）
- lzss.mjs / rle.mjs	压缩算法
- file_table.mjs	FILEPOS.DAT 文件索引（880个文件）
## Python 工具（本次开发）
文件	用途
- codetable.json	核心：字符索引 0-2575 → 字符映射
- codetable_checker.py	交互式逐字校验，支持断点续检、?待定、?模式只过待定
- pending_grid.py	生成所有 [?N] 字符的预览大图
- unknown_in_context.py	在对话句子里查找 [?N] 的上下文
- decode.py	把单个对话 JSON 解码成可读日文
- export_all_dialog.py	导出全部对话到 all_dialog.json（需 codetable 完成后重跑）
## 数据/备份
- codetable_old_offset96.json — 旧版备份（key 从 96 开始的错误版本）
- codetable_progress.json — 校验断点记录
- all_dialog.json — 旧导出，codetable 校验完成后需重新生成