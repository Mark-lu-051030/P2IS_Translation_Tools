"""通用 free-region UI 表批量翻译（配合 ../freetbl.py，读 ../out/<table>_zh.json）。

复用 DeepSeek-R1 客户端。这些表带 <XXXX> 格式码（占位/段落控制），
**必须原样保留、不增不减、原位置**。原位等长 → 每条中文字数 ≤ max。
直接写回 <table>_zh.json，分批 checkpoint，可断点续跑。

用法:
  python3 translate_freetbl.py contactui      # 交涉/战斗UI
  python3 translate_freetbl.py config         # 设置菜单
  python3 translate_freetbl.py config --limit 20
"""
import argparse, json, re, sys, time
from pathlib import Path

from openai import AzureOpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT = SCRIPT_DIR.parent

AZURE_ENDPOINT = "https://marklu-8057-resource.services.ai.azure.com/"
MODEL_DEPLOYMENT = "DeepSeek-R1-0528"
API_VERSION = "2024-12-01-preview"
BATCH_SIZE = 25
MAX_RETRIES = 3
TAG_RE = re.compile(r"<[0-9a-fA-F]{4}>")

SYSTEM_PROMPT = """你是日本游戏《女神异闻录 2 罪》（Persona 2: Innocent Sin, PS1）的简体中文汉化译者。
现在翻译的是游戏 **UI 字符串表**：菜单项、按钮、系统提示、说明文。

# 一、内容类型（按表而定，下面都可能出现）
- 交涉动作名：説得する→说服 / 漢を語る→谈论男人 / 踊る→跳舞 / カンフー→功夫 / 甘える→撒娇 等，简短动词短语。
- 战斗 UI：コンタクト→交涉 / 決定→确定 / 悪魔名→恶魔名 / 所持金→持有金 / 経験値→经验值 等。
- 队友关系状态：恋人!?→恋人!? / なんとなくいい感じ→感觉还不错 / お互い、ちょっと気になる感じ→彼此有点在意。
- 设置菜单：サウンド→声音 / 振動→振动 / マップ回転方向→地图旋转方向 / カーソル位置の記憶→记忆光标位置
  / 壁紙設定→壁纸设置 / ステレオ→立体声 / モノラル→单声道 / リアル→真实 / シンプル→简化 / EXIT→退出。
- 说明文（一句或多句）：自然简洁的中文。如「○ボタンで切り替え、×ボタンで終了します」→「○键切换，×键退出」。

# 二、格式码（铁律）
jp 里的 `<XXXX>`（如 <1103> <120e> <1106> <1205> <121d>）是格式/占位控制码，
**zh 里必须原样保留：一样的个数、一样的种类、一样的相对位置（在文字前就在前，在后就在后）**。
绝对不要新增、删除、改写这些 <XXXX> 标签。

# 三、长度（铁律）
每条给了 max（最大中文字符数，不含 <XXXX> 标签）。**zh 文字字符数 ≤ max**，超了会被丢弃。力求精炼。

# 四、原则
1. 纯英文/数字/符号（LV、:、数字）→ 原样返回。
2. Persona→Persona 保留英文；角色名锁定（达哉/麻耶/纯/雪乃/荣吉/丽莎/银子）。
3. 看不懂或像内部 debug 的 → 原样返回 jp（含其 <XXXX>）。

# 五、输出（严格 JSON，无 markdown 无解释）
{"translations": [{"id": 506, "zh": "<1103>说服"}, {"id": 818, "zh": "恶魔名         <120e>「"}]}
- id 用每条给的整数 id；zh 含保留的 <XXXX> 标签。
"""


def make_client():
    tp = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    return AzureOpenAI(azure_endpoint=AZURE_ENDPOINT, azure_ad_token_provider=tp,
                       api_version=API_VERSION)


def clean_r1(text):
    if "</think>" in text:
        text = text.split("</think>", 1)[-1]
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def translate_batch(client, entries):
    msg = "翻译以下 {} 条（保留所有 <XXXX> 标签，注意 max 字数）。\n\n{}".format(
        len(entries), json.dumps({"entries": entries}, ensure_ascii=False))
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            r = client.chat.completions.create(
                model=MODEL_DEPLOYMENT,
                messages=[{"role": "system", "content": SYSTEM_PROMPT},
                          {"role": "user", "content": msg}],
                temperature=0.3, max_tokens=16000)
            return json.loads(clean_r1(r.choices[0].message.content or ""))
        except Exception as e:
            print(f"  [尝试 {attempt}] 失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES:
                time.sleep(5 * attempt)
    return {"translations": []}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("table", help="freetbl 表名，如 contactui / config")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = ap.parse_args()

    SRC = ROOT / "out" / f"{args.table}_zh.json"
    if not SRC.exists():
        print(f"✗ {SRC} 不存在，先跑 python3 ../freetbl.py {args.table} extract")
        sys.exit(1)
    data = json.loads(SRC.read_text(encoding="utf-8"))
    by_off = {e["off"]: e for e in data}
    todo = [e for e in data if not (e.get("zh") or "").strip()]
    if args.limit:
        todo = todo[:args.limit]
    print(f"待翻 {len(todo)} 条（共 {len(data)}）")
    if not todo:
        return

    client = make_client()
    done = bad = 0
    for i in tqdm(range(0, len(todo), args.batch_size)):
        chunk = todo[i:i + args.batch_size]
        entries = [{"id": e["off"], "jp": e["jp"], "max": e["blen"] // 2 - 1} for e in chunk]
        res = translate_batch(client, entries)
        for tr in res.get("translations", []):
            e = by_off.get(tr.get("id"))
            if not e:
                continue
            zh = (tr.get("zh") or "").strip()
            # 校验格式码一致
            if sorted(TAG_RE.findall(zh)) != sorted(TAG_RE.findall(e["jp"])):
                e["_tag_mismatch"] = True; bad += 1
            e["zh"] = zh; done += 1
        SRC.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"✅ 翻 {done} 条（{bad} 条格式码不匹配需复查 _tag_mismatch）→ {SRC.name}")
    print("   下一步: python3 ../build.py")


if __name__ == "__main__":
    main()
