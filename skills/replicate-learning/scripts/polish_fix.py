# -*- coding: utf-8 -*-
"""排版修复通用工具 v2.27（⓪e E3/E4/E8）：
  A) ②/④/⑥ 节超长段按句读断段（两轮：句读优先 → 逗号软切）；
  B) ①/②/⑦ 节的裸围栏补 `text` 语言标注；
  C) ⑥ 节「其一/其二/…」内联枚举 → 列表项（保留引导句）；
  D) ⑥ 节标记段（【讲解】/【构造方式与实现手法】/【上下游】/【怎么用】/【怎么接】/【白话…】）之间补空行。
用法：python polish_fix.py <批次.md> [--dry]
"""
import io, re, sys

MAXP = 300
MARKER_RE = re.compile(r"^\s*\**【(讲解|构造方式与实现手法|上下游|怎么用|怎么接|白话[^】]*|边界[^】]*|上下游契约)】")
ENUM_RE = re.compile(r"(?=\*\*其[一二三四五六]，)")


def seg_bound(lines, open_pat, close_pat):
    st = en = None
    for i, l in enumerate(lines):
        if st is None and re.match(open_pat, l):
            st = i
        elif st is not None and re.match(close_pat, l):
            en = i
            break
    return (st, en) if st is not None else (None, None)


def split_long_para(para, maxp=MAXP):
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


def enum_split(para):
    """「其一，/其二，…」内联枚举 → [引导句, 列表项...]；不足 2 项返回 None。"""
    parts = [p.strip() for p in ENUM_RE.split(para) if p.strip()]
    if len(parts) < 3:
        return None
    out = [parts[0]] + ["- " + p for p in parts[1:]]
    return out


def fix_paras(lines, sec_name, dry=False):
    st, en = seg_bound(lines, r"^## %s\s" % sec_name, r"^## ")
    if st is None:
        return 0, 0
    out, n_cut, n_enum = [], 0, 0
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
        enum = enum_split(s) if not dry else None
        if enum:
            if not dry:
                out.extend(enum[0].split("\n"))
                for p in enum[1:]:
                    out.append("")
                    out.append(p)
            n_enum += 1
            continue
        parts = split_long_para(s)
        if parts:
            n_cut += 1
            if not dry:
                out.extend(parts[0].split("\n"))
                for p in parts[1:]:
                    out.append("")
                    out.append(p)
            continue
        out.append(l)
    if not dry:
        lines[:] = out
    return n_cut, n_enum


def fix_marker_spacing(lines, sec_name="⑥", dry=False):
    """⑥ 节内标记段之间补空行（段间必空行）。"""
    st, en = seg_bound(lines, r"^## %s\s" % sec_name, r"^## ")
    if st is None:
        return 0
    out, n, inside = [], 0, False
    prev_blank = True
    for i, l in enumerate(lines):
        if i <= st or (en is not None and i >= en):
            if re.match(r"^```", l):
                inside = not inside
            out.append(l)
            prev_blank = not l.strip()
            continue
        if re.match(r"^```", l):
            inside = not inside
        if (not inside) and MARKER_RE.match(l) and not prev_blank:
            out.append("")
            n += 1
        out.append(l)
        prev_blank = not l.strip()
    if not dry:
        lines[:] = out
    return n


def fix_bare_fences(lines, sec_names=("①", "②", "⑦"), dry=False):
    marks = []
    for nm in sec_names:
        st, en = seg_bound(lines, r"^## %s\s" % nm, r"^## ")
        if st is not None:
            marks.append((st, en if en is not None else len(lines), nm))
    n, inside = 0, False
    for i, l in enumerate(lines):
        m = re.match(r"^```(\S*)\s*$", l)
        if not m:
            continue
        if not inside:
            inside = True
            if not m.group(1):
                owner = next((nm for a, b, nm in marks if a < i < b), None)
                if owner:
                    if not dry:
                        lines[i] = "```text"
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
    r2 = fix_paras(lines, "②", dry)
    r4 = fix_paras(lines, "④", dry)
    r6 = fix_paras(lines, "⑥", dry)
    mk = fix_marker_spacing(lines, "⑥", dry)
    nf = fix_bare_fences(lines, dry=dry)
    if not dry:
        io.open(path, "w", encoding="utf-8", newline="").write("\n".join(lines))
    print("%s ②断段=%d/%d ④断段=%d/%d ⑥断段=%d/枚举=%d 标记段空行=%d 裸围栏补text=%d"
          % ("[dry] " if dry else "[write] ",
             r2[0], r2[1], r4[0], r4[1], r6[0], r6[1], mk, nf))


if __name__ == "__main__":
    main()
