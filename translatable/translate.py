"""P2IS 批量翻译脚本（Azure DeepSeek-R1）。

工作流：
  1. 读 ../all_translatable.json，抽 script: 开头、zh 空的条目
  2. 切 batch，每批 30 条
  3. 调 DeepSeek-R1 翻译
  4. 验证控制码守恒（不一致就标 needs_review）
  5. 每批结果存到 partials/<first_id>.json（断点续传）
  6. 跑完手动跑 merge.py 合回 all_translatable.json

用法:
  python3 translate.py                # 跑全部
  python3 translate.py --limit 50     # 只跑前 50 条（调试）
  python3 translate.py --file 185_8   # 只翻某个 file_sub
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from tqdm import tqdm

# ── 配置 ─────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT = SCRIPT_DIR.parent
SOURCE = ROOT / "all_translatable.json"
PARTIALS_DIR = SCRIPT_DIR / "partials"
PARTIALS_DIR.mkdir(exist_ok=True)

AZURE_ENDPOINT = "https://marklu-8057-resource.services.ai.azure.com/"
MODEL_DEPLOYMENT = "DeepSeek-R1-0528"
API_VERSION = "2024-12-01-preview"

BATCH_SIZE = 15   # 第二轮：从 30 砍半，单 batch token 压力小
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

# ── System Prompt ───────────────────────────────────────────
SYSTEM_PROMPT = """你是日本游戏《女神异闻录 2 罪》（Persona 2: Innocent Sin, PS1）的简体中文汉化译者。

# 一、角色姓名（强制锁定）
- 周防 達哉 → 周防 达哉（主角）
- 黛 純 → 黛 纯
- 倉成 麗美 / リサ → 丽莎（昵称，常用）
- 三科 栄吉 → 三科 荣吉
- ミッシェル → 米切（荣吉自封艺名）
- 死神番長 → 死神番长
- ケン / シヨーゴ / タケシ → 健 / 昭吾 / 武
- 天野 マヤ → 天野 麻耶
- 黛 ユキノ → 黛 雪乃
- 須藤 達也 → 须藤 达也
- 華小路 雅 → 华小路 雅
- ハナジー → 花姐
- 反谷 孝志 → 反谷 孝志（校长本名）
- ハンニャ / ハンニャ校長 → 般若 / 般若校长（绰号）
- 冴子先生 / 中島 冴子 → 冴子老师 / 中岛 冴子
- 南条 圭 → 南条 圭
- 城戸 玲司 → 城户 玲司

# 二、场所
- 七姉妹学園 → 七姊妹学园
- エルミン学園 → 艾尔敏学园
- 春日山高校 → 春日山高中（蔑称 カス校 → 渣校）
- 副都心、鳴海荘 → 副都心、鸣海庄

# 三、系统词
- ペルソナ → Persona（保留英文）
- ペルソナ使い → Persona 使者
- シャドウ → 影子
- 噂 → 传闻
- 紋章の呪い → 纹章诅咒
- ジョーカー / ジヨーカー → 小丑
- 仮面党 → 假面党
- 影人間 → 影子人

# 四、控制码（铁律）
**两条不可破的规则**：

1. **不增不减**：JP 里有几个 `<...>` 标签，ZH 里就**完全一样多、完全一样的种类**。
   - 错误示范：JP 只有 `<SURNAME/>`，ZH 加了 `<c1d:11/>`、`<c1d:1/>` → **绝对禁止**！
   - 不要"模仿"其他翻译里见过的标签——只看当前 entry 的 JP 用了哪些。

2. **原顺序原位置**：每个 `<...>` 在 ZH 里的位置要对应 JP 里的位置。

涉及的标签：`<SURNAME/>` `<NAME/>` `<c12/>` `<c13/>` `<c02/>` `<pause:N/>` `<c1d:N/>` `<c10:N/>` `<c11:N/>` `<option:N/>` `<option_end/>` `<keyitem:N/>`，以及任何其他 `<...>` 都同样保留不增减。

# 四 bis、Pages 数量守恒（铁律）
输入 entry 的 `pages` 有 N 项，输出 `pages_zh` 就**必须**有 N 项。
- JP 输入有 3 个 page → ZH `pages_zh` 数组**必须**有 3 个元素，每个对应翻一页，**绝不合并**。
- 即使三页内容看起来连贯（诗、角色介绍等），也要**保持分页**，每页独立翻译。

