#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_preflight.py —— 开批预检：**在注入与写作之前**把机器能判的问题一次报出来（方案 §3.2）。

**为什么需要它**（第48批实录）：注释密度的口径直到闸门失败才知道——首轮计划注入后才发现
「★ 方法签名缺注释 3 处、无注释连段 5 处」，随后又临时写了两个探针脚本、还因 API 误用失败两次，
而扫描结果与真实闸门并不一致。根因是**模型在反向推断门禁口径**。本工具把这件事收回来：
直接 `import` `gate_lecture`，用**同一套函数**（`check_density` / `check_sig` / `check_reverse`）
对"准备注入的块"先算一遍——预检结论与终检口径必然同源，不再是两套实现。

检查项（每项在 `--json` 里都有稳定规则 ID，ID 取自 `spec/00-质量契约.json`）：
  · **P-PLAN** 注释计划结构：键必须是源文件内**真实行号**；拼错、重复、越界、落在 Python 字符串
    内部 / 反斜杠续行 / 不支持行尾注释的语言上 → **可执行的错误**（不是打印警告然后漏掉）；
  · **P-HASH** 源文件哈希与 manifest 一致（不一致立即停止）；
  · **P-DENSITY** 同闸门口径算每个待注入块的最长无中文注释连段与注释条数下限，并给**可补注候选行**；
  · **P-SIG** ★ 类方法签名覆盖（按整类、跨块判定）；
  · **P-REVERSE** ★ 类源码行反向覆盖（注入前就知道会不会漏行）；
  · **P-PY** Python 块的注入安全（哪些行不会被标注）与语法可编译性（内存 `compile()`，不落 `.pyc`）；
  · **P-ADDR** 源码块寻址唯一性（`anchor`/`contains` 或稳定槽位必须唯一命中）；
  · **P-SNIP** `【怎么用】/【怎么接】` 教学合成片段的静态校验：语法、花括号、构造参数**个数与类型**；
    无法可靠判定的（参数顺序、第三方 API 行为）标 `manual_review`，**不声称可编译**；
  · **P-SCOPE** 本批适用的 17 节结构清单、⑫ 八条形态要求、文件名与证据等级要求。

不做的事：不写盘（只读预检）、不自动生成空话注释去凑密度、不为校验片段而编译整个项目。
"""
import argparse
import contextlib
import io
import json
import hashlib
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import gate_lecture as G                     # noqa: E402
import inject_source as INJ                  # noqa: E402
import lecture_checks as LC                  # noqa: E402
import new_batch as NB                       # noqa: E402

# 本脚本依赖的 gate 对外符号（skill_selfcheck 的 check_tools 逐条校验存在性）
GATE_API = ['index_sources', 'check_density', 'check_sig', 'check_reverse', 'parse_blocks',
            'is_key_line', 'has_cjk_comment', 'mark_text_block_lines', 'block_star', 'strip_anno',
            'norm_code', 'is_exempt', 'star_classes', 'method_names_of', 'CJK_LANGS',
            'LICENSE_HINT', 'CMT_LINE', 'PUNCT_ONLY', 'SIG', 'SPLIT_DECL', 'MINSNIP_RE',
            'USE_MARKS', 'WIRE_MARKS']
GATE_GLOBALS_SET = ['ROOT']

# 片段校验里允许出现的非本仓类型（JDK / 常用库 / 教学占位名）——**白名单只表示"不报 FAIL"**，
# 不等于"已确认存在"；命中白名单的符号仍由人工复核。
SNIPPET_WHITELIST = {
    "String", "Object", "Integer", "Long", "Double", "Float", "Boolean", "Short", "Byte", "Character",
    "List", "ArrayList", "LinkedList", "Map", "HashMap", "LinkedHashMap", "TreeMap", "Set", "HashSet",
    "LinkedHashSet", "TreeSet", "Collection", "Collections", "Arrays", "Objects", "Optional",
    "StringBuilder", "StringBuffer", "BigDecimal", "BigInteger", "LocalDate", "LocalDateTime",
    "LocalTime", "Duration", "Instant", "DateTimeFormatter", "Pattern", "Matcher", "Stream",
    "Collectors", "Comparator", "Thread", "Runnable", "CompletableFuture", "ExecutorService",
    "Executors", "TimeUnit", "AtomicInteger", "AtomicLong", "UUID", "Random", "Math", "System",
    "Exception", "RuntimeException", "IllegalArgumentException", "IllegalStateException",
    "UnsupportedOperationException", "NullPointerException", "Override", "Test", "ParameterizedTest",
    "Assertions", "Mockito", "ArgumentCaptor", "Mock", "InjectMocks", "SpringBootTest", "Autowired",
    "Service", "Component", "Configuration", "Bean", "Transactional", "Slf4j", "Log", "Getter",
    "Setter", "Data", "Builder", "Value", "NoArgsConstructor", "AllArgsConstructor",
    "RequiredArgsConstructor",
}
INTERNAL_NO_ANNO = {"cmd", "bat", "batch"}
SLOT_RE = re.compile(r"<!--\s*src-slot\s+([^>]*?)-->")


# ── 计划结构校验 ──────────────────────────────────────────────────────────
def normalize_anno_key(key):
    """与 `inject_source.build_block` 同口径：区间标注取首行号。返回 (规范键, 原文)。"""
    text = str(key).strip()
    return text.split("-")[0].strip(), text


def protected_lines(path, lang):
    """注入器**不会**给这些行加行尾标注（加了会改变语义）→ 注释计划里出现就是错。"""
    lines = INJ.read_lines(path)
    protected = {}
    low = (lang or "").lower()
    if low in {"python", "py"}:
        for n in INJ.python_string_lines(lines):
            protected[n] = "Python 多行字符串/文档字符串内部（tokenize 判定）"
    elif low not in INTERNAL_NO_ANNO:
        state = False
        for i, ln in enumerate(lines, 1):
            cnt = ln.count('"""')
            if state:
                protected[i] = "多行文本块内部"
                if cnt % 2 == 1:
                    state = False
            elif cnt % 2 == 1:
                state = True
    if INJ.anno_prefix(lang) is None:
        for i in range(1, len(lines) + 1):
            protected[i] = "该语言不支持行尾注释（%s）" % lang
    for i, ln in enumerate(lines, 1):
        if ln.rstrip().endswith("\\"):
            protected[i] = "行尾是反斜杠续行——追加任何字符都会改变语义"
    return protected


