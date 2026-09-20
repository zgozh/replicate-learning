#!/usr/bin/env python3
"""Choose the requested teaching book without creating implicit book debts."""

import argparse
import json
import re
import sys
from pathlib import Path


def resolve_books(request: str, stored=None) -> tuple[int, ...]:
    """Resolve explicit requests first; otherwise retain the confirmed scope."""
    text = re.sub(r"\s+", "", request or "")
    if re.search(r"只(?:要|讲|生成)?第?一册|先(?:只)?(?:要|讲|生成)?第?一册|关闭第?[二三]册", text):
        return (1,)
    if re.search(r"(?:不(?:需要|要|生成|讲)|暂不|无需).{0,6}第?[二三]册", text):
        return (1,)
    if re.search(r"三册(?:一起|同步|都|全部)|第[一二三]册(?:一起|同步|都)", text):
        return (1, 2, 3)
    explicit = []
    action = r"(?:开始|生成|写|制作|推进|继续|讲解|讲|开启|启用|要|补齐)"
    if re.search(action + r".{0,8}第?二册|第?二册(?:也|一起)?" + action, text):
        explicit.append(2)
    if re.search(action + r".{0,8}第?三册|第?三册(?:也|一起)?" + action, text):
        explicit.append(3)
    if explicit:
        return tuple(explicit)
    valid = sorted(set(stored or []))
    if valid and all(book in (1, 2, 3) for book in valid):
        return tuple(valid)
    return (1,)


def migrate_state(state: dict) -> dict:
    """Convert legacy first-book priority into the ordinary default scope."""
    result = dict(state)
    if state.get("books"):
        books = sorted(set(state["books"]))
    elif "第一册优先" in str(state.get("运行模式", "")):
        books = [1]
    elif state.get("explicit_all_books") is True:
        books = [1, 2, 3]
    else:
        books = [1]
    result["schema_version"] = 1
    result["books"] = books
    result["extensions"] = {
        "book2": {"status": "requested" if 2 in books else "not_requested"},
        "book3": {"status": "requested" if 3 in books else "not_requested"},
    }
    result.pop("欠账", None)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve the teaching scope for this turn")
    parser.add_argument("--request", required=True, help="用户原话")
    parser.add_argument("--state", type=Path, help="可选的已有 JSON 状态文件")
    args = parser.parse_args()
    state = json.loads(args.state.read_text(encoding="utf-8")) if args.state else {}
    normalized = migrate_state(state)
    normalized["books"] = list(resolve_books(args.request, normalized["books"]))
    normalized["extensions"] = {
        "book2": {"status": "requested" if 2 in normalized["books"] else "not_requested"},
        "book3": {"status": "requested" if 3 in normalized["books"] else "not_requested"},
    }
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(normalized, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
