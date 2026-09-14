#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate_lecture.py —— 批次讲解「内容真实性 + 注释密度」闸门（SKILL §6.4 C 组）

用法：
    python gate_lecture.py <批次讲解.md> --src <源码根目录> [--json out.json] [--verbose]

三项检查（任一不过 = 退出码 1）：
  ① 正向保真度：讲解里每个 java 代码块（凭类名归属源文件）的每一行代码，
      必须能在对应源文件里逐字找到。门槛 100%。
      —— 抓"讲解编造了源码里没有的代码"（SKILL §6.1 血证：某批仅 55.3%）。
  ② 反向完整度：★类源文件的每一条有效行，必须出现在讲解里。门槛 99.5%。
      —— 抓"摘录式贴码 / 整节缺失"。
  ③ 注释密度：按 §6.1.1「关键行」口径算
      (a) 无注释连段 <8 行  (b) 教学注释条数 ≥ 关键行数÷12  (c) ★类每个方法签名行或相邻行有注释
      —— 抓"只贴 `// :Lnn` 裸行号、没有一句讲解"。

免检小节：标题含 手写 / No-Framework / 不用框架 / 等价实现 / 反例 / 对照 的代码块不参与 ①②，
但会被统计并打印（防止借"反例"之名夹带未核实代码）。
"""
import os
import re
import sys
import json
import math
import collections

# ── 归一化 ────────────────────────────────────────────────────────────────
ANNO = re.compile(r"//\s*:L?(\d+(?:-\d+)?)[ \t]*(.*)$")
CJK = re.compile(r"[\u4e00-\u9fff]")
TRAIL_CMT = re.compile(r"(\s+(//|#|--).*)$")
CMT_LINE = re.compile(r"^\s*(//|/\*|\*|#|--)")
PUNCT_ONLY = re.compile(r"^[{}()\[\];,<>\s]*$")
DOCTYPE_DECL = re.compile(r"^\s*(?:public|private|protected|static|final|\s)*[A-Za-z_][\w<>\[\],\.\s]*\s+\w+\s*;\s*$")
LICENSE_HINT = re.compile(r"(Licensed to the Apache|Apache License|WITHOUT WARRANTIES|limitations under the License)")
EXEMPT = re.compile(
    r"(手写|No-Framework|不用框架|等价实现|反例|反面对照|对照实现|穿透卡|穿透|示例|演示|伪代码"
    r"|卡[一二三四五六七八九十0-9]|L0-L4|L1-L4|例 \d|Tiny|样例节选)", re.I)
CJK_LANGS = {"java", "sql", "yaml", "yml", "xml", "properties", "lua", "st", "json"}
SKIP_DIRS = {"target", "node_modules", ".git", ".tmp_audit", ".tmp_lecture", ".workbuddy"}
SPLIT_DECL = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Z][A-Za-z0-9_]*)")


def strip_anno(line):
    """去掉行尾 `// :Lnn <说明>`，返回 (剩余代码, 标注后的说明文字)"""
    m = ANNO.search(line)
    if not m:
        return line, ""
    return ANNO.sub("", line), (m.group(2) or "").strip()


def norm_code(line):
    """代码归一化：去行号标注、去行尾注释、折叠空白（折行/对齐差异不算差异）"""
    code, _ = strip_anno(line)
    code = code.replace("\t", " ")
    code = re.sub(r"\s+", " ", code).strip()
    return code


def has_cjk_comment(line):
    """该行是否有中文注释：行号标注后带中文，或行内注释含中文"""
    _, anno_text = strip_anno(line)
    if anno_text and CJK.search(anno_text):
        return True
    code, _ = strip_anno(line)
    head = code.split("//")[0]
    tail = code[len(head):]
    if tail and CJK.search(tail):
        return True
    if CMT_LINE.match(code) and CJK.search(code):
        return True
    return False


def mark_text_block_lines(bl):
    """标出处于文本块（\"\"\" 或 SQL 多行串）内部的行 —— 它们是数据不是逻辑，不计入密度"""
    inside = []
    state = False
    for ln in bl:
        code, _ = strip_anno(ln)
        cnt = code.count('"""')
        if state:
            inside.append(True)
            if cnt % 2 == 1:
                state = False
        else:
            inside.append(False) if cnt == 0 else inside.append(False)
            if cnt % 2 == 1:
                state = True
    return inside


def is_key_line(line, in_license, in_text_block=False):
    """§6.1.1「关键行」判定：非关键行不计入密度"""
    if in_text_block:
        return False
    code, _ = strip_anno(line)
    s = code.strip()
    if not s or in_license or LICENSE_HINT.search(s):
        return False
    if s.startswith(("package ", "import ", "export ")):
        return False
    if PUNCT_ONLY.match(s):
        return False
    if DOCTYPE_DECL.match(s):
        return False
    return True


