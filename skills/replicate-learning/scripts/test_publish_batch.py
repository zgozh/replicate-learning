"""The single batch record must publish all derived views safely (plan §3.5).

Acceptance from the plan:
  * preview the expected additions, re-run with zero change (idempotent);
  * a conflict in the *second* file leaves **every** target untouched;
  * the user's own edits survive;
  * a nested git repo only ever receives the files named in the record.
"""

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

LEDGERS = {
    "NOTES/项目文件覆盖矩阵.md": "# 覆盖矩阵\n\n| 文件 | 状态 |\n|---|---|\n| 旧件 | 已讲 |\n\n尾注。\n",
    "NOTES/总索引.md": "# 总索引\n\n## 批次清单\n\n- 阶段3批次47 已归档\n",
    "NOTES/阶段3-切分方案.md": "# 阶段3\n\n## 本阶段进度\n\n- 批次47 完成\n",
    "NOTES/复刻状态-下一步.md": "# 精简状态\n\n> 状态：进行中\n\n下一批：阶段3批次48\n",
}


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
    final.write_text(json.dumps({
        "schema_version": LC.SCHEMA_VERSION, "pass": True,
        "final_lecture_sha256": LC.sha256_file(lec), "verdict": "总判定: PASS",
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
