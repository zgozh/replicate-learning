# -*- coding: utf-8 -*-
"""排版修复通用工具（v2.26 · ⓪e E3/E4）：
  A) ②/④ 节超长段（>300 字）按句读断段（段间空行）；
  B) ①/②/⑦ 节的裸围栏补 `text` 语言标注。
用法：python polish_fix.py <批次.md> [--dry]
"""
import io, re, sys

MAXP = 300

def seg_bound(lines, open_pat, close_pat):
    """返回 (start_idx, end_idx)（0 基，[start, end)）"""
    st = en = None
    for i, l in enumerate(lines):
        if st is None and re.match(open_pat, l):
            st = i
        elif st is not None and re.match(close_pat, l):
            en = i
            break
    return (st, en) if st is not None else (None, None)

def split_long_para(para, maxp=MAXP):
    """把超长段按句读切成 ≤maxp 的若干段（两轮：句读优先，仍超长按逗号软切）；>=2 段时返回列表，否则 None。"""
    if len(para) <= maxp:
        return None
    parts, cur = [], ""
    for ch in para:
        cur += ch
        if ch in "。！？；" and len(cur) >= maxp * 0.6:
            parts.append(cur)
            cur = ""
    if cur:
        parts.append(cur)
    fixed = []
    for p in parts:
        if len(p) <= maxp:
            fixed.append(p)
            continue
        buf = ""
        for ch in p:
            buf += ch
            if ch in "，、：" and len(buf) >= maxp * 0.7:
                fixed.append(buf)
                buf = ""
        if buf:
            fixed.append(buf)
    return fixed if len(fixed) >= 2 else None

def fix_paras(lines, sec_name, dry=False):
    """在指定一级节内对"非表格/非列表/非围栏/非标题"的行做超长段断段。"""
    st, en = seg_bound(lines, r"^## %s\s" % sec_name, r"^## ")
    if st is None:
        return 0
    out, changes = [], 0
    inside = False
    for i, l in enumerate(lines):
        if i <= st or (en is not None and i >= en):
            if re.match(r"^```", l):
                inside = not inside
            out.append(l)
            continue
        if re.match(r"^```", l):
            inside = not inside
            out.append(l)
            continue
        s = l.strip()
        is_list = bool(re.match(r"^[-*+]\s", s)) or bool(re.match(r"^\d+[.、)]\s", s))
        skip = (not s) or inside or s.startswith("|") or s.startswith("#") \
               or s.startswith(">") or is_list
        if skip:
            out.append(l)
            continue
        parts = split_long_para(s)
        if parts and not dry:
            out.extend(parts[0].split("\n"))
            for p in parts[1:]:
                out.append("")
                out.append(p)
            changes += 1
        else:
            if parts:
                changes += 1
            out.append(l)
    if not dry:
        lines[:] = out
    return changes

def fix_bare_fences(lines, sec_names=("①", "②", "⑦"), dry=False):
    """把指定一级节内的裸开围栏补 `text`（图示/命令块）。"""
    marks = []
    for nm in sec_names:
        st, en = seg_bound(lines, r"^## %s\s" % nm, r"^## ")
        if st is not None:
            marks.append((st, en if en is not None else len(lines), nm))
    n = 0
    inside = False
    for i, l in enumerate(lines):
        m = re.match(r"^```(\S*)\s*$", l)
        if not m:
            continue
        if not inside:
            inside = True
            if not m.group(1):
                owner = next((nm for a, b, nm in marks if a < i < b), None)
                if owner and not dry:
                    lines[i] = "```text"
                if owner:
                    n += 1
        else:
            inside = False
    return n

def main():
    if len(sys.argv) < 2:
        print(__doc__); return
    path = sys.argv[1]
    dry = "--dry" in sys.argv
    lines = io.open(path, "r", encoding="utf-8").read().split("\n")
    c2 = fix_paras(lines, "②", dry)
    c4 = fix_paras(lines, "④", dry)
    nf = fix_bare_fences(lines, dry=dry)
    if not dry:
        io.open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
    print("%s ②断段=%d ④断段=%d 裸围栏补text=%d" % ("[dry] " if dry else "[write] ", c2, c4, nf))

if __name__ == "__main__":
    main()