# ── 讲解文件解析 ──────────────────────────────────────────────────────────
def parse_blocks(path):
    """返回 (全部行, [(起始行号, 语言, 行列表, 所属小节标题, 所属一级节标题, 类名线索)])"""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    out, cur, lang, start = [], None, None, 0
    # 预先算好每到一行的"最近一个含驼峰标识符的标题"，作为片段块的归属线索
    hint, hint_cur = {}, ""
    for i, l in enumerate(lines):
        if re.match(r"^#{2,5} ", l):
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", l)
                   if not re.fullmatch(r"L\d+", w)]      # 排除 `:L142` 这类行号引用
            if ids:
                hint_cur = " ".join(ids)
        hint[i + 1] = hint_cur
    for i, l in enumerate(lines):
        m = re.match(r"^(\s*)(`{3,})\s*([A-Za-z0-9_+-]*)\s*$", l)
        if cur is None:
            if m:
                cur, lang, start = [], (m.group(3) or "").lower(), i + 2
        else:
            if re.match(r"^\s*`{3,}\s*$", l):
                s3 = sect_of(lines, start, (3, 4, 5))
                s2 = sect_of(lines, start, (2,))
                out.append((start, lang, cur, s3 if s3 != "?" else s2, s2, hint.get(start, "")))
                cur = None
            else:
                cur.append(l)
    return lines, out


def sect_of(lines, start, levels=(2, 3, 4, 5)):
    """回溯最近的小节标题"""
    for i in range(start - 2, -1, -1):
        if re.match(r"^#{2,5} ", lines[i]):
            lv = len(lines[i]) - len(lines[i].lstrip("#"))
            if lv in levels:
                return lines[i].strip()
    return "?"


def find_classes(text):
    return re.findall(r"\b(?:class|interface|enum|record|@interface)\s+([A-Z][A-Za-z0-9_]*)", text)


# ── 源码索引 ──────────────────────────────────────────────────────────────
def index_sources(root):
    """返回 (类名 -> 文件列表, 代码行 -> Counter(文件))；后者用于无类名片段块的归属回退"""
    by_class = collections.defaultdict(list)
    rev = collections.defaultdict(collections.Counter)
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            if fn.endswith(".java"):
                p = os.path.join(dp, fn)
                by_class[fn[:-5]].append(p)
                for l in open(p, encoding="utf-8", errors="replace").read().split("\n"):
                    n = norm_code(l)
                    if n and not CMT_LINE.match(n):
                        rev[n][p] += 1
    return by_class, rev


_NS_CACHE = {}


def _ns(path):
    if path not in _NS_CACHE:
        _NS_CACHE[path] = src_nospace(path)
    return _NS_CACHE[path]


def line_ok_in(path, n):
    """该行是否属于源文件：先逐行比，再退化为"去空白子串"（容忍折行）"""
    if n in src_code_set(path):
        return True
    ns = re.sub(r"\s+", "", n.split("//")[0])
    if len(ns) < 8:
        return False
    return ns in _ns(path)


def attribute(code, classes, by_class, rev):
    """返回 (最佳源文件, 真·不命中行列表)；先按类名，再按内容回退"""
    pool_files = []
    for c in classes:
        pool_files += by_class.get(c, [])
    if not pool_files:
        # 内容回退：逐行投票
        votes = collections.Counter()
        for x in code:
            for f in rev.get(x, {}):
                votes[f] += 1
        if not votes:
            return None, None
        f, hit = votes.most_common(1)[0]
        if hit / len(code) < 0.85:
            return None, None
        pool_files = [f]
    best = None
    for p in set(pool_files):
        lost = [x for x in code if not line_ok_in(p, x)]
        if best is None or len(lost) < len(best[1]):
            best = (p, lost)
    return best


def src_code_set(path):
    s = set()
    for l in open(path, encoding="utf-8", errors="replace").read().split("\n"):
        n = norm_code(l)
        if n and not CMT_LINE.match(n):
            s.add(n)
    return s


def src_nospace(path):
    """整文件的"去空白"文本：用于容忍跨行折行差异（讲解把长行拆两行不算编造）"""
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = []
    for l in txt.split("\n"):
        c, _ = strip_anno(l)
        head = c.split("//")[0]
        out.append(head)
    return re.sub(r"\s+", "", "".join(out))


def src_lines(path):
    return open(path, encoding="utf-8", errors="replace").read().split("\n")


# ── 检查 ①：正向保真度 ───────────────────────────────────────────────────
def is_exempt(sect, h2):
    """免检判定：小节名或所属一级节名命中免检词，或属于 ⑨ No-Framework 节下的 ### 9.x"""
    if EXEMPT.search(sect or "") or EXEMPT.search(h2 or ""):
        return True
    if re.match(r"^#{3,5}\s*9\.", sect or ""):
        return True
    return False


