# P2IS 翻译运行日志

记录用 Azure DeepSeek-R1 批量翻译 script: entries 的运行数据，
方便后续复盘、写 B 站视频脚本、估算后续 strtbl/battle 阶段。

---

## 总体目标

- **script: 总数**: 11,670 条
- **此前已翻**（人工 + agent）: 1,055 条
- **本次目标**: 10,615 条剩余

---

## 第一轮（2026-05-25 晚 → 2026-05-26 凌晨）

### 配置
- `BATCH_SIZE = 30`
- `max_tokens = 8000`
- `temperature = 0.3`
- `MAX_RETRIES = 3`

### 关键事件
- **22:00** 启动 `python3 translate.py`
- **23:00 左右** 第一次出现 JSON 解析失败（max_tokens 不够，R1 输出截断）
- **凌晨 2:00 左右** 进度到 batch 71/371（19%），脚本崩溃
  - 报错: `TypeError: unhashable type: 'dict'`
  - 原因: `new_terms_all.add(term)` 中 term 偶尔是 dict 不是 str
  - 修复: 加 `isinstance(term, dict)` 兜底
- **崩溃时数据**: 1986 条 good + 60 条 bad（约 ~3% bad rate）
- **partials 全保留**，断点续传机制工作

### 第一轮持续时间
约 **4 小时**（22:00 → 凌晨 2:00）

---

## 第二轮（2026-05-26 早 → 下午）

### 配置（同第一轮）

### 关键事件
- **修复 bug 后重启**
- **早期 batch（66/305 时）发现 bad rate 飙到 ~77%**
  - 原因: 这批刚好碰到「90_19 / 90_20 等精灵卡角色介绍页」
  - R1 自作主张加 `<c1d:N/>` 控制码（jp 没有的），且把多 page 合成 1 page
- **system prompt 加严**:
  - "不增不减控制码：jp 里有几个 `<...>` 标签，zh 里完全一样多"
  - "Pages 数量守恒：N 个输入 page → N 个输出 page"
- **继续跑到完结**

### 第二轮持续时间
约 **7-8 小时**

### 最终统计
- **干净翻译 (good)**: 9,774 条 (93.2%)
- **needs_review (bad)**: 708 条 (6.7%)
- **FAILED (整批崩)**: 30 个 batch × 30 = ~900 条 (8.6%)
- **总 batch 数**: 351 成功 + 30 失败 = 381

### Token & 成本（Azure portal 数据）
- **请求总数**: ~870 次（含 retry）
- **总 token**: 约 1000 万
  - 输入: ~410 万
  - 输出: ~590 万
- **Azure 实际计费**: ~CA$10-15
- **应付款项**: CA$0（用免费额度抵扣）
- **剩余额度**: CA$273.81 → CA$258 左右

---

## 第三轮 / 收尾轮（2026-05-26 下午）

### 配置
- `BATCH_SIZE = 15`（砍半，降低单 batch token 压力）
- `max_tokens = 16000`（翻倍，避免输出截断）
- system prompt 不变（已加严）

### 目标
- 自动捡起 FAILED 的 ~900 条
- 自动捡起 needs_review 的 ~700 条（merge.py 跳过未合）
- 合计约 **1600 条**

### 预计耗时
~ **2-2.5 小时**

### 预期结果
- FAILED rate < 1%（基本能全救回来）
- 整体 good rate 提升到 ~98%

---

## 经验教训

1. **`max_tokens=8000` 对 R1 + 30 batch 不够**
   - R1 的 reasoning tokens 本身占大头
   - 一旦碰到角色介绍/解谜类长 entry，输出被截断
   - **建议默认配 `max_tokens=16000 + BATCH_SIZE=20`**

2. **system prompt 必须明示"不增不减"**
   - 不能只给"控制码原样保留"——R1 会加它见过的标签
   - 必须强调"jp 没有的，zh 也不能有"

3. **断点续传至关重要**
   - 第一轮崩了不丢数据
   - load_done_ids 只看 partials 里的 translations 字段，bad/FAILED 自动会被下次拾起

4. **R1 的输出格式偶尔抽风**
   - 会包 `<think>...</think>`、` ```json ` fences
   - `clean_r1_output` 函数必须有

5. **Azure DeepSeek-R1 的费用**
   - 不是纯免费（之前以为是），但极便宜
   - 10M token 约 ~CA$15 左右
   - CA$273 免费额度足够整套 script + strtbl + battle 全跑完

6. **bad 不全是 R1 不好**
   - 很多是「多/少 1 个 `<SURNAME/>`」对齐空格类问题
   - 翻译文本本身正确，只是控制码计数微差
   - autofix 脚本可以自动修一大批

---

## 下一步（待跑完第三轮后）

- [ ] merge 第三轮的 good
- [ ] 写 autofix.py 处理 needs_review 里"差 1-2 个 SURNAME"的常见 case
- [ ] 剩余真需人工审的 ~100-200 条人工过
- [ ] build.py 出新 ISO
- [ ] strtbl 管道建设 + LLM 翻
- [ ] battle parser 修复 + LLM 翻
- [ ] 网站 MVP + B 站视频
