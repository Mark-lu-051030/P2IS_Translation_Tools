/**
 * Compare function table from original P2IS binary vs what compile_script produces.
 * Shows: original addr values vs compiled addr values vs what's in the JSON.
 */
import * as fs from "fs";
import * as cdimage from "../lib/cdimage.mjs";
import * as archive from "../lib/archive.mjs";
import * as lzss from "../lib/lzss.mjs";
import * as scene from "../lib/scene_script.mjs";

const FILE_ID = 3;
const SUB_ID = 6;

let cd = await cdimage.init();
let arch_buf = await cdimage.read_file(cd, FILE_ID);
let files = archive.extract_files(arch_buf);
let sub = files[SUB_ID];

let total_comp = sub.readUInt32LE(4);
let uncomp_size = sub.readUInt32LE(8);
let orig = lzss.decompress(sub, 12, total_comp - 12, uncomp_size);

let script_json = JSON.parse(fs.readFileSync("out/scripts/3_6.json"));
let compiled = scene.compile_script(script_json);

// Read header from orig
let function_ptr_orig = orig[4];  // low byte only
let function_count_orig = orig[8]; // low byte only
let script_ptr_orig = orig.readUInt32LE(12);
let arg_ptr_orig = orig.readUInt32LE(16);
let diag_ptr_orig = orig.readUInt32LE(20);

// Read header from compiled
let function_ptr_comp = compiled.readUInt32LE(4);
let function_count_comp = compiled.readUInt32LE(8);
let script_ptr_comp = compiled.readUInt32LE(12);

console.log("=== HEADER COMPARISON (low byte) ===");
console.log(`function_ptr:   orig_byte=${function_ptr_orig.toString(16)} (=${function_ptr_orig})  comp=${function_ptr_comp.toString(16)}`);
console.log(`function_count: orig_byte=${function_count_orig} comp=${function_count_comp}`);
console.log(`script_ptr:     orig=${script_ptr_orig.toString(16)} comp=${script_ptr_comp.toString(16)}`);

console.log("\n=== FUNCTION TABLE (orig bytes 0x40/0x44 = addr/unk4) ===");
let instr_start_orig = script_ptr_orig;
for (let i = 0; i < function_count_orig; i++) {
  let entry_off = function_ptr_orig + i * 0x48;
  let name_end = orig.indexOf(0, entry_off);
  let name = orig.toString('ascii', entry_off, name_end);
  let addr_full = orig.readUInt32LE(entry_off + 0x40);
  let addr_byte = orig[entry_off + 0x40];  // low byte
  let unk4_full = orig.readUInt32LE(entry_off + 0x44);
  let unk4_byte = orig[entry_off + 0x44];

  // Compare with what compile_script produces
  let comp_entry_off = compiled[4] + i * 0x48;  // function_ptr_comp + i*0x48
  let comp_addr = compiled.readUInt32LE(comp_entry_off + 0x40);
  let comp_unk4 = compiled.readUInt32LE(comp_entry_off + 0x44);

  // What's in the JSON?
  let json_func = script_json.functions[i];
  let json_addr = json_func?.addr;
  let json_unk4 = json_func?.unk4;

  let addr_match = (addr_byte === comp_addr) ? "OK" : `MISMATCH (expected ${addr_byte}, got ${comp_addr})`;
  console.log(`  func[${i}] "${name}" addr_orig=0x${addr_full.toString(16)} (byte=0x${addr_byte.toString(16)}) json.addr=${json_addr} comp_addr=0x${comp_addr.toString(16)} ${addr_match}  unk4_byte=0x${unk4_byte.toString(16)} json.unk4=${json_unk4} comp_unk4=0x${comp_unk4.toString(16)}`);
}

console.log("\n=== ORIG LZSS COMPRESSED DATA (first 32 bytes at offset 12) ===");
let lzss_start = sub.slice(12, 44);
console.log(Array.from(lzss_start).map(b => b.toString(16).padStart(2,'0')).join(' '));

console.log("\n=== OUR LZSS COMPRESSED DATA (first 32 bytes at offset 12) ===");
let recompressed = lzss.compress(compiled, 0xc, true);
recompressed.writeUInt32LE(0x101, 0);
recompressed.writeUInt32LE(recompressed.byteLength, 4);
recompressed.writeUInt32LE(compiled.byteLength, 8);
let our_lzss = recompressed.slice(12, 44);
console.log(Array.from(our_lzss).map(b => b.toString(16).padStart(2,'0')).join(' '));

cdimage.close(cd);
