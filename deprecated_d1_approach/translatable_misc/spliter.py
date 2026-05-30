import json

path = 'all_translatable.json'

with open(path, 'r', encoding='utf-8') as f:
    data = json.load(f)

# print(data[1], data[2])
lines_count = len(data)

with open('translatable_1.json', 'w', encoding='utf-8') as f1, \
    open('translatable_2.json', 'w', encoding='utf-8') as f2, \
    open('translatable_3.json', 'w', encoding='utf-8') as f3, \
    open("translatable_4.json", 'w', encoding='utf-8') as f4, \
    open("translatable_5.json", 'w', encoding='utf-8') as f5:

    f1.write(json.dumps(data[:lines_count//5], ensure_ascii=False, indent=4))
    f2.write(json.dumps(data[lines_count//5:2*lines_count//5], ensure_ascii=False, indent=4))
    f3.write(json.dumps(data[2*lines_count//5:3*lines_count//5], ensure_ascii=False, indent=4))
    f4.write(json.dumps(data[3*lines_count//5:4*lines_count//5], ensure_ascii=False, indent=4))
    f5.write(json.dumps(data[4*lines_count//5:], ensure_ascii=False, indent=4))