def check_plan(plan, src_root, findings):
    """校验注释计划结构。返回 (blocks, targets, checked_keys)。"""
    blocks, targets, checked_keys, seen_target = [], [], 0, {}
    for idx, spec in enumerate(plan.get("blocks", [])):
        tag = spec.get("slot") or spec.get("anchor") or ("#%d" % (idx + 1))
        rel = spec.get("src")
        if not rel:
            findings.append(LC.make_finding("块缺少 `src`", where=tag))
            continue
        path = os.path.join(src_root, rel)
        if not os.path.isfile(path):
            findings.append(LC.make_finding("源文件不存在：%s" % rel, where=tag))
            continue
        lines = INJ.read_lines(path)
        total = len(lines)
        start, end = spec.get("start"), spec.get("end")
        if start is None and end is None:
            start, end = 1, total
        if not isinstance(start, int) or not isinstance(end, int):
            findings.append(LC.make_finding("start/end 必须是整数（收到 %r/%r）" % (start, end), where=tag))
            continue
        if not (1 <= start <= end <= total):
            findings.append(LC.make_finding("行范围 %d-%d 非法（文件共 %d 行）" % (start, end, total),
                                            where=rel))
            continue
        key = (rel, start, end)
        if key in seen_target:
            findings.append(LC.make_finding(
                "与 %s 指向同一段源码（%s %d-%d）：同段重复注入会让块身份不唯一" % (seen_target[key], rel, start, end),
                where=tag))
        seen_target[key] = tag
        protected = protected_lines(path, spec.get("lang", "java"))
        anno, seen_key = {}, {}
        for raw_key, note in (spec.get("anno") or {}).items():
            checked_keys += 1
            norm, original = normalize_anno_key(raw_key)
            if not norm.isdigit():
                findings.append(LC.make_finding("注释键 %r 不是行号（区间请写首行号）" % original, where=rel))
                continue
            n = int(norm)
            if original != norm and norm in seen_key:
                findings.append(LC.make_finding(
                    "注释键 %r 与 %r 规范化后同为第 %d 行（重复目标：只有一个会生效）"
                    % (original, seen_key[norm], n), where=rel, line=n))
            seen_key[norm] = original
            if n < 1 or n > total:
                findings.append(LC.make_finding("注释键 %d 超出源文件（共 %d 行）" % (n, total),
                                                where=rel, line=n))
                continue
            if not (start <= n <= end):
                findings.append(LC.make_finding(
                    "注释键 %d 不在本块注入范围 %d-%d 内——注入器会**静默忽略**它" % (n, start, end),
                    where=rel, line=n))
                continue
            if n in protected:
                findings.append(LC.make_finding(
                    "注释键 %d 落在不该标注的行上：%s——注入器不会标它，这条注释等于没写"
                    % (n, protected[n]), where=rel, line=n))
                continue
            anno[norm] = note
        lang = spec.get("lang") or "java"
        blocks.append(dict(spec=spec, tag=tag, rel=rel, path=path, start=start, end=end,
                           lang=lang, anno=anno, total=total))
        targets.append(dict(tag=tag, rel=rel, start=start, end=end, lang=lang))
    return blocks, targets, checked_keys


