import * as fs from "fs";
import * as archive from "../lib/archive.mjs";
import * as cdimage from "../lib/cdimage.mjs";
import * as file from "../lib/file.mjs";
import * as msg from "../lib/msg_script.mjs";

export const command = [`extract_f35`];
export const desc = "Extract scripts from files f35";
export const builder = {
  out: {
    alias: "o",
    default: ".",
  },
};
export const handler = async (argv) => {
  let start = argv.start;
  let end = argv.end ?? argv.start;
  let cd = await cdimage.init_readonly();
  if (!fs.existsSync(argv.out)) fs.mkdirSync(argv.out);
  let strings = [];
  let file_buff = await cdimage.read_file(cd, 35);

  let files = archive.extract_files(file_buff);
  files.forEach((f, o) => {
    if (f.readUInt16LE(2) != 0) {
      console.log(`Unexpected at ${o}`);
    }
    let res = file.parseFile(f);
    console.log(res);
    strings.push(msg.parse(res.data, 0));
  });
  fs.writeFileSync(
    `${argv.out}/35.json`,
    JSON.stringify({
      file: 35,
      strings,
    }, null, '\t')
  );
};
