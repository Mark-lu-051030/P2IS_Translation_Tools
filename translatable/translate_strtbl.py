"""P2IS strtbl（UI 字符串）批量翻译。基于 translate.py 改。

只翻玩家可见的 UI strtbl（白名单 file），跳过 debug/资源 ID 类。

白名单 file:
  0, 1     战斗菜单（SLPS）
  46       角色名
  47       魔法相性说明
  64-72    UI 提示（选择/库存/购买/传闻）
  84       角色对话/名字

排除（不可翻，会破坏游戏）:
  138 FMV列表 / 160,163 BGM文件名 / 166 事件注释 / 176 动作姿势注释 / 180 特效注释

用法:
  python3 translate_strtbl.py            # 跑全部白名单
  python3 translate_strtbl.py --limit 50
  python3 translate_strtbl.py --file 64  # 只翻某 file
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

SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT = SCRIPT_DIR.parent
SOURCE = ROOT / "all_translatable.json"
PARTIALS_DIR = SCRIPT_DIR / "partials_strtbl"
PARTIALS_DIR.mkdir(exist_ok=True)

AZURE_ENDPOINT = "https://marklu-8057-resource.services.ai.azure.com/"
MODEL_DEPLOYMENT = "DeepSeek-R1-0528"
API_VERSION = "2024-12-01-preview"

BATCH_SIZE = 25   # strtbl 短，batch 可大些
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

# 黑名单 file（确定的内部数据，翻了会破坏游戏或玩家看不到）：
#   160/163 BGM/SE 文件名（翻了游戏找不到音频资源）
#   176     动作姿势 debug 注释（10701 条，玩家看不到）
#   166     时计台事件注释 / 180 特效注释
# 黑名单外、含日文的条目都翻（地点名、菜单、提示、技能说明、小游戏名等玩家可见 UI）
BLACKLIST_FILES = {'160', '163', '176', '166', '180'}

SYSTEM_PROMPT = """你是日本游戏《女神异闻录 2 罪》（Persona 2: Innocent Sin, PS1）的简体中文汉化译者。
现在翻译的是**游戏 UI 字符串**（菜单项、系统提示、技能说明、角色名等短文本），不是对话剧情。

# 一、角色姓名（强制锁定）
- 周防 達哉→周防 达哉 / 黛 純→黛 纯 / 倉成 麗美・リサ→丽莎 / 三科 栄吉→三科 荣吉
- ミッシェル→米切 / 天野 マヤ→天野 麻耶 / 黛 ユキノ→黛 雪乃 / 須藤 達也→须藤 达也
- 華小路 雅→华小路 雅 / 反谷 孝志→反谷 孝志 / ハンニャ校長→般若校长 / 冴子先生→冴子老师
- 南条 圭→南条 圭 / 城戸 玲司→城户 玲司

# 二、系统词（强制锁定）
- ペルソナ→Persona（保留英文） / シャドウ→影子 / 噂→传闻 / 仮面党→假面党
- 攻撃→攻击 / 防御→防御 / 魔法→魔法 / アイテム→道具 / セーブ→保存 / ロード→读取
- ステータス→状态 / コンフィグ→设置 / アナライズ→分析 / 装備→装备 / 逃走/退却→逃跑

# 三、控制码（铁律）
**不增不减、原顺序原位置**：JP 里有几个 `<...>` 标签，ZH 里就完全一样多、一样的种类、一样的位置。
常见：`<pause:N/>` `<c1e:N/>` `<c1c:N/>` `<c1f/>` `<NAME/>` `<SURNAME/>`。
特别注意：`<c1e:0/>` 这类**必须原样保留**，它是 UI 格式控制码。

# 四、长度限制（重要）
UI 字符串显示空间有限，**中文字符数 ≤ 日文字符数**，尽量更短。菜单项力求精炼（2-4 字最佳）。

# 五、原则
1. 菜单项/按钮：用游戏界面惯用简短译法（如 戦闘開始→战斗开始，行動設定→行动设定）。
2. 系统提示句：自然简洁。
3. 纯符号/数字/英文 ID（如 "NULL"、"[?3223]"、"123456"）→ 原样返回，不翻译。
4. `\\n` 保留。
5. 看不懂或像内部 debug 的（含大量英文路径、文件名）→ 原样返回 jp。

