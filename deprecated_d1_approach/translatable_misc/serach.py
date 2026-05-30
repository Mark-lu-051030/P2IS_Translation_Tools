import json


path_1 = "/home/mark/Code/RomHacking/P2IS_Translation_Tools/all_translatable.json"
path_2 = "/home/mark/Code/RomHacking/P2IS_Translation_Tools/translatable/undone.json"

with open(path_2, "r", encoding="utf-8") as f:
    data = json.load(f)

item_list = []
count = 0

for item in data:
    count += 1
    item_id = item.get("id")
    item_meta = item.get("meta_zh")
    if item_id[1] == "c":
        if item_meta == "":
            item_list.append(item)
        else:
            for s in item.get("pages"):
                if s.get("zh") == "":
                    item_list.append(item)
                    break

print(f"需要翻译的条目数量: {len(item_list)}")
print(count)
"""
print("需要翻译的条目 ID 列表:")
for item_id in need_work:
    print(item_id)

with open("./undone.json", "w", encoding="utf-8") as f:
    json.dump(item_list, f, indent=4, ensure_ascii=False)
"""