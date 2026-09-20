"""Keep the executable skill entry short and the book scope unambiguous."""

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SkillContractTests(unittest.TestCase):
    def test_entry_is_short_and_points_to_preserved_detail(self):
        skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 220)
        self.assertIn("references/第一册质量细则.md", skill)
        self.assertTrue((ROOT / "references/第一册质量细则.md").is_file())

    def test_all_scope_docs_start_with_book_one(self):
        paths = [
            ROOT / "SKILL.md",
            ROOT / "references/V2执行协议.md",
            ROOT / "references/三本书与工程日志.md",
        ]
        for path in paths:
            with self.subTest(path=path):
                text = path.read_text(encoding="utf-8")
                self.assertIn("默认只", text)
                self.assertNotIn("默认同步", text)
                self.assertNotIn("单册优先模式", text)
                self.assertNotIn("暂停欠账", text)

    def test_v2_contract_requires_optional_books_only_when_requested(self):
        contract = json.loads((ROOT / "spec/V2质量契约.json").read_text(encoding="utf-8"))
        entry = next(item for item in contract["entries"] if item["id"] == "V2-02")
        self.assertIn("显式", entry["stmt"])


if __name__ == "__main__":
    unittest.main()
