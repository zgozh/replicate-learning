"""Structured gate results, and stamping ⑯ from them (plan §3.4).

Two things must hold or the whole "one machine-generated result" idea collapses:
  * a result can only stamp ⑯ when it actually describes **this** text and **this** contract
    (stale hash / wrong version / incomplete / blocking → refuse, file untouched);
  * the rendered table must distinguish ``未检查`` (zero objects) from ``通过``, so ⑯ can no longer
    claim coverage it never had.
"""

import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lecture_checks as LC
import sync_gate_result as S

CONTRACT = LC.load_contract()
VERSION = CONTRACT["version"]


def make_doc():
    return ("# 阶段测试批\n"
            "\n"
            "## ⑯ 教材质量自检\n"
            "\n"
            "**判据版本：v2.20**（本批按此版判据验收）。\n"
            "\n"
            "## 索引节\n"
            "\n"
            "尾注。\n")


def good_result(lecture_sha):
    checks = []
    for cid in S.REQUIRED_CHECKS:
        checks.append(LC.make_check(cid, LC.PASS, checked=7))
    checks.append(LC.make_check("G-PY", LC.NOT_CHECKED, checked=0))
    checks.append(LC.make_check("G-LECTURE", LC.REPORT, checked=1))
    return LC.make_result("gate_lecture.py", checks, contract_version=VERSION,
                          lecture_sha256=lecture_sha)


class ResultStampingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.doc = self.root / "批次9.md"
        self.doc.write_text(make_doc(), encoding="utf-8")
        self.result_path = self.root / "gate-result.json"
        self.write_result(good_result(LC.sha256_file(self.doc)))

    def tearDown(self):
        self.tmp.cleanup()

    def write_result(self, result):
        self.result_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

    def run_sync(self, extra=()):
        argv = sys.argv
        sys.argv = ["sync_gate_result.py", str(self.doc), "--src", str(self.root),
                    "--result-json", str(self.result_path), "--no-verify-final"] + list(extra)
        try:
            return S.main()
        finally:
            sys.argv = argv

    def test_apply_stamps_the_table_and_the_version_line(self):
        self.assertEqual(self.run_sync(["--apply"]), 0)
        text = self.doc.read_text(encoding="utf-8")
        self.assertIn("**七组闸门实测**", text)
        self.assertIn("规则 ID", text)
        self.assertIn("**判据版本：v%s**" % VERSION, text)
        self.assertNotIn("v2.20", text)

    def test_stamping_twice_keeps_a_single_table(self):
        self.assertEqual(self.run_sync(["--apply"]), 0)
        # 盖章后正文变了 → 必须**重新跑闸门**产出针对新正文的结果（这正是"旧结果不得给新正文背书"）
        self.write_result(good_result(LC.sha256_file(self.doc)))
        self.assertEqual(self.run_sync(["--apply"]), 0)
        text = self.doc.read_text(encoding="utf-8")
        self.assertEqual(text.count("**七组闸门实测**"), 1, "盖章必须幂等，不许堆表（BUG-S1）")
        self.assertEqual(len([l for l in text.split("\n") if S.NOTE_RE.match(l.strip())]), 1)

    def test_dry_run_does_not_write(self):
        before = self.doc.read_text(encoding="utf-8")
        self.assertEqual(self.run_sync(), 0)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), before)

    def test_stale_lecture_hash_is_refused(self):
        self.doc.write_text(self.doc.read_text(encoding="utf-8") + "\n补一行正文。\n", encoding="utf-8")
        before = self.doc.read_text(encoding="utf-8")
        self.assertEqual(self.run_sync(["--apply"]), 1)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), before, "拒绝盖章时不得改动正文")

    def test_wrong_contract_version_is_refused(self):
        result = good_result(LC.sha256_file(self.doc))
        result["contract_version"] = "2.17"
        self.write_result(result)
        before = self.doc.read_text(encoding="utf-8")
        self.assertEqual(self.run_sync(["--apply"]), 1)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), before)

    def test_missing_required_check_is_refused(self):
        result = good_result(LC.sha256_file(self.doc))
        result["checks"] = [c for c in result["checks"] if c["id"] != "G-DENSITY"]
        self.write_result(result)
        before = self.doc.read_text(encoding="utf-8")
        self.assertEqual(self.run_sync(["--apply"]), 1)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), before)

    def test_blocking_check_blocks_the_stamp(self):
        result = good_result(LC.sha256_file(self.doc))
        result["checks"].append(LC.make_check("G-SIG", LC.FAIL, checked=1,
                                              findings=[LC.make_finding("★类方法签名无注释：X → y")]))
        result["pass"] = False
        self.write_result(result)
        before = self.doc.read_text(encoding="utf-8")
        self.assertEqual(self.run_sync(["--apply"]), 1)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), before)

    def test_vacuous_pass_cannot_be_stamped(self):
        result = good_result(LC.sha256_file(self.doc))
        for c in result["checks"]:
            if c["id"] == "G-DENSITY":
                c["checked"] = 0
        self.write_result(result)
        self.assertEqual(self.run_sync(["--apply"]), 1)


