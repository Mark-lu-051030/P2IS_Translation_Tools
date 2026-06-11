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
// 精确填满压缩(2026-06-10): 压缩到 ≤ 目标后,用**有效 token** 把流撑到恰好 target_total_size,
// 不留零 padding。膨胀手段: ① run(2B) 展开成 literal(1+count B, +count-1) ② literal 拆分(每拆 +1B)。
// 背景: 游戏解码器输入有界(读满 tc-12), 尾部零 padding 会被当 token 解析 → 溢出解压缓冲 → 白屏/卡死
// (LZSS 同款 bug 已在 lzss.compress_to_size 根治; RLE 这份给 apply_zh 的 RLE 剧情/战斗脚本用,
//  Persona 変異/融合白屏即 RLE 文件 tc-padding 嫌疑)。装不下返回 null。
export const compress_to_size = (input, header_len, target_total_size) => {
  const n = input.byteLength;
  const target_payload = target_total_size - header_len;
  // 贪心 token 化(与 compress 相同策略)
  const tokens = [];   // {t:'R', s, n} run / {t:'L', s, n} literal
  let iptr = 0;
  while (iptr < n) {
    let run = 1;
    while (iptr + run < n && input[iptr + run] === input[iptr] && run < 130) run++;
    if (run >= 3) { tokens.push({ t: 'R', s: iptr, n: run }); iptr += run; }
    else {
      let len = 0;
      while (iptr + len < n && len < 128) {
        if (iptr + len + 2 < n && input[iptr + len] === input[iptr + len + 1] && input[iptr + len] === input[iptr + len + 2]) break;
        len++;
      }
      tokens.push({ t: 'L', s: iptr, n: len }); iptr += len;
    }
  }
  const litCost = k => Math.ceil(k / 128) + k;   // literal: 每 128 一个长度字节
  const cost = ts => ts.reduce((a, t) => a + (t.t === 'R' ? 2 : litCost(t.n)), 0);
  let gap = target_payload - cost(tokens);
  if (gap < 0) return null;                       // 贪心已超目标,装不下
  // Phase1: run → literal(膨胀 litCost(n)-2), 从小到大挑 extra ≤ gap 的
  const runs = tokens.map((t, i) => ({ i, extra: litCost(t.n) - 2 })).filter(x => tokens[x.i].t === 'R').sort((a, b) => a.extra - b.extra);
  for (const { i, extra } of runs) {
    if (gap <= 0) break;
    if (extra <= gap) { tokens[i].t = 'L'; gap -= extra; }
  }
  // Phase2: literal 拆分(拆出 1 字节独立 literal, 每次 +1), 填剩余 gap
  const final_tokens = [];
  for (const t of tokens) {
    if (gap > 0 && t.t === 'L' && t.n >= 2 && t.n <= 128) {
      const splits = Math.min(gap, t.n - 1);
      for (let j = 0; j < splits; j++) final_tokens.push({ t: 'L', s: t.s + j, n: 1 });
      final_tokens.push({ t: 'L', s: t.s + splits, n: t.n - splits });
      gap -= splits;
    } else final_tokens.push(t);
  }
  if (gap !== 0) return null;                     // 撑不满(全是 run 且不可拆等极端情况)
  // 序列化
  const out = Buffer.allocUnsafe(target_total_size);
  let optr = header_len;
  for (const t of final_tokens) {
    if (t.t === 'R') { out[optr++] = ((t.n - 3) | 0x80); out[optr++] = input[t.s]; }
    else {
      let done = 0;
      while (done < t.n) {                        // literal 超 128 分段
        const k = Math.min(128, t.n - done);
        out[optr++] = k - 1;
        input.copy(out, optr, t.s + done, t.s + done + k); optr += k;
        done += k;
      }
    }
  }
  if (optr !== target_total_size) return null;    // 防御: 序列化长度必须精确
  return out;
};

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
