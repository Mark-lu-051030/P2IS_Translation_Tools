const DEBUG_SCRIPT = true;
export const decompress = (input, ptr, compressed_size, uncompressed_size) => {
  let off = ptr;
  if (
    compressed_size == 0 ||
    uncompressed_size == 0 ||
    compressed_size > uncompressed_size
  ) {
    console.error(`Invalid compressed data at ${off}`);
    return null;
  }
  if (DEBUG_SCRIPT)
    console.log(
      `Trying to decompress LZSS encoded data ${compressed_size}->${uncompressed_size} at ${off}`
    );
  let output = Buffer.allocUnsafe(uncompressed_size);
  let optr = 0;
  while (optr < uncompressed_size) {
    if ((input[ptr] & 0x80) == 0x80) {
      let count = (input[ptr++] & 0x7f) + 3;
      let offset = input[ptr++] + 1;

      let s = optr - offset;
      if (s < 0) {
        console.log(`Going before 0 ${s}`);
        let c = -s;
        c = Math.min(c, count);
        output.fill(0, optr, optr + c);
        optr += c;
        count -= c;
        s += c;
      }
      //   while (s < 0 && count > 0) {
      //     output[optr++] = 0;
      //     s++;
      //     count--;
      //   }
      if (count) {
        if (s + count < optr) {
          output.copy(output, optr, s, s + count);
          optr += count;
        } else {
          while (count--) output[optr++] = output[s++];
        }
      }
    } else {
      let count = input[ptr++] + 1;
      input.copy(output, optr, ptr, ptr + count);
      optr += count;
      ptr += count;
      //while (count--) output[optr++] = input[ptr++];
    }
    // console.log(optr, ptr);
  }
  if (optr != uncompressed_size || ptr - off != compressed_size) {
    console.error(
      `LZSS Decompression failed at ${off}: expected ${
        ptr - off
      }=${compressed_size} and ${optr}=${uncompressed_size}`
    );
  }
  return output;
};

// 关键修复 (2026-05-23)：max_len 限制 backref 不匹配 input 末尾之外。
// 原版会匹配 "data + 隐式零" 产生越界 backref；游戏解码器宽容（写超长被静默忽略），
// 但 Python 严格解压器会 IndexError。修后输出对游戏行为不变，但严格 round-trip 可用。
let find_backref_no0 = (input, iptr) => {
  let best = {
    offset: 0,
    length: 1,
  };
  let getc = (iptr) => (iptr < 0 ? 0 : input[iptr]);
  let c = getc(iptr);
  let max_len = Math.min(128, input.byteLength - iptr);  // ⭐
  if (max_len < 2) return best;
  for (let s = iptr - 1; s > iptr - 256; s--) {
    if(s < 0) break;
    if (getc(s) == c) {
      let i = 1;
      for (; i < max_len; i++) {
        if (getc(s + i) != input[iptr + i]) break;
      }
      if (i > 2) {
        if (best.length < i) {
          best.type = "backref";
          best.offset = iptr - s;
          best.length = i;
        }
      }
    }
  }
  return best;
}

let find_backref = (input, iptr) => {
  let best = {
    offset: 0,
    length: 1,
  };
  let getc = (iptr) => (iptr < 0 ? 0 : input[iptr]);
  let c = getc(iptr);
  let max_len = Math.min(128, input.byteLength - iptr);  // ⭐
  if (max_len < 2) return best;
  for (let s = iptr - 1; s > iptr - 256; s--) {
    if (getc(s) == c) {
      let i = 1;
      for (; i < max_len; i++) {
        if (getc(s + i) != input[iptr + i]) break;
      }
      if (i > 2) {
        if (best.length < i) {
          best.type = "backref";
          best.offset = iptr - s;
          best.length = i;
        }
      }
    }
  }
  return best;
};

export const compress = (input, header_len, no0) => {
  let output = Buffer.allocUnsafe(input.byteLength + header_len);
  
  let uncompressed_size = input.byteLength;
  let optr = header_len;
  let iptr = 0;

  let backref = find_backref_no0;
  //if(no0) backref = find_backref_no0;

  while (iptr < uncompressed_size) {
    let best = backref(input, iptr);
    if (best.length == 1) {
      //uncompressed, let's see how many bytes we need to take
      let len = 1;
      while (
        iptr + len < uncompressed_size &&
        len < 128 &&
        backref(input, iptr + len).length == 1
      )
        len++;
      output[optr++] = len - 1;
      for (let i = 0; i < len; i++) {
        output[optr++] = input[iptr++];
      }
      //output.set(input.slice(iptr, iptr + len), optr + 1);
      //iptr += len;
    } else {
      output.writeUInt8((best.length - 3) | 0x80, optr++);
      output.writeUInt8(best.offset - 1, optr++);
      iptr += best.length;
    }
  }
  return output.slice(0, optr);
};
