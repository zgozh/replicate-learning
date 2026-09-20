"""Python source injection must preserve executable source semantics."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from inject_source import build_block


class PythonInjectionTests(unittest.TestCase):
    def test_multiline_string_content_is_not_annotated(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "sample.py").write_text(
                'SQL = """select\nfrom account\nwhere id = 1"""\nprint(SQL)\n', encoding="utf-8"
            )
            block, _ = build_block(str(root), "sample.py", 1, 4, {"2": "教学解释"}, "python")
            self.assertEqual(block[2], "from account")
            self.assertNotIn("←教材", block[2])
            self.assertIn("# :L4", block[4])


if __name__ == "__main__":
    unittest.main()
