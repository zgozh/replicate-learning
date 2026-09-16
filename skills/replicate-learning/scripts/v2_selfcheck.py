"""Check the V2 skill package without external dependencies."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    contract_path = ROOT / "spec" / "V2质量契约.json"
    try:
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"FAIL: cannot read V2 contract: {exc}")
        return 1

    failures: list[str] = []
    for entry in contract.get("entries", []):
        for relative in entry.get("required", []):
            path = ROOT / relative
            if not path.is_file():
                failures.append(f"{entry['id']}: missing {relative}")

    skill_text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
    protocol_text = (ROOT / "references" / "V2执行协议.md").read_text(encoding="utf-8")
    required_routes = ["学习/深度拆解/开始", "继续/next", "实验/验证机制", "架构挑战/重构/迁移", "Issue/功能/修复/让 AI 改代码", "验收/检查完整性"]
    for route in required_routes:
        if route not in skill_text:
            failures.append(f"V2-01: missing route {route}")

    for marker in ["Understand", "Investigate", "Predict", "Plan", "Delegate", "Review", "Test", "Accept"]:
        if marker not in protocol_text:
            failures.append(f"V2-04: missing stage {marker}")

    if failures:
        print("V2 self-check: FAIL")
        print("\n".join(f"- {item}" for item in failures))
        return 1

    print(f"V2 self-check: PASS ({len(contract.get('entries', []))} contract entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