class RenderTests(unittest.TestCase):
    def test_zero_object_checks_read_as_not_checked(self):
        result = good_result("a" * 64)
        block = S.render_from_result(result)
        self.assertIn("未检查", block)
        self.assertIn("`G-PY` | 非 Java 语言实检（2.24） | — | 未检查 |", block)
        self.assertIn("不计通过", block)

    def test_failures_are_listed_as_blocking_items(self):
        result = good_result("a" * 64)
        result["checks"].append(LC.make_check("G-SIG", LC.FAIL, checked=1,
                                              findings=[LC.make_finding("★类方法签名无注释：Foo → bar")]))
        block = S.render_from_result(result)
        self.assertIn("**不通过**", block)
        self.assertIn("阻塞项", block)
        self.assertIn("★类方法签名无注释", block)

    def test_block_end_still_eats_stacked_tables(self):
        """2.29 的幂等修复不许被本次重构破坏。"""
        note = "> 本表由 `scripts/sync_gate_result.py` 从闸门实跑输出生成，**不是复述旧结论**（血证 H15）；"
        rows = ["| # | 闸门组 | 实测值 | 结论 |", "|---|---|---|---|", "| ⓪ | 结构 | 旧 | 通过 |"]
        lines = ["## ⑯ 教材质量自检", "**七组闸门实测**（判据 v2.24）**：", ""] + rows + ["", note, ""]
        lines += rows + ["", note, ""]
        lines += ["**判据版本：v2.21**", "", "## 索引节"]
        self.assertEqual(S.block_end(lines, 1), 13)


class FinalVerificationTests(unittest.TestCase):
    def test_final_record_separates_before_and_after_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "plain.md"
            doc.write_text("# 普通文档\n\n正文。\n", encoding="utf-8")
            result = good_result(LC.sha256_file(doc))
            stamped = doc.read_text(encoding="utf-8") + "\n**七组闸门实测**（盖章测试）**：\n"
            doc.write_text(stamped, encoding="utf-8")
            final_json = root / "final.json"
            rc = S.verify_final(str(doc), str(root), str(final_json), result)
            self.assertEqual(rc, 0)
            rec = json.loads(final_json.read_text(encoding="utf-8"))
            self.assertEqual(rec["before_lecture_sha256"], result["lecture_sha256"])
            self.assertEqual(rec["final_lecture_sha256"], LC.sha256_file(doc))
            self.assertNotEqual(rec["before_lecture_sha256"], rec["final_lecture_sha256"])
            self.assertTrue(rec["pass"])
            self.assertTrue(rec["stamp_did_not_break_anything"])


class GateAllRecordFileTests(unittest.TestCase):
    """记录类文件声明了判据版本时，全库记分卡不许崩（原实现 `s_bad` 未定义 → NameError）。"""

    def test_record_class_file_with_declared_version_does_not_crash_scan(self):
        import gate_all
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # 记录类文件 + 声明判据版本 ≥ 2.21 → 走 `s_bad.extend(...)` 分支（原实现此时 s_bad 还没定义）
            (root / "批次0-整理批.md").write_text(
                "# 整理批\n\n> 判据版本：v2.21\n\n正文，但没有状态行也没有未完成清单。\n",
                encoding="utf-8")
            rows = gate_all.scan(str(root), str(root))
            self.assertEqual(len(rows), 1)
            self.assertIn("记录类", rows[0]["struct"], rows[0])


if __name__ == "__main__":
    unittest.main()