# ── 闸门同口径：密度 / ★签名 / ★反向 ──────────────────────────────────────
def emitted_block(block, src_root):
    """把"准备注入的块"渲染成与注入结果**逐字一致**的行。

    `inject_source.build_block` 会打印 "N 行不做内联标注" 这类信息行；预检自己有更好的报法，
    所以这里把它重定向掉，避免预检输出被注入器的提示刷屏。"""
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        fence, _src_lines = INJ.build_block(src_root, block["rel"], block["start"], block["end"],
                                            block["anno"], block["lang"])
    block["inject_notes"] = [l for l in buf.getvalue().split("\n") if l.strip()]
    return fence[1:-1]


def gate_block_tuples(blocks, src_root):
    """包成 gate 的块元组；首字段用序号（仅作报告用标识），并返回序号 → 计划块 的映射。"""
    tuples, index = [], {}
    for i, b in enumerate(blocks):
        body = emitted_block(b, src_root)
        tuples.append((i + 1, b["lang"], body, b["tag"], "## ⑥ 逐件讲解", b["tag"], [], ""))
        index[i + 1] = b
    return tuples, index


def key_line_flags(block):
    """按闸门口径标出块内窗口的每个关键行 (行号, 行内容, 是否已有关键注释, 该行是否纯注释行)。"""
    lines = INJ.read_lines(block["path"])
    window = lines[block["start"] - 1:block["end"]]
    tb = G.mark_text_block_lines(window)
    in_lic, seen_pkg = False, False
    out = []
    for off, ln in enumerate(window):
        code, _ = G.strip_anno(ln)
        if code.strip().startswith(("package ", "import ")):
            seen_pkg = True
        if G.LICENSE_HINT.search(code):
            in_lic = True
        if in_lic and "*/" in code:
            in_lic = False
        if seen_pkg:
            in_lic = False
        if not G.is_key_line(ln, in_lic, tb[off]):
            continue
        n = block["start"] + off
        out.append((n, ln, str(n) in block["anno"] or G.has_cjk_comment(ln),
                    bool(G.CMT_LINE.match(code.strip()))))
    return out


def suggest_lines(block, threshold=8, limit=3):
    """按闸门口径算出**最长无注释连段**，并优先给代码行候选（注释行只能算降级候选）。

    为什么要挑"连段中间的行"：一个 10 行的连段，在中间补 1 条注释即裂成 5+4 两段（都 <8），
    在首尾补则可能留下 9 行连段又得再补一次——补注位置直接决定要补几条。
    """
    flags = key_line_flags(block)
    runs, cur, run_start = [], 0, None
    for n, _ln, ok, _cmt in flags:
        if ok:
            if cur >= threshold:
                runs.append((run_start, prev_n, cur))
            cur, run_start = 0, None
        else:
            if cur == 0:
                run_start = n
            cur += 1
        prev_n = n
    if cur >= threshold:
        runs.append((run_start, prev_n, cur))
    if not runs:
        return [], len(flags)
    runs.sort(key=lambda r: -r[2])
    picks = []
    for a, b, _n in runs:
        seg = [f for f in flags if a <= f[0] <= b and not f[2]]
        code = [f for f in seg if not f[3]]
        pool = code or seg
        mid = len(pool) // 2
        for f in (pool[mid:mid + limit] + pool[:mid]):
            if f[0] not in [p[0] for p in picks]:
                picks.append(f)
            if len(picks) >= limit:
                break
        if len(picks) >= limit:
            break
    return [(n, ln.strip()[:64]) for n, ln, _ok, _c in picks], len(flags)


