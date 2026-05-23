const DEBUG_SCRIPT = false;

let archive_type = {
  13: {
    pad_each: true,
  },
  36: {
    pad_after_files: [0, 2, 4,6],
  },
  49: {
    group_files: 4,
  },
  50: {
    group_files: 2,
  },
  51: {
    pad_each: true,
  },
  52: {
    pad_each: true,
  },
  55: {
    pad_each: true,
  },
  56: {
    pad_on_change_to: 0x02,
  },
  514: {
    group_files: 2,
  },
  516: {
    pad_each: true,
  },
  682: {
    pad_each: true,
  },
  685: {
    pad_each: true,
  },
  686: {
    group_files: 2,
  },
  699: {
    group_files: 2,
  },
  700: {
    group_files: 2,
  },
  701: {
    group_files: 1,
  },
  702: {
    group_files: 1,
  },
  713: { group_files: 1 },
  714: { group_files: 1 },
  715: { group_files: 1 },
  716: { group_files: 1 },
  717: { group_files: 1 },
  718: { group_files: 1 },
  719: { group_files: 1 },
  720: { group_files: 1 },
  724: { group_files: 1 },
  725: { group_files: 1 },
  726: { group_files: 1 },
  729: { group_files: 1 },
  792: { group_files: 1 },
  793: { group_files: 1 },
  796: { group_files: 1 },
  797: { pad_after_files: [0, 1, 2, 59] },
  798: { group_files: 4 },
  799: { group_files: 1 },
  833: { group_files: 1 },
  834: { pad_subfile:true },
  842: { group_files: 2 },
  843: { group_files: 2 },
  849: { group_files: 1 },
  850: { group_files: 1 },
  852: { group_files: 2 },
  853: { group_files: 8 },
  861: { group_files: 1 },
};

export function extract_files(buff) {
  let ptr = 0;
  if (buff[0] > 0x3 || buff[0] == 0) {
    console.log(`Assuming single file`);
    return [buff];
  }
  let results = [];
  while (ptr < buff.byteLength) {
    let type = buff[ptr];
    if (type == 0) {
      //assume we need to seek to the end of the sector
      if (buff.readUInt32LE(ptr) != 0) return null;
      let orig = ptr;
      if (ptr & 0x7ff) {
        ptr += 0x7ff;
        ptr &= ~0x7ff;
      } else {
        ptr += 0x800;
      }
      if (DEBUG_SCRIPT)
        if (ptr != buff.byteLength)
          console.log(
            `Skipping ${ptr - orig} bytes at end of sector (${orig.toString(
              16
            )}) at file ${results.length}: ${ptr.toString(16)}.`
          );
      while (orig < ptr) {
        if (buff[orig++] != 0) {
          console.error(
            `Unexpected data at end of sector at ${(orig - 1).toString(16)}`
          );
          return null;
        }
      }
      continue;
    }
    let len = buff.readUInt32LE(ptr + 4);
    if (len == 0) {
      console.error(
        `Unexpectedly found length 0 at ${ptr.toString(16)} file ${
          results.length
        }.  Aborting.`
      );
      return [buff];
    }
    if(buff.readUInt16LE(ptr+2)!=0) {
      // console.log(`${results.length} ${ptr.toString(16)} ${buff.readUInt16LE(ptr+2)}`);
    }
    if (DEBUG_SCRIPT)
      if (buff[0] != 0x2 && buff.readUInt16LE(ptr + 2) != 0) {
        console.log(
          `Unexpected ${buff.readUInt16LE(ptr + 2)} at ${ptr.toString(
            16
          )}.  Type: ${buff[0]} ${buff[1]}`
        );
      }
    results.push(buff.slice(ptr, ptr + len));
    ptr += len;
    while (ptr & 3) ptr++; //skip to next word
  }
  return results;
}

/**
 * Replace sub-files in-place, preserving original archive size and sector layout.
 * replacements: Map of { sub_file_index → new_buffer }
 * Each new buffer must fit within the original sub-file's padded sector space.
 */
export function patch_archive_inplace(original, replacements) {
  let result = Buffer.from(original); // copy original
  let ptr = 0;
  let idx = 0;

  while (ptr < original.byteLength) {
    let type = original[ptr];
    if (type === 0) {
      ptr += 0x7ff;
      ptr &= ~0x7ff;
      continue;
    }
    let len = original.readUInt32LE(ptr + 4);
    if (len === 0) break;

    let sub_start = ptr;
    ptr += len;
    while (ptr & 3) ptr++;

    // Find the end of the padded space for this sub-file (where next sub-file or archive end)
    let padded_end = ptr;
    if (ptr < original.byteLength && original[ptr] === 0) {
      padded_end += 0x7ff;
      padded_end &= ~0x7ff;
    }

    if (replacements[idx] !== undefined) {
      let new_buf = replacements[idx];
      let available = padded_end - sub_start;
      if (new_buf.byteLength > available) {
        throw new Error(
          `Sub-file ${idx}: replacement ${new_buf.byteLength} bytes exceeds available space ${available} bytes`
        );
      }
      // Zero the whole padded space, then write new sub-file
      result.fill(0, sub_start, padded_end);
      new_buf.copy(result, sub_start);
    }

    if (ptr < original.byteLength && original[ptr] === 0) {
      ptr += 0x7ff;
      ptr &= ~0x7ff;
    }
    idx++;
  }
  return result;
}

