/**
 * 翻译 file 1117 sub1 的地图节点名称表（区域连接地图上的位置标签）。
 *
 * sub1 格式：每个条目 = [二进制头 uint16s][og码文本 uint16s][0x1000 分隔符]
 * 替换：按 og 码搜索日文名 → 覆写为 zh 码 + FW 补齐原长。
 */
import * as fs from "fs/promises";
import * as fss from "fs";
import * as archive from "./lib/archive.mjs";
import * as cdimage from "./lib/cdimage.mjs";
import { spawn } from "child_process";

const FIX_ECC = "/home/mark/Code/RomHacking/P2IS_Translation_Tools/fix_ecc.py";
const og = JSON.parse(fss.readFileSync("codetable_og.json", "utf8"));
const ct = JSON.parse(fss.readFileSync("codetable.json", "utf8"));
const ogRev = {};
for (const [k, v] of Object.entries(og)) if (typeof v === "string" && v.length === 1) ogRev[v] = parseInt(k);
const rev = {};
for (const [k, v] of Object.entries(ct)) if (typeof v === "string" && v.length === 1) rev[v] = parseInt(k);
const FW = rev["　"] ?? rev[" "];

// og码→字节
function ogBuf(s) {
    const out = [];
    for (const c of s) {
        const code = ogRev[c];
        if (code === undefined) throw new Error(`og missing: ${c}`);
        out.push(code & 0xff, (code >> 8) & 0xff);
    }
    return Buffer.from(out);
}
// zh码→字节（带 FW 填充到指定长度）
function zhBuf(s, total) {
    const out = [];
    for (const c of s) {
        const code = rev[c];
        if (code === undefined) throw new Error(`zh missing: ${c}`);
        out.push(code & 0xff, (code >> 8) & 0xff);
    }
    while (out.length / 2 < total) { out.push(FW & 0xff, (FW >> 8) & 0xff); }
    return Buffer.from(out);
}

// 替换列表（长名优先）：[jp_og, zh]
const REPLACEMENTS = [
    ["ケーブルカー頂上駅", "缆车山顶站"],  // 10→5 + FW×5
    ["ケーブルカー麓駅",   "缆车山麓站"],  // 9→5 + FW×4
    ["カラコル",           "卡拉科尔"],    // 4→4 exact
    ["頂上駅",             "山顶站"],      // 3→3 exact (缩略词条目)
    ["麓駅",               "麓站"],        // 2→2 exact (缩略词条目)
];

async function run_fix_ecc(start, end) {
    return new Promise((res, rej) => {
        const p = spawn("python3", [FIX_ECC, String(start), String(end)], { stdio: "ignore" });
        p.on("exit", c => c === 0 ? res() : rej(new Error(`fix_ecc ${c}`)));
    });
}

const FILE_ID = 1117;
const SUB_ID = 1;

const cd = await cdimage.init();
const arch_buf = await cdimage.read_file(cd, FILE_ID);
const sub_files = archive.extract_files(arch_buf);
const sub1 = Buffer.from(sub_files[SUB_ID]);
console.log(`File ${FILE_ID} sub${SUB_ID}: ${sub1.length} bytes`);

// 子文件头是 12 字节（tag4+tc4+uc4），原始文本从 offset 12 开始
const data = sub1.slice(12);
let hits = 0;

for (const [jp, zh] of REPLACEMENTS) {
    const needle = ogBuf(jp);
    const replacement = zhBuf(zh, jp.length);  // 补到原 jp 长度
    let idx = 0;
    while (true) {
        const i = data.indexOf(needle, idx);
        if (i < 0) break;
        replacement.copy(data, i);
        console.log(`  [${jp}] → [${zh}] at data offset ${i} (uint16 ${i / 2})`);
        hits++;
        idx = i + needle.length;
    }
}

if (hits === 0) {
    console.log("⚠ 没有找到任何匹配，文件可能已经被翻译过？");
    await cdimage.close(cd);
    process.exit(0);
}

// 把修改后的 data 写回 sub1（保持原 12 字节头不变）
data.copy(sub1, 12);
const patched = archive.patch_archive_inplace(arch_buf, { [SUB_ID]: sub1 });
await cdimage.write_file(cd, FILE_ID, patched);
const fileposdat = cd.fileposdat;
const file_block = fileposdat.readUInt32LE(FILE_ID * 8);
const file_size = fileposdat.readUInt32LE(FILE_ID * 8 + 4);
await cdimage.close(cd);

const file_sectors = Math.ceil(file_size / 2048);
await run_fix_ecc(file_block, file_block + file_sectors - 1);
await run_fix_ecc(23, 26);

console.log(`✓ ${hits} 处替换完成`);
