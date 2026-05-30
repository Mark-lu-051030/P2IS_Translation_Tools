import json 

path_1 = "/home/mark/Code/RomHacking/P2IS_Translation_Tools/translatable/undone.json"
path_2 = "/home/mark/Code/RomHacking/P2IS_Translation_Tools/translatable/undone1.json"

with open(path_1, "r", encoding="utf-8") as f:
    data1 = json.load(f)

with open(path_2, "r", encoding="utf-8") as f:
    data2 = json.load(f)


for item1, item2 in zip(data1, data2):
    pages1 = item1.get("pages", [])
    pages2 = item2.get("pages", [])
    for i in range(min(len(pages1), len(pages2))):
        jp1 = pages1[i].get("jp", "")
        jp2 = pages2[i].get("jp", "")
        if jp1 != jp2:
            print(f"ID: {item1['id']}  Page {i} JP 不同")
            print(f"  JP1: {jp1!r}")
            print(f"  JP2: {jp2!r}")