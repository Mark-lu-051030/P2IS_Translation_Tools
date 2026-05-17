import { decompress as lzss_decompress } from "./lzss.mjs";
import { decompress as rle_decompress } from "./rle.mjs";

const null_decompress = (buff, ptr, compressed_size, uncompressed_size) => {
  console.assert(
    buff.byteLength == compressed_size + ptr,
    `Expected buffer to be ${compressed_size + ptr} got ${buff.byteLength}`
  );
  let res = Buffer.alloc(compressed_size);
  buff.copy(res, 0, ptr);
  return res; //TODO: can't I just return the original buffer?
};

const FILE_OTHER = 1;
const FILE_IMAGE = 2;
const FILE_AUDIO = 3;

const COMPRESSION_NULL = 0;
const COMPRESSION_RLE = 1;
const COMPRESSION_LZSS = 2;

const compression_types = {
  [COMPRESSION_NULL]: {
    decompress: null_decompress,
  },
  [COMPRESSION_RLE]: {
    decompress: rle_decompress,
  },
  [COMPRESSION_LZSS]: {
    decompress: lzss_decompress,
  },
};

let read_cstr = (buff) => {
  buff.toString();
  let end = buff.indexOf(0);
  buff.toString("ascii", 0, end); //utf-8?  who knows
};

function check_TIM(buff) {
  if (buff.byteLength < 20) return false;
  if (buff.readUInt32LE(0) != 0x10) return false;
  //possibly a TIM, let's check!
  let hdr2 = buff.readUInt32LE(4);
  if ((hdr2 & ~0b1011) != 0) return false;
  return true;
  //this seems too restrictive, unsure why
  let len = buff.readUInt32LE(8);
  let w = buff.readUInt16LE(12);
  let h = buff.readUInt16LE(14);

  if ((hdr2 & 0b1000) != 0) {
    //CLUT present
    if (len != w * h * 2) return false;
    return true;
  }
  if (w > 1024 || h > 1024) return false;
  //this is *probably* good enough
  switch (hdr2 & 0x3) {
    case 0:
      if (len != (w * h) / 2) return false;
      break;
    case 1:
      if (len != w * h) return false;
      break;
    case 2:
      if (len != w * h * 2) return false;
    case 3:
      if (len != w * h * 3) return false;
  }
  return true;
}

function check_SMD(buff) {
  let ind = buff.indexOf("smd");
  if (ind > 0 && ind < 0x10) return true;
  return false;
}

function check_script(buff) {
  //TODO: maybe just check the first two words are 0x18 first
  if (buff.byteLength < 0x8) return false;
  let ind = buff.indexOf("START");
  if (ind == buff.readUInt32LE(0) || ind == buff.readUInt32LE(4)) return true;
  return false;
}

const filetypes = [
  {
    type: "tim",
    check: check_TIM,
  },
  {
    type: "smd",
    check: check_SMD,
  },
  {
    type: "script",
    check: check_script,
  },
];

export function parseFile(buff) {
  switch (buff[0]) {
    case FILE_OTHER:
      {
        let compression = compression_types[buff[1]];
        if (!compression) return null;
        let compressed_size = buff.readUInt32LE(4) - 0xc;
        let uncompressed_size = buff.readUInt32LE(8);
        let unk2 = buff.readUInt16LE(2);
        let off = 0xc;
        if (buff[1] == 0) {
          compressed_size += 4;
          off -= 4;
        }
        let res = compression.decompress(
          buff,
          off,
          compressed_size,
          uncompressed_size
        );
        if (res) {
          //figure out file type
          let type = filetypes.find((a) => a.check(res));
          if (type) {
            return {
              type: type.type,
              data: res,
              unk2,
            };
          }
        }
        return {
          unk2,
          data: res,
          type: "unknown",
        };
      }
      break;
    case FILE_IMAGE: {
      let compression = compression_types[buff[1]];
      if (!compression) return null;
      if (buff.byteLength < 16) return null;
      let x = buff.readUInt16LE(8);
      let y = buff.readUInt16LE(10);
      let w = buff.readUInt16LE(12);
      let h = buff.readUInt16LE(14);
      let compressed_size = buff.readUInt32LE(4) - 0x10;
      let uncompressed_size = w * h * 2;
      let unk2 = buff.readUInt16LE(2);
      let res = compression.decompress(
        buff,
        0x10,
        compressed_size,
        uncompressed_size
      );
      //   if (buff[1] == 0) {
      //     console.log(`${compressed_size} ${uncompressed_size}`);
      //   }
      return {
        data: buff,
        type: "image",
        w,
        h,
        x,
        y,
        unk2,
      };
    }
    case FILE_AUDIO:
      //audio preserves unk2 so no need to worry about it.
      return {
        data: buff,
        type: "audio",
      };
  }
}
