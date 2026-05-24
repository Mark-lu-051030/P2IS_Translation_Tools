import * as fs from "fs";

let font_file = fs.readFileSync("test_dir/f13/0000.bin");

console.log(font_file);

//0x480 2x12
//the rest 3x6

let lower = font_file.slice(0, 0x480);
let upper = font_file.slice(0x480);

let lower_count = 0x480 / 0xc;
let lower_width = 2 * 2;

let upper_width = 3 * 2;

console.log(lower_count);
let chars_per_row = 8;
let height = 0x12;
let rows = lower_count / chars_per_row;




let gen_file = (buff, width) => {
  let height = (buff.byteLength * 8) / width;
  let ptr = 0;
  let img = [`P2\n${width} ${height}\n1`];
  while (ptr < buff.byteLength) {
    let c = buff[ptr++];
    for (let i = 0; i < 8; i++) {
      img.push(c & 1);
      c >>= 1;
    }
  }
  return img;
};

let other_file = fs.readFileSync("test_dir/f13/1000.bin");

fs.writeFileSync("font0.pgm", gen_file(lower, 8).join("\n"));
fs.writeFileSync("font1.pgm", gen_file(upper, 12).join("\n"));
fs.writeFileSync(
  "font2.pgm",
  gen_file(other_file.slice(0, 0x480), 8).join("\n")
);
fs.writeFileSync("font3.pgm", gen_file(other_file.slice(0x480), 12).join("\n"));

// let img = [`P2\n${8} ${0x60}\n1\n`];

// let ptr = 0;
// while (ptr < lower.byteLength) {
//   for (let k = 0; k < 12; k++) {
//     let c = lower[ptr++];
//     let mask = 8;
//     while (mask-- > 0) {
//       img.push((c >> (8 - mask)) & 1);
//     }
//   }
// }

// fs.writeFileSync(`font0.pgm`, img.join("\n"));

// {
//   let upper_count = upper.byteLength / 0x12;
//   let rows = upper_count / chars_per_row;
//   let img = [`P2\n${3 * 2 * 2} ${upper.byteLength / 3}\n1\n`];

//   let ptr = 0;
//   while (ptr < upper.byteLength) {
//     let c = upper[ptr++];
//     let mask = 8;
//     while (mask-- > 0) {
//       img.push(c & 1);
//       c >>= 1;
//     }
//   }

//   fs.writeFileSync(`font1.pgm`, img.join("\n"));
// }

// let other_file = fs.readFileSync("test_dir/f13/1000.bin");
// {
//   let buff = other_file.slice(0, 0x480);
//   let width = 8;
//   let height = buff.byteLength / width;
//   let img = [`P2\n${width} ${height}\n1\n`];

//   let ptr = 0;
//   while (ptr < buff.byteLength) {
//     let c = buff[ptr++];
//     let mask = 8;
//     while (mask-- > 0) {
//       img.push(c & 1);
//       c >>= 1;
//     }
//   }
//   fs.writeFileSync(`font2.pgm`, img.join("\n"));
// }

// {
//   let buff = other_file.slice(0x480);
//   let width = 12;
//   let height = buff.byteLength / width;
//   let img = [`P2\n${width} ${height}\n1\n`];

//   let ptr = 0;
//   while (ptr < buff.byteLength) {
//     let c = buff[ptr++];
//     let mask = 8;
//     while (mask-- > 0) {
//       img.push(c & 1);
//       c >>= 1;
//     }
//   }
//   fs.writeFileSync(`font3.pgm`, img.join("\n"));
// }
