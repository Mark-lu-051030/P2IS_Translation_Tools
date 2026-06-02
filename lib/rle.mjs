const DEBUG_SCRIPT = false;
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
      `Trying to decompress RLE encoded data ${compressed_size}->${uncompressed_size} at ${off}`
    );
  let output = Buffer.allocUnsafe(uncompressed_size);
  let optr = 0;
  while (optr < uncompressed_size && ptr - off < compressed_size) {
    if ((input[ptr] & 0x80) == 0x80) {
      let count = (input[ptr++] & 0x7f) + 3;
      let char = input[ptr++];

      //while (count--) output[ptr++] = char;
      output.fill(char, optr, optr + count);
      optr += count;
    } else {
      let count = input[ptr++] + 1;
      if (isNaN(count)) {
        console.log(ptr - 1);
      }
      input.copy(output, optr, ptr, ptr + count);
      optr += count;
      ptr += count;
      //while (count--) output[optr++] = input[ptr++];
    }
  }
  if (optr != uncompressed_size || ptr - off != compressed_size) {
    console.error(
      `RLE Decompression failed at ${off}: expected ${
        ptr - off
      }=${compressed_size} and ${optr}=${uncompressed_size}`
    );
  }
  return output;
};

// RLE 压缩（与上面 decompress 的 token 格式严格对应）：
//   - run:     [0x80 | (count-3)][char]   count = 3..130 个相同字节
//   - literal: [count-1][...bytes]        count = 1..128 个原样字节（长度字节高位必须为 0）
// 调用约定与 lzss.compress 一致：前 header_len 字节留空（apply 写 tag/len/uncomp）。
// 已用 file 4 全部 102 个 RLE sub 验证往返一致。
export const compress = (input, header_len = 0) => {
  const n = input.byteLength;
  // 最坏情况（不可压数据）≈ 每 128 字节多 1 字节头，留足余量
  const output = Buffer.allocUnsafe(n + (n >> 6) + header_len + 64);
  let optr = header_len;
  let iptr = 0;
  while (iptr < n) {
    // 统计 iptr 处相同字节游程（上限 130）
    let run = 1;
    while (iptr + run < n && input[iptr + run] === input[iptr] && run < 130) run++;
    if (run >= 3) {
      output[optr++] = ((run - 3) | 0x80);
      output[optr++] = input[iptr];
      iptr += run;
    } else {
      // literal：收到某处起出现 ≥3 游程、或满 128、或到末尾为止
      let len = 0;
      while (iptr + len < n && len < 128) {
        if (
          iptr + len + 2 < n &&
          input[iptr + len] === input[iptr + len + 1] &&
          input[iptr + len] === input[iptr + len + 2]
        ) break;
        len++;
      }
      output[optr++] = len - 1;
      for (let i = 0; i < len; i++) output[optr++] = input[iptr++];
    }
  }
  return output.slice(0, optr);
};
