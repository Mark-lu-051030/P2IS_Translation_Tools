/**
 * Test: insert original sub-files 3 and 6 UNCHANGED (no recompression).
 * If game works after this, the problem is in LZSS recompression.
 * If game still crashes, the problem is in archive structure or ECC.
 */
import * as cdimage from "../lib/cdimage.mjs";
import * as archive from "../lib/archive.mjs";

const FILE_ID = 3;
const SUB_IDS = [3, 6];  // sub-files to "replace" with their own original bytes

let cd = await cdimage.init();
let arch = await cdimage.read_file(cd, FILE_ID);
let files = archive.extract_files(arch);

console.log(`Archive size: ${arch.byteLength}`);
SUB_IDS.forEach(id => {
  console.log(`Sub-file[${id}]: ${files[id].byteLength} bytes, magic=0x${files[id].readUInt32LE(0).toString(16)}`);
});

// Build replacements: sub-file index → EXACT ORIGINAL BYTES (no changes)
let replacements = {};
SUB_IDS.forEach(id => {
  replacements[id] = files[id];
});

let patched = archive.patch_archive_inplace(arch, replacements);
console.log(`Patched size: ${patched.byteLength} (should match ${arch.byteLength})`);

// Verify the patched archive matches original exactly
let differ = false;
for (let i = 0; i < arch.byteLength; i++) {
  if (arch[i] !== patched[i]) { differ = true; console.log(`Differs at byte ${i}`); break; }
}
if (!differ) console.log("Patched archive is IDENTICAL to original ✓");

await cdimage.write_file(cd, FILE_ID, patched);
console.log("Written. Now run:\n  python3 fix_ecc.py 23 26\n  python3 fix_ecc.py 29297 29378");
cdimage.close(cd);
