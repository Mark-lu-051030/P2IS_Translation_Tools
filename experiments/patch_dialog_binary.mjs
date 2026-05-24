/**
 * 直接在二进制层面修改对话文本，绕过 compile_script。
 * 把 file 181 sub-file 8 的 diag3 所有字符码改成 1。
 */
import * as cdimage from "../lib/cdimage.mjs";
import * as archive from "../lib/archive.mjs";
import * as lzss from "../lib/lzss.mjs";
import { parse as parse_dialog, calculate_dialog_length } from "../lib/msg_script.mjs";

const FILE_ID = 181;
const SUB_ID = 8;
const TARGET_DIAG_INDEX = 3;  // diag3 = 第4个对话（从0数）

let cd = await cdimage.init();
let arch = await cdimage.read_file(cd, FILE_ID);
let files = archive.extract_files(arch);
let sub = files[SUB_ID];

let total_comp = sub.readUInt32LE(4);
let uncomp_size = sub.readUInt32LE(8);
let orig = lzss.decompress(sub, 12, total_comp - 12, uncomp_size);
console.log(`解压后大小: ${orig.byteLength}`);

// 从 header 读 diag_ptr（第6个 uint32，偏移20）
let diag_ptr = orig.readUInt32LE(20);
console.log(`diag_ptr: 0x${diag_ptr.toString(16)}`);

// 顺序扫描对话，找 diag3 的位置
let off = diag_ptr;
for (let i = 0; i < TARGET_DIAG_INDEX; i++) {
    let diag = parse_dialog(orig, off, true);
    let len = diag ? calculate_dialog_length(diag) : 2;
    console.log(`diag${i}: offset=0x${off.toString(16)}, len=${len}`);
    off += len;
}
let diag3_start = off;
let diag3 = parse_dialog(orig, off, true);
let diag3_len = diag3 ? calculate_dialog_length(diag3) : 2;
let diag3_end = off + diag3_len;
console.log(`diag3: offset=0x${diag3_start.toString(16)}, len=${diag3_len}`);

// 修改：把字符码（高nibble=0，非零）全替换成 1
let modified = Buffer.from(orig);
let changed = 0;
for (let p = diag3_start; p < diag3_end - 1; p += 2) {
    let val = modified.readUInt16LE(p);
    let upper_nibble = (val >> 12) & 0xf;
    if (upper_nibble === 0 && val !== 0) {
        modified.writeUInt16LE(1, p);
        changed++;
    }
}
console.log(`替换了 ${changed} 个字符码 → 1`);

// 重压缩
let recomp = lzss.compress(modified, 0xc, true);
recomp.writeUInt32LE(0x101, 0);
recomp.writeUInt32LE(recomp.byteLength, 4);
recomp.writeUInt32LE(modified.byteLength, 8);
console.log(`重压缩: ${sub.byteLength} → ${recomp.byteLength} bytes`);

// 写回
let replacements = {};
replacements[SUB_ID] = recomp;
let patched = archive.patch_archive_inplace(arch, replacements);
await cdimage.write_file(cd, FILE_ID, patched);
console.log("写入完成。运行:");
console.log("  python3 fix_ecc.py 23 26");
console.log("  python3 fix_ecc.py 235195 235297");
cdimage.close(cd);
