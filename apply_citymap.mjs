// 城市俯视图(可移动选择地点的大地图)地点标签翻译。
// 标签按"区"分散在多个文件的未压缩区: 1113=平坂区 / 1114=夢崎区 / 1115=青華区 / 1116=港南区。
// 格式: og码地名 + 0x1000 终止符(非 0x0000, 后者渲染成「)。字段提取(要 RET 定界+≥3汉字)漏了它们。
// 做法: 精确匹配 JP 标签的 og 码序列, 且其后紧跟 0x1000(确保是完整标签不是更长串的子串),
// 原位替换为 CN 码 + 0x1000 终止 + 0x1000 填充到原字节宽(CN ≤ JP 码数, 装得下)。直接写扇区, 大小不变。
// ⚠️ 这些文件(1113-1117)是归档, apply_field 会往压缩区塞 NPC 对话。本步在 build 里位于 apply_field 之前,
//    从 BACKUP 读 + 整文件写回 WORK; 之后 apply_field 从 WORK 读(已含本步标签翻译)再改对话, 整文件写回保留两者。
import fs from "fs";
import { spawnSync } from "child_process";
const SECTOR = 0x930, BO = 24, BS = 2048;
const BACKUP = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin";
const WORK = "/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin";
const og = JSON.parse(fs.readFileSync("codetable_og.json", "utf8"));
const ct = JSON.parse(fs.readFileSync("codetable.json", "utf8"));
// ⚠️ og 字库一码多形: 同一字符(如 ヨ)有多个码(879/543)。建"字符→码集合"以便匹配时接受任一码,
//    否则预编码只取末码、indexOf 漏匹配(实测 ギガ・マッチヨ 的 ヨ)。
const ogRevAll = {}; for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) (ogRevAll[v] = ogRevAll[v] || new Set()).add(parseInt(k));
const rev = {}; for (const [k, v] of Object.entries(ct)) if (typeof v === "string" && v.length === 1) rev[v] = parseInt(k);

// 城市图各区地点标签 JP→CN。约束: CN 码数 ≤ JP 码数(原位等长替换, 不足用 0x1000 填充)。
// ⚠ og 码表只含游戏实际用到的字符:
//   - 平假名 が 不在 og → がってん/葛葉等标签在城市地图里实为其他编码/不存在
//   - 汉字 葉 不在 og → 青葉/葛葉 系列无法匹配(游戏用 青華)
//   - 小ョ/小ャ 不在 og(游戏只用大ヨ/大ヤ) → ジョリーロジャー 须写作 ジヨリーロジヤー
//   - 诊/· 不在中文码表 → 改用 院 / 直拼
const LABELS = {
  // 区名(显式翻译，防止 og 槽被字体注入占用导致渲染错字)
  "青華区": "青华区", "夢崎区": "梦崎区",
  // 街中共通 (file 1112)
  "アラヤ神社": "阿赖耶神社", "シルバーマン邸": "希尔巴曼宅",
  "ロータス": "莲花",           // Lotus(5字) > ロータス(4字) 太长 → 莲花
  "ロサカンディータ": "白玫瑰",
  // 平坂区 (file 1113)
  "スマイル平坂": "微笑平坂", "春日山高校": "春日山高校",
  "カメヤ横丁": "龟屋横丁", "カメヤ横町": "龟屋横町",
  "坂上ビル": "坂上大厦", "ライブ屋": "Live",
  "スマル・プリズン": "斯麦尔监狱", "宝瓶宮の神殿": "宝瓶宫神殿",
  "サトミタダシ": "里见直药局",
  "かおり": "香里",             // kaori(5字) > かおり(3字) 太长 → 香里
  "ラーメンしらいし": "白石拉面店",
  "東亜ディフェンス": "东亚防务",
  "富永カイロプラクティック": "富永整骨院",  // 诊不在CN码表 → 整骨院
  "トニーの店": "TONY店",       // TONY路摊(6字) > トニーの店(5字) 太长 → TONY店
  // 夢崎区 (file 1114)
  "ゾディアック": "黄道带", "ムー大陸": "姆大陆",
  "ギガ・マッチヨ": "巨型猛男",  // og只有大ヨ形式
  "パチンコ・シルバー": "弹珠店银",  // ·不在CN码表 → 直拼
  "夢崎センター街": "梦崎中央街道", "天蠍宮の神殿": "天蝎宫神殿",
  "ゴールド": "GOLD",
  "ビキニライン": "比基尼线",
  "ピースダイナー": "和平餐厅",
  // 青華区 (file 1115, og 用 青華 非 青葉)
  "青華公園": "青叶公园",
  "キスメット出版": "宿命出版社",
  "青華通り": "青叶通路",
  "獅子宮の神殿": "狮子宫神殿",
  "ケーブルカー麓駅": "缆车山麓站",
  "青華消防署": "青叶消防局",
  "クレール・ド・リュンヌ": "月光",
  "ダブル・スラッシュ": "W.SLASH",
  "野外音楽堂": "露天音乐场",
  // 港南区 (file 1116)
  "空の科学館": "空中科学馆",
  "ルナパレス港南": "港南月之公馆",
  "シーサイドモール": "海滨商场",
  "廃工場": "废工厂", "金牛宮の神殿": "金牛宫神殿",
  "港南警察署": "港南警察局",
  "恵比寿海岸": "惠比寿海岸",
  "珠閒瑠テレビ": "珠间瑠TV",
  "ジヨリーロジヤー": "海盗旗咖啡",  // og大ヨ/大ヤ形式(小ョ/小ャ不在og)
  "倫敦屋": "伦敦屋",
  "柊サイコセラピー": "柊心理院",    // 诊不在CN码表 → 心理院
  "珠閒瑠ジニー": "珠闲瑠占卜屋",
};
const FILES = [1112, 1113, 1114, 1115, 1116];  // 1112=街中(アラヤ神社/シルバーマン邸/ロータス @sub14未压缩区)

