"""判据版本门只有一个口径（2.30 修复 · 批次49 实录）。

缺陷（用户复现）：`style_scope()` 原先自带一个只认「判据 vX.Y」的正则，识别不了 ⑯ 的**规范版本字段**
`**判据版本：v2.30**`。于是同一份正文出现两个结论：

    · 首跑：⑯ 只有规范字段 → 认不出 → ⓪e/⓪f 落「报告档」，结构缺口只报不判红（退出码 0，看着像 PASS）；
    · 盖章：`sync_gate_result.py` 写进表头「判据 v2.30」→ 同一份正文被认出来 → 同一批缺口升 FAIL 档。

结果是"盖章前 PASS、盖章后失败"——**正文一个字没改**，却让人以为要重写讲解，白花了一大段时间。
这与 H27 同族：判据只在它能识别的形态上生效，于是"换个写法"就能绕过它。

这组测试钉住三件事：
  1. 两种形态（规范字段 / 盖章表头）必须给出**同一个档位**（首次门禁与盖章后档位一致）；
  2. 四个版本门（core/form/snip/style）必须**同源**，不许各认各的；
  3. 反向断言：旧正则确实认不出规范字段——留着它，是为了下次有人想"顺手优化"正则时先看见这段历史。
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import gate_lecture as G  # noqa: E402

V = G.GATE_VERSION       # 判据版本随升级变化——样本用当前版本，避免"每升一版就改一遍测试"

FIELD = ["## ⑯ 教材质量自检", "",
         "**判据版本：v%s**（本批按此版判据验收；判据变更见 references/第一册质量细则.md §6.6 变更登记）。" % V,
         "", "| 自检项 | 结论 |", "|---|---|", "| 1 | ✅ |"]
# 盖章后：`sync_gate_result.py` 在 ⑯ 标题后插入机器表，并把判据版本行刷新成同一版
STAMPED = (["## ⑯ 教材质量自检",
            "**七组闸门实测**（判据 v%s，结构化结果 schema v1，无阻塞项）**：" % V, "",
            "| 规则 ID | 检查组 | 核验对象 | 结论 |", "|---|---|---|---|",
            "| `G-STRUCT` | ⓪ 结构 | 17 | 通过 |", "",
            "> 本表由 `scripts/sync_gate_result.py` 从**结构化结果**渲染；判据版本 v%s。" % V]
           + FIELD[1:])
NONE = ["## ⑯ 教材质量自检", "", "| 自检项 | 结论 |", "|---|---|", "| 1 | ✅ |"]


class VersionFieldTests(unittest.TestCase):
    def test_find_versions_accepts_the_canonical_field_and_the_shorthand(self):
        self.assertEqual(G.find_versions("**判据版本：v2.30**"), ["2.30"])
        self.assertEqual(G.find_versions("> 判据版本 v2.21"), ["2.21"])
        self.assertEqual(G.find_versions("判据版本：2.30"), ["2.30"])
        self.assertEqual(G.find_versions("判据 v2.26｜其它"), ["2.26"])
        self.assertEqual(G.find_versions("批次按 v2.27 判"), ["2.27"])
        self.assertEqual(G.find_versions("没有版本号"), [])

    def test_ver_marker_reads_the_canonical_field_inside_sixteen(self):
        has_v, which, current = G.ver_marker(FIELD)
        self.assertTrue(has_v)
        self.assertEqual(which, V)
        self.assertTrue(current)

    def test_declared_version_reads_the_field_too(self):
        self.assertEqual(G.declared_version(FIELD), V)
        self.assertIsNone(G.declared_version(NONE))


class TierParityTests(unittest.TestCase):
    """首次门禁与盖章后必须同档——这就是本组测试要防的那个来回。"""

    def test_style_scope_recognises_the_canonical_field(self):
        e17, e810, e11, ver = G.style_scope(FIELD)
        self.assertEqual((e17, e810, e11, ver), (True, True, True, V))

    def test_first_run_and_stamped_agree_on_every_scope(self):
        self.assertEqual(G.style_scope(FIELD)[:3], G.style_scope(STAMPED)[:3])
        self.assertEqual(G.core_scope(FIELD), G.core_scope(STAMPED))
        self.assertEqual(G.form_scope(FIELD), G.form_scope(STAMPED))
        self.assertEqual(G.snip_scope(FIELD), G.snip_scope(STAMPED))

    def test_all_four_scopes_share_one_version_source(self):
        for lines in (FIELD, STAMPED):
            versions = {G.style_scope(lines)[3], G.ver_marker(lines)[1],
                        G.core_scope(lines)[1], G.form_scope(lines)[1], G.snip_scope(lines)[1]}
            self.assertEqual(versions, {V})

    def test_without_a_version_every_scope_falls_back_to_the_report_tier(self):
        self.assertEqual(G.style_scope(NONE)[:3], (False, False, False))
        self.assertEqual(G.style_scope(NONE)[3], None)
        self.assertEqual(G.core_scope(NONE), (False, None))
        self.assertEqual(G.form_scope(NONE), (False, None))
        self.assertEqual(G.snip_scope(NONE), (False, None))

    def test_style_tiers_follow_the_declared_version(self):
        def lines_with(ver):
            return ["## ⑯ 教材质量自检", "", "**判据版本：v%s**（本批按此版判据验收）。" % ver]
        self.assertEqual(G.style_scope(lines_with("2.25"))[:3], (False, False, False))
        self.assertEqual(G.style_scope(lines_with("2.26"))[:3], (True, False, False))
        self.assertEqual(G.style_scope(lines_with("2.27"))[:3], (True, True, False))
        self.assertEqual(G.style_scope(lines_with("2.28"))[:3], (True, True, True))
        self.assertEqual(G.style_scope(lines_with("2.30"))[:3], (True, True, True))

    def test_style4_gate_reads_the_same_version_as_style_scope(self):
        """⓪f（G-BATCH3）的档位取自 `style_scope` 的 ver——它是 2.30 那次翻转的现场，单独钉一条。"""
        for lines in (FIELD, STAMPED):
            style_ver = G.style_scope(lines)[3]
            self.assertIsNotNone(style_ver)
            self.assertTrue(float(style_ver) >= float(G.STYLE4_FAIL_SINCE))


class OldRegexRegressionGuard(unittest.TestCase):
    """反向断言：旧口径（本函数曾经的样子）认不出规范字段——这就是被修掉的那段历史。"""

    OLD_RE = r"判据\s*v?([\d]+\.[\d]+)"

    def test_the_old_pattern_misses_the_canonical_field(self):
        import re
        self.assertEqual(re.findall(OldRegexRegressionGuard.OLD_RE, "\n".join(FIELD)), [])
        # 但盖章表头能被它认出来 —— 一前一后两个结论，正是"盖章前 PASS、盖章后失败"的机制
        self.assertEqual(re.findall(OldRegexRegressionGuard.OLD_RE, "\n".join(STAMPED)), [V])


class DeclarationWinsTests(unittest.TestCase):
    """② 第二次收紧：**声明就是声明，后面的说明文字不得覆盖它**（批次49 复查实录）。

    第一版修复（认得出规范字段）之后仍留着一个口子：`find_versions` 返回 ⑯ 里的**全部**版本号，
    而 `ver_marker` 取**最后一个**。于是在规范声明后面补一句
    「历史判据 v2.17 仅供对照」，同一处 ⑦ 结构缺口就从 `rc=1` FAIL 档变成 `rc=0` 报告档（实测）。
    现在三级优先级**每级只取第一个**：规范字段 → 盖章表头/旧写法 → 任意 `vX.Y`。
    """

    DECL = ["## ⑯ 教材质量自检", "",
            "**判据版本：v%s**（本批按此版判据验收；判据变更见 references/第一册质量细则.md §6.6）。" % V]
    HISTORY = "（历史判据 v2.17 仅供对照；本节数字仍按上面声明的那一版核对。）"

    def test_a_later_historical_mention_does_not_downgrade_the_tier(self):
        self.assertEqual(G.style_scope(self.DECL)[:3], (True, True, True))
        with_history = self.DECL + ["", self.HISTORY]
        self.assertEqual(G.style_scope(with_history)[:3], (True, True, True))
        self.assertEqual(G.style_scope(with_history)[3], V)

    def test_all_four_scopes_ignore_the_historical_mention(self):
        with_history = self.DECL + ["", self.HISTORY]
        self.assertEqual(G.core_scope(with_history), G.core_scope(self.DECL))
        self.assertEqual(G.form_scope(with_history), G.form_scope(self.DECL))
        self.assertEqual(G.snip_scope(with_history), G.snip_scope(self.DECL))
        self.assertEqual(G.ver_marker(with_history)[1], V)

    def test_a_later_lookalike_declaration_does_not_win_either(self):
        """后面再写一条**同形态**的声明（写成 v2.17 或更早）也只认第一条。"""
        two = self.DECL + ["", "**判据版本：v2.17**（旧版对照）。"]
        self.assertEqual(G.style_scope(two)[3], V)
        self.assertEqual(G.style_scope(two)[:3], (True, True, True))

    def test_the_declaration_wins_over_the_stamped_header(self):
        """有规范字段时不许退回表头：字段是声明，表头只是机器表的口径。"""
        lines = ["## ⑯ 教材质量自检",
                 "**七组闸门实测**（判据 v2.24，结构化结果 schema v1）**：", "",
                 "**判据版本：v%s**（本批按此版判据验收）。" % V]
        self.assertEqual(G.style_scope(lines)[3], V)
        self.assertEqual(G.style_scope(lines)[:3], (True, True, True))

    def test_without_a_declaration_the_header_is_used_first_match_only(self):
        """没有规范字段时才退回表头；退回时同样只认第一个（后面的说明不得覆盖）。"""
        lines = ["## ⑯ 教材质量自检",
                 "**七组闸门实测**（判据 v%s，结构化结果 schema v1）**：" % V, "",
                 self.HISTORY]
        self.assertEqual(G.style_scope(lines)[3], V)
        self.assertEqual(G.style_scope(lines)[:3], (True, True, True))

    def test_old_last_match_rule_would_have_downgraded(self):
        """反向断言：旧的"取最后一个"口径在这份样本上给出 v2.17 —— 记录被修掉的那个口子。"""
        import re
        txt = "\n".join(self.DECL + ["", self.HISTORY])
        found = (re.findall(r"判据\s*(?:版\s*本)?\s*[:：]?\s*v?(\d+\.\d+)", txt)
                 or re.findall(r"\bv(\d+\.\d+)\b", txt))
        self.assertEqual(found[-1], "2.17", "旧口径的最后一个匹配正是那句历史说明")
        self.assertEqual(G.find_versions(txt), [V], "新口径只认声明的那个版本")


if __name__ == "__main__":
    unittest.main()
