import { assert } from "console";
import { compile_msg } from "./msg_script.mjs";
import { calculate_dialog_length } from "./msg_script.mjs";
import { parse as parse_dialog } from "./msg_script.mjs";

const parse_function = (data, text_start, start, size) => {
  let instr_ptr = start * 8 + text_start;
  let instructions = [];
  for (let i = 0; i < size; i++) {
    let op = data.readUInt16LE(instr_ptr);
    let imm = data.readUInt16LE(instr_ptr + 2);
    let arg_ptr = data.readUInt32LE(instr_ptr + 4);

    let arg_len = op == 0x0e ? 4 : data.readUInt32LE(instr_ptr + 12) - arg_ptr;
    let args = [];
    for (let i = 0; i < arg_len; i += 4) {
      args.push(data.readUInt32LE(i + arg_ptr));
    }
    let res = { op };
    if (args.length) res.args = args;
    if (imm != 0) res.imm = imm;
    instructions.push(res);
    instr_ptr += 8;
  }
  return instructions;
};

export const parse_script = (buff) => {
  let start_func_ptr = buff.readUInt32LE(0);
  let function_ptr = buff.readUInt32LE(4);
  let function_count = buff.readUInt32LE(8);
  let script_ptr = buff.readUInt32LE(12);
  let arg_ptr = buff.readUInt32LE(16);
  let diag_ptr = buff.readUInt32LE(20);
  let functions = [];

  let instr_data = buff.slice(script_ptr, arg_ptr);
  //let arg_data = buff.slice(arg_ptr, diag_ptr);
  let diag_data = buff.slice(diag_ptr);
  //   console.log(diag_ptr, diag_data);
  let diags = {};
  let diag_lookup = {};
  let diag_order = [];
  let diag_count = 0;

  let ptr = function_ptr;
  //read function info
  for (let i = 0; i < function_count; i++) {
    //0x48 bytes
    let name_end = buff.indexOf(0, ptr);
    let name = buff.toString("ascii", ptr, name_end);
    let addr = buff.readUInt32LE(ptr + 0x40);
    // console.assert(buff.readUInt32LE(ptr + 0x44) == 0, `Function ending`);
    let unk4 = buff.readUInt32LE(ptr + 0x44);
    functions.push({ name, addr, unk4 });

    ptr += 0x48;
  }
  for (let i = 0; i < function_count; i++) {
    let func = functions[i];
    let size = 0;
    if (i == function_count - 1) {
      size = (arg_ptr - script_ptr) / 8 - func.addr;
    } else {
      size = functions[i + 1].addr - func.addr;
    }
    //func.size = size;
    // console.log(`parsing ${func.name}`);
    func.instructions = parse_function(buff, script_ptr, func.addr, size);

    //sanity check
    console.assert(
      instr_data.readUInt16LE((functions[i].addr + size - 1) * 8) == 0x0e,
      `function ${functions[i].name} ends with return`
    );

    for (let i = 0; i < size; i++) {
      //TODO: don't hardcode this
      if (func.instructions[i].op == 0x13 || func.instructions[i].op == 0x10f) {
        let diag = func.instructions[i].args[0];
        if (diag_lookup[diag] === undefined) {
          let diag_name = `diag${diag_count++}`;
          diag_lookup[diag] = {
            type: "dialog",
            diag: diag_name,
          };
          diag_order.push([diag_name, diag]);
          diags[diag_name] = parse_dialog(diag_data, diag);
        }
        func.instructions[i].args[0] = diag_lookup[diag];
      }
    }

    diag_order.sort((a, b) => {
      return a[1] - b[1];
    });
  }

  //TODO: make sure we've eaten all the arguments
  //TODO: make sure the start_func_ptr actually points to a function called start?
  return {
    //start: start_func_ptr,
    functions,
    dialogs: diags,
    dialog_order: diag_order.map((a) => a[0]),
  };
};

const stringify_args = (args) => {
  return args.map((a) => {
    if (typeof a !== "number") return a;
    if (a > 1000)
      //assume large numbers are hex
      return {
        type: "hex",
        value: `0x${a.toString(16)}`,
      };
    else return a;
  });
};

export const stringify_script = (script) => {
  return JSON.stringify(
    script,
    (k, v) => {
      if (k == "op")
        return `${v
          .toString(16)
          .padStart((v.toString(16).length + 1) & ~0x1, "0")}`;
      if (k == "args") return stringify_args(v);
      if (k == "imm") return `0x${v.toString(16)}`;
      return v;
    },
    4
  );
};

