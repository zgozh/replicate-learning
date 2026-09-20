#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_build.py —— 从骨架 + 分片 + 注释计划**可重建**批次终稿（方案 §3.3）。

**为什么需要它**（第48批实录）：改注释靠"猜旧的 `contains` 占位串"，源码块靠"类声明消歧"钉住，
修一次注释就要手写一遍注入命令；单批还额外写了 10k 字符的一次性归档脚本去逐处找锚点。
正确形态是：**终稿永远是派生物**——`骨架 + parts/*.md + annotations.json` 一条命令重建，
改了注释只需重跑一次，块的身份由槽位 ID 与源路径决定，不依赖标题措辞或块内已替换的文本。

用法：
    python batch_build.py --batch <batch.json> [--dry-run] [--check] [--no-inject] [--quiet]

`batch.json`（由 `new_batch.py --batch-json` 生成）：
    {"src": <源码根>, "skeleton": <骨架.md>, "parts_dir": <分片目录>,
     "annotations": <含槽位的注释计划.json>, "out": <批次.md>}

  · `--dry-run`：只说会改什么（替换几节、注入几块、行数变化），**不写盘**；
  · `--check`  ：把重建结果与磁盘上的终稿逐字节比，一致 = 0（已验证是最新），不一致 = 1；
  · 失败一律**不写盘**：所有步骤都在内存里做完才落盘（tmpnew → os.replace），中途报错原文件保持原样。

2.30 修复（批次49 实录，四条 fail-closed 护栏）：
  1. **`skeleton` 与 `out` 不许同路径**——同路径时"重建"是就地改旧正文：省略 ⑥ 分片，旧 ⑥ 内容会
     原样留在结果里，"重建成功"是假象（旧 66 KB 正文冒充派生产物）；
  2. **`annotations` 必须存在，且不能是 `plan_source`**——原始注入计划只有 anchor/contains，不是槽位来源；
     指回它会让槽位寻址静默退化成旧寻址；
  3. **分片目录为空 = 拒绝**（`--allow-no-parts` 才放行）——指错目录时"重建"只会把骨架抄一遍；
  4. **任何一节若仍是骨架里的模板占位原文 = 拒绝**——这一节没有任何分片覆盖过它（正是"缺分片"的形态）。
  `--check` 另把 ⑯ 的**机器盖章块与判据版本行**排除在比对之外（它们由 `sync_gate_result.py` 写入，
  不属于"骨架+分片"的派生物）——否则盖章后的终稿会报几十行假差异，误导维护者去"重新构建"。

不做的事：不生成讲解内容、不发明件标题、不替模型写注释。
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import assemble_batch as AB                   # noqa: E402
import inject_source as INJ                   # noqa: E402
import lecture_checks as LC                   # noqa: E402
import sync_gate_result as SGR                # noqa: E402
from safe_edit import save as safe_save, scan_fences   # noqa: E402

# 依赖 `sync_gate_result` 的符号（`skill_selfcheck` 逐条校验存在性：跨工具耦合不许悄悄断）
SYNC_API = ['MARK_RE', 'NOTE_RE', 'VERLINE_RE', 'block_end']
SLOT_MARK_RE = re.compile(r"<!--\s*src-slot\s")
PLACEHOLDER_RE = re.compile(r"__[^_\r\n]{2,}__")     # 模板占位符形态：__xxx__


