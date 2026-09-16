#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""注释缺口定位器 —— ③ 注释密度不达标时，算出**满足判据所需的最小标注点集合**。

**为什么需要它**：③ 是全库最大的存量（实测 50/53 份讲解卡在它）。修 ③ 的正确姿势不是"通读全文找地方加注释"，
而是**先定位那几条 ≥8 行的无注释连段**，只在这些位置补注即可达标。这个动作在本项目里已经手写过两次
一次性探针脚本（写一次、用完即弃 → 换个会话再写一遍），所以收进技能。

用法：
    python annotate_gaps.py <讲解.md> [--src <仓库根>] [--json out.json]
    只报告，不写盘；补注的文字由人来写（本工具只回答"**补哪几行、补几条就够**"）。

两种块的补法不同（实测踩过）：
  · java 块：在行尾补 `// :L<真实行号>  ←教材：<说明>` —— 行号用**源码真实行号**（脚本会从已有标注里读，
    没有标注的块建议用 `scripts/inject_source.py` 的 `anno` 一次性重注入，别手打）。
  · sql / yaml / properties 块：**行尾的 `-- 说明` / `# 说明` 不计入密度**（判据只认 `//` 尾随或整行注释），
    所以要在目标行**上方插一整行**注释。
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gate_lecture as G  # noqa: E402

# 本脚本依赖的 gate 对外符号（skill_selfcheck 逐条校验存在性）
GATE_API = ['CJK_LANGS', 'LICENSE_HINT', 'mark_text_block_lines', 'is_key_line', 'block_star',
            'has_cjk_comment', 'strip_anno', 'is_exempt', 'parse_blocks', 'ANNO']
GATE_GLOBALS_SET = ['ROOT']


def check_gate_api():
    miss = [n for n in GATE_API if not hasattr(G, n)]
    gate_src = io.open(os.path.join(HERE, 'gate_lecture.py'), encoding='utf-8').read()
    miss += [n for n in GATE_GLOBALS_SET if not re.search(r'^\s*global\s+%s\b' % n, gate_src, re.M)]
    if miss:
        raise SystemExit('[ABORT] gate_lecture 缺少本脚本依赖的符号：%s\n'
                         '   → 判据改动动了内部结构，请同步更新 annotate_gaps.py 的 GATE_API。' % '、'.join(miss))


def scan(lecture, threshold=8):
    lines, blocks = G.parse_blocks(lecture)
    out = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang not in G.CJK_LANGS or len(bl) < 5 or G.is_exempt(sect, h2, mk, bl):
            continue
        in_lic, seen_pkg = False, False
        tb = G.mark_text_block_lines(bl)
        keys = []                                   # [(绝对行号, 行内容, 有中文注释)]
        for idx, ln in enumerate(bl):
            code, _ = G.strip_anno(ln)
            if code.strip().startswith(("package ", "import ")):
                seen_pkg = True
            if G.LICENSE_HINT.search(code):
                in_lic = True
            if in_lic and "*/" in code:
                in_lic = False
            if seen_pkg:
                in_lic = False
            if G.is_key_line(ln, in_lic, tb[idx]):
                keys.append((start + idx, ln, G.has_cjk_comment(ln)))
        key_n = len(keys)
        cmts = sum(1 for _n, _l, ok in keys if ok)
        need = max(5, -(-key_n // 12)) if G.block_star(sect, chain) else -(-key_n // 12)
        # 连段定位（与 gate 同口径：非关键行不重置计数）
        runs, cur, run_start = [], 0, None
        for n, l, ok in keys:
            if ok:
                if cur >= threshold:
                    runs.append((run_start, n - 1, cur))
                cur, run_start = 0, None
            else:
                if cur == 0:
                    run_start = n
                cur += 1
        if cur >= threshold:
            runs.append((run_start, keys[-1][0], cur))
        if not runs and cmts >= need:
            continue
        # 最小标注点：**每 (threshold-1) 个关键行放一个**（一个连段可能有 20+ 行，只放一个点会留下第二段长连段）
        picks = []
        for a, b, _n in runs:
            seg = [k for k in keys if a <= k[0] <= b]
            for idx in range(threshold - 2, len(seg), threshold - 1):
                picks.append(seg[idx])
        if cmts + len(picks) < need:                # 条数还不够 → 从前往后补足
            for n, l, ok in keys:
                if len(picks) + cmts >= need:
                    break
                if not ok and all(p[0] != n for p in picks):
                    picks.append((n, l, ok))
        out.append(dict(start=start, sect=sect.strip()[:60], lang=lang, key_lines=key_n, comments=cmts,
                        need=need, runs=[(a, b, n) for a, b, n in runs],
                        picks=[(n, l.strip()[:70]) for n, l, _ in picks]))
    return lines, out


def main():
    ap = argparse.ArgumentParser(description='③ 注释密度缺口定位（只报告）')
    ap.add_argument('lecture')
    ap.add_argument('--src', default=os.getcwd())
    ap.add_argument('--json')
    a = ap.parse_args()
    check_gate_api()
    G.ROOT = os.path.abspath(a.src)
    lines, gaps = scan(a.lecture)
    if not gaps:
        print('[OK ] 没有 ③ 缺口（所有非免检块都达标）')
        return 0
    print("③ 缺口：%d 个块" % len(gaps))
    for g in gaps:
        print("\n  块 :%-5d [%s] 关键行=%d 注释=%d（需 %d）  连段≥8: %s"
              % (g["start"], g["lang"], g["key_lines"], g["comments"], g["need"],
                 "、".join("%d-%d(%d)" % r for r in g["runs"]) or "无"))
        print("     %s" % g["sect"])
        if g["lang"] != "java":
            print("     ⚠ 非 java 块：行尾 `-- ` / `# ` 注释**不计入密度**，需在下列行**上方插一整行**注释")
        for n, txt in g["picks"]:
            m = G.ANNO.search(lines[n - 1]) if n - 1 < len(lines) else None
            hint = ("行尾补 `// :L%s  ←教材：…`" % m.group(1)) if m else \
                   ("行尾补 `// :L<真实行号>  ←教材：…`（本行无标注 → 建议用 inject_source 的 anno 重注入）"
                    if g["lang"] == "java" else "上方插一整行注释")
            print("     :%-5d %-68s ← %s" % (n, txt, hint))
    if a.json:
        json.dump(gaps, io.open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print("\n→ 已写 %s" % a.json)
    return 1


if __name__ == '__main__':
    sys.exit(main())
