#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把夹具分片里的 ⑨ 段（2.30 的 No-Framework 等价实现）换成 2.31 的「八股讲解」。

为什么夹具也要换：骨架由 `new_batch.py` 从**当前模板**生成、落笔即声明当前判据版本（2.31），
而夹具分片是 2.30 时代的真实批次48 素材——不换的话 e2e 重建出来的成品会带着旧 ⑨，
被 `G-KNOW` 正确地判 FAIL（"你声明了 2.31，⑨ 就得是八股讲解"）。
替换文本单独放 `fixture_sec9_bagu.md`（**不能放进 `parts/`**，否则会被当成第 6 个分片）。

用法：python apply_fixture_sec9.py [--dry]
"""
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PARTS = os.path.join(HERE, "parts")
NEW = os.path.join(HERE, "fixture_sec9_bagu.md")


def replace_sec9(text, new_sec):
    lines = text.split("\n")
    starts = [k for k, l in enumerate(lines) if re.match(r"^##\s*⑨\s", l)]
    if not starts:
        return text, False
    s = starts[0]
    e = next(k for k in range(s + 1, len(lines)) if re.match(r"^##\s*⑩\s", lines[k]))
    return "\n".join(lines[:s] + new_sec + lines[e:]), True


def main():
    dry = "--dry" in sys.argv
    new_sec = io.open(NEW, encoding="utf-8").read().rstrip("\n").split("\n") + [""]
    touched = []
    for fn in sorted(os.listdir(PARTS)):
        if not fn.endswith(".md"):
            continue
        p = os.path.join(PARTS, fn)
        text = io.open(p, encoding="utf-8").read()
        out, changed = replace_sec9(text, new_sec)
        if not changed:
            continue
        print("替换 %s 的 ⑨ 段（%d 行 → %d 行）" % (fn, text.count("\n") + 1, out.count("\n") + 1))
        touched.append(fn)
        if not dry:
            io.open(p, "w", encoding="utf-8", newline="").write(out)
    print("（dry-run，未写盘）" if dry else "已更新 %d 个分片" % len(touched))
    return 0


if __name__ == "__main__":
    sys.exit(main())
