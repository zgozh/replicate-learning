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

不做的事：不生成讲解内容、不发明件标题、不替模型写注释。
"""
import argparse
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import assemble_batch as AB                   # noqa: E402
import inject_source as INJ                   # noqa: E402
import lecture_checks as LC                   # noqa: E402
from safe_edit import save as safe_save, scan_fences   # noqa: E402


def load_batch(path):
    state = json.load(io.open(path, encoding="utf-8"))
    base = os.path.dirname(os.path.abspath(path))
    for key in ("src", "skeleton", "anchors", "annotations", "manifest", "out", "parts_dir"):
        if state.get(key) and not os.path.isabs(state[key]):
            state[key] = os.path.normpath(os.path.join(base, state[key]))
    return state


def collect_parts(parts_dir):
    if not parts_dir or not os.path.isdir(parts_dir):
        return []
    return [os.path.join(parts_dir, fn) for fn in sorted(os.listdir(parts_dir))
            if fn.endswith(".md") and not fn.endswith(".tmpnew")]


def assemble(skeleton_path, part_paths):
    base = io.open(skeleton_path, encoding="utf-8").read()
    if not part_paths:
        return base, []
    parts = [io.open(p, encoding="utf-8").read() for p in part_paths]
    merged = AB.assemble(base, parts)
    _pre, base_sections = AB.split_sections(base, allow_preamble=True)
    _pre2, out_sections = AB.split_sections(merged, allow_preamble=True)
    replaced = sorted(h for h in out_sections if out_sections[h] != base_sections.get(h))
    return merged, replaced


def build(state, inject=True):
    """返回 (text, report)。任何一步失败都抛 SystemExit——调用方保证此时磁盘未被改动。"""
    report = {}
    skeleton = state.get("skeleton")
    if not skeleton or not os.path.isfile(skeleton):
        raise SystemExit("[ABORT] batch.json 里的 skeleton 不存在：%s" % skeleton)
    text, replaced = assemble(skeleton, collect_parts(state.get("parts_dir")))
    report["parts_replaced"] = replaced
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


def main():
    LC.configure_stdio()
    ap = argparse.ArgumentParser(description="从骨架 + 分片 + 注释计划重建批次终稿")
    ap.add_argument("--batch", required=True, help="batch.json（new_batch.py --batch-json 生成）")
    ap.add_argument("--dry-run", action="store_true", help="只报告会改什么，不写盘")
    ap.add_argument("--check", action="store_true", help="与磁盘终稿逐字节比对（一致=0，不一致=1）")
    ap.add_argument("--no-inject", action="store_true", help="只组装不注入（排查分片用）")
    a = ap.parse_args()

    state = load_batch(a.batch)
    text, report = build(state, inject=not a.no_inject)
    out = state.get("out")
    if not out:
        raise SystemExit("[ABORT] batch.json 里没有 out（终稿路径）")

    print("批次 %s → %s" % (state.get("batch_id"), out))
    print("  分片：%d 份（%s）" % (len(collect_parts(state.get("parts_dir"))),
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
        old_lines, new_lines = current.split("\n"), text.split("\n")
        diff = sum(1 for x, y in zip(old_lines, new_lines) if x != y) + abs(len(old_lines) - len(new_lines))
        print("  [FAIL] 磁盘终稿与重建结果不一致（约 %d 行差异）——先跑一次不带 --check 的构建" % diff)
        return 1

    if a.dry_run:
        print("  （dry-run：未写盘）")
        return 0

    if os.path.isfile(out) and io.open(out, encoding="utf-8").read() == text:
        print("  [OK ] 内容与磁盘一致，无需写盘（重复构建是幂等的）")
        return 0
    safe_save(text.split("\n"), out, backup=True)
    print("  → 已写盘 %s" % out)
    print("  下一步：python scripts/batch_preflight.py --src %s --plan %s --manifest %s --lecture %s"
          % (state.get("src"), state.get("annotations"),
             state.get("manifest") or "<清单.json>", out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