def run_gate_style_checks(blocks, src_root):
    """用 gate 的同一套函数算密度 / ★签名 / ★反向。返回 (checks, notes)。"""
    G.ROOT = os.path.abspath(src_root)
    by_class, rev_index = G.index_sources(G.ROOT)
    tuples, index = gate_block_tuples(blocks, src_root)
    density = G.check_density(tuples, by_class, rev_index)
    sig = G.check_sig(tuples, by_class)
    reverse = G.check_reverse(tuples, [], by_class)
    notes = []

    d_findings = []
    for r in density:
        blk = index.get(r["start"])
        if blk is None or r["exempt"]:
            continue
        if r["max_run"] >= 8:
            picks, key_n = suggest_lines(blk)
            d_findings.append(LC.make_finding(
                "最长无中文注释连段 %d 行（判据 <8）——从这些候选行里挑信息量最大的补注释：%s"
                % (r["max_run"],
                   "；".join(":%d %s" % (n, t) for n, t in picks) or "（无候选：该范围几乎全是文本块/非关键行）"),
                where=blk["rel"], line=blk["start"], part_id=blk["tag"]))
        if r["comments"] < r["need"]:
            d_findings.append(LC.make_finding(
                "教学注释 %d 条 < 下限 %d 条（关键行 %d）" % (r["comments"], r["need"], r["key_lines"]),
                where=blk["rel"], line=blk["start"], part_id=blk["tag"]))

    s_findings = []
    for r in sig:
        blk = next((b for b in blocks if os.path.basename(b["rel"]) == os.path.basename(r["src"])), None)
        s_findings.append(LC.make_finding(
            "★类方法签名无注释：%s → %s（在签名行或相邻行补注释）"
            % (r["cls"], "、".join(r["missing"][:10])),
            where=r["src"], line=(blk or {}).get("start")))

    r_findings = []
    for r in reverse:
        if r["cov"] >= 0.995:
            continue
        r_findings.append(LC.make_finding(
            "★类 %s 源码行覆盖 %.1f%%（判据 ≥99.5%%）→ 缺 %d 行，样本：%s"
            % (r["cls"], r["cov"] * 100, r["miss"], "；".join(s[:50] for s in r["samples"][:3])),
            where=r.get("src")))

    java_n = sum(1 for b in blocks if (b["lang"] or "").lower() == "java")
    star_n = len(G.star_classes(tuples, by_class))
    checks = []
    if java_n and density:
        checks.append(LC.make_check("P-DENSITY", LC.FAIL if d_findings else LC.PASS,
                                    checked=len(density), findings=d_findings,
                                    note="与 gate_lecture.check_density 同口径；%d 个 java 块" % java_n))
    else:
        checks.append(LC.make_check("P-DENSITY", LC.NOT_CHECKED, checked=0,
                                    note=("本批计划里没有 java 块" if not java_n else
                                          "java 块都不足 5 行或没有关键行 → 密度判据不适用")
                                         + "（记 NOT_CHECKED，不当成通过）"))
    if star_n:
        checks.append(LC.make_check("P-SIG", LC.FAIL if s_findings else LC.PASS,
                                    checked=star_n, findings=s_findings,
                                    note="★类方法签名按整类、跨块判定（与闸门 ③c 同口径）"))
        checks.append(LC.make_check("P-REVERSE", LC.FAIL if r_findings else LC.PASS,
                                    checked=len(reverse), findings=r_findings,
                                    note="注入前先算 ★ 类源码行覆盖，避免写到一半才发现整段漏行"))
    else:
        checks.append(LC.make_check("P-SIG", LC.NOT_CHECKED, checked=0,
                                    note="本批没有 ★ 类块 → 签名判据不适用（写 NOT_CHECKED，不写 PASS）"))
        checks.append(LC.make_check("P-REVERSE", LC.NOT_CHECKED, checked=0,
                                    note="本批没有 ★ 类块 → 反向覆盖判据不适用"))
    return checks, notes


# ── Python 与教学片段 ─────────────────────────────────────────────────────
def python_checks(blocks):
    py_blocks = [b for b in blocks if (b["lang"] or "").lower() in {"python", "py"}]
    if not py_blocks:
        return [LC.make_check("P-PY", LC.NOT_CHECKED, checked=0, note="本批计划里没有 Python 块")]
    findings, unannotatable, compiled = [], 0, 0
    for b in py_blocks:
        protected = protected_lines(b["path"], b["lang"])
        unannotatable += len([n for n in protected if b["start"] <= n <= b["end"]])
        whole_file = b["start"] == 1 and b["end"] >= b["total"]
        if whole_file:
            src = "\n".join(INJ.read_lines(b["path"])[b["start"] - 1:b["end"]])
            try:
                compile(src, os.path.basename(b["rel"]), "exec")
                compiled += 1
            except SyntaxError as exc:
                findings.append(LC.make_finding("Python 源码语法错误：%s" % exc.msg,
                                                where=b["rel"], line=exc.lineno))
    status = LC.FAIL if findings else LC.REPORT
    note = ("Python 块 %d 个；%d 行因语法限制不会被标注（正常，改用块外解释）；"
            "整文件块 %d 个通过内存 compile()（不写 .pyc、不污染宿主项目）；"
            "Python 的密度/行号为报告档（契约 S24），故本项整体记 REPORT" %
            (len(py_blocks), unannotatable, compiled))
    return [LC.make_check("P-PY", status, checked=len(py_blocks), findings=findings, note=note)]