def check_fidelity(blocks, by_class, rev):
    rows = []
    for start, lang, bl, sect, h2, hint in blocks:
        if lang != "java":
            continue
        text = "\n".join(bl)
        # 类名线索 = 块内 class 声明 + 小节标题驼峰标识符 + 最近含类名的标题（片段块靠后两者归属）
        # 注意排除 `L142` 这类"行号引用"（它也满足驼峰正则，会带偏归属）
        def _ids(t):
            return [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", t) if not re.fullmatch(r"L\d+", w)]
        classes = SPLIT_DECL.findall(text)
        if not classes:
            classes = _ids(sect) or _ids(hint)
        code = [norm_code(x) for x in bl]
        code = [c for c in code if c and not CMT_LINE.match(c)]
        if len(code) < 5:
            continue
        cand, lost = attribute(code, classes, by_class, rev)
        rows.append(dict(start=start, sect=sect, h2=h2, lang=lang, classes=classes,
                         n_code=len(code), exempt=is_exempt(sect, h2),
                         cand=os.path.relpath(cand, ROOT) if cand else None,
                         lost=len(lost) if lost is not None else None,
                         lost_samples=(lost[:4] if lost else [])))
    return rows


# ── 检查 ②：反向完整度（★类） ────────────────────────────────────────────
def check_reverse(blocks, lines, by_class):
    """★类 = 小节标题里带 ★ 且能提取到类名的代码块"""
    rows = []
    for start, lang, bl, sect, h2, hint in blocks:
        if lang != "java" or "★" not in sect:
            continue
        if is_exempt(sect, h2):
            continue          # 样例节选 / 手写版等免检块不参与 ★完整性（它们本就不是整文件）
        classes = find_classes("\n".join(bl))
        if not classes:
            continue
        for c in classes[:1]:
            cands = by_class.get(c)
            if not cands:
                continue
            p = cands[0]
            lect = set()
            for blk in blocks:
                for x in blk[2]:
                    n = norm_code(x)
                    if n:
                        lect.add(n)
            real, miss = 0, []
            for sl in src_lines(p):
                t = norm_code(sl)
                if not t or CMT_LINE.match(t) or t.startswith(("import ", "package ")) or PUNCT_ONLY.match(t):
                    continue
                real += 1
                if t not in lect:
                    miss.append(t)
            cov = (real - len(miss)) / real if real else 1.0
            rows.append(dict(cls=c, src=os.path.relpath(p, ROOT), sect=sect,
                             real=real, miss=len(miss), cov=round(cov, 4),
                             samples=miss[:3]))
    return rows


# ── 检查 ③：注释密度 ─────────────────────────────────────────────────────
def check_density(blocks):
    rows = []
    for start, lang, bl, sect, h2, hint in blocks:
        if lang not in CJK_LANGS or len(bl) < 5:
            continue
        exempt = is_exempt(sect, h2)
        # 许可证头检测：package/import 之前的块注释
        in_lic, seen_pkg = False, False
        keys = []
        tb = mark_text_block_lines(bl)
        for idx, ln in enumerate(bl):
            code, _ = strip_anno(ln)
            if code.strip().startswith(("package ", "import ")):
                seen_pkg = True
            # 许可证头：只有真的出现 license 文本才进入；遇到块注释结束符立即退出
            # （否则"以 /* 开头的片段块"——比如节选样例——会被整块误判为许可证头而跳过密度检查）
            if LICENSE_HINT.search(code):
                in_lic = True
            if in_lic and "*/" in code:
                in_lic = False
            if seen_pkg:
                in_lic = False
            if not is_key_line(ln, in_lic, tb[idx]):
                continue
            keys.append((ln, has_cjk_comment(ln)))
        key_n = len(keys)
        # (a) 无注释连段
        mx, cur, runs = 0, 0, 0
        for _, ok in keys:
            if ok:
                if cur >= 8:
                    runs += 1
                mx = max(mx, cur)
                cur = 0
            else:
                cur += 1
        if cur >= 8:
            runs += 1
        mx = max(mx, cur)
        # (b) 教学注释条数
        cmts = sum(1 for _, ok in keys if ok)
        need = max(5, math.ceil(key_n / 12)) if ("★" in sect) else math.ceil(key_n / 12)
        rows.append(dict(start=start, sect=sect, exempt=exempt, key_lines=key_n,
                         comments=cmts, max_run=mx, bad_runs=runs,
                         need=need, star=("★" in sect)))
    return rows


def main():
    global ROOT
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    lec = sys.argv[1]
    root = "."
    verbose = "--verbose" in sys.argv
    jout = None
    if "--src" in sys.argv:
        root = sys.argv[sys.argv.index("--src") + 1]
    if "--json" in sys.argv:
        jout = sys.argv[sys.argv.index("--json") + 1]
    ROOT = os.path.abspath(root)

    if not os.path.isfile(lec):
        print("找不到讲解文件：", lec)
        return 2
    lines, blocks = parse_blocks(lec)
    by_class, rev = index_sources(ROOT)

    print("=" * 96)
    print("批次讲解闸门（§6.4 C 组）:", os.path.basename(lec))
    print("源码根目录:", ROOT)
    print("=" * 96)

    # ① 正向
    fid = check_fidelity(blocks, by_class, rev)
    chk = [r for r in fid if not r["exempt"]]
    tot = sum(r["n_code"] for r in chk)
    lost = sum(r["n_code"] if r["lost"] is None else r["lost"] for r in chk)   # 注意：不能用 `or`，0 是合法值
    unattr = [r for r in chk if r["lost"] is None]
    print(f"\n① 正向保真度：{len(chk)} 个代码块 / {tot} 行代码 → 不命中 {lost} 行 "
          f"= 保真度 {100.0*(tot-lost)/tot if tot else 100:.1f}%  "
          f"{'PASS' if lost == 0 and not unattr else 'FAIL'}")
    for r in chk:
        if r["lost"] is None:
            print(f"   ! 无法归属源文件  {os.path.basename(lec)}:{r['start']}  {r['sect']}")
        elif r["lost"]:
            print(f"   ! 不命中 {r['lost']}/{r['n_code']} 行  :{r['start']}  {r['sect']}")
            print(f"     归属 = {r['cand']}")
            for s in r["lost_samples"]:
                print(f"       源码里没有: {s[:88]}")
    ex = [r for r in fid if r["exempt"]]
    if ex:
        print(f"   （免检小节 {len(ex)} 个代码块 / {sum(r['n_code'] for r in ex)} 行："
              f"{', '.join(sorted({r['sect'] for r in ex}))[:110]}）")

    # ② 反向
    rev = check_reverse(blocks, lines, by_class)
    print(f"\n② 反向完整度（★类）：{len(rev)} 个★类")
    bad_rev = [r for r in rev if r["cov"] < 0.995]
    for r in rev:
        tag = "OK " if r["cov"] >= 0.995 else "FAIL"
        print(f"   [{tag}] {r['cls']:<34} 有效行={r['real']:<4} 缺失={r['miss']:<4} 覆盖={r['cov']*100:.1f}%")
        for s in r["samples"]:
            print(f"          缺失: {s[:82]}")
    print(f"   → {'PASS' if not bad_rev else 'FAIL'}")

    # ③ 密度
    den = check_density(blocks)
    print(f"\n③ 注释密度（§6.1.1）：{len(den)} 个代码块")
    bad_den = []
    for r in den:
        reasons = []
        if r["max_run"] >= 8:
            reasons.append(f"无注释连段 {r['max_run']} 行")
        if r["comments"] < r["need"]:
            reasons.append(f"注释 {r['comments']} < 需 {r['need']}")
        if reasons and not r["exempt"]:
            bad_den.append((r, reasons))
    for r, reasons in sorted(bad_den, key=lambda x: -x[0]["max_run"])[:25]:
        print(f"   [FAIL] :{r['start']:<6} 关键行={r['key_lines']:<4} 注释={r['comments']:<4} "
              f"最长无注释={r['max_run']:<4} {r['sect'][:44]}")
        print(f"          → {'; '.join(reasons)}")
    if len(bad_den) > 25:
        print(f"   ...另有 {len(bad_den)-25} 个不达标块")
    print(f"   → {'PASS' if not bad_den else 'FAIL'}")

    ok = (lost == 0 and not unattr and not bad_rev and not bad_den)
    print("\n④ 残留引用自查（闸门盲区，SKILL §6.4「⑥ 节之外的残留引用检查」必做清单，需人工过）：")
    print("   ②多步示意（是否漏步/顺序反）｜⑦调用链表（方法名·字段名·两跳顺序）｜⑦边界条件表（行为是否与真实分支一致）")
    print("   ⑧穿透卡 L3·L4（异常类型是否与真实 throw/测试断言一致）｜⑩反例的 ✅ 代码（API 是否真实存在）")
    print("   ⑪测试表（方法名·构造实参·assertThrows 异常类 —— 逐条打开真实测试文件核对）｜⑯自检表（是否复述旧结论）")
    print("\n" + "=" * 96)
    print("总判定:", "PASS ✅" if ok else "FAIL ❌（C 组任一不过 = 当场修）")
    print("=" * 96)

    if jout:
        json.dump(dict(fidelity=fid, reverse=rev, density=den, pass_=ok),
                  open(jout, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("明细已写:", jout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
