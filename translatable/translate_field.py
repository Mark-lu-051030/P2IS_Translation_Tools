"""字段文本批量翻译（Azure DeepSeek-R1）——翻 out/field_text_clean.json 的唯一 jp。

这些是主管道漏掉的文本：外景/事件对话(file 1075)、装备说明(64-67)、传闻/简介(84/163)等，
格式统一为「日文字符 + <cXX/> 控制码标签 + \\n」。复用 translate.py 的客户端/清洗/角色名。

工作流：
  1. 读 ../out/field_text_clean.json → 取唯一 jp（同一 jp 只翻一次）
  2. 切 batch(20)，调 DeepSeek-R1，严格保留 <...> 标签
  3. 每批存 partials_field/<idx>.json（断点续传）
  4. 跑完自动合出 ../out/field_text_zh.json（同 jp 的所有出现位置都填上 zh）

用法:
  python3 translate_field.py                # 跑全部
  python3 translate_field.py --limit 40     # 只跑前 40 条（先验证质量/成本）
  python3 translate_field.py --merge        # 仅合并 partials → field_text_zh.json
"""
import argparse, json, re, sys, time
from pathlib import Path
from tqdm import tqdm

# 复用 translate.py 的客户端、R1 输出清洗、模型常量（避免重复维护）
from translate import make_client, clean_r1_output, MODEL_DEPLOYMENT

SCRIPT_DIR = Path(__file__).parent.resolve()
ROOT = SCRIPT_DIR.parent
TODO_FILE = ROOT / "out" / "field_to_translate.json"   # 唯一 jp 汇总（翻译输入）
CLEAN_FILE = ROOT / "out" / "field_text_clean.json"    # 全部出现位置（合并/回插用）
OUT_ZH = ROOT / "out" / "field_text_zh.json"
PARTIALS = SCRIPT_DIR / "partials_field"
PARTIALS.mkdir(exist_ok=True)
BATCH_SIZE = 20
MAX_RETRIES = 3
RETRY_BACKOFF = 5
TAG_RE = re.compile(r"<[^>]+>")

SYSTEM_PROMPT = """你是日本游戏《女神异闻录 2 罪》(Persona 2: Innocent Sin, PS1) 的简体中文汉化译者。
现在翻译的是**游戏内字段文本**：外景 NPC/事件对话、交涉选项、装备说明、传闻情报、人物简介等。

# 一、角色姓名（强制锁定，与已汉化正文一致——以下为准，不得自行改读音）
周防 達哉→周防 达哉(主角 Tatsuya) / 天野 舞耶·マヤ→天野 **舞耶**（⚠保持汉字"舞耶"，绝不要改成"麻耶"！）/
黛 純·ジュン→黛 纯 / 倉成 麗美·リサ→丽莎 / 三科 栄吉→三科 荣吉 / ミッシェル→米切 /
黛 ユキノ→黛 雪乃 / 須藤 達也→须藤 达也(反派,达"也"不是达"哉") / 華小路 雅→华小路 雅 /
ケン·シヨーゴ·タケシ→健·昭吾·武 / 死神番長→死神番长 / ハンニャ→般若

# 一bis、地名（强制锁定，与已汉化菜单/地图一致）
七姉妹学園→七姐妹学园 / 春日山高校→春日山高中(日「高校」=高中) / シバルバー→希巴尔巴 /
カラコル→卡拉科尔 / スマイル平坂→微笑平坂 / ムー大陸→穆大陆 / ゾディアック→黄道宫 /
廃工場→废工厂 / 駐輪場→停车场 / 階段→楼梯 / 空の科学館→天空科学馆 / 野外音楽堂→露天音乐厅 /
区名照搬: 平坂区/港南区/夢崎区→平坂区/港南区/梦崎区

# 二、控制码标签（铁律，最重要）
文本里的 `<...>` 是游戏控制码（如 `<c1d:11/>` `<ce:0/>` `<c8:5/>` `<c10:227/>` `<c21/>` `<c6/>` `<NAME/>` `<SURNAME/>`）。
1. **不增不减不改**：JP 有几个 `<...>`、什么种类、带什么参数(冒号后的数字)，ZH 必须**完全一样**，一个不少、参数不变。
2. **原顺序原位置**：每个 `<...>` 在 ZH 的相对位置要对应 JP。
3. **换行符 `\\n`（铁律）**：原文里的换行是**字面两个字符**「反斜杠 + 字母 n」，**不是真正的换行**。
   译文里**必须照样用字面 `\\n`**（写成反斜杠加 n），**绝对不要输出真的换行/回车**。
   `\\n` 的**个数和位置必须和原文完全一致**——原文有几个 `\\n`，译文就有几个，一个不能少、不能多、不能挪。
   （这控制游戏文本框的分行；漏了或多了会导致排版错乱或文字溢出。）
4. 只翻译标签和 `\\n` 之间的**日文文字**，标签和 `\\n` 本身原样照抄。

# 三、风格
- 简体中文，口语自然（外景对话很多是路人/搞笑语气，按语气翻）。
- 装备说明(【兜】【飾】等)、数值(攻击力/防御力/VIT等)按游戏术语简洁翻；【】内分类词保留括号。
- 长度尽量**不超过原文**（游戏文本框/原位空间有限）。

# 四、输出格式（严格 JSON，不要任何解释）
{"translations":[{"id":"u0","zh":"译文"},{"id":"u1","zh":"译文"}]}
每条对应输入的 id，zh 为译文（含原样保留的所有 <...> 和 \\n）。"""