def extract_slots(text_or_path):
    """读出讲解/骨架里的源码槽位标记（Phase 3 的稳定寻址）。"""
    text = io.open(text_or_path, encoding="utf-8").read() if os.path.isfile(text_or_path) else text_or_path
    out = []
    for m in SLOT_RE.finditer(text):
        attrs = dict(re.findall(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"', m.group(1)))
        attrs["at"] = text[:m.start()].count("\n") + 1
        out.append(attrs)
    return out


def check_addressing(plan, lecture, findings):
    _lines, blocks = INJ.parse(lecture)
    slots = extract_slots(lecture)
    checked = 0
    for spec in plan.get("blocks", []):
        if spec.get("slot"):
            checked += 1
            hits = [s for s in slots if s.get("id") == spec["slot"]]
            if len(hits) != 1:
                findings.append(LC.make_finding(
                    "槽位 %r 命中 %d 处（应为 1）——槽位 ID 是块身份，重名/落空都必须先修"
                    % (spec["slot"], len(hits))))
            continue
        anchor = spec.get("anchor")
        if not anchor:
            continue
        checked += 1
        lang = spec.get("lang", "java")
        hits = [k for k, b in enumerate(blocks)
                if anchor in b[3] and b[1] == lang
                and (not spec.get("contains") or spec["contains"] in "\n".join(b[2]))]
        if len(hits) != 1:
            findings.append(LC.make_finding(
                "anchor %r%s 命中 %d 个 %s 块（应为 1）→ 候选小节：%s"
                % (anchor, (" + contains %r" % spec["contains"]) if spec.get("contains") else "",
                   len(hits), lang, [blocks[k][3].strip()[:40] for k in hits] or ["（无）"])))
    return checked


def snippet_blocks_from_lecture(lecture):
    """取【怎么用】/【怎么接】/【扩展步骤】标记之下的代码块（教学合成片段）。"""
    lines = INJ.read_lines(lecture)
    _all, parsed = INJ.parse(lecture)
    marks = tuple(G.USE_MARKS) + tuple(G.WIRE_MARKS) + ("【扩展步骤】",)
    out = []
    for start, lang, body, _title in parsed:
        marker = None
        for j in range(start - 1, -1, -1):
            if lines[j].startswith("#"):
                break
            if any(m in lines[j] for m in marks):
                marker = lines[j].strip()[:40]
                break
        if marker:
            out.append(dict(start=start + 1, lang=lang, body=body, marker=marker))
    return out


def java_class_body(src_text, cls):
    m = re.search(r"\bclass\s+%s\b[^{]*\{" % re.escape(cls), src_text)
    if not m:
        return None
    depth, i, src_end = 0, m.end() - 1, len(src_text)
    while i < src_end:
        if src_text[i] == "{":
            depth += 1
        elif src_text[i] == "}":
            depth -= 1
            if depth == 0:
                return src_text[m.end():i]
        i += 1
    return None


def parse_java_constructor(src_text, cls):
    """该类的构造器参数类型列表；多个/零个构造器或解析不出 → None（标人工审读）。"""
    body = java_class_body(src_text, cls)
    if body is None:
        return None
    ctors = []
    for cm in re.finditer(r"(?:public|protected|private)?\s*%s\s*\(([^)]*)\)\s*\{" % re.escape(cls), body):
        params = [p.strip() for p in cm.group(1).split(",") if p.strip()]
        types = []
        for p in params:
            toks = p.replace("final ", "").split()
            types.append(toks[0] if len(toks) >= 2 else "")
        ctors.append(types)
    return ctors[0] if len(ctors) == 1 else None


def infer_arg_type(arg):
    a = arg.strip()
    if re.match(r'^".*"$', a) or re.match(r"^'.*'$", a):
        return "String"
    if re.match(r"^-?\d+[lL]$", a):
        return "long"
    if re.match(r"^-?\d+\.\d+[fFdD]?$", a):
        return "double"
    if re.match(r"^-?\d+$", a):
        return "int"
    if a in ("true", "false"):
        return "boolean"
    m = re.match(r"^new\s+([A-Z][A-Za-z0-9_]*)\s*\(", a)
    if m:
        return m.group(1)
    m = re.match(r"^([A-Z][A-Za-z0-9_]*)\.", a)
    if m:
        return m.group(1)
    return None


TYPE_COMPAT = {"int": {"long", "Integer", "Long"}, "long": {"Long"}, "double": {"Double", "float"},
               "float": {"Float"}, "boolean": {"Boolean"}}


def split_top_level_args(inner):
    out, depth, cur, quote = [], 0, "", None
    for ch in inner:
        if quote:
            cur += ch
            if ch == quote:
                quote = None
            continue
        if ch in "\"'":
            quote = ch
            cur += ch
            continue
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur)
    return out


def check_snippets(lecture, by_class, findings, manual):
    snippets = snippet_blocks_from_lecture(lecture)
    base = os.path.basename(lecture)
    for sn in snippets:
        text = "\n".join(sn["body"])
        lang = (sn["lang"] or "").lower()
        if lang in {"python", "py"}:
            try:
                compile(text, "snippet", "exec")
            except SyntaxError as exc:
                findings.append(LC.make_finding("教学片段语法错误（%s）：%s" % (sn["marker"], exc.msg),
                                                where=base, line=sn["start"]))
            continue
        if lang != "java":
            continue
        if text.count("{") != text.count("}"):
            findings.append(LC.make_finding(
                "教学片段花括号不配对（%d 开 / %d 闭）——照抄会编译不过" % (text.count("{"), text.count("}")),
                where=base, line=sn["start"]))
        for cm in re.finditer(r"\bnew\s+([A-Z][A-Za-z0-9_]*)\s*\(", text):
            cls = cm.group(1)
            if cls in SNIPPET_WHITELIST or by_class.get(cls):
                continue
            manual.append(LC.make_finding(
                "片段里出现无法核实的类型 `new %s(...)`（本仓无此类，也不在 JDK/常用库白名单）" % cls,
                where=base, line=sn["start"], severity=LC.REPORT))
        for cm in re.finditer(r"new\s+([A-Z][A-Za-z0-9_]*)\s*\(([^;]*?)\)\s*;", text):
            cls, inner = cm.group(1), cm.group(2)
            cands = by_class.get(cls)
            if not cands:
                continue
            params = parse_java_constructor("\n".join(INJ.read_lines(cands[0])), cls)
            if params is None:
                manual.append(LC.make_finding(
                    "`new %s(...)` 的构造器无法唯一定位（多个/零个/解析不出签名）→ 参数个数与顺序需人工对照源码"
                    % cls, where=base, line=sn["start"], severity=LC.REPORT))
                continue
            args = [x for x in split_top_level_args(inner) if x.strip()]
            if len(args) != len(params):
                findings.append(LC.make_finding(
                    "`new %s(...)` 传了 %d 个实参，源码构造器要 %d 个（%s）——照抄编译不过"
                    % (cls, len(args), len(params), ", ".join(params)), where=base, line=sn["start"]))
                continue
            kinds = [infer_arg_type(x) for x in args]
            for i, (k, p) in enumerate(zip(kinds, params)):
                if not k or k == p or k in TYPE_COMPAT.get(p, set()) or p in TYPE_COMPAT.get(k, set()):
                    continue
                others = [j + 1 for j, q in enumerate(params)
                          if q == k or k in TYPE_COMPAT.get(q, set()) or q in TYPE_COMPAT.get(k, set())]
                if others:
                    findings.append(LC.make_finding(
                        "`new %s(...)` 第 %d 个实参推断类型是 %s，落在形参 %s 上；第 %s 位才是 %s"
                        "——**疑似参数顺序错误**（按源码签名核对）"
                        % (cls, i + 1, k, p, "/".join(str(o) for o in others), k),
                        where=base, line=sn["start"]))
                else:
                    manual.append(LC.make_finding(
                        "`new %s(...)` 第 %d 个实参推断类型 %s 与形参 %s 不符 → 人工确认"
                        % (cls, i + 1, k, p), where=base, line=sn["start"], severity=LC.REPORT))
        if "new " not in text:
            manual.append(LC.make_finding(
                "片段（%s）里没有可校验的构造调用 → 只能人工审读" % sn["marker"],
                where=base, line=sn["start"], severity=LC.REPORT))
    return len(snippets)


def scope_checklist():
    tpl_sections = [l[3:].strip() for l in NB.skeleton_lines(notes=[]) if l.startswith("## ")]
    contract = LC.load_contract()
    hints = [e["id"] + "：" + e["stmt"][:56] for e in contract["entries"]
             if e["id"] in ("A2", "A3", "A4", "S4", "S8", "S12", "S20")]
    return {
        "sections": tpl_sections,
        "vib_items": ["真实需求", "现状勘察", "方案比较", "增量实现", "多轮提示词", "产出后审查",
                      "验证反馈循环", "最终沉淀"],
        "evidence_levels": ["【事实-源码】", "【实测】", "【事实-历史】", "【外部事实】", "【推断】"],
        "naming": ("阶段N-<主题>/批次M-<一句话主题>（<本批核心类★>）.md；总长 ≤40 字；"
                   "禁 Windows 非法字符 \\ / : * ? \" < > |"),
        "contract_hints": hints,
    }


def main():
    LC.configure_stdio()                # stdout 被重定向时按 GBK 编码会崩在打印上
    ap = argparse.ArgumentParser(description="开批预检：注入/写作之前把机器能判的问题一次报出来")
    ap.add_argument("--src", required=True, help="宿主仓库根目录")
    ap.add_argument("--plan", required=True, help="注释计划 JSON（与 inject_source 同一个 plan）")
    ap.add_argument("--manifest", action="append",
                    help="本批源文件清单 JSON（**可多次传**，会合并；P-HASH 要求清单覆盖注释计划里的"
                         "全部源文件，缺件直接 FAIL）")
    ap.add_argument("--lecture", help="已组装/已注入的讲解（可选：查寻址唯一性与教学片段）")
    ap.add_argument("--json", help="把结构化结果写到该路径")
    a = ap.parse_args()

    src_root = os.path.abspath(a.src)
    if not os.path.isdir(src_root):
        raise SystemExit("[ABORT] --src 不是目录：%s" % src_root)
    plan = json.load(io.open(a.plan, encoding="utf-8"))
    lecture = None
    if a.lecture:
        lecture = a.lecture if os.path.isabs(a.lecture) else os.path.join(src_root, a.lecture)
        if not os.path.isfile(lecture):
            raise SystemExit("[ABORT] 讲解文件不存在：%s" % lecture)

    checks = []
    plan_findings = []
    manifest_fp = None
    blocks, targets, checked_keys = check_plan(plan, src_root, plan_findings)
    checks.append(LC.make_check("P-PLAN", LC.FAIL if plan_findings else LC.PASS,
                                checked=len(plan.get("blocks", [])) or 0, findings=plan_findings,
                                note="核验 %d 个块 / %d 条注释键" % (len(blocks), checked_keys)))

    if a.manifest:
        # ① 多份清单合并（批次49 实录：4 个源文件分别 prepare 出 4 份清单，只传其中一份 → P-HASH 只核了 1 个文件）；
        # ② **覆盖性**：清单必须覆盖注释计划用到的**全部**源文件，缺件直接 FAIL——
        #    "清单里有的都合格"不等于"本批源码都被钉住了"，这正是漏检的形态（Goodhart）。
        files, roots, names = {}, [], []
        for mp in a.manifest:
            man = json.load(io.open(mp, encoding="utf-8"))
            names.append(os.path.basename(mp))
            if man.get("source_root"):
                roots.append(man["source_root"])
            for rel, meta in (man.get("files") or {}).items():
                key = rel.replace("\\", "/").lstrip("./")
                files.setdefault(key, (os.path.basename(mp), meta))
        # 结构化结果里的清单指纹：一份 = 文件 sha256；多份 = 各份「名字 + sha256」拼接后的 sha256（确定性）
        if len(a.manifest) == 1:
            manifest_fp = LC.sha256_file(a.manifest[0])
        else:
            payload = "\n".join("%s\t%s" % (os.path.basename(mp), LC.sha256_file(mp) or "?")
                               for mp in a.manifest)
            manifest_fp = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        plan_rels = sorted({(b.get("rel") or "").replace("\\", "/").lstrip("./")
                            for b in blocks if b.get("rel")})
        missing = [r for r in plan_rels if r not in files]
        bad, checked = [], 0
        for rel in missing:
            bad.append(LC.make_finding(
                "清单**没覆盖**注释计划里的源文件：%s（%d 份清单合计 %d 个文件 / 本批计划用了 %d 个）"
                "——缺件的清单不能当通过：把本批全部 --file 一次 `batch_manifest.py prepare` 成一份清单，"
                "或把多份清单都 `--manifest` 传进来" % (rel, len(names), len(files), len(plan_rels)),
                where=rel))
        for rel in plan_rels:
            if rel not in files:
                continue
            checked += 1
            got = LC.sha256_file(os.path.join(src_root, rel))
            if got is None:
                bad.append(LC.make_finding("清单里的源文件不存在：%s" % rel, where=rel))
            elif got != files[rel][1].get("sha256"):
                bad.append(LC.make_finding(
                    "源文件已变化（hash 不一致，清单来自 %s）：%s" % (files[rel][0], rel), where=rel))
        extra = sorted(set(files) - set(plan_rels))
        note_bits = []
        if len(names) > 1:
            note_bits.append("合并 %d 份清单" % len(names))
        note_bits.append("覆盖计划源文件 %d/%d" % (len(plan_rels) - len(missing), len(plan_rels)))
        if extra:
            note_bits.append("清单另有 %d 个不在本批计划里的文件（不参与判定）：%s"
                             % (len(extra), "、".join(extra[:3])))
        if roots and any(os.path.abspath(r) != src_root for r in roots):
            note_bits.append("清单 source_root=%s 与 --src=%s 不同 → 按**相对路径**比对 hash"
                             "（夹具/搬迁场景常见）；请确认这确实是同一份源码"
                             % ("、".join(sorted(set(roots))), src_root))
        if not plan_rels:
            checks.append(LC.make_check("P-HASH", LC.NOT_CHECKED, checked=0,
                                        note="注释计划里没有可核对的源文件 → 清单无处可比对（不能当通过）"))
        elif not checked:
            checks.append(LC.make_check("P-HASH", LC.NOT_CHECKED, checked=0, findings=bad,
                                        note="清单没有覆盖本批任何一个源文件——不能当通过"))
        else:
            checks.append(LC.make_check("P-HASH", LC.FAIL if bad else LC.PASS,
                                        checked=checked, findings=bad, note="；".join(note_bits)))

    gate_checks, _notes = run_gate_style_checks(blocks, src_root)
    checks.extend(gate_checks)
    checks.extend(python_checks(blocks))

    if lecture:
        addr_f = []
        addr_n = check_addressing(plan, lecture, addr_f)
        checks.append(LC.make_check("P-ADDR", LC.FAIL if addr_f else LC.PASS, checked=addr_n,
                                    findings=addr_f,
                                    note="anchor/contains 或槽位必须唯一命中（零命中与重名都 fail closed）"))
        by_class, _rev = G.index_sources(src_root)
        snip_f, snip_manual = [], []
        snip_n = check_snippets(lecture, by_class, snip_f, snip_manual)
        if snip_n:
            checks.append(LC.make_check("P-SNIP", LC.FAIL if snip_f else LC.REPORT, checked=snip_n,
                                        findings=snip_f + snip_manual,
                                        note="可静态判定的（语法/花括号/构造参数个数与明显类型错位）报 FAIL；"
                                             "参数顺序与第三方 API 行为标 manual_review，不声称可编译"))
        else:
            checks.append(LC.make_check("P-SNIP", LC.NOT_CHECKED, checked=0,
                                        note="讲解里没有【怎么用】/【怎么接】片段 → 无可校验对象"))

    scope = scope_checklist()
    checks.append(LC.make_check("P-SCOPE", LC.REPORT, checked=len(scope["sections"]),
                                note="17 节清单 / ⑫ 八条 / 证据等级随结果给出，不必把整份细则灌进上下文"))

    result = LC.make_result("batch_preflight.py", checks,
                            lecture_sha256=LC.sha256_file(lecture) if lecture else None,
                            source_manifest_sha256=manifest_fp,
                            source_root=src_root,
                            extra={"scope": scope, "targets": targets})
    print(LC.render(result))
    print("\n本批适用清单（开写前对一次，不必重读整份细则）：")
    print("  17 节：%s" % "｜".join(s.split("（")[0] for s in scope["sections"]))
    print("  ⑫ 八条：%s" % "、".join(scope["vib_items"]))
    print("  证据等级：%s" % "、".join(scope["evidence_levels"]))
    print("  文件名：%s" % scope["naming"])
    if a.json:
        io.open(a.json, "w", encoding="utf-8", newline="").write(
            json.dumps(result, ensure_ascii=False, indent=1) + "\n")
        print("\n→ 结构化结果已写 %s" % a.json)
    if not result["pass"]:
        print("\n预检 FAIL：以上每条都指向具体文件与行号，改注释计划后重跑即可"
              "（**不要靠在闸门与注入之间反复试错**）")
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
