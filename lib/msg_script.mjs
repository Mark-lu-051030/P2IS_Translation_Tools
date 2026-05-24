import * as msg from "./msg_commands.mjs";
import { command_lookup } from "./msg_commands.mjs";

// export const parse = (data, off) => {

//   let pages = [];
//   let lines = [];
//   let line = [];

//   let choice_count = 0;
//   //   console.log(`parsing dialog at ${off}`);

//   while (true) {
//     let cmd = data.readUInt16LE(off);
//     off += 2;
//     switch ((cmd >> 12) & 0xf) {
//       default:
//         console.log(
//           `Unknown command type ${cmd.toString(16)} at ${(off - 2).toString(
//             16
//           )}`
//         );
//         break;
//       case 0: //emoji
//         line.push({ emoji: cmd });
//         break;
//       case 1: {
//         let len = (cmd >> 8) & 0xf;
//         let args = [];
//         for (let i = 1; i < len; i++) {
//           args.push(data.readUInt16LE(off));
//           off += 2;
//         }
//         let info = msg.commands[cmd & 0xff];
//         if (info) {
//           console.assert(
//             len == info.len,
//             `Command len for ${cmd.toString(16)} ${len} ${info.len}`
//           );
//         } else {
//           console.log(`Unknown command ${cmd.toString(16)}`);
//         }

//         switch (cmd & 0xff) {
//           case msg.CMD_RET:
//             return pages;
//           case msg.CMD_NEWLINE:
//             line.push("\n");
//             lines.push(line);
//             line = [];
//             break;
//           case msg.CMD_END_PAGE:
//             // if (line.length) lines.push(line);
//             // console.assert(
//             //   lines.length <= 5,
//             //   `Expected max lines 5, found ${lines.length}`,
//             //   lines
//             // );
//             pages.push({ lines, footer: line });
//             line = [];
//             lines = [];
//             break;
//           case msg.CMD_TEXT:
//             let str = [];
//             while (data[off]) str.push(String.fromCharCode(data[off++]));
//             off++; //consume 0
//             if (off & 0x1) off++; //alignment 2
//             line.push(str.join(""));
//             break;
//           case msg.CMD_CHOICE:
//             choice_count = args[0];
//             break;
//           case msg.CMD_CHOICE_END:
//             let options = lines.splice(
//               lines.length - choice_count,
//               choice_count
//             );
//             lines.push({
//               options,
//             });
//             break;
//           default:
//             {
//               let obj = {};
//               if (info) {
//                 obj.cmd = info.alias;
//               } else {
//                 obj.cmd = cmd & 0xff;
//               }
//               if (args.length) obj.args = args;
//               line.push(obj);
//             }
//             break;
//         }
//       }
//     }
//   }
// };

//example?
let test = {
  type: "page",
  lines: [["Some line"], ["Line", 1]],
};

export const parse = (data, off, suppressError) => {
  let items = [];

  let choice_count = 0;
  //   console.log(`parsing dialog at ${off}`);

  while (off < data.byteLength) {
    let cmd = data.readUInt16LE(off);
    off += 2;
    switch ((cmd >> 12) & 0xf) {
      default:
        if(!suppressError)
        console.log(
          `Unknown command type ${cmd.toString(16)} at ${(off - 2).toString(
            16
          )}`
        );
        return false;
        break;
      case 0: //emoji
        // 注意：cmd==0 是合法字符 code 0 = 「（开引号），不是 end-of-data
        // 原版在此 return false 会让任何包含 「 的对话解析失败（例如 file 181 diag20）
        // 真正的终止符是 CMD_RET (0x1103)；这里继续 push
        items.push(cmd);
        break;
      case 1: {
        //cmd
        let len = (cmd >> 8) & 0xf;
        let args = [];
        for (let i = 1; i < len; i++) {
          args.push(data.readUInt16LE(off));
          off += 2;
        }
        let info = msg.commands[cmd & 0xff];
        if (info) {
          if(!suppressError)
          console.assert(
            len == info.len,
            `Command len for ${cmd.toString(16)} ${len} ${info.len}`
          );
        } else {
          if(!suppressError)
          console.log(`Unknown command ${cmd.toString(16)}`);
        }

        switch (cmd & 0xff) {
          case msg.CMD_RET:
            items.push([msg.CMD_RET]);
            return items;
          case msg.CMD_TEXT:
            let str = [];
            while (data[off]) str.push(String.fromCharCode(data[off++]));
            off++; //consume 0
            if (off & 0x1) off++; //alignment 2
            items.push(str.join(""));
            break;
          default:
            {
              let obj = [];
              //   if (info) {
              //     obj.push(info.alias);
              //   } else {
              obj.push(cmd & 0xff);
              //   }

              if (args.length) obj.push(...args); //args = args;
              items.push(obj);
            }
            break;
        }
      }
    }
  }
};
const sum = (a, b) => a + b;
const calculate_line_length = (line) => {
  if (line.options) {
    return 6 + line.options.map(calculate_line_length).reduce(sum, 0);
  }
  return line
    .map((l) => {
      if (l.cmd) {
        if (l.args) return l.args.length * 2 + 2;
        return 2;
      }
      if (l == "\n") {
        return 2;
      }
      if (l.emoji) {
        return 2;
      }
      console.assert(typeof l === "string");
      let len = l.length + 1;
      if (len & 1) len++;
      return len + 2;
    })
    .reduce(sum, 0);
};
// export const calculate_dialog_length = (diag) => {
//   return diag
//     .map(
//       (page) =>
//         page.lines.map(calculate_line_length).reduce(sum, 2) +
//         calculate_line_length(page.footer)
//     )
//     .reduce(sum, 2);
// };

