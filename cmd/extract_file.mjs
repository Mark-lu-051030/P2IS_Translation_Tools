import * as fs from "fs";
import * as archive from "../lib/archive.mjs";
import * as cdimage from "../lib/cdimage.mjs";
import * as file from "../lib/file.mjs";

export const command = [`extract_file start [end]`];
export const desc = "Extract scripts from files start..end";
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
export const handler = async (argv) => {
  let start = argv.start;
  let end = argv.end ?? argv.start;
  let cd = await cdimage.init_readonly();
  if (!fs.existsSync(argv.out)) fs.mkdirSync(argv.out);
  for (let i = start; i <= end; i++) {
    console.log(`${i}`);
    if (!fs.existsSync(`${argv.out}/${i}/`)) fs.mkdirSync(`${argv.out}/${i}/`);
    let file_buff = await cdimage.read_file(cd, i);

    let files = archive.extract_files(file_buff);
    files.forEach((f, o) => {
      let res = file.parseFile(f);
      if (i == 860 && o == 0) {
        let arch = archive.extract_files(res.data);
        arch.forEach((a, p) => {
          let data = file.parseFile(a);
          fs.writeFileSync(`${argv.out}/${i}/${o}/${p}.${data.type}`, data.data);
        });
      }
      if (res) fs.writeFileSync(`${argv.out}/${i}/${o}.${res.type}`, res.data);
    });
  }
};
