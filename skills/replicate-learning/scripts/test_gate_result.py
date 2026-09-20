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

    def test_self_reported_failure_cannot_be_stamped(self):
        """审查发现：只按 checks[] 判定时，pass=false/verdict=FAIL 但各项写 PASS 的结果会被盖章。"""
        result = good_result(LC.sha256_file(self.doc))
        result["pass"] = False
        result["pass_"] = False
        result["verdict"] = "总判定: FAIL ❌"
        self.write_result(result)
        before = self.doc.read_text(encoding="utf-8")
        self.assertEqual(self.run_sync(["--apply"]), 1)
        self.assertEqual(self.doc.read_text(encoding="utf-8"), before)
        problems = LC.validate_result(result, expect_lecture_sha256=LC.sha256_file(self.doc))
        blob = " ".join(problems)
        self.assertIn("pass=False", blob)
        self.assertIn("pass_=False", blob)
        self.assertIn("verdict=", blob)

    def test_rendered_top_level_confusing_pass_flags(self):
        result = good_result(LC.sha256_file(self.doc))
        result["pass_"] = False          # gate 的 pass_ 字段单独指向失败
        self.write_result(result)
        self.assertEqual(self.run_sync(["--apply"]), 1)

    def test_result_with_contradictory_conclusion_is_refused(self):
        result = good_result(LC.sha256_file(self.doc))
        result["checks"].append(LC.make_check("G-SIG", LC.FAIL, checked=1))
        result["pass"] = True            # 有阻塞项却自称通过
        self.write_result(result)
        self.assertEqual(self.run_sync(["--apply"]), 1)
        self.assertTrue(any("结论与检查项矛盾" in p
                            for p in LC.validate_result(result)))

    def test_rolls_back_even_when_verification_itself_raises(self):
        """审查第二轮：复检过程**抛异常**（结果文件损坏等）也必须回滚，不能绕过还原。"""
        from unittest import mock
        bad = ("# 阶段测试批\n\n> 判据版本：v2.30\n\n"
               "## ⑯ 教材质量自检\n\n**判据版本：v2.30**（本批按此版判据验收）。\n\n## 索引节\n\n尾注。\n")
        self.doc.write_text(bad, encoding="utf-8")
        self.write_result(good_result(LC.sha256_file(self.doc)))
        before = self.doc.read_bytes()

        def boom(*_a, **_k):
            raise OSError("模拟复检自身出错（磁盘/权限/子进程异常）")

        argv = sys.argv
        sys.argv = ["sync_gate_result.py", str(self.doc), "--src", str(self.root),
                    "--result-json", str(self.result_path), "--apply",
                    "--final-json", str(self.root / "final.json")]
        try:
            with mock.patch.object(S, "verify_final", boom):
                rc = S.main()
        finally:
            sys.argv = argv
        self.assertEqual(rc, 1)
        self.assertEqual(self.doc.read_bytes(), before, "复检抛异常时也必须回滚讲义")
        rec = json.loads((self.root / "final.json").read_text(encoding="utf-8"))
        self.assertTrue(rec["rolled_back"])
        self.assertIn("模拟复检自身出错", rec["verification_error"])

    def test_corrupt_final_result_file_is_treated_as_failure(self):
        """复检读到的结果文件是半截/损坏 JSON 时：不抛异常，按未通过处理。"""
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "plain.md"
            doc.write_text("# 普通文档\n\n正文。\n", encoding="utf-8")
            jout = str(doc) + ".gate-final.json"

            class FakeProc:
                returncode = 0
                stdout = "总判定: PASS ✅\n"
                stderr = ""

            def fake_run(cmd, **kwargs):
                Path(jout).write_text("{半截的 JSON", encoding="utf-8")
                return FakeProc()

            with mock.patch.object(S.subprocess, "run", fake_run):
                code, rec = S.verify_final(str(doc), str(root), None,
                                           {"lecture_sha256": "a" * 64})
            self.assertNotEqual(code, 0, rec)
            self.assertFalse(rec["stamp_did_not_break_anything"])
            self.assertIn("result_read_error", rec)

    def test_restore_reports_failure_instead_of_raising(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = str(Path(tmp) / "sub" / "not-there.md")   # 父目录不存在 → 写失败
            self.assertFalse(S.restore(missing, b"x"))

    def test_rolls_back_when_post_stamp_verification_fails(self):
        """盖章后复检失败必须**自动还原讲义**（审查发现的第三处缺陷）。

        这里构造一个真实场景：结果本身自洽（各项 PASS、pass=true、哈希与当前正文一致）而被盖章，
        但这份正文其实过不了闸门（声明了判据版本却缺 ⓪e/⓪f 要求的形态）——
        盖章后复跑必然 FAIL，讲义必须回到盖章前的字节。
        """
        bad = ("# 阶段测试批\n\n> 判据版本：v2.30\n\n"
               "## ⑯ 教材质量自检\n\n**判据版本：v2.30**（本批按此版判据验收）。\n\n## 索引节\n\n尾注。\n")
        self.doc.write_text(bad, encoding="utf-8")
        self.write_result(good_result(LC.sha256_file(self.doc)))
        before = self.doc.read_bytes()
        argv = sys.argv
        sys.argv = ["sync_gate_result.py", str(self.doc), "--src", str(self.root),
                    "--result-json", str(self.result_path), "--apply",
                    "--final-json", str(self.root / "final.json")]
        try:
            rc = S.main()
        finally:
            sys.argv = argv
        self.assertEqual(rc, 1, "盖章后复检失败必须返回非 0")
        self.assertEqual(self.doc.read_bytes(), before, "失败时必须自动回滚讲义")
        rec = json.loads((self.root / "final.json").read_text(encoding="utf-8"))
        self.assertFalse(rec["stamp_did_not_break_anything"])
        self.assertTrue(rec["rolled_back"])


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
            code, rec = S.verify_final(str(doc), str(root), str(final_json), result)
            self.assertEqual(code, 0, rec)
            S.write_final_record(str(final_json), rec)
            self.assertEqual(rec["before_lecture_sha256"], result["lecture_sha256"])
            self.assertEqual(rec["final_lecture_sha256"], LC.sha256_file(doc))
            self.assertNotEqual(rec["before_lecture_sha256"], rec["final_lecture_sha256"])
            self.assertTrue(rec["pass"])
            self.assertEqual(rec["exit_code"], 0)
            self.assertTrue(rec["stamp_did_not_break_anything"])

    def test_final_verification_requires_zero_exit_code(self):
        """只看结构化 pass 会漏掉"检查器崩了但结果文件是旧的"：退出码非 0 一律算没通过。"""
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            doc = root / "plain.md"
            doc.write_text("# 普通文档\n\n正文。\n", encoding="utf-8")
            jout = str(doc) + ".gate-final.json"

            class FakeProc:
                returncode = 1
                stdout = "总判定: PASS ✅\n"
                stderr = "boom\n"

            def fake_run(cmd, **kwargs):
                # 模拟"闸门崩了但上一个结果文件还在"：结果自述 pass=true，进程退出码却是 1
                Path(jout).write_text(json.dumps({"pass": True, "contract_version": "2.30",
                                                  "checks": []}), encoding="utf-8")
                return FakeProc()

            with mock.patch.object(S.subprocess, "run", fake_run):
                code, rec = S.verify_final(str(doc), str(root), None,
                                           {"lecture_sha256": "a" * 64})
            self.assertNotEqual(code, 0, rec)
            self.assertFalse(rec["stamp_did_not_break_anything"])
            self.assertEqual(rec["exit_code"], 1)
            self.assertFalse(os.path.exists(jout), "复检用的临时结果文件必须清掉")


class ConclusionFieldTests(unittest.TestCase):
    """审查第三轮：结论字段**缺失**与"取值不合格"同样必须拒绝（原来缺字段即放行）。"""

    def test_make_result_always_emits_the_conclusion_fields(self):
        result = good_result("a" * 64)
        for field in ("pass", "pass_", "verdict"):
            self.assertIn(field, result)
        self.assertTrue(result["pass"])
        self.assertTrue(result["pass_"])
        self.assertTrue(str(result["verdict"]).startswith("PASS"))

    def test_validate_result_requires_each_conclusion_field(self):
        for field in ("pass", "pass_", "verdict"):
            with self.subTest(field=field):
                result = good_result("a" * 64)
                result.pop(field)
                problems = LC.validate_result(result, expect_lecture_sha256="a" * 64,
                                              expect_contract_version=VERSION,
                                              required_ids=list(S.REQUIRED_CHECKS))
                self.assertTrue(any(("缺少顶层结论字段 %s" % field) in p for p in problems), problems)

    def test_validate_result_rejects_a_result_without_any_conclusion_fields(self):
        problems = LC.validate_result({"schema_version": LC.SCHEMA_VERSION,
                                       "checks": [{"id": "G-STRUCT", "status": LC.PASS,
                                                   "checked": 1}]})
        blob = " ".join(problems)
        for field in ("pass", "pass_", "verdict"):
            self.assertIn("缺少顶层结论字段 %s" % field, blob)


class VerdictStrictnessTests(unittest.TestCase):
    """审查第四轮：`verdict` 只认确切写法，**不能"包含 PASS"就算通过**（`BYPASS` 曾能溜过）。"""

    def test_accepts_only_the_two_canonical_forms(self):
        for good in ("PASS", "pass", " PASS ", "PASS ✅", "总判定: PASS", "总判定: PASS ✅",
                     "总判定：PASS ✅", "PASS。"):
            with self.subTest(verdict=good):
                self.assertTrue(LC.verdict_is_pass(good), good)

    def test_rejects_lookalikes_and_failures(self):
        for bad in ("BYPASS", "PASSED", "NOT PASS", "PASSFAIL", "  ", "", None, True, 1,
                    "总判定: FAIL ❌", "FAIL", "总判定: BYPASS ✅", "通过", "pas"):
            with self.subTest(verdict=bad):
                self.assertFalse(LC.verdict_is_pass(bad), bad)

    def test_bypass_verdict_blocks_the_stamp(self):
        for lookalike in ("BYPASS", "总判定: BYPASS ✅", "PASSED"):
            with self.subTest(verdict=lookalike):
                result = good_result("a" * 64)
                result["verdict"] = lookalike
                problems = LC.validate_result(result, expect_lecture_sha256="a" * 64,
                                              expect_contract_version=VERSION,
                                              required_ids=list(S.REQUIRED_CHECKS))
                self.assertTrue(any("verdict" in p for p in problems), problems)


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
