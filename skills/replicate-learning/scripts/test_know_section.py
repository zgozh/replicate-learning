"""⑨ 八股讲解的机械判定（2.31 · SSOT `S25` · gate `G-KNOW`）。

背景：用户第五轮要求把 ⑨「No-Framework 等价实现」换成「八股讲解」（"读讲解时顺手把面试考点也学了"）。
机械判定只判"有没有"（L2 内容契约）：条数 ≥6 / 每条的四个固定标记 / 回链本批代码 / 速查表；
内容好不好仍由 ⑯ 自检 + 人工审读。存量批次（⑨ 仍是 No-Framework）只报一句、不逐项挑刺。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_lecture as G  # noqa: E402


def item(n, *, definition=True, why=True, link=True):
    seg = ["**考点 %d · 第 %d 个考点**" % (n, n), "",
           "- **【考点】** 面试官会怎么问第 %d 个问题？" % n]
    if definition:
        seg.append("- **【一句话定义】** 标准答法（可背诵）。")
    if why:
        seg.append("- **【为什么考】** 考的是边界处理能力【外部事实】")
    if link:
        seg.append("- **【本批落点】** `6.%d` 的 `:L%d`" % (n, 40 + n))
    return seg + [""]


def section(n_items=6, **kw):
    lines = ["## ⑨ 八股讲解（本批涉及的面试与工程常识）", ""]
    for i in range(1, n_items + 1):
        lines += item(i, **kw)
    # 速查表本身也带落点列——测"没有回链"时必须连它一起去掉，否则表里的 `6.x` 会让判定为 True
    loc = "`6.1 :L86`" if kw.get("link", True) else "—"
    lines += ["**本批八股速查表**", "", "| 考点 | 一句话答 | 本批落点 |", "|---|---|---|",
              "| 切分策略 | 固定/递归/语义 | %s |" % loc, ""]
    return lines


LEGACY = ["## ⑨ No-Framework 等价实现", "", "一段开篇声明。", "",
          "**框架到底多送了什么**：", "", "| 框架便利 | 手写代价 |", "|---|---|", "| A | B |", ""]


class KnowSectionTests(unittest.TestCase):
    def test_a_complete_section_passes(self):
        kn = G.check_know("\n".join(section(6)))
        self.assertTrue(kn["present"])
        self.assertFalse(kn["legacy"])
        self.assertEqual(kn["items"], 6)
        self.assertEqual(kn["missing"], [])
        self.assertTrue(kn["link"])
        self.assertTrue(kn["table"])

    def test_too_few_items_is_counted(self):
        kn = G.check_know("\n".join(section(5)))
        self.assertEqual(kn["items"], 5)
        self.assertLess(kn["items"], G.KNOW_MIN_ITEMS)

    def test_a_missing_field_is_reported_per_field(self):
        kn = G.check_know("\n".join(section(6, definition=False)))
        self.assertEqual(kn["items"], 6)
        self.assertIn("**【一句话定义】**", kn["missing"])
        self.assertNotIn("**【为什么考】**", kn["missing"])

    def test_no_backlink_is_reported(self):
        kn = G.check_know("\n".join(section(6, link=False)))
        self.assertFalse(kn["link"])

    def test_the_legacy_noframework_section_is_flagged_not_picked_apart(self):
        kn = G.check_know("\n".join(LEGACY))
        self.assertTrue(kn["present"])
        self.assertTrue(kn["legacy"], "旧的 No-Framework 节必须能被认出来")
        self.assertEqual(kn["items"], 0)

    def test_a_missing_section_is_reported(self):
        kn = G.check_know("## ⑧ 穿透卡\n\n内容\n")
        self.assertFalse(kn["present"])

    def test_gate_check_status_is_fail_only_for_batches_declaring_2_31(self):
        """档位：声明 ≥2.31 判 FAIL；存量（无声明/更早）只报告——不追溯。"""
        strict, ver = G.know_scope(["## ⑯ 教材质量自检", "",
                                    "**判据版本：v2.31**（本批按此版判据验收）。"])
        self.assertTrue(strict)
        self.assertEqual(ver, "2.31")
        old, ver2 = G.know_scope(["## ⑯ 教材质量自检", "",
                                  "**判据版本：v2.30**（本批按此版判据验收）。"])
        self.assertFalse(old)
        self.assertEqual(ver2, "2.30")
        none, ver3 = G.know_scope(["## ⑯ 教材质量自检", "", "| 1 | ✅ |"])
        self.assertFalse(none)
        self.assertIsNone(ver3)

    def test_the_gate_reports_the_section_even_when_it_is_legacy(self):
        """整份跑一遍闸门：旧 No-Framework 批次只多一行报告，退出码不变。"""
        import io
        import os
        import subprocess
        import tempfile
        here = Path(__file__).resolve().parent
        lec = tempfile.mktemp(suffix=".md")
        io.open(lec, "w", encoding="utf-8", newline="").write("\n".join(LEGACY) + "\n")
        try:
            p = subprocess.run([sys.executable, "-B", str(here / "gate_lecture.py"), lec,
                                "--src", str(here)], capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
            self.assertIn("⑨", p.stdout)
            self.assertIn("No-Framework", p.stdout)
        finally:
            os.unlink(lec)


if __name__ == "__main__":
    unittest.main()
