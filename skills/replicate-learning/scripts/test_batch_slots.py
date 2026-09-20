"""Stable source slots and repeatable batch builds (plan §3.3).

Acceptance from the plan, pinned on the real batch 48 material and on two synthetic edge cases:
  * repair 9 annotations and rebuild twice — the 8 source blocks must still be found uniquely,
    without editing a single ``contains`` string;
  * one section holding two Java blocks and a Python block containing a multi-line string;
  * a wrong slot id or a drifted source hash must refuse to write, leaving the file untouched.
"""

import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_build as BB
import inject_source as INJ
import new_batch as NB
import assemble_batch as AB

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
B48 = SKILL / "tests" / "fixtures" / "batch48"
PYMINI = SKILL / "tests" / "fixtures" / "py_mini"
SRC48 = B48 / "project"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run_new_batch(tmp, plan, title="智能切片策略", classes="TableChunker★", out_name="批次48.md",
                  skeleton_name="skeleton.md", src=SRC48, extra_argv=()):
    """生成骨架 + batch.json。`--out` 是终稿、`--skeleton` 是骨架（2.30 起两者必须不同路径）。"""
    out = str(Path(tmp) / out_name)
    skeleton = str(Path(tmp) / skeleton_name)
    state = str(Path(tmp) / "batch.json")
    argv = sys.argv
    sys.argv = ["new_batch.py", "--stage", "3", "--batch", "48", "--title", title,
                "--classes", classes, "--sha", "16984b9", "--out", out, "--skeleton", skeleton,
                "--src", str(src), "--plan", str(plan), "--batch-json", state] + list(extra_argv)
    try:
        NB.main()
    finally:
        sys.argv = argv
    return skeleton, json.load(io.open(state, encoding="utf-8"))


class SlotMechanicsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_skeleton_marks_every_planned_source_with_a_stable_slot(self):
        skeleton, state = run_new_batch(self.root, B48 / "b48_inject_plan_fixed.json")
        text = io.open(skeleton, encoding="utf-8").read()
        self.assertEqual(text.count("<!-- src-slot"), 8)
        self.assertEqual(len(state["slots"]), 8)
        for slot in state["slots"]:
            self.assertTrue(slot["slot"].startswith("source:"))
            self.assertIn(digest(SRC48 / slot["src"])[:8], slot["slot"])
        # 槽位 ID 必须同时出现在骨架与注释计划里，否则注入器两边对不上
        plan = json.load(io.open(state["annotations"], encoding="utf-8"))
        self.assertEqual([b["slot"] for b in plan["blocks"]], [s["slot"] for s in state["slots"]])

    def test_slot_injection_is_idempotent(self):
        skeleton, state = run_new_batch(self.root, B48 / "b48_inject_plan_fixed.json")
        plan = state["annotations"]
        self.assertEqual(INJ.main_with(["inject_source.py", skeleton, plan, "--src", str(SRC48)]), 0)
        first = Path(skeleton).read_bytes()
        self.assertEqual(INJ.main_with(["inject_source.py", skeleton, plan, "--src", str(SRC48)]), 0)
        self.assertEqual(Path(skeleton).read_bytes(), first, "重复注入必须逐字节一致")

    def test_extra_annotations_need_no_contains_edits(self):
        skeleton, state = run_new_batch(self.root, B48 / "b48_inject_plan_fixed.json")
        plan_path = Path(state["annotations"])
        plan = json.load(io.open(plan_path, encoding="utf-8"))
        self.assertEqual(INJ.main_with(["inject_source.py", skeleton, str(plan_path), "--src", str(SRC48)]), 0)
        before = Path(skeleton).read_bytes()
        # 再补 9 条注释（真实场景：闸门又报了几处密度连段），**不动任何 contains**
        added = 0
        for block in plan["blocks"]:
            for line in ("30", "31", "33", "34", "36", "37", "40", "42", "44", "46", "48"):
                n = int(line)
                if block["start"] <= n <= block["end"] and line not in block.get("anno", {}):
                    block.setdefault("anno", {})[line] = "补注：这一行要说明的原因"
                    added += 1
                    if added >= 9:
                        break
            if added >= 9:
                break
        self.assertEqual(added, 9)
        io.open(plan_path, "w", encoding="utf-8", newline="").write(
            json.dumps(plan, ensure_ascii=False, indent=1))
        self.assertEqual(INJ.main_with(["inject_source.py", skeleton, str(plan_path), "--src", str(SRC48)]), 0)
        text = Path(skeleton).read_text(encoding="utf-8")
        self.assertNotEqual(Path(skeleton).read_bytes(), before, "补注后内容必须变化")
        for block in plan["blocks"]:
            self.assertIn(block["slot"], text)
            self.assertIn(block["src"], text)
        markers = text.count("<!-- src-slot")
        self.assertEqual(markers, 8, "重注入不得复制槽位标记")

    def test_wrong_slot_id_refuses_and_leaves_the_file_untouched(self):
        skeleton, state = run_new_batch(self.root, B48 / "b48_inject_plan_fixed.json")
        plan_path = Path(state["annotations"])
        plan = json.load(io.open(plan_path, encoding="utf-8"))
        before = Path(skeleton).read_bytes()
        plan["blocks"][0]["slot"] = "source:deadbeef:6.1"
        plan["blocks"][0].pop("anchor", None)
        io.open(plan_path, "w", encoding="utf-8", newline="").write(json.dumps(plan, ensure_ascii=False))
        with self.assertRaises(SystemExit):
            INJ.main_with(["inject_source.py", skeleton, str(plan_path), "--src", str(SRC48)])
        self.assertEqual(Path(skeleton).read_bytes(), before)

    def test_drifted_source_hash_refuses_the_write(self):
        skeleton, state = run_new_batch(self.root, B48 / "b48_inject_plan_fixed.json")
        # 造一个"源文件被改过"的仓库副本：内容变一行 → hash 与槽位标记不符
        src = self.root / "src"
        shutil.copytree(SRC48, src)
        victim = src / state["slots"][0]["src"]
        victim.write_text(victim.read_text(encoding="utf-8") + "\n// drift\n", encoding="utf-8")
        before = Path(skeleton).read_bytes()
        with self.assertRaises(SystemExit) as ctx:
            INJ.main_with(["inject_source.py", skeleton, str(state["annotations"]), "--src", str(src)])
        self.assertIn("hash", str(ctx.exception))
        self.assertEqual(Path(skeleton).read_bytes(), before)


