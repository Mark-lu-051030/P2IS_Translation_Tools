import * as fs from "fs";
import * as archive from "../lib/archive.mjs";
import * as cdimage from "../lib/cdimage.mjs";
import * as file from "../lib/file.mjs";
import * as scene_script from "../lib/scene_script.mjs";

export const command = [`extract_script start [end]`];
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
    description: "Last file to extract.  If absent only one file is extracted."
    //demandOption: false,
  },
};
export const handler = async (argv) => {
  let start = argv.start ;
  let end = argv.end ?? argv.start;
  let cd = await cdimage.init_readonly();  // 强制从 iso_backup 读，防止从被改的 live ISO 反向污染
  if (!fs.existsSync(argv.out)) fs.mkdirSync(argv.out);
  for (let i = start; i <= end; i++) {
    console.log(`${i}`);
    let file_buff = await cdimage.read_file(cd, i);

    

    let files = archive.extract_files(file_buff);
    files.forEach((f, o) => {
      let res;
      try {
        res = file.parseFile(f);
      } catch (e) {
        console.log(`  skip ${i}_${o}: ${e.message}`);
        return;
      }
      if (res && res.type == "script") {
        console.log(f[0],f[1]);
        console.assert(f[1]==2, `LZSS aoeu`);
        let script = scene_script.parse_script(res.data);
        script.file = i;
        script.file_num = o;
        fs.writeFileSync(`${argv.out}/${i}_${o}.json`, JSON.stringify(script, null, 2));
      }
    });
  }
};