export function extract_file_offsets(buff) {
  let ptr = 0;
  if (buff[0] > 0x3 || buff[0] == 0) {
    console.log(`Assuming single file`);
    return [buff];
  }
  let results = [];
  while (ptr < buff.byteLength) {
    let type = buff[ptr];
    if (type == 0) {
      //assume we need to seek to the end of the sector
      if (buff.readUInt32LE(ptr) != 0) return null;
      let orig = ptr;
      if (ptr & 0x7ff) {
        ptr += 0x7ff;
        ptr &= ~0x7ff;
      } else {
        ptr += 0x800;
      }
      if (DEBUG_SCRIPT)
        if (ptr != buff.byteLength)
          console.log(
            `Skipping ${ptr - orig} bytes at end of sector (${orig.toString(
              16
            )}) at file ${results.length}: ${ptr.toString(16)}.`
          );
      while (orig < ptr) {
        if (buff[orig++] != 0) {
          console.error(
            `Unexpected data at end of sector at ${(orig - 1).toString(16)}`
          );
          return null;
        }
      }
      continue;
    }
    let len = buff.readUInt32LE(ptr + 4);
    if (len == 0) {
      console.error(
        `Unexpectedly found length 0 at ${ptr.toString(16)} file ${
          results.length
        }.  Aborting.`
      );
      return [buff];
    }
    if(buff.readUInt16LE(ptr+2)!=0) {
      // console.log(`${results.length} ${ptr.toString(16)} ${buff.readUInt16LE(ptr+2)}`);
    }
    if (DEBUG_SCRIPT)
      if (buff[0] != 0x2 && buff.readUInt16LE(ptr + 2) != 0) {
        console.log(
          `Unexpected ${buff.readUInt16LE(ptr + 2)} at ${ptr.toString(
            16
          )}.  Type: ${buff[0]} ${buff[1]}`
        );
      }
    // results.push(buff.slice(ptr, ptr + len));
    results.push(ptr);
    ptr += len;
    while (ptr & 3) ptr++; //skip to next word
  }
  return results;
}

export function build_archive(files, num) {
  let len = 0;
  let info = archive_type[num] ?? {
    pad_each: false,
    pad_audio: false,
  };

  let pad_segment = (i, subfile_ind, this_subfile_ind) => {
    let offset = info.file_offset??0;
    i+= offset;
    if (info.pad_after_files && info.pad_after_files.indexOf(i) != -1)
      return true;
    if (info.group_files && i % info.group_files == info.group_files - 1)
      return true;
    if (info.pad_on_change_to) {
      let n = i + 1;
      if (n < files.length) {
        return (
          files[n][0] == info.pad_on_change_to && files[n][0] != files[i][0]
        );
      }
    }
    if(info.pad_subfile) {
      if(subfile_ind > this_subfile_ind) return true;
    }
    return info.pad_each || (info.pad_audio && files[i][0] == 0x03);

  };

  let subfile_ind = 0;

  for (let i = 0; i < files.length; i++) {
    if (0x800 - (len & 0x7ff) < 0x10) {
      len += 0x800 - (len & 0x7ff);
      //   console.log(`adding end of sector space`);
    }

    while (len & 3) len++;
    len += files[i].byteLength;
    if (pad_segment(i)) {
      if ((len & 0x7ff) != 0) {
        len += 0x800 - (len & 0x7ff);
      }
    }
  }
  // if (pad_length && (len & 0x7ff) != 0) {
  //   len += 0x800 - (len & 0x7ff);
  // }
  let output = Buffer.alloc(len);
  let ptr = 0;
  for (let i = 0; i < files.length; i++) {
    while (ptr & 3) ptr++;
    if (0x800 - (ptr & 0x7ff) < 0x10) {
      console.log(
        `adding end of sector space ${0x800 - (ptr & 0x7ff)} ${ptr.toString(
          16
        )}`
      );
      ptr += 0x800 - (ptr & 0x7ff);
    }
    // console.log(ptr.toString(16));
    files[i].copy(output, ptr);
    let this_subfile_ind = files[i].readUInt16LE(2);
    ptr += files[i].byteLength;

    if (pad_segment(i, subfile_ind, this_subfile_ind)) {
      if ((ptr & 0x7ff) != 0) {
        ptr += 0x800 - (ptr & 0x7ff);
      }
      // console.log(`Padding at file ${i+1} ${ptr.toString(16)}`);
    }
    subfile_ind= this_subfile_ind;
  }
  return output;
}
