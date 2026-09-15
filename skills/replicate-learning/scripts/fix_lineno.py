#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""行号标注修正器（两件事一起做）：
  ① 数字纠偏：按"行内容在源文件里唯一定位"重写编号（口径与 `gate_lecture.check_lineno` 一致）
  ② 格式升级：`// :36`（已作废）→ `// :L36`（§6.4 规定格式），全文件统一

**为什么它随技能发布**：④ 行号一致性是机械判据，但修它靠手改必然错——把 `:L34` 改成 `:L35`
这种活，人工核对 100 处就会有 5 处漏。本脚本的定位不是"猜偏移量"，而是：
**按该行代码在源文件里出现的位置唯一定位真行号**（内容不唯一就跳过，不猜）。

用法：
    python fix_lineno.py <讲解.md> [...]                      # 只报告（缺省）
    python fix_lineno.py <讲解.md> [...] --apply              # 写回（tmpnew → os.replace）
    python fix_lineno.py <讲解.md> --src D:\\proj --apply
    python fix_lineno.py <讲解.md> --ignore-format            # 只纠偏，不做格式升级

安全护栏（③ 相关，别删）：位于 ⑤ 用法标记之下的块（`mk`）**不改格式**——否则会把教学合成片段
变成"声明自己是源码"，无谓地制造新的 ①②③④ 失败；这类块单独列在 `[跳过·⑤标记之下]` 里供人工判断。
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gate_lecture as G  # noqa: E402

# 本脚本依赖的 gate 对外符号（skill_selfcheck 会逐条校验存在性）。
# 判据改动若删/改了这些名字，本脚本会**静默失准**（而它要写回 NOTES 里的行号）——所以必须被自检钉住。
#   ① GATE_API      = import 时就存在的模块级名字（常量 / 正则 / 函数 / 快照状态）
#   ② GATE_GLOBALS_SET = 由 gate 的 main() 内部 `global` 声明、**必须由调用方写入**的全局
#      （ROOT 影响 os.path.relpath 的基准，写错 → 归属全错但不会报错，所以单独校验）
GATE_API = ['ANNO', 'PUNCT_ONLY', 'CMT_LINE', 'SPLIT_DECL', 'norm_code',
            'index_sources', 'parse_blocks', 'resolve_snapshot', 'load_snapshot',
            'is_exempt', 'is_hist', 'snap_file_lines', 'src_lines', 'attribute',
            'SNAPSHOT', 'SNAP_TAR', 'SNAP_UNION', '_snap_file_cache']
GATE_GLOBALS_SET = ['ROOT']


def check_gate_api():
    miss = [n for n in GATE_API if not hasattr(G, n)]
    gate_src = io.open(os.path.join(HERE, 'gate_lecture.py'), encoding='utf-8').read()
    miss += [n for n in GATE_GLOBALS_SET if not re.search(r'^\s*global\s+%s\b' % n, gate_src, re.M)]
    if miss:
        raise SystemExit('[ABORT] gate_lecture 缺少本脚本依赖的符号：%s\n'
                         '   → 判据改动动了内部结构。请同步更新 fix_lineno.py 的 GATE_API '
                         '与取值方式，再重跑（不要直接改 gate 迁就本脚本）。' % '、'.join(miss))


def rebuild(x, real):
    """把 x 里的行号标注重写为 `// :L<real>`，保留标注后的说明文字"""
    m = G.ANNO.search(x)
    if not m:
        return x, None
    prefix = x[:m.start()]
    spec = m.group(1)
    note = m.group(2)
    parts = spec.split("-")
    delta = real - int(parts[0])
    new_spec = "-".join(str(int(p) + delta) for p in parts)
    newx = "%s// :L%s%s" % (prefix, new_spec, ("  " + note) if note else "")
    return newx, (int(parts[0]), real)


