import json

def load_json(fp):
    with open(fp, 'r', encoding='utf-8') as f:
        return json.load(f)
    
def check_match(json1, json2):
    id1 = [item['id'] for item in json1]
    id2 = [item['id'] for item in json2]

    count = 0
    list = []
    for i in id1:
        if i not in id2:
            count += 1
            list.append(i)
    return count, list


if __name__ == "__main__":
    json1 = load_json('/home/mark/Code/RomHacking/P2IS_Translation_Tools/out/field_text.json')
    json2 = load_json('/home/mark/Code/RomHacking/P2IS_Translation_Tools/out/field_text_zh.json')

    count, missing_ids = check_match(json1, json2)
    print(f"Total missing IDs: {count}")
    print(f"Missing IDs: {missing_ids}")
    json1_lookup = {item['id']: item for item in json1}

    for missied in missing_ids:
        missied_item = json1_lookup[missied].copy()
        json2.append(missied_item)

    with open('/home/mark/Code/RomHacking/P2IS_Translation_Tools/out/field_text_zh.json','w', encoding='utf-8') as f:
        json.dump(json2, f, ensure_ascii=False, indent=4)