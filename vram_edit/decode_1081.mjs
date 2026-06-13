import * as fs from 'fs';
import * as lzss from '../lib/lzss.mjs';
import * as rle from '../lib/rle.mjs';

/**
 * 解析并解压单个 sub-file Buffer
 * @param {Buffer} subBuffer - 包含 12 字节头部和压缩数据的纯净 Buffer
 */
function unpackSubFile(subBuffer) {
  const type = subBuffer.readUInt8(0);
  const subtype = subBuffer.readUInt8(1); 
  const subIndex = subBuffer.readUInt16LE(2);
  const totalSize = subBuffer.readUInt32LE(4);
  const uncompSize = subBuffer.readUInt32LE(8);

  console.log(`正在处理 Sub-file [${subIndex}]: 压缩类型=${subtype}, 总大小=${totalSize}, 解压后目标大小=${uncompSize}`);

  if (totalSize === 0 || uncompSize === 0) {
    console.error(`Sub-file [${subIndex}] 数据异常！`);
    return null;
  }

  const compPayloadSize = totalSize - 12; 
  let decompressedData = null;

  if (subtype === 2) {
    console.log(`-> 识别为 LZSS 压缩，开始解压...`);
    decompressedData = lzss.decompress(subBuffer, 12, compPayloadSize, uncompSize);
    
  } else if (subtype === 1) {
    console.log(`-> 识别为 RLE 压缩，开始解压...`);
    decompressedData = rle.decompress(subBuffer, 12, compPayloadSize, uncompSize);
    
  } else {
    console.log(`-> 未知或未压缩类型 (${subtype})，直接提取。`);
    decompressedData = Buffer.allocUnsafe(compPayloadSize);
    subBuffer.copy(decompressedData, 0, 12, totalSize);
  }

  if (decompressedData && decompressedData.byteLength === uncompSize) {
     console.log(`-> 解压成功！得到 ${decompressedData.byteLength} 字节。`);
  } else {
     console.error(`-> 解压失败或大小不匹配！`);
  }

  return decompressedData;
}

/**
 * 批量提取容器 Buffer 中的所有子文件
 * @param {Buffer} containerBuffer - 包含所有 sub-file 的大文件 Buffer (比如用 rblk 读出来的 file 59)
 * @param {string} outputDir - 解压后文件存放的文件夹路径
 */
function extractAllSubFiles(containerBuffer, outputDir) {
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  let offset = 0;
  let fileCount = 0;

  console.log(`开始批量解包，容器总大小: ${containerBuffer.byteLength} 字节`);

  while (offset < containerBuffer.byteLength) {
    if (offset + 12 > containerBuffer.byteLength) {
      break;
    }

    const totalSize = containerBuffer.readUInt32LE(offset + 4);

    if (totalSize === 0) {
      console.log(`[偏移量 ${offset}] 撞到 0x00 填充区，文件链结束。`);
      break;
    }

    if (offset + totalSize > containerBuffer.byteLength) {
      console.warn(`[警告] 提取到最后发现数据截断！这不应该发生。`);
      break;
    }

    const subBuffer = containerBuffer.subarray(offset, offset + totalSize);

    const decompressedData = unpackSubFile(subBuffer);

    if (decompressedData) {
      const outputPath = `${outputDir}/sub_${fileCount}.bin`;
      fs.writeFileSync(outputPath, decompressedData);
    }

    offset += totalSize;
    fileCount++;
  }

  console.log(`\n🎉 批量解包彻底完成！共成功提取了 ${fileCount} 个子文件到 ${outputDir} 文件夹。`);
}


const testBinPath = '/home/mark/Code/RomHacking/P2IS_Translation_Tools/vram_edit/F1081.BIN'; 

if (fs.existsSync(testBinPath)) {
  const container = fs.readFileSync(testBinPath);
  extractAllSubFiles(container, './extracted_files');
} else {
  console.log(`找不到测试文件 ${testBinPath}，请修改路径。`);
}