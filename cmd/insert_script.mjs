import * as fs from "fs";
import * as archive from "../lib/archive.mjs";
import * as cdimage from "../lib/cdimage.mjs";
import * as file from "../lib/file.mjs";
import * as msg from "../lib/msg_script.mjs";
import * as scene from "../lib/scene_script.mjs";
import * as lzss from "../lib/lzss.mjs";

import * as pt from "../lib/locale/pt.mjs";

let locales = {
  pt,
};

export const command = [`insert_script [files..]`];
export const desc = "Reinsert script";
export const builder = {
  files: {
    demandOption: true,
    type: "array",
  },
  lang: {
    default: "en",
  },
};

export const handler = async (argv) => {
  console.log(argv.files);
  let cd = await cdimage.init();
  let group = {};
  let group_ids = [];
  for (let i = 0; i < argv.files.length; i++) {
    let name = argv.files[i];
    console.log(`Processing ${name}`);
    let file = JSON.parse(fs.readFileSync(name));

    if (locales[argv.lang]) {
      let locale = locales[argv.lang];
      file.dialog_order.forEach((d) => {
        for (let i = 0; i < file.dialogs[d].length; i++) {
          if (typeof file.dialogs[d][i] === "string") {
            file.dialogs[d][i] = file.dialogs[d][i]
              .split("")
              .map((a) => {
                if (locale.char_map[a]) {
                  return locale.char_map[a];
                }
                return a;
              })
              .join("");
            // console.log(file.dialogs[d][i]);
          }
        }
      });
    }

    let compiled = scene.compile_script(file);
    let compressed = lzss.compress(compiled, 0xc, true);

    compressed.writeUInt32LE(0x101, 0);
    compressed.writeUInt32LE(compressed.byteLength, 4);
    compressed.writeUInt32LE(compiled.byteLength, 8);
    if (!group[file.file]) {
      group[file.file] = [];
      group_ids.push(file.file);
    }
    group[file.file].push([compressed, file.file_num]);
    // fs.writeFileSync(`${file.file}_${file.file_num}.bin`, compiled);
  }
  for (let i = 0; i < group_ids.length; i++) {
    let file = group_ids[i];
    let arch = await cdimage.read_file(cd, file);
    let files = archive.extract_files(arch);
    console.log(`Processing file ${file}`);

    // Check if archive uses sector-alignment padding (type=0 entries).
    // If so, use in-place patching to preserve original sub-file sector positions.
    let has_sector_padding = false;
    {
      let p = 0;
      while (p < arch.byteLength) {
        let t = arch[p];
        if (t === 0) { has_sector_padding = true; break; }
        let l = arch.readUInt32LE(p + 4);
        if (l === 0) break;
        p += l;
        while (p & 3) p++;
      }
    }

    let new_arch;
    if (has_sector_padding) {
      // Build replacements map: sub-file index → new buffer (with header field copied)
      let replacements = {};
      group[file].forEach(([buff, id]) => {
        buff.writeUInt16LE(files[id].readUInt16LE(2), 2); //copy whatever that is
        replacements[id] = buff;
      });
      new_arch = archive.patch_archive_inplace(arch, replacements);
      console.log(`File ${file}: in-place patch, archive stays ${new_arch.byteLength} bytes`);
    } else {
      group[file].forEach(([buff, id]) => {
        buff.writeUInt16LE(files[id].readUInt16LE(2), 2); //copy whatever that is
        files[id] = buff;
      });
      new_arch = archive.build_archive(files, file);
      if (new_arch.byteLength > arch.byteLength) {
        throw new Error(`File ${file}: new archive ${new_arch.byteLength} bytes exceeds original ${arch.byteLength} bytes — text too long, aborting`);
      }
    }

    if (file == 735) {
      console.log(`Patching dungeon EXE table`);
      let ptr = 0;
      console.log(`${files.length}`);
      let exe = await cdimage.read_file(cd, 736);
      let off = 0x1afcc;
      for (let i = 0; i < files.length; i++) {
        let sector = Math.floor(ptr / 0x800);
        let sector_off = ptr & 0x7ff;
        exe.writeUInt16LE(sector, off + 2);
        exe.writeUInt16LE(sector_off, off);
        // console.log(files[i], i);
        exe.writeUInt32LE(files[i].byteLength, off + 4);
        off += 8;
        ptr += files[i].byteLength;
        while (ptr & 3) ptr++;
        if (0x800 - (ptr & 0x7ff) < 0x10) {
          ptr += 0x800 - (ptr & 0x7ff);
        }
      }
      await cdimage.write_file(cd, 736, exe);
    }

    // continue;
    // fs.writeFileSync(`${file}.bin`, new_arch);
    await cdimage.write_file(cd, file, new_arch);

    // let buff = Buffer.alloc(file.max_len);
    // let ind_ptr = 4;
    // let str_ptr = file.strings.length * 4 + 4;
    // buff.writeUInt32LE(0, file.strings.length);
    // file.strings.forEach((str) => {
    //   buff.writeUInt32LE(str_ptr, ind_ptr);
    //   ind_ptr += 4;
    //   str_ptr += msg.compile_msg(str, buff, str_ptr);
    // });
    // // console.log(buff);
    // console.log(file.max_len - str_ptr);
    // //continue;

    // let file_buff = await cdimage.read_file(cd, file.file);
    // let files = archive.extract_files(file_buff);

    // buff.copy(files[file.file_num], file.offset);
    // //   files[file.file_num]. = buff;
    // let res = archive.build_archive(files);
    // console.log(res);
    // await cdimage.write_file(cd, file.file, res);
  }

  //   if (!fs.existsSync(argv.out)) fs.mkdirSync(argv.out);
  //   for (let i = start; i <= end; i++) {
  //     console.log(`${i}`);
  //     // if (!fs.existsSync(`${argv.out}/${i}/`)) fs.mkdirSync(`${argv.out}/${i}/`);
  //     let file_buff = await cdimage.read_file(cd, i);

  //     let files = archive.extract_files(file_buff);
  //     files.forEach((f, o) => {
  //       console.log(f);
  //       let res = search_for_string_table(f);
  //       if (res) {
  //         res.forEach((t, k) => {
  //           t.file = i;
  //           t.file_num = o;
  //           let len = (t.strings.length + 1) * 4;
  //           t.strings.forEach(
  //             (line) => (len += msg.calculate_dialog_length(line))
  //           );
  //           t.max_len = len;
  //           fs.writeFileSync(
  //             `${argv.out}/${i > 0 ? i : "SLUS"}_${o}_${k}.json`,
  //             JSON.stringify(t, null, 4)
  //           );
  //         });
  //       }
  //       //   let res = file.parseFile(f);
  //       //   if (res) fs.writeFileSync(`${argv.out}/${i}_${o}.${res.type}`, res.data);
  //     });
  //   }
  cdimage.close(cd);
};