def load_todo_file():
    return json.loads(TODO_FILE.read_text(encoding="utf-8"))   # [{id,jp,zh,count}]


def load_done():
    done = {}
    for f in PARTIALS.glob("*.json"):
        try:
            for t in json.loads(f.read_text(encoding="utf-8")).get("translations", []):
                done[t["jp"]] = t["zh"]
        except Exception:
            pass
    return done


SHORT_PROMPT = SYSTEM_PROMPT + """

# 五、长度硬约束（本轮=重译更短，最重要）
每条带一个 max 值。译文 **去掉所有 <...> 标签和 \\n 之后的可见字数，必须 ≤ 该条 max**。
原译文太长，游戏文本框/原位空间放不下。在不超 max 的前提下尽量保留原意：
可精简措辞、用更短的同义词、删可省的语气词/重复。标签和 \\n 的个数仍须与原文一致。"""


def translate_batch(client, entries, system_prompt=SYSTEM_PROMPT):
    user_msg = "翻译以下 {} 条游戏文本：\n\n{}".format(
        len(entries), json.dumps({"entries": entries}, ensure_ascii=False, indent=1))
    for attempt in range(1, MAX_RETRIES + 1):
        raw = ""
        try:
            completion = client.chat.completions.create(
                model=MODEL_DEPLOYMENT,
                messages=[{"role": "system", "content": system_prompt},
                          {"role": "user", "content": user_msg}],
                temperature=0.3, max_tokens=16000)
            raw = completion.choices[0].message.content or ""
            return json.loads(clean_r1_output(raw))
        except json.JSONDecodeError as e:
            print(f"  [尝试{attempt}] JSON解析失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES: time.sleep(RETRY_BACKOFF * attempt)
            else:
                (PARTIALS / f"FAILED_{entries[0]['id']}.txt").write_text(raw, encoding="utf-8")
                return {"translations": []}
        except Exception as e:
            print(f"  [尝试{attempt}] API失败: {e}", file=sys.stderr)
            if attempt < MAX_RETRIES: time.sleep(RETRY_BACKOFF * attempt)
            else: return {"translations": []}


# 名字归一化：DeepSeek 偶尔用错读音/字，合并时统一成与主线一致的写法（发现新错名加这里）
NAME_FIX = {"麻耶": "舞耶"}
def fix_names(s):
    for wrong, right in NAME_FIX.items():
        s = s.replace(wrong, right)
    return s

def do_merge():
    data = json.loads(CLEAN_FILE.read_text(encoding="utf-8"))
    done = load_done()
    n = 0
    for e in data:
        if e["jp"] in done:
            e["zh"] = fix_names(done[e["jp"]]); n += 1
    OUT_ZH.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    review = sum(1 for e in data if e.get("zh") and sorted(TAG_RE.findall(e["jp"])) != sorted(TAG_RE.findall(e["zh"])))
    print(f"合并: {n}/{len(data)} 条填了译文 → {OUT_ZH}（标签不守恒待复查: {review}）")


TOOLONG_FILE = ROOT / "out" / "field_toolong.json"
PARTIALS_SHORT = SCRIPT_DIR / "partials_field_short"
PARTIALS_SHORT.mkdir(exist_ok=True)


def do_retrans():
    """重译 out/field_toolong.json 里的太长条目更短，合回 field_text_zh.json。"""
    data = json.loads(TOOLONG_FILE.read_text(encoding="utf-8"))
    # 同 jp 多处出现取最小 budget（满足最小的就都塞得下）
    byjp = {}
    for e in data:
        jp, b = e["jp"], e["budget"]
        if jp not in byjp or b < byjp[jp]:
            byjp[jp] = b
    done = {}
    for f in PARTIALS_SHORT.glob("*.json"):
        try:
            for t in json.loads(f.read_text(encoding="utf-8")).get("translations", []):
                done[t["jp"]] = t["zh"]
        except Exception:
            pass
    todo = [{"id": f"s{i}", "jp": jp, "max": b} for i, (jp, b) in enumerate(byjp.items()) if jp not in done]
    print(f"太长唯一 {len(byjp)}, 已重译 {len(done)}, 待 {len(todo)}")
    if todo:
        client = make_client()
        idmap_all = {}
        bar = tqdm(range(0, len(todo), BATCH_SIZE), total=(len(todo) + BATCH_SIZE - 1) // BATCH_SIZE, desc="重译", unit="batch")
        for bi in bar:
            batch = todo[bi:bi + BATCH_SIZE]
            res = translate_batch(client, batch, SHORT_PROMPT)
            idmap = {e["id"]: (e["jp"], e["max"]) for e in batch}
            trans = []
            for t in res.get("translations", []):
                jpb = idmap.get(t.get("id"))
                if not jpb:
                    continue
                jp, mx = jpb
                zh = t.get("zh", "")
                vis = len(re.sub(r"<[^>]*>", "", zh).replace("\\n", "").replace("\n", ""))
                trans.append({"jp": jp, "zh": zh, "over": vis > mx})
            (PARTIALS_SHORT / f"{batch[0]['id']}.json").write_text(
                json.dumps({"translations": trans}, ensure_ascii=False, indent=1), encoding="utf-8")
            bar.set_postfix(超长=sum(1 for t in trans if t["over"]))
    # 合回 field_text_zh.json
    done = {}
    for f in PARTIALS_SHORT.glob("*.json"):
        for t in json.loads(f.read_text(encoding="utf-8")).get("translations", []):
            done[t["jp"]] = t["zh"]
    fz = json.loads(OUT_ZH.read_text(encoding="utf-8"))
    n = 0
    for e in fz:
        if e["jp"] in done:
            e["zh"] = fix_names(done[e["jp"]]); n += 1
    OUT_ZH.write_text(json.dumps(fz, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"重译合回 {n} 条 → {OUT_ZH}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--merge", action="store_true")
    ap.add_argument("--retrans", action="store_true", help="重译 out/field_toolong.json 的太长条目更短")
    ap.add_argument("--file", type=int, help="只翻在该 file id 出现的条目（如 --file 64，先小范围验证闭环）")
    args = ap.parse_args()
    if args.retrans:
        do_retrans(); return
    if args.merge:
        do_merge(); return

    allrows = load_todo_file()
    done = load_done()
    only_jp = None
    if args.file is not None:
        clean = json.loads(CLEAN_FILE.read_text(encoding="utf-8"))
        only_jp = {e["jp"] for e in clean if e["id"].startswith(f"field:{args.file}:")}
        print(f"--file {args.file}: 该文件涉及唯一 jp {len(only_jp)} 条")
    todo = [{"id": r["id"], "jp": r["jp"]} for r in allrows
            if r["jp"] not in done and (only_jp is None or r["jp"] in only_jp)]
    if args.limit: todo = todo[:args.limit]
    print(f"唯一 jp 总 {len(allrows)}, 已翻 {len(done)}, 待翻 {len(todo)}")
    if not todo:
        do_merge(); return

    client = make_client()
    n_batches = (len(todo) + BATCH_SIZE - 1) // BATCH_SIZE
    bar = tqdm(range(0, len(todo), BATCH_SIZE), total=n_batches, desc="翻译", unit="batch")
    done_cnt = len(done)
    for bi in bar:
        batch = todo[bi:bi + BATCH_SIZE]
        res = translate_batch(client, batch)
        idmap = {e["id"]: e["jp"] for e in batch}
        trans = []
        for t in res.get("translations", []):
            jp = idmap.get(t.get("id"))
            if jp is None: continue
            zh = t.get("zh", "")
            nl_jp = jp.count("\\n")
            nl_zh = zh.count("\\n") + zh.count("\n")   # 字面 \n + 真换行 都算
            bad = (sorted(TAG_RE.findall(jp)) != sorted(TAG_RE.findall(zh))) or (nl_jp != nl_zh)
            trans.append({"jp": jp, "zh": zh, "review": bad})
        # 按本批首条目的全局唯一 id 命名（如 u140.json），避免不同运行(全量/--file)批次序号冲突覆盖
        (PARTIALS / f"{batch[0]['id']}.json").write_text(
            json.dumps({"translations": trans}, ensure_ascii=False, indent=1), encoding="utf-8")
        done_cnt += len(trans)
        nbad = sum(1 for t in trans if t["review"])
        bar.set_postfix(done=done_cnt, total=len(allrows), 异常=nbad)
    print("\n翻译完成，合并中…")
    do_merge()


if __name__ == "__main__":
    main()