export const import_script = (script) => {
  return JSON.parse(script, (k, v) => {
    if (k == "op") return parseInt(v, 16);
    if (k == "imm") return parseInt(v);
    return v;
  });
};

export const compile_function = (
  func,
  buff,
  func_ptr,
  instr_ptr,
  arg_ptr,
  diag_lookup,
  instr_start
) => {
  let name = func.name;
  if (name == "START") buff.writeUInt32LE(func_ptr, 0);
  // console.log(`Compiling ${func.name}`);

  // Write name, then broadcast last char into remaining name bytes + addr/unk4 fields
  let lastChar = name.charCodeAt(name.length - 1);
  buff.fill(lastChar, func_ptr, func_ptr + 0x48);
  let ptr = func_ptr;
  name.split("").forEach((c) => (buff[ptr++] = c.charCodeAt(0)));

  // addr: write as uint16 at 0x40, then broadcast unk4 into bytes 0x42-0x47
  let off = (instr_ptr - instr_start) / 8;
  let unk4 = func.unk4 ?? 0;
  buff.writeUInt16LE(off, func_ptr + 0x40);
  buff[func_ptr + 0x42] = unk4; buff[func_ptr + 0x43] = unk4;
  buff[func_ptr + 0x44] = unk4; buff[func_ptr + 0x45] = unk4;
  buff[func_ptr + 0x46] = unk4; buff[func_ptr + 0x47] = unk4;

  func.instructions.forEach((instr) => {
    let op = parseInt(instr.op);
    let imm = parseInt(instr.imm ?? 0);
    buff.writeUInt16LE(op, instr_ptr);
    buff.writeUInt16LE(imm, instr_ptr + 2);
    buff.writeUInt32LE(arg_ptr, instr_ptr + 4);
    instr.args?.forEach((arg) => {
      let val = arg;
      switch (arg.type) {
        case "hex":
          val = parseInt(arg.value, 16);
          break;
        case "dialog":
          val = diag_lookup[arg.diag];
          break;
      }
      buff.writeUInt32LE(val, arg_ptr);
      arg_ptr += 4;
    });
    instr_ptr += 8;
  });
  func_ptr += 0x48;

  return [func_ptr, instr_ptr, arg_ptr];
};

const debug_log = (val) => {
  console.log(val);
  return val;
};

const sum = (a, b) => a + b;
export const compile_script = (script) => {
  let header_len = 0x18;
  let func_ptr = header_len;
  let func_len = script.functions.length * 0x48;
  let instr_ptr = func_ptr + func_len;
  let instr_len =
    script.functions.map((func) => func.instructions.length).reduce(sum, 0) * 8;
  let arg_ptr = instr_ptr + instr_len;

  let arg_len =
    script.functions
      .map((func) =>
        func.instructions
          .map((instr) => (instr.args ? instr.args.length : 0))
          .reduce(sum, 0)
      )
      .reduce(sum, 0) * 4;

  let diag_ptr = arg_ptr + arg_len;
  let diag_len = Object.values(script.dialogs)
    .map((diag) => (diag ? calculate_dialog_length(diag) : 2))
    .reduce(sum, 0);
  let total_len = diag_ptr + diag_len;

  let buff = Buffer.alloc(total_len);
  buff.writeUInt32LE(func_ptr, 4);
  buff.writeUInt32LE(script.functions.length, 8);
  buff.writeUInt32LE(instr_ptr, 12);
  buff.writeUInt32LE(arg_ptr, 16);
  buff.writeUInt32LE(diag_ptr, 20);

  let diag_lookup = {};
  let diag_start = diag_ptr;

  script.dialog_order.forEach((name) => {
    let diag = script.dialogs[name];
    diag_lookup[name] = diag_ptr - diag_start;
    if (diag) {
      diag_ptr += compile_msg(diag, buff, diag_ptr);
    } else {
      buff.writeUInt16LE(0, diag_ptr);
      diag_ptr += 2;
    }
  });

  let instr_start = instr_ptr;
  script.functions.forEach(
    (func) =>
      ([func_ptr, instr_ptr, arg_ptr] = compile_function(
        func,
        buff,
        func_ptr,
        instr_ptr,
        arg_ptr,
        diag_lookup,
        instr_start
      ))
  );
  return buff;
};