function rfile(fd, id) {
  const o = Buffer.alloc(0x2400), s = Buffer.alloc(SECTOR); let off = 0, sec = 0x17 * SECTOR;
  while (off < 0x2400) { fs.readSync(fd, s, 0, SECTOR, sec); const c = Math.min(BS, 0x2400 - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; }
  const blk = o.readUInt32LE(id * 8), sz = o.readUInt32LE(id * 8 + 4);
  const b = Buffer.alloc(sz), s2 = Buffer.alloc(SECTOR); let o2 = 0, sc = blk * SECTOR;
  while (o2 < sz) { fs.readSync(fd, s2, 0, SECTOR, sc); const c = Math.min(BS, sz - o2); s2.copy(b, o2, BO, BO + c); o2 += c; sc += SECTOR; }
  return { buf: b, blk, sz };
}

// 预编码 JP/CN 码（一次性，所有文件共用）。jcSets[k] = 第 k 字符可接受的 og 码集合(一码多形)。
const jobs = [];
for (const [jp, cn] of Object.entries(LABELS)) {
  const chars = [...jp];
  const jcSets = chars.map(c => ogRevAll[c]);
  if (jcSets.some(s => !s)) { console.log(`⚠ JP "${jp}" 含未知 og 码, 跳过`); continue; }
  const cc = [...cn].map(c => rev[c]);
  if (cc.some(x => x === undefined)) { console.log(`⚠ CN "${cn}" 含缺字, 跳过`); continue; }
  if (cc.length > chars.length) { console.log(`⚠ CN "${cn}"(${cc.length}) 比 JP "${jp}"(${chars.length}) 长, 跳过`); continue; }
  jobs.push({ jp, cn, jcSets, cc, jlen: chars.length });
}

const DRY = process.env.CITYMAP_DRY === '1';  // 只报告命中, 不写盘(单独验证用; 完整 build 勿设)
// 从 WORK 读: 1112-1117 是归档(apply_field 写对话进去),从 BACKUP 读整文件写回会抹掉对话翻译。
// WORK 里标签仍是日文码(没人改过)→照样命中;已翻过的标签第二次跑match不到=幂等。
const bfd = fs.openSync(WORK, "r");
const wfd = DRY ? null : fs.openSync(WORK, "r+");
let grandTotal = 0;

for (const FILE of FILES) {
  const { buf: a, blk, sz } = rfile(bfd, FILE);
  const touched = new Set();
  let hits = 0;
  const log = [];
  for (const { jp, cn, jcSets, cc, jlen } of jobs) {
    let n = 0;
    // 偶对齐滑窗: 逐字符接受该字符的任一 og 码(一码多形), 且整串后紧跟 0x1000 终止 → 完整标签
    for (let p = 0; p + jlen * 2 <= a.length; p += 2) {
      let ok = true;
      for (let k = 0; k < jlen; k++) { if (!jcSets[k].has(a.readUInt16LE(p + k * 2))) { ok = false; break; } }
      if (!ok) continue;
      const after = (p + jlen * 2 + 1 < a.length) ? a.readUInt16LE(p + jlen * 2) : -1;
      if (after !== 0x1000) continue;
      for (let i = 0; i < cc.length; i++) a.writeUInt16LE(cc[i], p + i * 2);
      a.writeUInt16LE(0x1000, p + cc.length * 2);                                    // CN 后紧跟终止符
      for (let i = cc.length + 1; i < jlen; i++) a.writeUInt16LE(0x1000, p + i * 2);  // 余下填充(不被读)
      touched.add(blk + Math.floor(p / BS));
      if (p + jlen * 2 > (Math.floor(p / BS) + 1) * BS) touched.add(blk + Math.floor((p + jlen * 2) / BS));  // 跨扇区
      n++; hits++;
    }
    if (n) log.push(`${jp}→${cn}×${n}`);
  }
  if (!hits) { console.log(`file${FILE}: 无可改标签`); continue; }
  if (!DRY) {
    // 整文件写回 WORK
    let wo = 0, wsec = blk * SECTOR;
    while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(wfd, a, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
    const lo = Math.min(...touched), hi = Math.max(...touched);
    spawnSync("python3", ["fix_ecc.py", String(lo), String(hi)], { stdio: "ignore" });
    console.log(`file${FILE}: ${hits} 处  [${log.join('  ')}]  ECC ${lo}-${hi}`);
  } else {
    console.log(`file${FILE}: ${hits} 处  [${log.join('  ')}]  (dry)`);
  }
  grandTotal += hits;
}
fs.closeSync(bfd);
if (wfd !== null) fs.closeSync(wfd);
console.log(`✅ 城市图标签共写回 ${grandTotal} 处 / ${FILES.length} 个文件`);
