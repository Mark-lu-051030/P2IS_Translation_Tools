import * as fs from 'fs';
import * as lzss from '../lib/lzss.mjs';

const SECTOR = 0x930, BO = 24, BS = 2048
const ORIG = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan) - 副本.bin';

const fd = fs.openSync(ORIG, 'r');
function rblk(blk, sz) {
    const out = Buffer.allocUnsafe(sz);
    const sec = Buffer.alloc(SECTOR);
    let off = 0;
    let s = blk * SECTOR;
    while (off < sz) {
        fs.readSync(fd, sec, 0, SECTOR, s);
        const c = Math.min(BS, sz - off);
        sec.copy(out, off, BO, BO + c);
        off += c;
        s += SECTOR;
    }
    return out;
}

const fpd = rblk(0x17, 0x2400);
const blk = fpd.readUInt32LE(59 * 8);
const sz = fpd.readUInt32LE(59 * 8 + 4);
console.log('file59: block', blk, 'size', sz);

const file59 = rblk(blk, sz)
const tc0 = file59.readUInt32LE(4)
const p = (tc0 + 0x7ff) & ~0x7ff;
const sub0 = lzss.decompress(file59, 12,
    tc0 - 12, file59.readUInt32LE(8));
const sub1 = lzss.decompress(
    file59, p + 12, file59.readUint32LE(p+4) - 12, file59.readUint32LE(p+8)
);
console.log('解压: sub0', sub0.length, 'sub1', sub1.length);

const og = JSON.parse(fs.readFileSync('codetable_og.json', 'utf8'));

// TODO 4: 字 → sub0 槽号（只收单字符条目；槽号 key 是字符串要 parseInt）
const char2slot = {};
for (const [k, v] of Object.entries(og)) {
    if (typeof v === 'string' && v.length === 1) char2slot[v] = parseInt(k);
}
console.log('og 单字符条目:', Object.keys(char2slot).length);

// TODO 5: 位图匹配——拿 sub0 里每个字的 18 字节位图，去 sub1 按 18 步长找唯一相同者
const GLYPHS1 = Math.floor((sub1.length - 0x480) / 18);
const result = {};       // 字 → sub1 槽号
const unmatched = [];    // 全零/零命中/多命中的字
for (const [ch, slot0] of Object.entries(char2slot)) {
    const off0 = 0x480 + slot0 * 18;
    if (off0 + 18 > sub0.length) continue;
    const bmp = sub0.slice(off0, off0 + 18);
    if (bmp.every(b => b === 0)) { unmatched.push([ch, '空位图']); continue; }
    const hits = [];
    for (let i = 0; i < GLYPHS1; i++) {
        const o = 0x480 + i * 18;
        if (Buffer.compare(sub1.slice(o, o + 18), bmp) === 0) hits.push(i);
    }
    if (hits.length === 1) result[ch] = hits[0];
    else unmatched.push([ch, hits.length === 0 ? '零命中' : `多命中${hits.length}`]);
}

// TODO 6: 验收 + 输出
console.log('验收: 数 →', result['数'], '(应1663)  字 →', result['字'], '(应1293)  亜 →', result['亜'], '(应170)');
console.log(`命中 ${Object.keys(result).length} 字 / unmatched ${unmatched.length}`);
const reasons = {};
for (const [, r] of unmatched) reasons[r.replace(/\d+/, 'N')] = (reasons[r.replace(/\d+/, 'N')] || 0) + 1;
console.log('unmatched 分类:', reasons);

// 输出格式与 codetable_og 同构: {槽号: 字}
const jis = {};
for (const [ch, slot] of Object.entries(result)) jis[String(slot)] = ch;
fs.writeFileSync('codetable_jis.json', JSON.stringify(jis));
fs.writeFileSync('subfile1/unmatched.json', JSON.stringify(unmatched, null, 1));
console.log(`→ codetable_jis.json (${Object.keys(jis).length} 槽)  + subfile1/unmatched.json`);
fs.closeSync(fd);
