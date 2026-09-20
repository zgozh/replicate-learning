"""Regression tests for deterministic section assembly."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from assemble_batch import assemble, write_batch


class AssembleTests(unittest.TestCase):
    def test_replaces_only_named_sections_and_keeps_java_python_blocks(self):
        base = "# 批次\n\n## ① 背景\n旧背景\n\n## ② 源码\n旧源码\n"
        part = "## ② 源码\n```java\nclass A {}\n```\n```python\ndef f(): pass\n```\n"
        expected = "# 批次\n\n## ① 背景\n旧背景\n\n" + part
        self.assertEqual(assemble(base, [part], expected_sections=2), expected)

    def test_rejects_unknown_duplicate_and_unclosed_sections(self):
        base = "# 批次\n\n## ① 背景\n旧\n\n## ② 源码\n旧\n"
        with self.assertRaises(ValueError):
            assemble(base, ["## ③ 错误\n内容\n"], expected_sections=2)
        with self.assertRaises(ValueError):
            assemble(base, ["## ② 源码\n新\n", "## ② 源码\n重写\n"], expected_sections=2)
        with self.assertRaises(ValueError):
            assemble(base, ["## ② 源码\n```python\npass\n"], expected_sections=2)

    def test_output_is_idempotent_and_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "批次.md"
            content = "# 批次\n\n## ① 背景\n新\n"
            write_batch(path, content)
            write_batch(path, content)
            with self.assertRaises(FileExistsError):
                write_batch(path, content + "修改")
            write_batch(path, content + "修改", force=True)
            self.assertEqual(path.read_text(encoding="utf-8"), content + "修改")


if __name__ == "__main__":
    unittest.main()
