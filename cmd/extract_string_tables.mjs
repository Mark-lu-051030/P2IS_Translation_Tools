import * as fs from "fs";
import * as archive from "../lib/archive.mjs";
import * as cdimage from "../lib/cdimage.mjs";
import * as file from "../lib/file.mjs";
import * as msg from "../lib/msg_script.mjs";

export const command = [`extract_string_tables start [end]`];
export const desc = "Extract string tables from files start..end";
export const builder = {
  out: {
    alias: "o",
    default: ".",
  },
  start: {
    //   default: 0,
    //   max: 880,
    number: true,
    demandOption: true,
  },
  end: {
    //   default: 880,
    number: true,
    description: "Last file to extract.  If absent only one file is extracted.",
    //demandOption: false,
  },
};

let is_string_table = (buff, ptr) => {
  let debug = ptr==0xdd644-0xaf000;
  let len = buff.readUInt32LE(ptr);
  
  if (!len || len > 2048 || ptr + len * 4 > buff.byteLength) {
    if(debug) console.log("here", len);
    return false;
  }
  let strings = [];
  for (let i = 0; i < len; i++) {
    let s_ptr = buff.readUInt32LE(ptr + 4 + 4 * i) + ptr;
    if (s_ptr > buff.byteLength - 2) {
      return false;
    }
    if(i==0&&s_ptr != ptr + len*4+4) {
      // console.warn(`First entry does not follow index table`);
      return false;
    }
    let value = buff.readUInt32LE(s_ptr);
    let res = msg.parse(buff, s_ptr, true);
    if (!res) return false;
    strings.push(res);
  }
  return strings;
};

let search_for_string_table = (buff) => {
  let ptr = 0;
  let tables = [];
  while (ptr < buff.byteLength - 4) {
    let res = is_string_table(buff, ptr);
    if(ptr == 0xdd644-0x1000) {
      console.log(res);
    }
    if (res) {
      //TODO
      console.log(`Found at ${ptr.toString(16)}`);
      tables.push({
        offset: ptr,
        strings: res,
      });
    }
    ptr += 4;
  }
  return tables;
};

export const handler = async (argv) => {
  let start = argv.start;
  let end = argv.end ?? argv.start;
  let cd = await cdimage.init_readonly();
  if (!fs.existsSync(argv.out)) fs.mkdirSync(argv.out);
  for (let i = start; i <= end; i++) {
    console.log(`${i}`);
    // if (!fs.existsSync(`${argv.out}/${i}/`)) fs.mkdirSync(`${argv.out}/${i}/`);
    let file_buff = await cdimage.read_file(cd, i);

    let files = archive.extract_files(file_buff);
    files.forEach((f, o) => {
      
      console.log(f);
      let res = search_for_string_table(f);
      if (res) {
        res.forEach((t, k) => {
          t.file = i;
          t.file_num = o;
          let len = (t.strings.length + 1) * 4;
          t.strings.forEach((line) => (len += msg.calculate_dialog_length(line)));
          t.max_len = len;
          fs.writeFileSync(
            `${argv.out}/${i>0?i:'SLUS'}_${o}_${k}.json`,
            JSON.stringify(t, null, 4)
          );
        });
      }
      //   let res = file.parseFile(f);
      //   if (res) fs.writeFileSync(`${argv.out}/${i}_${o}.${res.type}`, res.data);
    });
  }
  cdimage.close(cd);
};