class SlotEdgeCaseTests(unittest.TestCase):
    """同一小节两个 java 块 / Python 多行字符串 —— 真批次里反复踩到的两种。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root / "app").mkdir()
        (self.root / "Batch.java").write_text(
            "package demo;\n\npublic class Batch {\n"
            "    private final int size;\n\n"
            "    public Batch(int size) {\n        this.size = size;\n    }\n\n"
            "    public int doubled() {\n        return size * 2;\n    }\n}\n", encoding="utf-8")
        (self.root / "app" / "sample.py").write_text(
            'SQL = """select id,\n       name\nfrom account"""\n\n\n'
            'def fetch(conn):\n    cur = conn.cursor()\n    cur.execute(SQL)\n'
            '    row = cur.fetchone()\n    return row\n', encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def _skeleton(self, plan):
        plan_path = self.root / "plan.json"
        io.open(plan_path, "w", encoding="utf-8", newline="").write(
            json.dumps(plan, ensure_ascii=False, indent=1))
        skeleton, state = run_new_batch(self.root, plan_path, title="边界用例", classes="Batch★",
                                       src=self.root)
        # 件内补一个"教学合成片段"块（同一小节里的第二个块）
        text = Path(skeleton).read_text(encoding="utf-8")
        text = text.replace("**【怎么用】**", "**【怎么用】**\n\n```java\nBatch b = new Batch(3);\n```")
        Path(skeleton).write_text(text, encoding="utf-8")
        return skeleton, state

    def test_two_blocks_in_one_section_are_addressed_uniquely(self):
        plan = {"blocks": [{"lang": "java", "src": "Batch.java", "start": 1, "end": 13,
                            "anchor": "#### 6.1 `Batch★`",
                            "anno": {"3": "类声明", "7": "构造器注入"}}]}
        skeleton, state = self._skeleton(plan)
        self.assertEqual(INJ.main_with(["inject_source.py", skeleton, str(state["annotations"]), "--src", str(self.root)]), 0)
        text = Path(skeleton).read_text(encoding="utf-8")
        self.assertIn("public class Batch {", text)
        self.assertIn("```java\nBatch b = new Batch(3);\n```", text, "教学合成片段不得被源码注入吃掉")
        lines = text.split("\n")
        start = next(i for i, l in enumerate(lines) if l.startswith("#### 6.1"))
        end = next((i for i in range(start + 1, len(lines))
                    if lines[i].startswith("#### 6.2") or lines[i].startswith("## ")), len(lines))
        src_blocks = [i for i in range(start, end) if lines[i].startswith("```java")]
        self.assertEqual(len(src_blocks), 2, "同一小节里的源码块与教学片段块必须各自唯一")

    def test_python_multiline_string_stays_untouched(self):
        plan = {"blocks": [{"lang": "python", "src": "app/sample.py", "start": 1, "end": 11,
                            "anchor": "#### 6.1 `sample.py`",
                            "anno": {"1": "SQL 常量：多行字符串内部不许加注释"}}]}
        skeleton, state = self._skeleton(plan)
        self.assertEqual(INJ.main_with(["inject_source.py", skeleton, str(state["annotations"]), "--src", str(self.root)]), 0)
        text = Path(skeleton).read_text(encoding="utf-8")
        self.assertIn("       name", text, "字符串内部行必须逐字保留")
        self.assertNotIn("name  # :L2", text)
        self.assertIn("# :L1", text)


class BatchBuildTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _state(self, with_parts):
        skeleton, state = run_new_batch(self.root, B48 / "b48_inject_plan_fixed.json")
        if with_parts:
            parts = self.root / "parts"
            parts.mkdir()
            for fn in os.listdir(B48 / "parts"):
                shutil.copyfile(B48 / "parts" / fn, parts / fn)
            state["parts_dir"] = str(parts)
        state["out"] = str(self.root / "批次48.md")
        state_path = self.root / "batch.json"
        io.open(state_path, "w", encoding="utf-8", newline="").write(
            json.dumps(state, ensure_ascii=False, indent=1))
        return state_path, skeleton, state
    def test_rebuild_is_repeatable_from_parts(self):
        state_path, _skeleton, state = self._state(with_parts=True)
        text1, rep1 = BB.build(state)
        self.assertEqual(rep1["sections"], 17)
        self.assertEqual(len(rep1["injected"]), 8)
        text2, rep2 = BB.build(BB.load_batch(str(state_path)))
        self.assertEqual(text1, text2, "同一份骨架 + 分片 + 注释计划必须重建出同一份终稿")
        self.assertEqual(len(rep2["injected"]), 8)

    def test_legacy_parts_fall_back_with_a_warning(self):
        """真实批次48 的分片是旧格式（无槽位标记）→ 必须退回 anchor 旧寻址并告警，而不是硬失败。"""
        _state_path, _skeleton, state = self._state(with_parts=True)
        _text, report = BB.build(state)
        self.assertTrue(report["legacy_fallback"], "旧分片应触发兼容告警")
        modes = {m for m, _l, _s in report["injected"]}
        self.assertEqual(modes, {"anchor"})
        self.assertEqual(len(report["injected"]), 8)

    def test_check_detects_a_stale_product(self):
        state_path, _skeleton, state = self._state(with_parts=True)
        argv = sys.argv
        sys.argv = ["batch_build.py", "--batch", str(state_path)]
        try:
            self.assertEqual(BB.main(), 0)
            sys.argv = ["batch_build.py", "--batch", str(state_path), "--check"]
            self.assertEqual(BB.main(), 0)
            Path(state["out"]).write_text("被手改过的终稿\n", encoding="utf-8")
            sys.argv = ["batch_build.py", "--batch", str(state_path), "--check"]
            self.assertEqual(BB.main(), 1)
            sys.argv = ["batch_build.py", "--batch", str(state_path), "--dry-run"]
            self.assertEqual(BB.main(), 0)
            self.assertEqual(Path(state["out"]).read_text(encoding="utf-8"), "被手改过的终稿\n",
                             "--dry-run 不得写盘")
        finally:
            sys.argv = argv

    def test_broken_part_is_refused_before_writing(self):
        state_path, _skeleton, state = self._state(with_parts=False)
        parts = self.root / "parts"
        parts.mkdir()
        (parts / "bad.md").write_text("## ⑥ 逐件讲解（完整代码 + 逐行说明）\n未完的围栏\n```java\n",
                                      encoding="utf-8")
        state["parts_dir"] = str(parts)
        with self.assertRaises((SystemExit, ValueError)):
            BB.build(state)

    def test_assembled_product_has_all_seventeen_sections(self):
        _state_path, _skeleton, state = self._state(with_parts=True)
        text, _rep = BB.build(state)
        _pre, sections = AB.split_sections(text, allow_preamble=True)
        self.assertEqual(len(sections), 17)


class BuildGuardTests(unittest.TestCase):
    """2.30 修复（批次49 实录）：四条 fail-closed 护栏，每条都对应一次真实的"假重建"。"""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _state(self, with_parts=True):
        skeleton, state = run_new_batch(self.root, B48 / "b48_inject_plan_fixed.json")
        if with_parts:
            parts = self.root / "parts"
            parts.mkdir()
            for fn in os.listdir(B48 / "parts"):
                shutil.copyfile(B48 / "parts" / fn, parts / fn)
            state["parts_dir"] = str(parts)
        state_path = self.root / "batch.json"
        io.open(state_path, "w", encoding="utf-8", newline="").write(
            json.dumps(state, ensure_ascii=False, indent=1))
        return state_path, skeleton, state

    def test_new_batch_refuses_identical_skeleton_and_out(self):
        argv = sys.argv
        same = str(self.root / "x.md")
        sys.argv = ["new_batch.py", "--stage", "3", "--batch", "48", "--title", "t",
                    "--out", same, "--skeleton", same, "--src", str(SRC48),
                    "--plan", str(B48 / "b48_inject_plan_fixed.json")]
        try:
            with self.assertRaises(SystemExit) as ctx:
                NB.main()
            self.assertIn("同一个路径", str(ctx.exception))
        finally:
            sys.argv = argv

    def test_new_batch_refuses_batch_json_without_a_plan(self):
        argv = sys.argv
        sys.argv = ["new_batch.py", "--stage", "3", "--batch", "48", "--title", "t",
                    "--out", str(self.root / "批次48.md"), "--skeleton", str(self.root / "skel.md"),
                    "--src", str(SRC48), "--batch-json", str(self.root / "batch.json")]
        try:
            with self.assertRaises(SystemExit) as ctx:
                NB.main()
            self.assertIn("--plan", str(ctx.exception))
        finally:
            sys.argv = argv

    def test_state_points_at_one_editable_annotation_plan(self):
        _state_path, _skeleton, state = self._state()
        self.assertNotEqual(os.path.normcase(state["skeleton"]), os.path.normcase(state["out"]))
        self.assertTrue(os.path.isfile(state["annotations"]))
        self.assertNotEqual(os.path.normcase(state["annotations"]),
                            os.path.normcase(state["plan_source"]))
        self.assertEqual(state["annotations_slots"], 8)
        plan = json.load(io.open(state["annotations"], encoding="utf-8"))
        self.assertEqual(len([b for b in plan["blocks"] if b.get("slot")]), 8)

    def test_identical_skeleton_and_out_in_batch_json_is_refused(self):
        _state_path, _skeleton, state = self._state()
        state["out"] = state["skeleton"]
        with self.assertRaises(SystemExit) as ctx:
            BB.build(state)
        self.assertIn("同一个路径", str(ctx.exception))

    def test_annotations_pointing_back_at_the_raw_plan_is_refused(self):
        _state_path, _skeleton, state = self._state()
        state["annotations"] = state["plan_source"]
        with self.assertRaises(SystemExit) as ctx:
            BB.build(state)
        self.assertIn("plan_source", str(ctx.exception))

    def test_empty_parts_dir_is_refused_by_default(self):
        _state_path, _skeleton, state = self._state(with_parts=False)
        with self.assertRaises(SystemExit) as ctx:
            BB.build(state)
        self.assertIn("一个 .md 都没有", str(ctx.exception))
        # 明知骨架里已写全正文时，显式放行
        text, report = BB.build(state, allow_no_parts=True)
        self.assertEqual(report["sections"], 17)
        self.assertTrue(text)

    def test_missing_sixth_part_cannot_borrow_the_old_product(self):
        """缺 ⑥ 分片时，⑥ 仍是骨架里的模板占位原文 → 必须拒绝（不得把旧 ⑥ 当"重建结果"）。"""
        _state_path, _skeleton, state = self._state()
        (Path(state["parts_dir"]) / "b48_part_6.md").unlink()
        with self.assertRaises(SystemExit) as ctx:
            BB.build(state)
        msg = str(ctx.exception)
        self.assertIn("模板占位原文", msg)
        self.assertIn("⑥", msg)

    def test_parts_dir_lost_entirely_is_refused(self):
        _state_path, _skeleton, state = self._state()
        state["parts_dir"] = str(self.root / "nope")
        with self.assertRaises(SystemExit) as ctx:
            BB.build(state)
        self.assertIn("一个 .md 都没有", str(ctx.exception))

    def test_check_ignores_the_machine_stamp(self):
        """盖章后的终稿（⑯ 多出机器块 + 版本行被刷新）不得报"重建不一致"。"""
        state_path, _skeleton, state = self._state()
        argv = sys.argv
        sys.argv = ["batch_build.py", "--batch", str(state_path)]
        try:
            self.assertEqual(BB.main(), 0)
            out = Path(state["out"])
            lines = out.read_text(encoding="utf-8").split("\n")
            i16 = next(k for k, l in enumerate(lines) if l.startswith("## ⑯"))
            stamp = ["**七组闸门实测**（判据 v2.30，结构化结果 schema v1，无阻塞项）**：", "",
                     "| 规则 ID | 检查组 | 核验对象 | 结论 |", "|---|---|---|---|",
                     "| `G-STRUCT` | ⓪ 结构 | 17 | 通过 |", "",
                     "> 本表由 `scripts/sync_gate_result.py` 从**结构化结果**渲染；判据版本 v2.30。"]
            lines[i16 + 1:i16 + 1] = stamp
            out.write_text("\n".join(lines), encoding="utf-8")
            sys.argv = ["batch_build.py", "--batch", str(state_path), "--check"]
            self.assertEqual(BB.main(), 0, "⑯ 的机器盖章块与版本行必须被排除在重建比对之外")
            # 正文真被改坏时仍然要报
            out.write_text(out.read_text(encoding="utf-8").replace("**本批一句话**", "**本批一句话被改**"),
                           encoding="utf-8")
            self.assertEqual(BB.main(), 1)
        finally:
            sys.argv = argv

    def test_strip_machine_stamp_removes_block_and_normalises_version(self):
        # 版式与真文件一致：机器块插在 `## ⑯` 之后、判据版本行之前（`sync_gate_result.write_block` 的落点）
        text = ("## ⑯ 教材质量自检\n"
                "**七组闸门实测**（判据 v2.30，结构化结果 schema v1）：\n\n"
                "| 规则 ID | 检查组 | 核验对象 | 结论 |\n|---|---|---|---|\n"
                "| `G-STRUCT` | ⓪ 结构 | 17 | 通过 |\n\n"
                "> 本表由 `scripts/sync_gate_result.py` 生成；判据版本 v2.30。\n\n"
                "**判据版本：v2.29**（本批按此版判据验收）。\n\n"
                "| 自检项 | 结论 |\n|---|---|\n| 1. 初学者能否看懂 | ✅ |\n")
        out = BB.strip_machine_stamp(text)
        self.assertNotIn("七组闸门实测", out)
        self.assertNotIn("G-STRUCT", out)
        self.assertIn("**判据版本：<盖章版本>**", out)
        self.assertIn("| 1. 初学者能否看懂 | ✅ |", out, "机器块以外的正文必须逐字保留")

    def test_check_accepts_a_product_whose_version_line_was_refreshed(self):
        """骨架/分片写的是旧版本号、盖章把它刷成当前版 —— 这是正常流程，不得报「不一致」。"""
        state_path, _skeleton, state = self._state()
        argv = sys.argv
        sys.argv = ["batch_build.py", "--batch", str(state_path)]
        try:
            self.assertEqual(BB.main(), 0)
            out = Path(state["out"])
            text = out.read_text(encoding="utf-8")
            self.assertIn("**判据版本：", text)
            out.write_text(text.replace("**判据版本：v2.30**", "**判据版本：v2.31**", 1), encoding="utf-8")
            sys.argv = ["batch_build.py", "--batch", str(state_path), "--check"]
            self.assertEqual(BB.main(), 0, "判据版本行由 sync 刷新，不属于重建差异")
        finally:
            sys.argv = argv


if __name__ == "__main__":
    unittest.main()