def load_batch(path):
    state = json.load(io.open(path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(path))
    for key in ("src", "skeleton", "anchors", "annotations", "manifest", "out", "parts_dir"):
        if state.get(key) and not os.path.isabs(state[key]):
            state[key] = os.path.normpath(os.path.join(base, state[key]))
    if state.get("manifests"):
        state["manifests"] = [m if os.path.isabs(m) else os.path.normpath(os.path.join(base, m))
                              for m in state["manifests"]]
    return state


def collect_parts(parts_dir):
    if not parts_dir or not os.path.isdir(parts_dir):
        return []
    return [os.path.join(parts_dir, fn) for fn in sorted(os.listdir(parts_dir))
            if fn.endswith(".md") and not fn.endswith(".tmpnew")]


def assemble(skeleton_path, part_paths):
    """返回 (merged, replaced, stale)：replaced = 被分片换掉的节；stale = 仍是模板占位原文的节。"""
    base = io.open(skeleton_path, encoding="utf-8").read()
    if not part_paths:
        return base, [], []
    parts = [io.open(p, encoding="utf-8").read() for p in part_paths]
    merged = AB.assemble(base, parts)
    _pre, base_sections = AB.split_sections(base, allow_preamble=True)
    _pre2, out_sections = AB.split_sections(merged, allow_preamble=True)
    replaced = sorted(h for h in out_sections if out_sections[h] != base_sections.get(h))
    stale = sorted(h for h in out_sections
                   if out_sections[h] == base_sections.get(h)
                   and PLACEHOLDER_RE.search(out_sections[h] or ""))
    return merged, replaced, stale


def guard_config(state, allow_no_parts=False):
    """配置体检（全 fail closed）：路径错配一律拒绝，不做"尽量猜"。返回分片列表。"""
    skeleton, out = state.get("skeleton"), state.get("out")
    if not skeleton:
        raise SystemExit("[ABORT] batch.json 里没有 skeleton（骨架路径）")
    if not os.path.isfile(skeleton):
        raise SystemExit("[ABORT] batch.json 里的 skeleton 不存在：%s" % skeleton)
    if not out:
        raise SystemExit("[ABORT] batch.json 里没有 out（终稿路径）")
    if os.path.normcase(os.path.abspath(skeleton)) == os.path.normcase(os.path.abspath(out)):
        raise SystemExit(
            "[ABORT] skeleton 与 out 是**同一个路径**：%s\n"
            "   → 终稿必须由「骨架 + 分片 + 注释计划」派生；同路径时构建是**就地改旧正文**，\n"
            "     省略某个分片会让旧内容原样留在「重建」结果里（旧正文冒充派生产物）。\n"
            "   → 修法：`new_batch.py --out <终稿.md> --skeleton <骨架.md>` 生成两个不同路径，\n"
            "     或手工把 batch.json 的 skeleton 指到独立骨架文件。" % skeleton)
    ann = state.get("annotations")
    if not ann:
        raise SystemExit("[ABORT] batch.json 里没有 annotations（含槽位的注释计划）")
    if not os.path.isfile(ann):
        raise SystemExit("[ABORT] annotations 不存在：%s\n"
                         "   → 它是 `new_batch.py --plan … --batch-json …` 派生的**唯一一份可编辑注释计划**；\n"
                         "     文件不在就重新生成，别把 annotations 指回原始注入计划。" % ann)
    ps = state.get("plan_source")
    if ps and os.path.normcase(os.path.abspath(ps)) == os.path.normcase(os.path.abspath(ann)):
        raise SystemExit(
            "[ABORT] annotations 指回了 `plan_source`（原始注入计划）：%s\n"
            "   → 原生计划只有 anchor/contains，没有槽位；槽位寻址会静默退化成旧寻址" % ann)
    skel_txt = io.open(skeleton, encoding="utf-8").read()
    n_skel = len(SLOT_MARK_RE.findall(skel_txt))
    try:
        plan = json.load(io.open(ann, encoding="utf-8"))
    except ValueError as exc:
        raise SystemExit("[ABORT] annotations 不是合法 JSON（%s）：%s" % (exc, ann))
    n_ann = len([b for b in plan.get("blocks", []) if b.get("slot")])
    if n_skel and not n_ann:
        raise SystemExit(
            "[ABORT] 骨架里有 %d 个源码槽位，但 annotations 里一个槽位都没有：%s\n"
            "   → 你多半把 annotations 指回了原始计划（它不是槽位来源），或手改坏了这份计划。"
            % (n_skel, ann))
    if n_ann and n_skel != n_ann:
        raise SystemExit("[ABORT] 槽位对不上：骨架 %d 个 / annotations %d 个——"
                         "两者必须同一次生成、逐个对应" % (n_skel, n_ann))
    parts = collect_parts(state.get("parts_dir"))
    if not parts and not allow_no_parts:
        raise SystemExit(
            "[ABORT] 分片目录里一个 .md 都没有：%s\n"
            "   → 没有分片时「重建」只会把骨架抄一遍（旧内容冒充重建结果）。\n"
            "   → 确认 parts_dir 指对了；确实要只组装骨架时加 --allow-no-parts。"
            % state.get("parts_dir"))
    return parts


def build(state, inject=True, allow_no_parts=False):
    """返回 (text, report)。任何一步失败都抛 SystemExit——调用方保证此时磁盘未被改动。"""
    report = {}
    skeleton = state.get("skeleton")
    parts = guard_config(state, allow_no_parts=allow_no_parts)
    text, replaced, stale = assemble(skeleton, parts)
    report["parts_replaced"] = replaced
    report["parts_count"] = len(parts)
    report["stale_sections"] = stale
    if stale:
        raise SystemExit(
            "[ABORT] 这些节仍是骨架里的**模板占位原文**，没有任何分片覆盖它们：\n   %s\n"
            "   → 缺分片 / 分片文件名不对 / parts_dir 指错；补上分片再构建"
            "（否则「重建」会把这些节原样带进终稿）。" % "\n   ".join(stale))
    if inject and state.get("annotations"):
        plan = json.load(io.open(state["annotations"], encoding="utf-8"))
        lines = text.split("\n")
        _lines, blocks = INJ.parse_lines(lines)      # 内存解析：不落中间文件
        repl, fallback = INJ.plan_replacements(lines, blocks, plan, state["src"])
        lines = INJ.apply_replacements(lines, repl)
        report["injected"] = [(r[0], r[5], r[4]) for r in repl]
        report["legacy_fallback"] = fallback
        text = "\n".join(lines)
        report["plan"] = state["annotations"]
    issues, _events = scan_fences(text.split("\n"))
    if issues:
        raise SystemExit("[ABORT] 重建结果围栏不自洽（拒绝写盘）：\n   " + "\n   ".join(issues[:6]))
    _pre, sections = AB.split_sections(text, allow_preamble=True)
    report["sections"] = len(sections)
    if len(sections) != 17:
        raise SystemExit("[ABORT] 重建结果 17 节校验失败（实为 %d 节）——分片或骨架被改坏了，拒绝写盘"
                         % len(sections))
    report["lines"] = text.count("\n") + 1
    return text, report


def strip_machine_stamp(text):
    """抹掉 ⑯ 里的**机器盖章块**与判据版本行（`sync_gate_result.py` 的产物），供 `--check` 比对。

    为什么必须抹：盖章块不属于「骨架 + 分片 + 注释计划」的派生物，不抹就会让**盖章后的终稿**
    报出几十行假差异、提示"先跑一次构建"——维护者据此会以为终稿重建不出来（批次49 实录：48 行）。
    识别用的常量直接取 `sync_gate_result` 的（`SYNC_API` 声明 + selfcheck 校验存在性），不复制一份。
    """
    lines = text.split("\n")
    i16 = next((k for k, l in enumerate(lines) if re.match(r"^##\s*⑯", l)), None)
    if i16 is not None:
        old = next((k for k in range(i16, min(i16 + 60, len(lines))) if SGR.MARK_RE.match(lines[k])), None)
        if old is not None:
            end = SGR.block_end(lines, old)
            del lines[old:end + 1]
    return "\n".join(SGR.VERLINE_RE.sub("**判据版本：<盖章版本>**", l) for l in lines)


def main():
    LC.configure_stdio()
    ap = argparse.ArgumentParser(description="从骨架 + 分片 + 注释计划重建批次终稿")
    ap.add_argument("--batch", required=True, help="batch.json（new_batch.py --batch-json 生成）")
    ap.add_argument("--dry-run", action="store_true", help="只报告会改什么，不写盘")
    ap.add_argument("--check", action="store_true", help="与磁盘终稿逐字节比对（一致=0，不一致=1）")
    ap.add_argument("--no-inject", action="store_true", help="只组装不注入（排查分片用）")
    ap.add_argument("--allow-no-parts", action="store_true",
                    help="明知分片目录为空（正文直接写在骨架里）时放行——缺省拒绝")
    a = ap.parse_args()

    state = load_batch(a.batch)
    text, report = build(state, inject=not a.no_inject, allow_no_parts=a.allow_no_parts)
    out = state.get("out")
    if not out:
        raise SystemExit("[ABORT] batch.json 里没有 out（终稿路径）")

    print("批次 %s → %s" % (state.get("batch_id"), out))
    print("  骨架：%s" % state.get("skeleton"))
    print("  分片：%d 份（%s）" % (report.get("parts_count", 0),
                                 "、".join(os.path.basename(p) for p in collect_parts(state.get("parts_dir"))) or "无"))
    if report.get("parts_replaced"):
        print("  组装替换 %d 节：%s" % (len(report["parts_replaced"]),
                                      "、".join(h.split(" ")[0] for h in report["parts_replaced"])))
    if "injected" in report:
        modes = {}
        for mode, _label, _src in report["injected"]:
            modes[mode] = modes.get(mode, 0) + 1
        print("  注入 %d 块（%s）← %s"
              % (len(report["injected"]),
                 "、".join("%s %d" % (k, v) for k, v in sorted(modes.items())),
                 os.path.basename(report["plan"])))
        for _mode, label, src in report["injected"][:12]:
            print("     %-30s %s" % (str(label)[:30], src))
        for slot, why in report.get("legacy_fallback") or []:
            print("     ⚠ 槽位 %s 未命中 → 退回 anchor 旧寻址（兼容旧分片）：%s" % (slot, why[:90]))
    print("  节数=%d 行数=%d" % (report["sections"], report["lines"]))

    if a.check:
        if not os.path.isfile(out):
            print("  [FAIL] 磁盘上没有终稿 %s——无法比对" % out)
            return 1
        current = io.open(out, encoding="utf-8").read()
        if current == text:
            print("  [OK ] 磁盘终稿与重建结果一致（分片/注释已全部落盘）")
            return 0
        cur_n, new_n = strip_machine_stamp(current), strip_machine_stamp(text)
        if cur_n == new_n:
            print("  [OK ] 排除 ⑯ 的机器盖章块与判据版本行后，磁盘终稿与重建结果一致"
                  "（那两处由 sync_gate_result.py 写入，不属于派生物）")
            return 0
        old_lines, new_lines = cur_n.split("\n"), new_n.split("\n")
        diff = sum(1 for x, y in zip(old_lines, new_lines) if x != y) + abs(len(old_lines) - len(new_lines))
        print("  [FAIL] 磁盘终稿与重建结果不一致（约 %d 行差异，已排除 ⑯ 的机器盖章块）"
              "——先跑一次不带 --check 的构建" % diff)
        return 1

    if a.dry_run:
        print("  （dry-run：未写盘）")
        return 0

    if os.path.isfile(out) and io.open(out, encoding="utf-8").read() == text:
        print("  [OK ] 内容与磁盘一致，无需写盘（重复构建是幂等的）")
        return 0
    safe_save(text.split("\n"), out, backup=True)
    print("  → 已写盘 %s" % out)
    _mans = " ".join("--manifest %s" % m for m in (state.get("manifests") or [])) \
        or ("--manifest %s" % state["manifest"] if state.get("manifest") else "")
    print("  下一步：python scripts/batch_preflight.py --src %s --plan %s %s --lecture %s"
          % (state.get("src"), state.get("annotations"), _mans, out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
