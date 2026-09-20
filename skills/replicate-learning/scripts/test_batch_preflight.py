"""Regression tests for the open-batch preflight (plan §3.2).

The acceptance evidence is the *real* batch 48: its first-round annotation plan must be reported as
"3 ★ signature gaps + 5 density runs" **before** injection, and the repaired plan must come back clean.
That is exactly what the original session discovered only after injecting and running the gate — and
only after writing two throwaway probe scripts whose results disagreed with the gate.
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_preflight as P
import lecture_checks as LC

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
FIX = SKILL / "tests" / "fixtures"
B48 = FIX / "batch48"
PYMINI = FIX / "py_mini"


def run_main(argv):
    """跑 main()，返回 (退出码, 输出文本)。"""
    buf = io.StringIO()
    old = sys.argv
    sys.argv = ["batch_preflight.py"] + argv
    try:
        with contextlib.redirect_stdout(buf):
            rc = P.main()
    finally:
        sys.argv = old
    return rc, buf.getvalue()


def load_result(path):
    return LC.load_result(path)


def checks_by_id(result):
    return {c["id"]: c for c in result["checks"]}


class Batch48FixtureTests(unittest.TestCase):
    """真实批次48：首轮计划必须报出与当时闸门一致的结论。"""

    SRC = str(B48 / "project")
    PLAN_R1 = str(B48 / "b48_inject_plan_r1.json")
    PLAN_FIXED = str(B48 / "b48_inject_plan_fixed.json")
    MANIFEST = str(B48 / "b48_manifest.json")

    def _run(self, plan):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "pre.json")
            rc, text = run_main(["--src", self.SRC, "--plan", plan, "--manifest", self.MANIFEST,
                                 "--json", out])
            return rc, text, load_result(out)

    def test_first_round_plan_reports_the_three_signature_gaps(self):
        rc, _text, result = self._run(self.PLAN_R1)
        self.assertNotEqual(rc, 0)
        sig = checks_by_id(result)["P-SIG"]
        self.assertEqual(sig["status"], LC.FAIL)
        blob = json.dumps(sig, ensure_ascii=False)
        for method in ("appendRow", "sanitizeCell", "appendSeparator"):
            self.assertIn(method, blob, "首轮计划应报出 %s 的签名缺注释" % method)
        self.assertIn("TableChunker", blob)

    def test_first_round_plan_reports_the_five_density_runs(self):
        rc, _text, result = self._run(self.PLAN_R1)
        self.assertNotEqual(rc, 0)
        density = checks_by_id(result)["P-DENSITY"]
        self.assertEqual(density["status"], LC.FAIL)
        self.assertEqual(len(density["findings"]), 5, density["findings"])
        runs = sorted(int(f["message"].split("最长无中文注释连段 ")[1].split(" 行")[0])
                      for f in density["findings"])
        self.assertEqual(runs, [8, 8, 10, 10, 10])
        files = sorted(os.path.basename(f["where"]) for f in density["findings"])
        self.assertEqual(files, ["CodeChunker.java", "ImageChunker.java", "ListChunker.java",
                                "ParagraphChunker.java", "TableChunker.java"])

    def test_density_findings_point_at_real_code_lines_not_only_comments(self):
        _rc, _text, result = self._run(self.PLAN_R1)
        density = checks_by_id(result)["P-DENSITY"]
        for f in density["findings"]:
            hint = f["message"].split("补注释：")[1]
            self.assertRegex(hint, r":\d+ \S", "候选行必须带行号与真实源码内容")
            self.assertNotIn(":1 /*", hint)

    def test_repaired_plan_is_clean(self):
        rc, text, result = self._run(self.PLAN_FIXED)
        self.assertEqual(rc, 0, text)
        self.assertTrue(result["pass"], LC.render(result))
        ids = checks_by_id(result)
        self.assertEqual(ids["P-DENSITY"]["status"], LC.PASS)
        self.assertEqual(ids["P-SIG"]["status"], LC.PASS)
        self.assertGreater(ids["P-DENSITY"]["checked"], 0)
        self.assertGreater(ids["P-SIG"]["checked"], 0)

    def test_result_is_bound_to_the_checked_content(self):
        _rc, _text, result = self._run(self.PLAN_FIXED)
        self.assertEqual(result["lecture_sha256"], None)          # 预检阶段还没有成稿
        self.assertTrue(result["source_manifest_sha256"])
        self.assertTrue(result["contract_sha256"])
        for c in result["checks"]:
            self.assertIn(c["status"], LC.STATUSES)
            self.assertTrue(c["contract"], "每条检查都必须挂到 SSOT 条款 ID")


class ManifestCoverageTests(unittest.TestCase):
    """P-HASH 必须要求清单**覆盖注释计划里的全部源文件**（批次49 实录）。

    当时的形态：4 个源文件分别 `batch_manifest.py prepare` 出 4 份清单，只把其中一份传给预检——
    清单里那 1 个文件哈希是对的，于是 P-HASH PASS，而本批另外 3 个源文件**根本没被钉住**。
    "清单里有的都合格"不等于"本批源码都被核过"，这就是漏检的形态。
    """

    SRC = str(B48 / "project")
    PLAN = str(B48 / "b48_inject_plan_fixed.json")
    MANIFEST = str(B48 / "b48_manifest.json")

    def _run(self, tmp, manifests, plan=None):
        out = os.path.join(tmp, "pre.json")
        argv = ["--src", self.SRC, "--plan", plan or self.PLAN]
        for m in manifests:
            argv += ["--manifest", m]
        argv += ["--json", out]
        rc, text = run_main(argv)
        return rc, text, load_result(out)

    def _truncate(self, tmp, keep):
        """按文件名子集裁一份清单（模拟"一个文件一份清单"）。"""
        man = json.load(io.open(self.MANIFEST, encoding="utf-8"))
        keys = [k for k in sorted(man["files"]) if os.path.basename(k) in keep]
        man["files"] = {k: man["files"][k] for k in keys}
        path = os.path.join(tmp, "one.json")
        io.open(path, "w", encoding="utf-8", newline="").write(json.dumps(man, ensure_ascii=False, indent=1))
        return path, keys

    def test_full_manifest_covers_every_source_of_the_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            rc, text, result = self._run(tmp, [self.MANIFEST])
            self.assertEqual(rc, 0, text)
            ph = checks_by_id(result)["P-HASH"]
            self.assertEqual(ph["status"], LC.PASS)
            self.assertEqual(ph["checked"], 8)
            self.assertIn("覆盖计划源文件 8/8", ph["note"])

    def test_a_single_file_manifest_is_refused_and_names_the_missing_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path, keys = self._truncate(tmp, {"TableChunker.java"})
            self.assertEqual(len(keys), 1)
            rc, text, result = self._run(tmp, [path])
            self.assertNotEqual(rc, 0)
            ph = checks_by_id(result)["P-HASH"]
            self.assertEqual(ph["status"], LC.FAIL)
            blob = json.dumps(ph, ensure_ascii=False)
            for missing in ("CodeChunker.java", "HeadingChunker.java", "HeadingHandler.java",
                            "HtmlTableChunker.java", "ImageChunker.java", "ListChunker.java",
                            "ParagraphChunker.java"):
                self.assertIn(missing, blob, "缺件必须逐个点名：%s" % missing)
            self.assertIn("没覆盖", blob)
            self.assertIn("覆盖计划源文件 1/8", ph["note"])

    def test_several_manifests_are_merged_and_cover_the_plan_together(self):
        """4 份单文件清单一起传 → 合并后覆盖 8/8，P-HASH PASS（"每个文件一份清单"是允许的用法）。"""
        with tempfile.TemporaryDirectory() as tmp:
            man = json.load(io.open(self.MANIFEST, encoding="utf-8"))
            keys = sorted(man["files"])
            paths = []
            for i, k in enumerate(keys):
                part = dict(man)
                part["files"] = {k: man["files"][k]}
                p = os.path.join(tmp, "m%d.json" % i)
                io.open(p, "w", encoding="utf-8", newline="").write(
                    json.dumps(part, ensure_ascii=False, indent=1))
                paths.append(p)
            self.assertEqual(len(paths), 8)
            rc, text, result = self._run(tmp, paths)
            self.assertEqual(rc, 0, text)
            ph = checks_by_id(result)["P-HASH"]
            self.assertEqual(ph["status"], LC.PASS)
            self.assertEqual(ph["checked"], 8)
            self.assertIn("合并 8 份清单", ph["note"])
            self.assertTrue(result["source_manifest_sha256"], "多份清单也要给出确定性指纹")

    def test_a_drifted_hash_is_still_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            man = json.load(io.open(self.MANIFEST, encoding="utf-8"))
            first = sorted(man["files"])[0]
            man["files"][first]["sha256"] = "0" * 64
            path = os.path.join(tmp, "drift.json")
            io.open(path, "w", encoding="utf-8", newline="").write(
                json.dumps(man, ensure_ascii=False, indent=1))
            rc, text, result = self._run(tmp, [path])
            self.assertNotEqual(rc, 0)
            ph = checks_by_id(result)["P-HASH"]
            self.assertEqual(ph["status"], LC.FAIL)
            self.assertIn("hash 不一致", json.dumps(ph, ensure_ascii=False))


class PlanStructureTests(unittest.TestCase):
    def test_bad_keys_in_python_plan_are_all_reported(self):
        rc, text = run_main(["--src", str(PYMINI / "project"), "--plan",
                             str(PYMINI / "plan_bad_keys.json")])
        self.assertNotEqual(rc, 0)
        for expected in ("不是行号", "超出源文件", "Python 多行字符串", "反斜杠续行"):
            self.assertIn(expected, text)

    def test_valid_python_plan_reports_counts_instead_of_passing_silently(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "pre.json")
            rc, _text = run_main(["--src", str(PYMINI / "project"), "--plan",
                                  str(PYMINI / "plan.json"), "--json", out])
            result = load_result(out)
        self.assertEqual(rc, 0)
        ids = checks_by_id(result)
        self.assertEqual(ids["P-PY"]["status"], LC.REPORT)
        self.assertEqual(ids["P-PY"]["checked"], 1)
        self.assertIn("compile()", ids["P-PY"]["note"])
        for cid in ("P-DENSITY", "P-SIG", "P-REVERSE"):
            self.assertEqual(ids[cid]["status"], LC.NOT_CHECKED, cid)
            self.assertEqual(ids[cid]["checked"], 0)

    def test_java_plan_key_problems_are_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Foo.java").write_text(
                "package demo;\n\npublic class Foo {\n"
                + "".join("    private int f%d = %d;\n" % (i, i) for i in range(1, 8))
                + "    public int sum() {\n        return f1 + f2;\n    }\n}\n", encoding="utf-8")
            plan = {
                "blocks": [{"anchor": "6.1 Foo", "lang": "java", "src": "Foo.java", "start": 1,
                            "end": 12, "anno": {"3": "类声明", "99": "越界", "x": "非数字"}}]
            }
            (root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            rc, text = run_main(["--src", str(root), "--plan", str(root / "plan.json")])
            self.assertNotEqual(rc, 0)
            self.assertIn("超出源文件", text)
            self.assertIn("不是行号", text)

    def test_duplicate_normalized_keys_are_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Foo.java").write_text(
                "package demo;\n\npublic class Foo {\n" + "".join(
                    "    private int f%d = %d;\n" % (i, i) for i in range(1, 9))
                + "    public int sum() {\n        return f1 + f2;\n    }\n}\n", encoding="utf-8")
            plan = {"blocks": [{"anchor": "6.1 Foo", "lang": "java", "src": "Foo.java",
                                "start": 1, "end": 13, "anno": {"5": "甲", "5-7": "乙"}}]}
            (root / "plan.json").write_text(json.dumps(plan, ensure_ascii=False), encoding="utf-8")
            rc, text = run_main(["--src", str(root), "--plan", str(root / "plan.json")])
            self.assertNotEqual(rc, 0)
            self.assertIn("规范化后同为第 5 行", text)

    def test_source_hash_mismatch_stops_the_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Foo.java").write_text("package demo;\npublic class Foo {}\n", encoding="utf-8")
            manifest = {"schema_version": 1, "source_root": ".", "files": {
                "Foo.java": {"sha256": "0" * 64, "bytes": 1}}}
            (root / "m.json").write_text(json.dumps(manifest), encoding="utf-8")
            plan = {"blocks": [{"src": "Foo.java", "lang": "java"}]}
            (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
            with tempfile.TemporaryDirectory() as tmp2:
                out = os.path.join(tmp2, "pre.json")
                rc, text = run_main(["--src", str(root), "--plan", str(root / "plan.json"),
                                     "--manifest", str(root / "m.json"), "--json", out])
                result = load_result(out)
            self.assertNotEqual(rc, 0)
            self.assertEqual(checks_by_id(result)["P-HASH"]["status"], LC.FAIL)
            self.assertIn("hash 不一致", text)


class SnippetTests(unittest.TestCase):
    """`【怎么用】/【怎么接】` 片段：能判的判，判不了的标 manual_review（不声称可编译）。"""

    def _run_snippet(self, snippet):
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        (root / "Foo.java").write_text(
            "package demo;\n\npublic class Foo {\n"
            "    private final String name;\n    private final int size;\n\n"
            "    public Foo(String name, int size) {\n"
            "        this.name = name;\n        this.size = size;\n    }\n}\n", encoding="utf-8")
        lecture = root / "batch.md"
        lecture.write_text(
            "## ⑥ 逐件讲解\n\n### 6.1 Foo\n\n**【怎么用】**\n\n```java\n" + snippet + "\n```\n",
            encoding="utf-8")
        plan = {"blocks": [{"anchor": "6.1 Foo", "lang": "java", "src": "Foo.java", "start": 6,
                            "end": 10, "anno": {"7": "构造器：两个字段都由调用方注入，本类不做默认值"}}]}
        (root / "plan.json").write_text(json.dumps(plan), encoding="utf-8")
        out = root / "pre.json"
        rc, text = run_main(["--src", str(root), "--plan", str(root / "plan.json"),
                             "--lecture", str(lecture), "--json", str(out)])
        return rc, text, load_result(str(out)), tmp

    def test_wrong_argument_count_is_a_hard_failure(self):
        rc, text, result, tmp = self._run_snippet("Foo foo = new Foo(\"a\", 1, 2);")
        try:
            self.assertNotEqual(rc, 0)
            snip = checks_by_id(result)["P-SNIP"]
            self.assertEqual(snip["status"], LC.FAIL)
            self.assertIn("传了 3 个实参", json.dumps(snip, ensure_ascii=False))
        finally:
            tmp.cleanup()

    def test_swapped_argument_order_is_caught_when_types_disagree(self):
        rc, _text, result, tmp = self._run_snippet("Foo foo = new Foo(7, \"a\");")
        try:
            self.assertNotEqual(rc, 0)
            blob = json.dumps(checks_by_id(result)["P-SNIP"], ensure_ascii=False)
            self.assertIn("疑似参数顺序错误", blob)
        finally:
            tmp.cleanup()

    def test_correct_snippet_is_not_reported_as_failure(self):
        rc, text, result, tmp = self._run_snippet("Foo foo = new Foo(\"a\", 7);")
        try:
            self.assertEqual(rc, 0, text)
            self.assertEqual(checks_by_id(result)["P-SNIP"]["status"], LC.REPORT)
        finally:
            tmp.cleanup()

    def test_unknown_type_is_marked_manual_review(self):
        _rc, _text, result, tmp = self._run_snippet("Widget w = new Widget(\"a\", 1);")
        try:
            snip = checks_by_id(result)["P-SNIP"]
            blob = json.dumps(snip, ensure_ascii=False)
            self.assertIn("无法核实", blob)
            self.assertTrue(all(f.get("severity") != LC.FAIL for f in snip["findings"] if "无法核实" in f["message"]))
        finally:
            tmp.cleanup()

    def test_unbalanced_braces_are_a_hard_failure(self):
        rc, _text, result, tmp = self._run_snippet("Foo foo = new Foo(\"a\", 1);\nif (foo != null) {")
        try:
            self.assertNotEqual(rc, 0)
            blob = json.dumps(checks_by_id(result)["P-SNIP"], ensure_ascii=False)
            self.assertIn("花括号不配对", blob)
        finally:
            tmp.cleanup()


class ResultSchemaTests(unittest.TestCase):
    def test_zero_objects_cannot_be_reported_as_pass(self):
        with self.assertRaises(ValueError):
            LC.make_check("P-DENSITY", LC.PASS, checked=0)

    def test_inapplicable_check_cannot_be_reported_as_pass(self):
        with self.assertRaises(ValueError):
            LC.make_check("P-DENSITY", LC.PASS, checked=3, applicable=False)

    def test_registry_ids_all_exist_in_the_ssot(self):
        self.assertEqual(LC.unknown_contract_ids(), [])

    def test_validate_result_rejects_stale_hashes_and_versions(self):
        result = LC.make_result("test", [LC.make_check("P-DENSITY", LC.PASS, checked=2)],
                                contract_version="2.30", lecture_sha256="a" * 64,
                                source_manifest_sha256="b" * 64)
        self.assertEqual(LC.validate_result(result, expect_lecture_sha256="a" * 64,
                                            expect_manifest_sha256="b" * 64,
                                            expect_contract_version="2.30",
                                            required_ids=["P-DENSITY"]), [])
        problems = LC.validate_result(result, expect_lecture_sha256="c" * 64,
                                      expect_manifest_sha256="b" * 64,
                                      expect_contract_version="2.29", required_ids=["P-PLAN"])
        blob = " ".join(problems)
        self.assertIn("正文在检查之后被改过", blob)
        self.assertIn("旧结果不得给新正文背书", blob)
        self.assertIn("缺少必需检查 P-PLAN", blob)

    def test_validate_result_flags_a_vacuous_pass(self):
        bad = {"schema_version": LC.SCHEMA_VERSION, "checks": [
            {"id": "P-DENSITY", "status": LC.PASS, "checked": 0}]}
        self.assertTrue(any("真空通过" in p for p in LC.validate_result(bad)))


if __name__ == "__main__":
    unittest.main()
