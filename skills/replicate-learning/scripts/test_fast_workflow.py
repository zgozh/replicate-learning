"""Focused behavior tests for the default study scope and batch evidence."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from study_scope import migrate_state, resolve_books
from batch_manifest import build_manifest, changed_files


class ScopeTests(unittest.TestCase):
    def test_generic_start_and_continue_default_to_book_one(self):
        self.assertEqual(resolve_books("学习这个项目"), (1,))
        self.assertEqual(resolve_books("继续下一批"), (1,))
        self.assertEqual(resolve_books("给这段做一个实验"), (1,))

    def test_second_and_third_books_require_explicit_request(self):
        self.assertEqual(resolve_books("开始第二册实验教材"), (2,))
        self.assertEqual(resolve_books("生成第三册架构挑战"), (3,))
        self.assertEqual(resolve_books("三册一起推进"), (1, 2, 3))
        self.assertEqual(resolve_books("第二册会讲什么？"), (1,))
        self.assertEqual(resolve_books("不需要第二册"), (1,))

    def test_continue_respects_an_explicit_existing_scope(self):
        self.assertEqual(resolve_books("继续", (1, 2, 3)), (1, 2, 3))
        self.assertEqual(resolve_books("先只要第一册", (1, 2, 3)), (1,))

    def test_legacy_first_book_priority_is_not_an_extension_debt(self):
        state = {"运行模式": "第一册优先", "欠账": ["第二册", "第三册"]}
        result = migrate_state(state)
        self.assertEqual(result["books"], [1])
        self.assertEqual(result["extensions"]["book2"]["status"], "not_requested")
        self.assertEqual(result["extensions"]["book3"]["status"], "not_requested")
        self.assertNotIn("欠账", result)


class ManifestTests(unittest.TestCase):
    def test_java_and_python_sources_are_treated_equally(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "A.java").write_text("class A {}\n", encoding="utf-8")
            (root / "b.py").write_text("def f():\n    return 1\n", encoding="utf-8")
            manifest = build_manifest(root, ["A.java", "b.py"])
            self.assertEqual(set(manifest["files"]), {"A.java", "b.py"})
            self.assertEqual(changed_files(manifest, root), [])
            (root / "b.py").write_text("def f():\n    return 2\n", encoding="utf-8")
            self.assertEqual(changed_files(manifest, root), ["b.py"])

    def test_manifest_rejects_paths_outside_project(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                build_manifest(root, ["../elsewhere.py"])


if __name__ == "__main__":
    unittest.main()
