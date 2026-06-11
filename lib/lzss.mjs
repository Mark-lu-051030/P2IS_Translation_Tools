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
  let max_len = Math.min(130, input.byteLength - iptr);  // ⭐ 130=格式上限((byte&0x7f)+3)
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
  let max_len = Math.min(130, input.byteLength - iptr);  // ⭐ 130=格式上限((byte&0x7f)+3)
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

// 最优解析压缩器（DP）。token 格式与 compress/decompress 完全一致（游戏可解），
// 但用动态规划求全局最小字节数，而非贪心。比原版游戏压缩器更紧或持平，
// 故重压不改数据时 ≤ 原大小（贪心版会胀 ~0.4%）。
// 代价模型：literal run k(1..128)=1+k 字节覆盖 k 输入；backref L(3..130)=2 字节覆盖 L 输入。
// 边界：source s≥0、offset(=i-s)∈[1,256]、L≤min(130, n-i)——与 find_backref_no0 同约束，
// 保证严格 round-trip（不引用 input 末尾之外 / 负位置）。
export const compress_optimal = (input, header_len = 0) => {
  const n = input.byteLength;
  const cost = new Float64Array(n + 1);
  const chLen = new Int32Array(n + 1);  // >0 = backref 长度; <0 = literal run 长度(取负)
  const chOff = new Int32Array(n + 1);  // backref offset
  cost[n] = 0;
  for (let i = n - 1; i >= 0; i--) {
    let best = Infinity, bLen = 0, bOff = 0;
    // 最长匹配 + 其 offset
    const maxlen = Math.min(130, n - i);
    let lmax = 0, lmaxOff = 0;
    if (maxlen >= 3) {
      const lo = Math.max(0, i - 256);
      for (let s = i - 1; s >= lo; s--) {
        if (input[s] !== input[i]) continue;
        let l = 1;
        while (l < maxlen && input[s + l] === input[i + l]) l++;
        if (l > lmax) { lmax = l; lmaxOff = i - s; if (l === maxlen) break; }
      }
    }
    if (lmax >= 3) {
      for (let L = 3; L <= lmax; L++) {
        const c = 2 + cost[i + L];
        if (c < best) { best = c; bLen = L; bOff = lmaxOff; }
      }
    }
    const kmax = Math.min(128, n - i);
    for (let k = 1; k <= kmax; k++) {
      const c = 1 + k + cost[i + k];
      if (c < best) { best = c; bLen = -k; bOff = 0; }
    }
    cost[i] = best; chLen[i] = bLen; chOff[i] = bOff;
  }
  // 序列化
  const out = [];
  let i = 0;
  while (i < n) {
    const L = chLen[i];
    if (L < 0) {
      const k = -L;
      out.push(k - 1);
      for (let j = 0; j < k; j++) out.push(input[i + j]);
      i += k;
    } else {
      out.push(((L - 3) & 0x7f) | 0x80);
      out.push(chOff[i] - 1);
      i += L;
    }
  }
  const result = Buffer.alloc(header_len + out.length);
  Buffer.from(out).copy(result, header_len);
  return result;
};

// 精确目标大小压缩器：输出恰好 target_total_size 字节（header + payload）。
// 原理：先 DP 得最短流，再把 backref token 展开成 literal run（不改解压输出，只让流变长），
// 精确填满 target_payload 字节——无零填充，tc == r.byteLength == op（枚举+解压都正确）。
// 用途：地图 archive 紧密排列 sub，tc 必须等于原始槽大小，同时不能有尾部零字节。
export const compress_to_size = (input, header_len, target_total_size) => {
  const n = input.byteLength;
  const target_payload = target_total_size - header_len;

  // DP（与 compress_optimal 相同）
  const cost = new Float64Array(n + 1);
  const chLen = new Int32Array(n + 1);
  const chOff = new Int32Array(n + 1);
  cost[n] = 0;
  for (let i = n - 1; i >= 0; i--) {
    let best = Infinity, bLen = 0, bOff = 0;
    const maxlen = Math.min(130, n - i);
    let lmax = 0, lmaxOff = 0;
    if (maxlen >= 3) {
      const lo = Math.max(0, i - 256);
      for (let s = i - 1; s >= lo; s--) {
        if (input[s] !== input[i]) continue;
        let l = 1;
        while (l < maxlen && input[s + l] === input[i + l]) l++;
        if (l > lmax) { lmax = l; lmaxOff = i - s; if (l === maxlen) break; }
      }
    }
    if (lmax >= 3) {
      for (let L = 3; L <= lmax; L++) {
        const c = 2 + cost[i + L];
        if (c < best) { best = c; bLen = L; bOff = lmaxOff; }
      }
    }
    const kmax = Math.min(128, n - i);
    for (let k = 1; k <= kmax; k++) {
      const c = 1 + k + cost[i + k];
      if (c < best) { best = c; bLen = -k; bOff = 0; }
    }
    cost[i] = best; chLen[i] = bLen; chOff[i] = bOff;
  }

  // Token 列表
  const tokens = [];
  for (let i = 0; i < n; ) {
    const L = chLen[i];
    if (L < 0) { tokens.push({t:'L', s:i, n:-L}); i += -L; }
    else        { tokens.push({t:'R', s:i, n:L,  o:chOff[i]}); i += L; }
  }

  // literal cost：ceil(n/128) 个 count 字节 + n 个数据字节
  const litCost = n => Math.ceil(n / 128) + n;

  const min_payload = tokens.reduce((a, t) => a + (t.t === 'L' ? litCost(t.n) : 2), 0);
  if (min_payload > target_payload) return null;

  let gap = target_payload - min_payload;

  // Phase 1：把 backref 展开成 literal（按 extra 升序——方便精细控制）
  const refs = tokens
    .map((t, i) => ({i, extra: litCost(t.n) - 2}))
    .filter(x => tokens[x.i].t === 'R')
    .sort((a, b) => a.extra - b.extra);
  for (const {i, extra} of refs) {
    if (gap <= 0) break;
    if (extra <= gap) { tokens[i].t = 'L'; gap -= extra; }
  }

  // Phase 2：把 literal run 拆分（每次拆出 1 字节独立 run，增加 1 字节），填余下 gap
  const final_tokens = [];
  for (const t of tokens) {
    if (gap > 0 && t.t === 'L' && t.n >= 2 && t.n <= 128) {
      const splits = Math.min(gap, t.n - 1);
      for (let j = 0; j < splits; j++) final_tokens.push({t:'L', s:t.s+j, n:1});
      final_tokens.push({t:'L', s:t.s+splits, n:t.n-splits});
      gap -= splits;
    } else {
      final_tokens.push(t);
    }
  }

  if (gap !== 0) return null; // 不应发生

  // 序列化
  const out = [];
  for (const t of final_tokens) {
    if (t.t === 'R') {
      out.push(((t.n - 3) & 0x7f) | 0x80);
      out.push(t.o - 1);
    } else {
      for (let o = 0; o < t.n; o += 128) {
        const chunk = Math.min(128, t.n - o);
        out.push(chunk - 1);
        for (let j = 0; j < chunk; j++) out.push(input[t.s + o + j]);
      }
    }
  }

  if (out.length !== target_payload) return null;

  const result = Buffer.alloc(header_len + target_payload);
  Buffer.from(out).copy(result, header_len);
  return result;
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
