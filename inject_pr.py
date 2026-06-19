import argparse
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MAIN_PATH = ROOT / "all_translatable.json"
FIELD_PATH = ROOT / "out" / "field_text_zh.json"
CHANGES_PATH = ROOT / "open_requests_changes.json"


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def save_json(path, data):
    with path.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
        file.write("\n")


def compact(text):
    """忽略 PR 导出时丢失或增加的换行和空格。"""
    return re.sub(r"\s+", "", text.replace(r"\n", "\n"))


def format_new_text(new_text, old_text, is_script=False):
    text = new_text.replace(r"\n", "\n")

    # script 修改在 open_requests_changes.json 中通常被压成一行。
    if is_script:
        text = re.sub(r"[ \t]+(?=<SURNAME/>)", "\n", text)

    # 保留目标文本原有的首尾换行风格。
    if old_text.startswith("\n") and not text.startswith("\n"):
        text = "\n" + text
    if old_text.endswith("\n") and not text.endswith("\n"):
        text += "\n"
    return text


def split_script_id(change_id):
    """返回 all_translatable 的 id 和页码；:p1 表示 pages[1]。"""
    match = re.fullmatch(r"(script:.+:diag\d+)(?::p(\d+))?", change_id)
    if not match:
        return None
    return match.group(1), int(match.group(2) or 0)


def main(dry_run=False):
    main_items = load_json(MAIN_PATH)
    field_items = load_json(FIELD_PATH)
    requests = load_json(CHANGES_PATH)

    scripts_by_id = {item["id"]: item for item in main_items}
    fields_by_id = {item["id"]: item for item in field_items}

    changed_scripts = 0
    changed_fields = 0
    warnings = []
    manual_changes = []

    for request in requests:
        for change_id, change in request.get("changes", {}).items():
            script_target = split_script_id(change_id)

            if script_target:
                item_id, page_number = script_target
                item = scripts_by_id.get(item_id)
                if item is None:
                    warnings.append(f"找不到 script: {change_id}")
                    continue
                if page_number >= len(item.get("pages", [])):
                    warnings.append(f"script 页码不存在: {change_id}")
                    continue

                page = item["pages"][page_number]
                old_text = page.get("zh", "")
                original = change.get("original", "")
                if original and compact(old_text) != compact(original):
                    warnings.append(f"旧文本不一致，仍按 ID 更新: {change_id}")

                page["zh"] = format_new_text(
                    change.get("new", ""), old_text, is_script=True
                )
                changed_scripts += 1

            elif change_id.startswith("field:"):
                item = fields_by_id.get(change_id)
                if item is None:
                    warnings.append(f"找不到 field: {change_id}")
                    continue

                old_text = item.get("zh", "")
                original = change.get("original", "")
                if original and compact(old_text) != compact(original):
                    warnings.append(f"旧文本不一致，仍按 ID 更新: {change_id}")

                item["zh"] = format_new_text(change.get("new", ""), old_text)
                changed_fields += 1

            else:
                manual_changes.append(
                    {
                        "source_file": request.get("source_file"),
                        "id": change_id,
                        **change,
                    }
                )

    if not dry_run:
        save_json(MAIN_PATH, main_items)
        save_json(FIELD_PATH, field_items)

    mode = "预览" if dry_run else "已写入"
    print(f"{mode}: scripts {changed_scripts} 条，field {changed_fields} 条")

    if warnings:
        print("\n警告:")
        for warning in warnings:
            print(f"- {warning}")

    if manual_changes:
        print("\n需要手动修改:")
        print(json.dumps(manual_changes, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="注入 open_requests_changes.json")
    parser.add_argument(
        "--dry-run", action="store_true", help="只显示结果，不修改 JSON 文件"
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run)
