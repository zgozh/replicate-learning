"""The single batch record must publish all derived views safely (plan §3.5).

Acceptance from the plan:
  * preview the expected additions, re-run with zero change (idempotent);
  * a conflict in the *second* file leaves **every** target untouched;
  * the user's own edits survive;
  * a nested git repo only ever receives the files named in the record.
"""

import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import lecture_checks as LC
import publish_batch as P
from test_gate_result import good_result

LEDGERS = {
    "NOTES/项目文件覆盖矩阵.md": "# 覆盖矩阵\n\n| 文件 | 状态 |\n|---|---|\n| 旧件 | 已讲 |\n\n尾注。\n",
    "NOTES/总索引.md": ("# 总索引\n\n## 批次清单\n\n- 阶段3批次47 已归档\n\n"
                        "| 批次 | 标题 | 判据 | 状态 |\n|---|---|---|---|\n"
                        "| 批次47 | 智能切片 | 判据 v2.29 | 已验收 |\n"
                        "| 批次49 | 切片收口与装配 | 判据 v2.30 | 已验收 |\n"),
    "NOTES/阶段3-切分方案.md": "# 阶段3\n\n## 本阶段进度\n\n- 批次47 完成\n",
    "NOTES/复刻状态-下一步.md": "# 精简状态\n\n> 状态：进行中\n\n下一批：阶段3批次48\n",
}

# 回修场景的真实形态：判据 2.30 → 2.31 之后，总索引里那一行还印着旧版本号。
OLD_ROW = "| 批次49 | 切片收口与装配 | 判据 v2.30 | 已验收 |"
NEW_ROW = "| 批次49 | 切片收口与装配 | 判据 v2.31 | 已验收 |"


def make_project(tmp, lecture=True):
    root = Path(tmp)
    for rel, body in LEDGERS.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    lec = root / "NOTES" / "教学讲解" / "批次48-智能切片.md"
    lec.parent.mkdir(parents=True, exist_ok=True)
    lec.write_text("# 阶段3 · 批次48\n\n正文。\n", encoding="utf-8")
    final = root / "NOTES" / ".replicate-learning" / "b48.final.json"
    final.parent.mkdir(parents=True, exist_ok=True)
    # 一份**健康**的最终记录：发布入口会逐项核对 pass / exit_code / rolled_back /
    # stamp_did_not_break_anything / contract_version / final_lecture_sha256（审查第二轮要求）
    final.write_text(json.dumps({
        "schema_version": LC.SCHEMA_VERSION, "pass": True, "exit_code": 0,
        "rolled_back": False, "stamp_did_not_break_anything": True,
        "contract_version": LC.load_contract()["version"],
        "final_lecture_sha256": LC.sha256_file(lec), "verdict": "总判定: PASS ✅",
    }, ensure_ascii=False), encoding="utf-8")
    return root, lec, final


def make_record(root, lec, final, targets=None):
    return {
        "schema_version": 1,
        "project_root": str(root),
        "batch_id": "stage3-b48",
        "batch_no": 48,
        "next_batch": "stage3-b49",
        "title": "智能切片策略",
        "book": 1,
        "lecture": str(Path(lec).relative_to(root)).replace("\\", "/"),
        "gate_final": str(Path(final).relative_to(root)).replace("\\", "/"),
        "lecture_sha256": LC.sha256_file(lec),
        "teaching": [{"file": "rag/src/main/java/TableChunker.java", "role": "主讲"},
                     {"file": "rag/src/main/java/ChunkContext.java", "role": "回链"}],
        "targets": targets if targets is not None else [
            {"file": "NOTES/项目文件覆盖矩阵.md", "op": "insert_before_anchor", "anchor": "| 旧件 | 已讲 |",
             "idempotent_key": "批次48",
             "text": "| rag/.../TableChunker.java | 已讲（阶段3批次48） |"},
            {"file": "NOTES/总索引.md", "op": "append_section", "idempotent_key": "批次48-智能切片",
             "text": "### 批次48-智能切片\n\n- 主讲：TableChunker★\n"},
            {"file": "NOTES/阶段3-切分方案.md", "op": "ensure_line", "idempotent_key": "批次48 完成",
             "text": "- 批次48 完成"},
            {"file": "NOTES/复刻状态-下一步.md", "op": "replace_anchor", "anchor": "下一批：阶段3批次48",
             "expect": "阶段3批次48", "idempotent_key": "下一批：阶段3批次49",
             "text": "下一批：阶段3批次49"},
        ],
    }


class PublishTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.lec, self.final = make_project(self.tmp.name)
        self.record_path = self.root / "batch_record.json"
        self.write_record(make_record(self.root, self.lec, self.final))

    def tearDown(self):
        self.tmp.cleanup()

    def write_record(self, rec):
        self.record_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    def run_publish(self, extra=()):
        argv = sys.argv
        sys.argv = ["publish_batch.py", "--record", str(self.record_path)] + list(extra)
        try:
            return P.main()
        finally:
            sys.argv = argv

    def snapshot(self):
        return {rel: (self.root / rel).read_text(encoding="utf-8") for rel in LEDGERS}

    def test_dry_run_previews_without_writing(self):
        before = self.snapshot()
        self.assertEqual(self.run_publish(), 0)
        self.assertEqual(self.snapshot(), before)

    def test_two_updates_on_the_same_file_both_land(self):
        """审查发现：同一文件的多条更新会互相覆盖（每条都从磁盘原文起算）。

        真实形态：同一个状态文件既要补一行"本批已完成"，又要改"下一批"指针。
        """
        rec = make_record(self.root, self.lec, self.final)
        rec["targets"] = [
            {"file": "NOTES/复刻状态-下一步.md", "op": "ensure_line",
             "idempotent_key": "阶段3批次48 已完成", "text": "- 阶段3批次48 已完成"},
            {"file": "NOTES/复刻状态-下一步.md", "op": "replace_anchor",
             "anchor": "下一批：阶段3批次48", "expect": "阶段3批次48",
             "idempotent_key": "下一批：阶段3批次49", "text": "下一批：阶段3批次49"},
        ]
        self.write_record(rec)
        self.assertEqual(self.run_publish(["--apply"]), 0)
        text = (self.root / "NOTES/复刻状态-下一步.md").read_text(encoding="utf-8")
        self.assertIn("- 阶段3批次48 已完成", text, "第一条更新被第二条覆盖了")
        self.assertIn("下一批：阶段3批次49", text)
        self.assertNotIn("下一批：阶段3批次48", text)

    def test_three_updates_on_the_same_file_are_sequential(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["targets"] = [
            {"file": "NOTES/阶段3-切分方案.md", "op": "ensure_line",
             "idempotent_key": "A", "text": "- A 第一条"},
            {"file": "NOTES/阶段3-切分方案.md", "op": "ensure_line",
             "idempotent_key": "B", "text": "- B 第二条"},
            {"file": "NOTES/阶段3-切分方案.md", "op": "append_section",
             "idempotent_key": "C", "text": "- C 第三条"},
        ]
        self.write_record(rec)
        self.assertEqual(self.run_publish(["--apply"]), 0)
        text = (self.root / "NOTES/阶段3-切分方案.md").read_text(encoding="utf-8")
        for token in ("- A 第一条", "- B 第二条", "- C 第三条"):
            self.assertIn(token, text)
        # 重复发布仍然零变化（分组后的幂等性）
        after = text
        self.assertEqual(self.run_publish(["--apply"]), 0)
        self.assertEqual((self.root / "NOTES/阶段3-切分方案.md").read_text(encoding="utf-8"), after)

    def test_same_file_conflict_in_the_second_update_leaves_the_file_untouched(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["targets"] = [
            {"file": "NOTES/复刻状态-下一步.md", "op": "ensure_line",
             "idempotent_key": "阶段3批次48 已完成", "text": "- 阶段3批次48 已完成"},
            {"file": "NOTES/复刻状态-下一步.md", "op": "replace_anchor",
             "anchor": "不存在的锚点", "text": "下一批：阶段3批次49"},
        ]
        self.write_record(rec)
        before = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertEqual(self.snapshot(), before, "同一文件的第二条冲突时，第一条也不许落盘")

    def test_apply_updates_every_view_once(self):
        self.assertEqual(self.run_publish(["--apply"]), 0)
        matrix = (self.root / "NOTES/项目文件覆盖矩阵.md").read_text(encoding="utf-8")
        self.assertIn("阶段3批次48", matrix)
        self.assertIn("| 旧件 | 已讲 |", matrix, "插入不得吃掉锚点行")
        index = (self.root / "NOTES/总索引.md").read_text(encoding="utf-8")
        self.assertIn("### 批次48-智能切片", index)
        stage = (self.root / "NOTES/阶段3-切分方案.md").read_text(encoding="utf-8")
        self.assertIn("- 批次48 完成", stage)
        state = (self.root / "NOTES/复刻状态-下一步.md").read_text(encoding="utf-8")
        self.assertIn("下一批：阶段3批次49", state)
        self.assertNotIn("下一批：阶段3批次48", state)

    def test_second_run_changes_nothing(self):
        self.assertEqual(self.run_publish(["--apply"]), 0)
        after_first = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 0)
        self.assertEqual(self.snapshot(), after_first, "重复发布必须零变化（幂等）")

    def test_conflict_in_second_file_leaves_every_target_untouched(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["targets"][1]["anchor"] = None
        rec["targets"][1]["op"] = "insert_before_anchor"
        rec["targets"][1]["anchor"] = "这一行根本不存在"
        self.write_record(rec)
        before = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertEqual(self.snapshot(), before, "第二处冲突时第一处也不许写下去")

    def test_missing_anchor_is_a_conflict(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["targets"][0]["anchor"] = "不存在的锚点"
        self.write_record(rec)
        before = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertEqual(self.snapshot(), before)

    def test_user_edits_survive(self):
        extra = "\n用户自己加的一行：不要覆盖我。\n"
        p = self.root / "NOTES/项目文件覆盖矩阵.md"
        p.write_text(p.read_text(encoding="utf-8") + extra, encoding="utf-8")
        self.assertEqual(self.run_publish(["--apply"]), 0)
        self.assertIn("用户自己加的一行", p.read_text(encoding="utf-8"))

    def test_path_escape_is_refused(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["targets"][0]["file"] = "../outside.md"
        self.write_record(rec)
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertFalse((Path(self.tmp.name).parent / "outside.md").exists())

    def test_stale_lecture_hash_is_refused(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["lecture_sha256"] = "0" * 64
        self.write_record(rec)
        before = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertEqual(self.snapshot(), before)

    def test_gate_final_must_match_the_current_lecture(self):
        self.lec.write_text(self.lec.read_text(encoding="utf-8") + "\n盖章后又改了一行。\n",
                            encoding="utf-8")
        rec = make_record(self.root, self.lec, self.final)
        rec.pop("lecture_sha256")            # 记录没记哈希，但门禁最终记录对不上 → 仍然拒绝
        self.write_record(rec)
        before = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertEqual(self.snapshot(), before)

    def test_failed_gate_record_is_refused(self):
        self.final.write_text(json.dumps({"pass": False, "final_lecture_sha256":
                                          LC.sha256_file(self.lec)}), encoding="utf-8")
        before = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertEqual(self.snapshot(), before)

    # ── 审查第二轮：发布入口必须用**完整结论校验**，不能只看单个字段 ──
    def _final(self, drop=(), **overrides):
        rec = {"schema_version": LC.SCHEMA_VERSION, "pass": True, "exit_code": 0,
               "rolled_back": False, "stamp_did_not_break_anything": True,
               "contract_version": LC.load_contract()["version"],
               "final_lecture_sha256": LC.sha256_file(self.lec)}
        rec.update(overrides)
        for field in drop:
            rec.pop(field, None)
        self.final.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")

    def test_gate_final_missing_required_fields_is_refused(self):
        """审查第三轮：字段**缺失**与"取值不合格"同样必须拒绝（原来缺字段即放行）。"""
        for field in ("pass", "exit_code", "rolled_back", "stamp_did_not_break_anything",
                      "contract_version", "final_lecture_sha256"):
            with self.subTest(field=field):
                self._final(drop=(field,))
                before = self.snapshot()
                self.assertEqual(self.run_publish(["--apply"]), 1, "缺 %s 仍被接受" % field)
                self.assertEqual(self.snapshot(), before)

    def test_gate_final_with_null_required_field_is_refused(self):
        for field in ("contract_version", "stamp_did_not_break_anything"):
            with self.subTest(field=field):
                self._final(**{field: None})
                self.assertEqual(self.run_publish(["--apply"]), 1, "%s=null 仍被接受" % field)

    def test_gate_final_type_confusion_is_refused(self):
        """审查第四轮：`exit_code=true`、`pass=1`、`rolled_back=0` 这类**类型冒充**必须拒绝。

        JSON 里 `true` 与 `1` 能被 `==`/真值判断混为一谈，一旦放过就等于"没通过也能写成通过"。
        """
        cases = [
            ("exit_code", True), ("exit_code", False), ("exit_code", "0"), ("exit_code", 0.0),
            ("exit_code", 1), ("exit_code", "1"),
            ("pass", 1), ("pass", "true"), ("pass", "True"), ("pass", 0),
            ("stamp_did_not_break_anything", 1), ("stamp_did_not_break_anything", "true"),
            ("rolled_back", 0), ("rolled_back", "false"), ("rolled_back", ""),
            ("contract_version", 2.3), ("contract_version", " 2.30 "), ("contract_version", "2.17"),
            ("final_lecture_sha256", 12345), ("final_lecture_sha256", ""),
        ]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                self._final(**{field: value})
                before = self.snapshot()
                self.assertEqual(self.run_publish(["--apply"]), 1,
                                 "%s=%r（%s）仍被接受" % (field, value, type(value).__name__))
                self.assertEqual(self.snapshot(), before)

    def test_gate_final_with_exact_types_is_accepted(self):
        self._final()                       # pass=True / exit_code=0 / rolled_back=False（真布尔/真整数）
        self.assertEqual(self.run_publish(["--apply"]), 0)

    def test_gate_final_with_failed_rollback_is_refused(self):
        self._final(rollback_ok=False)
        self.assertEqual(self.run_publish(["--apply"]), 1)

    def test_gate_final_with_nonzero_exit_code_is_refused(self):
        """pass=true 但 exit_code=1（复检进程其实没通过）→ 不得发布。"""
        self._final(exit_code=1, stamp_did_not_break_anything=False)
        before = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertEqual(self.snapshot(), before)

    def test_gate_final_marked_rolled_back_is_refused(self):
        self._final(rolled_back=True, stamp_did_not_break_anything=False)
        self.assertEqual(self.run_publish(["--apply"]), 1)

    def test_gate_final_with_verification_error_is_refused(self):
        self._final(verification_error="JSONDecodeError: boom")
        self.assertEqual(self.run_publish(["--apply"]), 1)

    def test_gate_final_with_stale_contract_version_is_refused(self):
        self._final(contract_version="2.17")
        self.assertEqual(self.run_publish(["--apply"]), 1)

    def test_healthy_gate_final_is_accepted(self):
        self._final()
        self.assertEqual(self.run_publish(["--apply"]), 0)

    def test_direct_gate_result_entry_uses_full_validation(self):
        """旧的直接发布入口：`pass=false / verdict=FAIL` 但无阻塞项的记录也必须被拒。"""
        forged = good_result(LC.sha256_file(self.lec))
        for c in forged["checks"]:
            c["status"] = LC.PASS
            c["checked"] = c.get("checked") or 1
        forged["pass"] = False
        forged["pass_"] = False
        forged["verdict"] = "总判定: FAIL ❌"
        gr = self.root / "gate_result.json"
        gr.write_text(json.dumps(forged, ensure_ascii=False), encoding="utf-8")
        rec = make_record(self.root, self.lec, self.final)
        rec.pop("gate_final")
        rec["gate_result"] = "gate_result.json"
        self.write_record(rec)
        before = self.snapshot()
        self.assertEqual(self.run_publish(["--apply"]), 1)
        self.assertEqual(self.snapshot(), before)

    def test_direct_gate_result_entry_accepts_a_healthy_result(self):
        gr = self.root / "gate_result.json"
        gr.write_text(json.dumps(good_result(LC.sha256_file(self.lec)), ensure_ascii=False),
                      encoding="utf-8")
        rec = make_record(self.root, self.lec, self.final)
        rec.pop("gate_final")
        rec["gate_result"] = "gate_result.json"
        self.write_record(rec)
        self.assertEqual(self.run_publish(["--apply"]), 0)

    def test_direct_gate_result_entry_needs_the_required_checks(self):
        forged = good_result(LC.sha256_file(self.lec))
        forged["checks"] = [c for c in forged["checks"] if c["id"] != "G-DENSITY"]
        (self.root / "gate_result.json").write_text(json.dumps(forged, ensure_ascii=False),
                                                    encoding="utf-8")
        rec = make_record(self.root, self.lec, self.final)
        rec.pop("gate_final")
        rec["gate_result"] = "gate_result.json"
        self.write_record(rec)
        self.assertEqual(self.run_publish(["--apply"]), 1)

    def test_duplicate_master_files_are_refused(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["teaching"].append({"file": "rag/src/main/java/TableChunker.java", "role": "主讲"})
        self.write_record(rec)
        self.assertEqual(self.run_publish(["--apply"]), 1)

    def test_next_batch_number_may_not_regress(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["next_batch"] = "stage3-b47"
        self.write_record(rec)
        self.assertEqual(self.run_publish(["--apply"]), 1)

    def test_book_two_is_out_of_scope(self):
        rec = make_record(self.root, self.lec, self.final)
        rec["book"] = 2
        self.write_record(rec)
        self.assertEqual(self.run_publish(["--apply"]), 1)


class UpdateLineTests(unittest.TestCase):
    """回修**已发布行**（判据 2.30 → 2.31 之后，派生视图里行内的旧版本号必须跟着改）。

    为什么需要第五种 op（实现模型在批次49 的反馈）：`publish_batch` 原本只有四种"首次发布"op，
    回修已发布批次的既有行**没有对应通道**，只能另写一次性脚本——而那正是本工具存在的理由
    （逐处找锚点的一次性脚本会留下互相矛盾的状态）。旧 op 也表达不了这件事：
      · `replace_anchor` 拿旧行当锚点，回修一次后锚点消失 → **重复运行报"锚点命中 0 处"**（不幂等）；
      · `idempotent_key` 在回修场景里必然已在文件中（对象本来就是已发布批次）→ 按 key 跳过 =
        **回修静默不生效**。
    所以 `update_line` 的幂等按**目标行现状**判（行==text 跳过 / 行==expect 改 / 其他中止），
    并要求 anchor 在回修后仍唯一命中（否则幂等不可判定）。
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.lec, self.final = make_project(self.tmp.name)
        self.record_path = self.root / "batch_record.json"

    def tearDown(self):
        self.tmp.cleanup()

    def repair_record(self, targets, **overrides):
        rec = make_record(self.root, self.lec, self.final, targets=targets)
        rec.update(overrides)
        return rec

    def write_record(self, rec):
        self.record_path.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")

    def run_publish(self, extra=("--apply",)):
        argv = sys.argv
        sys.argv = ["publish_batch.py", "--record", str(self.record_path)] + list(extra)
        try:
            with contextlib.redirect_stdout(io.StringIO()) as buf:
                rc = P.main()
            return rc, buf.getvalue()
        finally:
            sys.argv = argv

    def index(self):
        return (self.root / "NOTES/总索引.md").read_text(encoding="utf-8")

    def snapshot(self):
        return {rel: (self.root / rel).read_text(encoding="utf-8") for rel in LEDGERS}

    def target(self, **override):
        t = {"file": "NOTES/总索引.md", "op": "update_line",
             "anchor": "| 批次49 |", "expect": OLD_ROW, "text": NEW_ROW}
        t.update(override)
        return t

    def test_repair_rewrites_the_published_line(self):
        self.write_record(self.repair_record([self.target()]))
        rc, out = self.run_publish()
        self.assertEqual(rc, 0, out)
        self.assertIn(NEW_ROW, self.index())
        self.assertNotIn("判据 v2.30", self.index())
        self.assertIn("回修锚点行", out)

    def test_repair_is_idempotent_on_rerun(self):
        """回修通道必须自己幂等——否则第二次发布会报冲突（旧 op 的形态）。"""
        self.write_record(self.repair_record([self.target()]))
        self.assertEqual(self.run_publish()[0], 0)
        after = self.snapshot()
        rc, out = self.run_publish()
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.snapshot(), after, "重复回修必须零变化")
        self.assertIn("该行已是回修后的内容", out)

    def test_repair_does_not_depend_on_the_idempotent_key(self):
        """回修对象本来就是已发布批次 → `idempotent_key` 必然已在文件中。

        若照旧按 key 跳过，回修会"成功返回但什么都没改"（静默不生效）——这正是要避免的形态。
        """
        self.write_record(self.repair_record([self.target(idempotent_key="批次49")]))
        self.assertIn("批次49", self.index())
        rc, out = self.run_publish()
        self.assertEqual(rc, 0, out)
        self.assertIn(NEW_ROW, self.index(), "带 idempotent_key 的回修被当成'已发布过'跳过了")

    def test_repair_with_wrong_expect_aborts_and_writes_nothing(self):
        self.write_record(self.repair_record([self.target(expect="| 批次49 | 别的标题 | 判据 v2.30 | 已验收 |")]))
        before = self.snapshot()
        rc, out = self.run_publish()
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(), before, "expect 不符时必须一个文件都不动")
        self.assertIn("expect 不符", out)

    def test_expect_must_be_the_whole_line_not_a_substring(self):
        """`replace_anchor` 的 expect 是**子串**语义；回修改的是整行，所以这里必须是整行原文。

        允许子串 = 允许"没读过这一行就改掉它"——回修恰恰是最需要"我知道这行现在是什么"的动作。
        """
        self.write_record(self.repair_record([self.target(expect="判据 v2.30")]))
        before = self.snapshot()
        rc, out = self.run_publish()
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("整行", out)

    def test_anchor_that_cannot_survive_the_repair_is_refused(self):
        """anchor 必须是回修后仍在的定位串；否则下次运行找不到它 → 幂等不可判定。"""
        self.write_record(self.repair_record([self.target(anchor=OLD_ROW)]))
        before = self.snapshot()
        rc, out = self.run_publish()
        self.assertEqual(rc, 1, "锚点回修后消失仍被接受——回修通道不幂等")
        self.assertEqual(self.snapshot(), before)
        self.assertIn("回修后命中 0 处", out)

    def test_repair_requires_expect_and_text(self):
        for drop in ("expect", "text"):
            with self.subTest(drop=drop):
                t = self.target()
                t.pop(drop)
                self.write_record(self.repair_record([t]))
                before = self.snapshot()
                rc, out = self.run_publish()
                self.assertEqual(rc, 1, "缺 %s 仍被接受" % drop)
                self.assertEqual(self.snapshot(), before)
                self.assertIn(drop, out)

    def test_repair_refuses_multiline_text(self):
        """一次只改一行：多行会让"这行改没改过"无法判定（块改动走 insert/replace）。"""
        self.write_record(self.repair_record([self.target(text=NEW_ROW + "\n| 追加 | 行 |")]))
        before = self.snapshot()
        rc, out = self.run_publish()
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("只改一行", out)

    def test_repair_refuses_a_no_op_target(self):
        self.write_record(self.repair_record([self.target(text=OLD_ROW)]))
        before = self.snapshot()
        rc, out = self.run_publish()
        self.assertEqual(rc, 1)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("不需要回修", out)

    def test_repair_mixes_with_first_publish_targets_on_the_same_file(self):
        """同一文件里"补一行"与"回修一行"共存：按文件分组、串行叠加，两条都要落盘。"""
        self.write_record(self.repair_record([
            {"file": "NOTES/总索引.md", "op": "ensure_line", "idempotent_key": "批次48 已归档",
             "text": "- 阶段3批次48 已归档"},
            self.target(idempotent_key="批次49"),
        ]))
        rc, out = self.run_publish()
        self.assertEqual(rc, 0, out)
        self.assertIn("- 阶段3批次48 已归档", self.index())
        self.assertIn(NEW_ROW, self.index())

    def test_repair_is_all_or_nothing_across_files(self):
        rec = self.repair_record([
            self.target(),
            {"file": "NOTES/阶段3-切分方案.md", "op": "insert_before_anchor",
             "anchor": "这一行根本不存在", "text": "- x"},
        ])
        self.write_record(rec)
        before = self.snapshot()
        self.assertEqual(self.run_publish()[0], 1)
        self.assertEqual(self.snapshot(), before, "另一处冲突时，回修也不许先落盘")

    def test_repair_preview_writes_nothing(self):
        self.write_record(self.repair_record([self.target()]))
        before = self.snapshot()
        rc, out = self.run_publish(extra=())          # 缺省 dry-run
        self.assertEqual(rc, 0, out)
        self.assertEqual(self.snapshot(), before)
        self.assertIn("未写盘", out)

    def test_repair_needs_a_passing_gate_like_any_other_publish(self):
        """回修也是发布：讲义哈希 / 门禁最终记录照样要先验后写。"""
        self.final.write_text(json.dumps({"pass": False, "final_lecture_sha256":
                                          LC.sha256_file(self.lec)}), encoding="utf-8")
        self.write_record(self.repair_record([self.target()]))
        before = self.snapshot()
        self.assertEqual(self.run_publish()[0], 1)
        self.assertEqual(self.snapshot(), before)


class GitAddTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root, self.lec, self.final = make_project(self.tmp.name)
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.name", "t"], check=True)
        subprocess.run(["git", "-C", str(self.root), "config", "user.email", "t@e"], check=True)
        subprocess.run(["git", "-C", str(self.root), "add", "--", "NOTES"], check=True)
        subprocess.run(["git", "-C", str(self.root), "commit", "-qm", "init"], check=True)
        self.record_path = self.root / "batch_record.json"
        self.record_path.write_text(json.dumps(make_record(self.root, self.lec, self.final),
                                              ensure_ascii=False), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def staged(self):
        p = subprocess.run(["git", "-c", "core.quotepath=false", "-C", str(self.root),
                            "diff", "--cached", "--name-only"], capture_output=True, text=True,
                           encoding="utf-8")
        return sorted(x for x in p.stdout.split("\n") if x.strip())

    def test_only_record_files_are_staged(self):
        (self.root / "无关文件.md").write_text("不该被 add\n", encoding="utf-8")
        argv = sys.argv
        sys.argv = ["publish_batch.py", "--record", str(self.record_path), "--apply", "--git-add"]
        try:
            self.assertEqual(P.main(), 0)
        finally:
            sys.argv = argv
        staged = self.staged()
        for rel in LEDGERS:
            self.assertIn(rel.replace("\\", "/"), staged)
        self.assertNotIn("无关文件.md", staged)
        self.assertNotIn("batch_record.json", staged)
        self.assertEqual(len(staged), 4, "只 stage 本批记录里的视图文件（讲义未改动故不在暂存差异里）")
        # `git add` 的命令行里必须**点名**讲义与四个视图（共 5 个），且不含任何通配
        ok, why = P.git_add(str(self.root), [str(self.root / r) for r in LEDGERS], str(self.lec))
        self.assertTrue(ok, why)
        self.assertIn("5 个文件", why)
        self.assertIn("未使用 git add -A", why)


if __name__ == "__main__":
    unittest.main()