def fix_file(path, src, apply=False, upgrade_format=True):
    by_class, rev = G.index_sources(src)
    lines, blocks = G.parse_blocks(path)
    sha, _how = G.resolve_snapshot(lines)
    if sha:
        G.load_snapshot(sha)
    else:
        G.SNAPSHOT = G.SNAP_TAR = G.SNAP_UNION = None
        G._snap_file_cache.clear()

    fixed, upgraded, skipped = [], [], []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java":
            continue
        exempt = G.is_exempt(sect, h2, mk, bl)
        classes = G.SPLIT_DECL.findall("\n".join(bl))
        if not classes:
            classes = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", sect) if not re.fullmatch(r"L\d+", w)]
            if not classes:
                classes = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", hint) if not re.fullmatch(r"L\d+", w)]
        code = [G.norm_code(x) for x in bl]
        code = [c for c in code if c and not G.CMT_LINE.match(c)]
        cand = None
        idx = {}
        if len(code) >= 5:
            cand, _ = G.attribute(code, classes, by_class, rev)
        if cand is not None:
            base = None
            if G.is_hist(sect, chain) and G.SNAPSHOT:
                base = G.snap_file_lines(os.path.relpath(cand, src))
            src_body = base if base is not None else G.src_lines(cand)
            for i, l in enumerate(src_body):
                n = G.norm_code(l)
                if n:
                    idx.setdefault(n, []).append(i + 1)

        for j, x in enumerate(bl):
            m = G.ANNO.search(x)
            if not m:
                continue
            had_L = bool(re.search(r"//\s*:L\d", x))
            n = G.norm_code(x)
            real = None
            if cand is not None and len(n) >= 8 and not G.PUNCT_ONLY.match(n):
                where = idx.get(n, [])
                if len(where) == 1:                    # 内容唯一才定位，不唯一就不猜
                    real = where[0]
            if mk and not exempt:                      # ③ 安全护栏：⑤ 标记之下的块不动格式（只报）
                skipped.append((start + j, sect[:44], x.strip()[-24:]))
                continue
            if real is None:
                if not had_L and upgrade_format:       # 无法定位但格式旧 → 只升级格式，编号照搬
                    newx, _ = rebuild(x, int(m.group(1).split("-")[0]))
                    lines[start - 1 + j] = newx
                    upgraded.append((start + j, m.group(1)))
                continue
            newx, pair = rebuild(x, real)
            lines[start - 1 + j] = newx
            if not had_L and upgrade_format:
                upgraded.append((start + j, m.group(1)))
            if pair and pair[0] != pair[1]:
                fixed.append((start + j, pair[0], pair[1], os.path.basename(cand), n[:58]))

    print("== %s" % os.path.basename(path))
    for ln, want, real, f, s in fixed:
        print("   [纠偏] :%-5d :L%-4d → :L%-4d  %-26s %s" % (ln, want, real, f, s))
    if upgrade_format:
        print("   [升级格式] %d 处 `// :N` → `// :Lnn`" % len(upgraded))
    if skipped:
        print("   [跳过·⑤标记之下] %d 处（人工判断，勿当源码声明）" % len(skipped))
        for ln, sect, tail in skipped[:5]:
            print("        :%-5d %s  %s" % (ln, sect, tail))
    if apply and (fixed or upgraded):
        tmp = path + ".tmpnew"
        io.open(tmp, "w", encoding="utf-8", newline="").write("\n".join(lines))
        os.replace(tmp, path)
        print("   → 已写回")
    return len(fixed), len(upgraded)


def main():
    ap = argparse.ArgumentParser(description='行号标注修正（缺省只报告）')
    ap.add_argument('files', nargs='+')
    ap.add_argument('--src', default=os.getcwd(), help='源码根目录（缺省=当前目录）')
    ap.add_argument('--apply', action='store_true', help='写回文件（缺省只报告）')
    ap.add_argument('--ignore-format', action='store_true', help='只纠偏，不做 `// :N` → `// :Lnn` 升级')
    a = ap.parse_args()
    check_gate_api()
    src = os.path.abspath(a.src)
    G.ROOT = src
    tf = tu = 0
    for p in a.files:
        x, y = fix_file(p, src, a.apply, not a.ignore_format)
        tf += x
        tu += y
    print("\n总计：纠偏 %d 处，格式升级 %d 处%s" % (tf, tu, "（已写回）" if a.apply else "（未写回）"))
    return 0


if __name__ == '__main__':
    sys.exit(main())