# 六、输出格式（严格 JSON，不要 markdown，不要解释）
{
  "translations": [
    {"id": "strtbl:0_0_0:0", "zh": "战斗开始"},
    {"id": "strtbl:64_0_0:0", "zh": "方向键左右选择数量 ○键确定"}
  ]
}
- 每条对应一个 id，zh 是翻译后文本（含保留的控制码）。
"""


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


def load_untranslated(file_filter=None):
    data = json.loads(SOURCE.read_text(encoding="utf-8"))
    out = []
    for e in data:
        if not e["id"].startswith("strtbl:"):
            continue
        fid = e["id"].split(":")[1].split("_")[0]
        if fid in BLACKLIST_FILES:
            continue
        if file_filter and fid != file_filter:
            continue
        pages = e.get("pages", [])
        if not pages:
            continue
        jp = pages[0].get("jp", "").strip()
        if not jp:
            continue
        if pages[0].get("zh", "").strip():
            continue  # 已翻译
        if not _is_translatable(jp):
            continue  # 纯 ASCII/符号/数字模板 — 游戏 code 引用，不翻
        out.append({"id": e["id"], "jp": jp})
    return out


def _is_translatable(jp):
    """判断是否该翻译。纯 ASCII/符号/数字（UI 模板、占位符、ID）不翻，保留原文。
    例：'0123456789' 'LV' 'ON' 'OFF' 'EXIT' 'RESERVE' ':' '/' 'B' 等。
    只要含至少一个日文假名/汉字才翻。"""
    clean = TAG_RE.sub("", jp).replace("\n", "").strip()
    if not clean:
        return False
    # 含日文假名 (ぁ-ヿ) 或 CJK 汉字 (一-鿿) 才翻
    for ch in clean:
        if "぀" <= ch <= "ヿ" or "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿":
            return True
    return False


def load_done_ids():
    done = set()
    for f in PARTIALS_DIR.glob("*.json"):
        try:
            batch = json.loads(f.read_text(encoding="utf-8"))
            for t in batch.get("translations", []):
                done.add(t["id"])
        except Exception:
            pass
    return done


def clean_r1_output(text):
    if "</think>" in text:
        text = text.split("</think>", 1)[-1]
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


TAG_RE = re.compile(r"<[^>]+>")


def control_codes_match(jp, zh):
    return sorted(TAG_RE.findall(jp)) == sorted(TAG_RE.findall(zh))


def translate_batch(client, entries):
    user_msg = "请翻译以下 {} 条 UI 字符串。\n\n{}".format(
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
                max_tokens=16000,
            )
            raw = completion.choices[0].message.content or ""
            return json.loads(clean_r1_output(raw))
        except json.JSONDecodeError as e:
            print(f"  [尝试 {attempt}] JSON 解析失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            else:
                debug_path = PARTIALS_DIR / f"FAILED_{entries[0]['id'].replace(':', '_')}.txt"
                debug_path.write_text(raw, encoding="utf-8")
                print(f"  ✗ 最终失败，原始返回存到 {debug_path}", file=sys.stderr)
                return {"translations": []}
        except Exception as e:
            print(f"  [尝试 {attempt}] API 调用失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
            else:
                return {"translations": []}


def validate_and_save(batch_input, result):
    input_by_id = {e["id"]: e for e in batch_input}
    good, bad = [], []
    for tr in result.get("translations", []):
        eid = tr.get("id")
        if eid not in input_by_id:
            bad.append({**tr, "_issue": "未知 id"})
            continue
        jp = input_by_id[eid]["jp"]
        zh = tr.get("zh", "")
        if not control_codes_match(jp, zh):
            bad.append({
                **tr,
                "_issue": f"控制码不匹配 jp={sorted(TAG_RE.findall(jp))} zh={sorted(TAG_RE.findall(zh))}"
            })
        else:
            good.append(tr)

    if good or bad:
        first_id = batch_input[0]["id"].replace(":", "_").replace("/", "_")
        out = {"translations": good, "needs_review": bad}
        (PARTIALS_DIR / f"{first_id}.json").write_text(
            json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return len(good), len(bad)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--file")
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    print(f"读取 {SOURCE}（黑名单 file: {sorted(BLACKLIST_FILES, key=lambda x:int(x))}，其余含日文都翻）...")
    all_entries = load_untranslated(file_filter=args.file)
    print(f"  白名单可翻译条目: {len(all_entries)}")

    done = load_done_ids()
    print(f"  已完成: {len(done)}")
    entries = [e for e in all_entries if e["id"] not in done]
    if args.limit:
        entries = entries[: args.limit]
    print(f"  本次要翻: {len(entries)}\n")
    if not entries:
        print("没有待翻译条目，退出。")
        return

    client = make_client()
    total_good = total_bad = 0
    pbar = tqdm(range(0, len(entries), args.batch_size), desc="批次", unit="batch")
    for i in pbar:
        batch = entries[i : i + args.batch_size]
        result = translate_batch(client, batch)
        good, bad = validate_and_save(batch, result)
        total_good += good
        total_bad += bad
        pbar.set_postfix({"good": total_good, "bad": total_bad})

    print(f"\n完成。✓ {total_good} 条干净 / ⚠ {total_bad} 条需审查")
    print(f"partials 存在 {PARTIALS_DIR.name}/，跑 merge_strtbl.py 合回 all_translatable.json")


if __name__ == "__main__":
    main()
