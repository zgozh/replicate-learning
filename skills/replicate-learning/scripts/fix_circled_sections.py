#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修复 17 节一级标题被吞掉的带圈数字（血证 H25）。

背景：\u2467(\u2467=8) / \u2468(=9) / \u246e(=15) / \u246f(=16) 等带圈数字在某些落盘链路上
会静默丢失，标题变成 `##  L0-L4 底层穿透卡`（多一个空格、没有编号）——而 gate 的
section_form_check 会把它判成"缺失的规范节标题"。本脚本按"标题正文"反查应有的编号并补齐。

用法：python fix_circled_sections.py <讲解.md> [--dry]
"""
import io
import re
import sys

CIRCLED = "\u2460\u2461\u2462\u2463\u2464\u2465\u2466\u2467\u2468\u2469\u246a\u246b\u246c\u246d\u246e\u246f"

# 序号（0 基）-> 标题正文的前缀特征
TITLES = [
    "\u5728\u7cfb\u7edf\u5168\u666f\u4e2d\u7684\u4f4d\u7f6e",                                  # 1
    "\u4e1a\u52a1\u573a\u666f\u4e0e\u7aef\u5230\u7aef\u95ed\u73af",                            # 2
    "\u6587\u4ef6\u6e05\u5355\u4e0e\u4e00\u53e5\u8bdd\u804c\u8d23",                            # 3
    "\u65b0\u6982\u5ff5\u767d\u8bdd\u89e3\u91ca",                                              # 4
    "\u6279\u524d\u4e24\u4e2a\u5185\u90e8\u6e05\u5355",                                        # 5
    "\u9010\u4ef6\u8bb2\u89e3",                                                                # 6
    "\u8c03\u7528\u94fe\u3001\u6570\u636e\u6d41\u3001\u72b6\u6001\u53d8\u5316\u4e0e\u8fb9\u754c",  # 7
    "L0-L4 \u5e95\u5c42\u7a7f\u900f\u5361",                                                    # 8
    "No-Framework \u7b49\u4ef7\u5b9e\u73b0",                                                  # 9
    "\u5931\u8d25\u53cd\u4f8b",                                                                # 10
    "\u6d4b\u8bd5\u89c6\u89d2",                                                                # 11
    "Vibecoding \u89c6\u89d2",                                                                 # 12
    "\u9a8c\u8bc1\u8bc1\u636e\u4e0e\u5df2\u77e5\u9650\u5236",                                  # 13
    "\u590d\u4e60\u95ee\u7b54",                                                                # 14
    "\u524d\u7f6e\u77e5\u8bc6",                                                                # 15
    "\u6559\u6750\u8d28\u91cf\u81ea\u68c0",                                                    # 16
]
INDEX_PREFIX = "\u7d22\u5f15"


def main():
    path = sys.argv[1]
    dry = "--dry" in sys.argv
    lines = io.open(path, encoding="utf-8").read().split("\n")
    fixed = []
    for i, l in enumerate(lines):
        m = re.match(r"^## (?!#)(.*)$", l)
        if not m:
            continue
        body = m.group(1)
        if body[:1] in CIRCLED or body.lstrip().startswith(INDEX_PREFIX):
            continue
        text = body.strip()
        for idx, prefix in enumerate(TITLES):
            if text.startswith(prefix):
                new = "## %s %s" % (CIRCLED[idx], text)
                fixed.append((i + 1, l, new))
                lines[i] = new
                break
    if not fixed:
        print("no fix needed")
    for no, old, new in fixed:
        print(":L%d\n  - %s\n  + %s" % (no, old, new))
    if fixed and not dry:
        io.open(path, "w", encoding="utf-8", newline="\n").write("\n".join(lines))
        print("written: %s (%d fixed)" % (path, len(fixed)))


if __name__ == "__main__":
    main()