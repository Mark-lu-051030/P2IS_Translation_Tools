"""道具/Persona/技能/恶魔名 主表批量翻译（读 ../out/nametable_zh.json）。

复用 translate_strtbl.py 的 Azure DeepSeek-R1 客户端。名表特殊点：
  1. 原位等长替换 → 每条中文字数必须 ≤ max（= blen//2-1），逐条传给 LLM。
  2. 锁定 Persona/角色/神话名，与对话翻译保持一致。
  3. 直接写回 nametable_zh.json（按 off 定位），分批 checkpoint，可断点续跑。

用法:
  python3 translate_nametable.py            # 翻全部未翻条目
  python3 translate_nametable.py --limit 100
"""
import argparse, json, re, sys, time
from pathlib import Path

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT = SCRIPT_DIR.parent
NAMETABLE = ROOT / "out" / "nametable_zh.json"

AZURE_ENDPOINT = "https://marklu-8057-resource.services.ai.azure.com/"
MODEL_DEPLOYMENT = "DeepSeek-R1-0528"
API_VERSION = "2024-12-01-preview"
BATCH_SIZE = 30
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 5

SYSTEM_PROMPT = """你是日本游戏《女神异闻录 2 罪》（Persona 2: Innocent Sin, PS1）的简体中文汉化译者。
现在翻译的是**名称表**：道具名、技能名、Persona/恶魔名、防具名等短名词。

# 一、Persona/恶魔/神话名（音译，用通行中文译名）
- 神话名用通行译法：アポロ→阿波罗 / ツクヨミ→月读 / アルテミス→阿尔忒弥斯 / アーサー→亚瑟
  / サラスヴァティ→辩才天 / バッカス→巴克斯 / ダグダ→达格达 / クー・フーリン→库丘林
  / ヴォルカヌス→伏尔甘 / エビス→惠比寿 / フクロクジュ→福禄寿
- 「・改」后缀 = 改造版，译作「·改」保留。

# 二、角色名（强制锁定，与对话一致）
- 周防 達哉→周防 达哉 / 黛 純→黛 纯 / リサ→丽莎 / 三科 栄吉→三科 荣吉 / ミッシェル→米切
  / 天野 マヤ→天野 麻耶 / ユキノ→雪乃 / ジュン→纯

# 三、道具/技能名
- 用游戏惯用译法，意译为主、简洁。如 傷薬→伤药 / 仙桃→仙桃 / 反魂香→反魂香 / メギド→玛达。
- 片假名外来道具名酌情意译或音译（ガラガラドリンク→哗啦啦饮料 之类）。

# 四、长度硬限制（铁律）
每条给了 max（最大中文字符数）。**zh 的字符数必须 ≤ max**，超了会被丢弃。名字尽量短。

# 五、原则
1. 纯符号/数字/英文/ID（如 "R"、"SS"、"CHARIOT"）→ 原样返回。
2. 看不懂或像内部 debug 的 → 原样返回 jp。
3. 不要加任何控制码或 `<...>` 标签。

# 六、输出格式（严格 JSON，无 markdown 无解释）
{"translations": [{"id": 586, "zh": "伤药"}, {"id": 594, "zh": "四次元橡皮"}]}
- id 用每条给的 id（整数），zh 是译名。
"""


def make_client():
    tp = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(azure_endpoint=AZURE_ENDPOINT, azure_ad_token_provider=tp,
                       api_version=API_VERSION)


def clean_r1_output(text):
    if "</think>" in text:
        text = text.split("</think>", 1)[-1]
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def translate_batch(client, entries):
    user_msg = "请翻译以下 {} 条名称（注意每条 max 字数上限）。\n\n{}".format(
        len(entries), json.dumps({"entries": entries}, ensure_ascii=False))
    for attempt in range(1, MAX_RETRIES + 1):
        raw = ""
        try:
            completion = client.chat.completions.create(
                model=MODEL_DEPLOYMENT,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": user_msg}],
                temperature=0.3, max_tokens=16000)
            raw = completion.choices[0].message.content or ""
            return json.loads(clean_r1_output(raw))
        except Exception as e:
            print(f"  [尝试 {attempt}] 失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    return {"translations": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    data = json.loads(NAMETABLE.read_text(encoding="utf-8"))
    by_off = {e["off"]: e for e in data}
    todo = [e for e in data if not e.get("skip") and not (e.get("zh") or "").strip()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"待翻 {len(todo)} 条（共 {len(data)}，已跳过 skip）")
    if not todo:
        return

    client = make_client()
    done = toolong = 0
    for i in tqdm(range(0, len(todo), args.batch_size)):
        chunk = todo[i:i + args.batch_size]
        entries = [{"id": e["off"], "jp": e["jp"], "max": e["blen"] // 2 - 1} for e in chunk]
        res = translate_batch(client, entries)
        for tr in res.get("translations", []):
            e = by_off.get(tr.get("id"))
            if not e:
                continue
            zh = (tr.get("zh") or "").strip()
            cap = e["blen"] // 2 - 1
            if len(zh) > cap:
                e["_toolong"] = True; toolong += 1
            e["zh"] = zh; done += 1
        # 每批 checkpoint 写回，可断点续跑
        NAMETABLE.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 翻 {done} 条（{toolong} 条超长需缩短），已写回 {NAMETABLE.name}")
    print("   下一步: python3 ../build.py（inject 自动扫名表新字 + nametable apply 原位写回）")


if __name__ == "__main__":
    main()