# 五、风格
- 主角：沉默冷静，少话。
- 不良/小混混：粗野，可用"老子/搞屁/臭小子"。
- 混混跟班：油腻拖音"～"。
- 般若校长：威严古板方言味，"岂有此理！"
- Persona 觉醒之声：古风庄严，"吾即汝、汝即吾"。
- 绷带学生：自嘲幽默。
- 路人学生：自然口语。
- 荣吉（番长）：自恋洋泾浜，可用"老子/Baby/Okay~"，怪叫如"木哦哦哦"。

# 六、原则
1. 意译 > 直译，自然中文。
2. JP 没有的粗口别加。
3. 中文字符数 ≤ 日文字符数 × 1.1，精炼。
4. 原文 `\\n` 在 ZH 里也保留 `\\n`。

# 七、输出格式（严格 JSON，不要 markdown，不要解释）
返回纯 JSON 对象：
{
  "translations": [
    {
      "id": "script:181_8:diag0",
      "meta_zh": "???",
      "pages_zh": ["\\n<SURNAME/>………？"]
    }
  ],
  "new_terms": []
}

- `pages_zh` 是数组，与输入 `pages` 一一对应。
- 输入有 meta_jp 才输出 meta_zh，否则省略 meta_zh 字段（或空串）。
- new_terms：遇到术语表外的新角色/地名就列出，无则 []。
"""


# ── Azure 客户端 ────────────────────────────────────────────
def make_client():
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(),
        "https://cognitiveservices.azure.com/.default",
    )
    return AzureOpenAI(
        azure_endpoint=AZURE_ENDPOINT,
        azure_ad_token_provider=token_provider,
        api_version=API_VERSION,
    )


# ── 数据加载 ────────────────────────────────────────────────
def load_untranslated(file_filter=None):
    """从 all_translatable.json 加载待翻译条目。

    file_filter: e.g. "185_8" 只翻这个 file_sub
    """
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    out = []
    for e in data:
        if not e["id"].startswith("script:"):
            continue  # 暂不处理 strtbl / battle
        if file_filter and not e["id"].startswith(f"script:{file_filter}:"):
            continue

        # 判断是否需要翻译
        needs_pages = any(
            not p.get("zh", "").strip() for p in e.get("pages", [])
        )
        needs_meta = (
            "meta_jp" in e
            and e["meta_jp"].strip()
            and not e.get("meta_zh", "").strip()
        )
        if not (needs_pages or needs_meta):
            continue

        # 构造给 LLM 的精简结构
        item = {"id": e["id"]}
        if "meta_jp" in e and e["meta_jp"].strip():
            item["meta_jp"] = e["meta_jp"]
        item["pages"] = [{"jp": p["jp"]} for p in e.get("pages", [])]
        out.append(item)
    return out


def load_done_ids():
    """扫 partials/ 收集已完成的 id（断点续传）。"""
    done = set()
    for f in PARTIALS_DIR.glob("*.json"):
        try:
            batch = json.loads(f.read_text(encoding="utf-8"))
            for t in batch.get("translations", []):
                done.add(t["id"])
        except Exception:
            pass
    return done


# ── R1 输出清洗 ─────────────────────────────────────────────
def clean_r1_output(text):
    """R1 偶尔包 <think>...</think> 和 ```json fences。"""
    if "</think>" in text:
        text = text.split("</think>", 1)[-1]
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


# ── 控制码验证 ──────────────────────────────────────────────
TAG_RE = re.compile(r"<[^>]+>")


def control_codes_match(jp, zh):
    """检查 zh 是否保留了 jp 里所有控制码（数量+种类）。"""
    return sorted(TAG_RE.findall(jp)) == sorted(TAG_RE.findall(zh))


# ── 翻译一批 ────────────────────────────────────────────────
def translate_batch(client, entries):
    """调 API 翻译一批 entries，返回 parsed JSON 字典。"""
    user_msg = "请翻译以下 {} 条对话。\n\n{}".format(
        len(entries),
        json.dumps({"entries": entries}, ensure_ascii=False, indent=2),
    )

    for attempt in range(1, MAX_RETRIES + 1):
        raw = ""
        try:
            completion = client.chat.completions.create(
                model=MODEL_DEPLOYMENT,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
                max_tokens=16000,   # 第二轮：翻倍，避免 R1 思考长输出被截断
            )
            raw = completion.choices[0].message.content or ""
            cleaned = clean_r1_output(raw)
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            print(f"  [尝试 {attempt}] JSON 解析失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            else:
                debug_path = PARTIALS_DIR / f"FAILED_{entries[0]['id'].replace(':', '_')}.txt"
                debug_path.write_text(raw, encoding="utf-8")
                print(f"  ✗ 最终失败，原始返回存到 {debug_path}", file=sys.stderr)
                return {"translations": [], "new_terms": []}
        except Exception as e:
            print(f"  [尝试 {attempt}] API 调用失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            else:
                return {"translations": [], "new_terms": []}


# ── 验证 + 保存 ─────────────────────────────────────────────
def validate_and_save(batch_input, result):
    """验证翻译结果，返回 (good_count, bad_count)。"""
    input_by_id = {e["id"]: e for e in batch_input}
    good, bad = [], []

    for tr in result.get("translations", []):
        eid = tr.get("id")
        if eid not in input_by_id:
            bad.append({**tr, "_issue": "未知 id"})
            continue
        original = input_by_id[eid]
        issues = []

        # 检查 pages_zh 数量
        if len(tr.get("pages_zh", [])) != len(original["pages"]):
            issues.append(
                f"pages 数量不匹配: jp={len(original['pages'])}, zh={len(tr.get('pages_zh', []))}"
            )

        # 检查每页控制码守恒
        for i, (orig_page, zh_text) in enumerate(
            zip(original["pages"], tr.get("pages_zh", []))
        ):
            if not control_codes_match(orig_page["jp"], zh_text):
                jp_tags = sorted(TAG_RE.findall(orig_page["jp"]))
                zh_tags = sorted(TAG_RE.findall(zh_text))
                issues.append(
                    f"page{i} 控制码不匹配: jp={jp_tags}, zh={zh_tags}"
                )

        if issues:
            bad.append({**tr, "_issues": issues})
        else:
            good.append(tr)

    # 保存
    if good or bad:
        first_id = batch_input[0]["id"].replace(":", "_").replace("/", "_")
        out = {
            "translations": good,
            "needs_review": bad,
            "new_terms": result.get("new_terms", []),
        }
        (PARTIALS_DIR / f"{first_id}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return len(good), len(bad)


# ── 主函数 ──────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, help="只跑前 N 条（调试用）")
    ap.add_argument("--file", help="只翻指定 file_sub，如 185_8")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    print(f"读取 {SOURCE}...")
    all_entries = load_untranslated(file_filter=args.file)
    print(f"  未翻译条目: {len(all_entries)}")

    done = load_done_ids()
    print(f"  已完成 ({PARTIALS_DIR.name}/): {len(done)}")

    entries = [e for e in all_entries if e["id"] not in done]
    if args.limit:
        entries = entries[: args.limit]
    print(f"  本次要翻: {len(entries)}\n")

    if not entries:
        print("没有待翻译条目，退出。")
        return

    client = make_client()
    batch_size = args.batch_size

    total_good = 0
    total_bad = 0
    new_terms_all = set()

    pbar = tqdm(range(0, len(entries), batch_size), desc="批次", unit="batch")
    for i in pbar:
        batch = entries[i : i + batch_size]
        result = translate_batch(client, batch)
        good, bad = validate_and_save(batch, result)
        total_good += good
        total_bad += bad
        for term in result.get("new_terms", []):
            # R1 有时返回 dict 而不是字符串，统一转字符串
            if isinstance(term, dict):
                term = json.dumps(term, ensure_ascii=False)
            new_terms_all.add(str(term))
        pbar.set_postfix({"good": total_good, "bad": total_bad})

    print(f"\n完成。✓ {total_good} 条干净 / ⚠ {total_bad} 条需审查")
    if new_terms_all:
        print(f"\n新术语（请补入 glossary.md）:")
        for t in sorted(new_terms_all):
            print(f"  - {t}")


if __name__ == "__main__":
    main()
