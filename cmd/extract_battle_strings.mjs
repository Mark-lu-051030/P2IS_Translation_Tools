import * as fs from "fs";
import * as archive from "../lib/archive.mjs";
import * as cdimage from "../lib/cdimage.mjs";
import * as file from "../lib/file.mjs";
import * as msg from "../lib/msg_script.mjs";

export const command = [`extract_battle_strings start [end]`];
export const desc = "Extract battle strings from files start..end";
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

let search_for_string_table = (buff) => {
  let ptr = 0;
  let tables = [];
  if(buff[0] != 8) {
      return [];
  }
  let string_ptr = buff.readUInt16LE(6);
  let table_ptr = buff.readUInt16LE(4);
  let table_start = table_ptr;
  let table_end = string_ptr;
  let strings = [];
  while (table_ptr < table_end) {
      strings.push(msg.parse(buff, string_ptr + buff.readUInt16LE(table_ptr), true));
      table_ptr+= 2;
  }
  return [{strings, table_start, string_ptr}];
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
        if(f[0]==1 && f[8]==8 && f[1] != 0) {
            // compressed battle strings - skip for now
            return;
        }
      
      //console.log(f);
      let res = search_for_string_table(f.slice(8));
      if (res) {
          //console.log(res);
        res.forEach((t, k) => {
          t.file = i;
          t.file_num = o;
          let len = (t.strings.length) * 2;
          t.strings.forEach((line) => { if (line) len += msg.calculate_dialog_length(line); });
          t.max_len = len;
          fs.writeFileSync(
            `${argv.out}/${i}_${o}_${k}.json`,
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
