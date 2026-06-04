/**
 * 把 out/strtbl_zh/*.json 的中文 string table 写回 ISO。
 *
 * strtbl 所在 sub-file 是未压缩格式（type 0xc2），直接在 offset 处覆写字节即可。
 * 不需要 LZSS 重压缩。
 *
 * 约束：编码后总字节数 ≤ max_len（不能溢出到下一个 table）。
 *
 * 用法: node apply_strtbl.mjs <file_id> <sub_id> <table_idx>
 *       node apply_strtbl.mjs all     # 处理 out/strtbl_zh/ 里全部
 */
import * as fs from "fs/promises";
import * as fss from "fs";
import * as path from "path";
import { fileURLToPath } from "url";
import { spawn } from "child_process";
import * as cdimage from "./lib/cdimage.mjs";
import * as archive from "./lib/archive.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const STRTBL_ZH_DIR = path.join(__dirname, "out", "strtbl_zh");
const REPORT_DIR = path.join(__dirname, "out", "build_report");
const FIX_ECC = path.join(__dirname, "fix_ecc.py");

// 把 items 数组转字节流（uint16 LE）
function items_to_bytes(items) {
    const out = [];
    for (const item of items) {
        if (Array.isArray(item)) {
            // 控制码：[cmd] 或 [cmd, arg, arg, ...]
            // 编码 = 0x1000 | (词数<<8) | cmd，len nibble = 总 uint16 词数(cmd + 参数个数)。
            // ⚠ 原来写 0x1100|cmd 是 bug：len nibble 恒=1(表示0参)，但带参命令后面又跟了 arg，
            //   游戏读完命令把 arg 当成字符 → 带参控制码的 strtbl(如谣言描述<c1d:N/>)错乱/闪一下消失。
            // 例: [1]→0x1101(0参) / [0x1d,11]→0x121d+000b(1参) / [5,0]→0x1205+0000(1参)。
            const cmd = item[0];
            const val = 0x1000 | ((item.length & 0xf) << 8) | (cmd & 0xff);
            out.push(val & 0xff, (val >> 8) & 0xff);
            for (let i = 1; i < item.length; i++) {
                const arg = item[i];
                out.push(arg & 0xff, (arg >> 8) & 0xff);
            }
        } else {
            // 字符码 uint16 LE
            out.push(item & 0xff, (item >> 8) & 0xff);
        }
    }
    return Buffer.from(out);
}

async function fix_ecc(start, end) {
    return new Promise((res, rej) => {
        const p = spawn("python3", [FIX_ECC, String(start), String(end)], { stdio: "inherit" });
        p.on("exit", c => c === 0 ? res() : rej(new Error(`fix_ecc exited ${c}`)));
    });
}

