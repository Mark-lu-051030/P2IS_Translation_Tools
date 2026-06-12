// M4b 写盘半场: 把 naming_glyphs.json 的字形写进 WORK file59 sub1。
// sub1 在 D1 layout 的 file59 偏移 65536, 重压必须 compress_to_size 精确填满原 tc
// (与 sub0/归档同一条铁律), round-trip 校验后回写 + 修 ECC。幂等(重跑覆盖同样字节)。
// 用法: node subfile1/inject_naming_glyphs.mjs
import * as fs from 'fs';
import * as lzss from '../lib/lzss.mjs';
import { spawnSync } from 'child_process';
import { fileURLToPath } from 'url';
import * as path from 'path';
process.chdir(path.join(path.dirname(fileURLToPath(import.meta.url)), '..'));

const SECTOR = 0x930, BO = 24, BS = 2048;
const WORK = '/home/mark/Code/RomHacking/Game/P2IS_PSX/ogd/Persona 2 - Tsumi - Innocent Sin (Japan).bin';
const SUB1_OFF = 65536;   // D1 32-sector layout

const glyphs = JSON.parse(fs.readFileSync('subfile1/naming_glyphs.json', 'utf8'));
const fd = fs.openSync(WORK, 'r+');
function rblk(blk, sz) {
  const o = Buffer.allocUnsafe(sz), s = Buffer.alloc(SECTOR);
  let off = 0, sec = blk * SECTOR;
  while (off < sz) { fs.readSync(fd, s, 0, SECTOR, sec); const c = Math.min(BS, sz - off); s.copy(o, off, BO, BO + c); off += c; sec += SECTOR; }
  return o;
}
const fpd = rblk(0x17, 0x2400);
const blk = fpd.readUInt32LE(59 * 8), sz = fpd.readUInt32LE(59 * 8 + 4);
const a = rblk(blk, sz);
const tag = a.readUInt32LE(SUB1_OFF), tc = a.readUInt32LE(SUB1_OFF + 4), uc = a.readUInt32LE(SUB1_OFF + 8);
const d = Buffer.from(lzss.decompress(a, SUB1_OFF + 12, tc - 12, uc));
let n = 0;
for (const [slot, bytes] of Object.entries(glyphs)) {
  const off = 0x480 + parseInt(slot) * 18;
  if (off + 18 > d.length) { console.log(`✗ 槽 ${slot} 越界`); process.exit(1); }
  Buffer.from(bytes).copy(d, off); n++;
}
const r = lzss.compress_to_size(d, 12, tc);
if (!r) { console.log('✗ compress_to_size 装不下原 tc'); process.exit(1); }
r.writeUInt32LE(tag, 0); r.writeUInt32LE(tc, 4); r.writeUInt32LE(uc, 8);
const chk = lzss.decompress(r, 12, tc - 12, uc);
if (Buffer.compare(chk, d) !== 0) { console.log('✗ round-trip 失败'); process.exit(1); }
r.copy(a, SUB1_OFF);
let wo = 0, wsec = blk * SECTOR;
while (wo < sz) { const c = Math.min(BS, sz - wo); fs.writeSync(fd, a, wo, c, wsec + BO); wo += c; wsec += SECTOR; }
fs.closeSync(fd);
spawnSync('python3', ['fix_ecc.py', String(blk), String(blk + Math.ceil(sz / BS) - 1)], { stdio: 'ignore' });
console.log(`✅ ${n} 个简体字形注入 sub1, tc 精确填满 ${tc}, round-trip ✓`);
