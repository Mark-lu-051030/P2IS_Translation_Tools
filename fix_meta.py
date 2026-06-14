import json
import os

def main():
    dict_path = os.path.join(os.path.dirname(__file__), 'meta_dict.json')
    if not os.path.exists(dict_path):
        print(f"❌ 找不到 {dict_path}！请先运行 python3 generate_meta_dict.py 生成。")
        return
        
    with open(dict_path, 'r', encoding='utf-8') as f:
        META_MAPPING = json.load(f)

    file_path = os.path.join(os.path.dirname(__file__), 'all_translatable.json')
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    changes = 0
    for entry in data:
        m_jp = entry.get('meta_jp')
        m_zh = entry.get('meta_zh')
        
        # 如果当前日文名在我们的标准字典里
        if m_jp in META_MAPPING:
            target_zh = META_MAPPING[m_jp]
            
            # 特殊处理：字典里有空字符串的目标，为了防止误清空，我们忽略掉
            if not target_zh:
                continue
                
            # 如果发现中文名和标准名字不一样，就执行替换
            if m_zh != target_zh:
                print(f"[{entry['id']}] 修改说话人: '{m_zh}' -> '{target_zh}'")
                entry['meta_zh'] = target_zh
                changes += 1

    if changes > 0:
        # 将修改写回文件
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        print(f"\n✅ 批量替换完成！共修正了 {changes} 处说话人译名。")
    else:
        print("\n✨ 扫描完毕，当前所有的说话人译名都与标准表一致，无需修改。")

if __name__ == '__main__':
    main()