async function apply_one(zh_data) {
    const { file: FILE_ID, file_num: SUB_ID, offset, max_len, strings } = zh_data;
    console.log(`\n=== file ${FILE_ID} sub ${SUB_ID} table @ offset ${offset} (max_len ${max_len}) ===`);

    // 1. 重建 string table 结构（关键！游戏靠索引表的指针定位每个 string）：
    //    [count u32][ptr0 u32][ptr1 u32]...[ptrN u32][string0 bytes][string1 bytes]...
    //    每个 ptr 是相对 table 起点的字节偏移。重复 string 去重共享指针（省空间，跟原版一致）。
    const N = strings.length;
    const new_table = Buffer.alloc(max_len);
    new_table.writeUInt32LE(N, 0);          // count
    let ind_ptr = 4;                         // 索引表写入位置
    let str_ptr = N * 4 + 4;                 // string 数据区起点（count 4字节 + N个指针）
    const seen = new Map();                  // 去重: string字节hex → 已写的 str_ptr
    for (const items of strings) {
        const bytes = items_to_bytes(items);
        const key = bytes.toString('hex');
        if (seen.has(key)) {
            new_table.writeUInt32LE(seen.get(key), ind_ptr);   // 复用已有 string 指针
        } else {
            if (str_ptr + bytes.byteLength > max_len) {
                console.log(`  ❌ 超过 max_len（需 ${str_ptr + bytes.byteLength} > ${max_len}）`);
                return { ok: false, reason: 'too_big', detail: `${str_ptr + bytes.byteLength} > ${max_len}` };
            }
            new_table.writeUInt32LE(str_ptr, ind_ptr);
            bytes.copy(new_table, str_ptr);
            seen.set(key, str_ptr);
            str_ptr += bytes.byteLength;
        }
        ind_ptr += 4;
    }
    console.log(`  ${N} strings → 索引表+数据 ${str_ptr} 字节 (max ${max_len}, 余 ${max_len - str_ptr})`);
    const total_bytes = str_ptr;

    // 3. 读 ISO，取 sub-file，在 offset 处覆写
    const cd = await cdimage.init();
    const fileposdat = cd.fileposdat;
    const file_block = fileposdat.readUInt32LE(FILE_ID * 8);
    const file_size = fileposdat.readUInt32LE(FILE_ID * 8 + 4);
    console.log(`  file 在 sector ${file_block}, size ${file_size}`);

    const arch_buf = await cdimage.read_file(cd, FILE_ID);
    const sub_files = archive.extract_files(arch_buf);

    // ⚠ 只覆写重建表的实际长度 total_bytes，不碰 total~max_len 之间的原字节！
    // extract 的 max_len 可能偏大（覆盖到下一个未识别的 table），全清零会破坏紧邻数据。
    const new_table_trimmed = new_table.subarray(0, total_bytes);

    let patched;
    if (sub_files.length === 1 && sub_files[0] === arch_buf) {
        // single file（archive.mjs 'Assuming single file'）：直接在 file 内 offset 覆写
        patched = Buffer.from(arch_buf);
        console.log(`  single file, length ${patched.byteLength}, write at offset ${offset} (${total_bytes}B)`);
        new_table_trimmed.copy(patched, offset);
    } else {
        // 真 archive：找 SUB_ID sub-file, 在 offset 覆写, 用 patch_archive_inplace 替换
        const sub_data = Buffer.from(sub_files[SUB_ID]);
        console.log(`  sub-file ${SUB_ID}: length ${sub_data.byteLength}, write ${total_bytes}B at offset ${offset}`);
        new_table_trimmed.copy(sub_data, offset);
        patched = archive.patch_archive_inplace(arch_buf, { [SUB_ID]: sub_data });
    }

    // 5. 写回 ISO
    await cdimage.write_file(cd, FILE_ID, patched);
    await cdimage.close(cd);

    // 6. 修 ECC
    const file_sectors = Math.ceil(file_size / 2048);
    await fix_ecc(file_block, file_block + file_sectors - 1);
    await fix_ecc(23, 26);   // FILEPOS.DAT 可能被 cdimage.close 改

    return { ok: true, bytes: total_bytes, max: max_len };
}

async function main() {
    const args = process.argv.slice(2);
    fss.mkdirSync(REPORT_DIR, { recursive: true });

    let files;
    if (args[0] === 'all' || args.length === 0) {
        // 跳过 SLUS_*.json（file 0 = 65MB SLPS，由 apply_strtbl_slps.py 用 raw-sector 处理，更快更对）
        files = fss.readdirSync(STRTBL_ZH_DIR)
            .filter(f => f.endsWith('.json') && !f.startsWith('SLUS_'));
    } else if (args.length >= 3) {
        files = [`${args[0]}_${args[1]}_${args[2]}.json`];
    } else {
        console.log('用法: node apply_strtbl.mjs all');
        console.log('     node apply_strtbl.mjs <file> <sub> <table>');
        process.exit(1);
    }

    const results = { ok: 0, skipped: [] };
    for (const fname of files.sort()) {
        const fp = path.join(STRTBL_ZH_DIR, fname);
        if (!fss.existsSync(fp)) {
            console.log(`⚠ ${fname} 不存在，跳过`);
            continue;
        }
        const zh_data = JSON.parse(fss.readFileSync(fp, 'utf-8'));
        try {
            const r = await apply_one(zh_data);
            if (r.ok) results.ok++;
            else results.skipped.push({ file: fname, ...r });
        } catch (e) {
            console.log(`  ✗ ${fname}: ${e.message}`);
            results.skipped.push({ file: fname, reason: 'error', detail: e.message });
        }
    }

    console.log(`\n=== strtbl 总结 ===`);
    console.log(`  成功: ${results.ok}`);
    console.log(`  跳过: ${results.skipped.length}`);
    fss.writeFileSync(path.join(REPORT_DIR, 'strtbl_summary.json'), JSON.stringify(results, null, 2));
}

main().catch(e => { console.error(e); process.exit(1); });