export const calculate_dialog_length = (msg) => {
  return msg
    .map((item) => {
      switch (typeof item) {
        case "string":
          let len = 2 + item.length + 1;
          if (len & 1) len++;
          return len;
        case "object":
          return 2 * item.length;
        case "number":
          return 2;
        default:
          console.error(`Unknown item ${JSON.stringify(item)}`);
      }
    })
    .reduce(sum, 0);
};

const write_command = (cmd, buff, ptr) => {
  let len = 1;
  if (typeof cmd === "number") cmd = { cmd };
  if (cmd.args) len += cmd.args.length;
  let val = cmd.cmd;
  if (typeof cmd.cmd == "string") val = command_lookup[cmd.cmd].cmd;
  buff.writeUInt16LE(0x1000 | (len << 8) | val, ptr);
  ptr += 2;
  if (cmd.args) {
    cmd.args.forEach((arg) => {
      buff.writeUInt16LE(arg, ptr);
      ptr += 2;
    });
  }
  return len * 2;
};

const compile_choice = (choice, buff, off) => {
  console.log(choice);
  let ptr = off;
  let len = choice.options.length;
  ptr += write_command({ cmd: msg.CMD_CHOICE, args: [len] }, buff, ptr);
  choice.options.forEach((line) => (ptr += compile_line(line, buff, ptr)));
  ptr += write_command(msg.CMD_CHOICE, buff, ptr);
  return ptr - off;
};

const compile_line_element = (el, buff, off) => {
  if (el == "\n") {
    return write_command(msg.CMD_NEWLINE, buff, off);
  }
  if (el.options !== undefined) return compile_choice(el, buff, off);
  if (el.emoji !== undefined) {
    buff.writeUInt16LE(el.emoji, off);
    return 2;
  }
  if (el.cmd !== undefined) return write_command(el, buff, off);
  let ptr = off;
  ptr += write_command(msg.CMD_TEXT, buff, off);
  console.log(el);
  el.split("").forEach((c) => {
    buff[ptr++] = c.charCodeAt(0);
  });
  buff[ptr++] = 0;
  if (ptr & 1) buff[ptr++] = 0;
  return ptr - off;
};
const compile_line = (line, buff, off) => {
  let ptr = off;
  if (line.options) return compile_choice(line, buff, off);
  line.forEach((el) => (ptr += compile_line_element(el, buff, ptr)));
  return ptr - off;
};
const compile_page = (page, buff, off) => {
  let ptr = off;
  page.lines.forEach((line) => {
    ptr += compile_line(line, buff, ptr);
  });
  ptr += compile_line(page.footer, buff, ptr);
  ptr += write_command(msg.CMD_END_PAGE, buff, ptr);
  return ptr - off;
};
export const compile_dialog = (diag, buff, off) => {
  let ptr = off;
  diag.forEach((page) => {
    ptr += compile_page(page, buff, ptr);
  });
  ptr += write_command(msg.CMD_RET, buff, ptr);
  return ptr - off;
};

export const compile_msg = (msg, buff, off) => {
  let ptr = off;
  msg.forEach((item) => {
    // console.log(typeof item, item);
    switch (typeof item) {
      case "string":
        buff.writeUInt16LE(0x1136, ptr);
        ptr += 2;
        item.split("").forEach((c) => {
          buff[ptr++] = c.charCodeAt(0);
        });
        buff[ptr++] = 0;
        if (ptr & 1) buff[ptr++] = 0;
        break;
      case "object":
        let len = item.length;
        buff.writeUInt16LE(0x1000 | (len << 8) | item[0], ptr);
        ptr += 2;

        item.slice(1).forEach((a) => {
          buff.writeUInt16LE(a, ptr);
          ptr += 2;
        });
        break;
      case "number":
        buff.writeUInt16LE(item, ptr);
        ptr += 2;
        break;
      default:
        console.error(`Unknown item ${JSON.stringify(item)}`);
    }
  });
  return ptr - off;
};
