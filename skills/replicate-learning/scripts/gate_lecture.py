#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate_lecture.py —— 批次讲解「内容真实性 + 注释密度 + 行号一致性 + 用法与接入」闸门（SKILL §6.4 C 组）

判据版本：见下方 GATE_VERSION。**任何判据变更（新增/收紧/放宽检查项或门槛）都必须**：
  ① 递增 GATE_VERSION；② 在 SKILL §6.6 记一条变更（版本 / 改了什么 / 影响哪些批次 / 存量工单）；
  ③ 跑回归集确认"不该变的批次判定不变"。道理：判据一改，存量批次会集体变红或变绿（实测两次：
  加快照机制后 9 批 77 行由 FAIL 转为"源码演进"；加 ⑤ 后阶段8批次4 由全绿转红），没有版本号就查不出"这批是按哪版判的"。
改技能文档本身的 DoD（改完必须跑 `scripts/skill_selfcheck.py` 全绿 → 回归集判定不变 → 同步四处副本）见 SKILL §6.6。

用法：
    python gate_lecture.py <批次讲解.md> --src <源码根目录>
        [--snapshot <commit>]   # 不传则自动读批头「源码依据：commit <sha>」
        [--json out.json] [--verbose]

五项检查（任一不过 = 退出码 1）：
  ① 正向保真度：讲解里每个 java 代码块（凭类名归属源文件）的每一行代码，
      必须能在「当前源码树」或「本批声明的源码快照」里逐字找到。
      - 只在当前树命中 → 正常；
      - 只在快照命中 → **源码演进**（本批之后该文件被重写）：不计 FAIL，单独打印漂移量；
      - 两处都没有 → **候选编造/改写**：计 FAIL（这是本检查真正要抓的东西）。
      - 批头未声明快照时，退回"只比当前树"，并在报告里提示"无法区分演进与编造"。
  ② 反向完整度：★类源文件的每一条有效行，必须出现在讲解里（**全批所有块并集**）。门槛 99.5%。
      —— 抓"摘录式贴码 / 整节缺失"。★ 记录在父标题（如 `### 6.5 Xxx★`）同样生效。
      2.13：★ 块的**类名归属**加了标题链兜底 + 同类去重（血证 H23）——原实现只认"块自身含类声明"，
      而 ⑥ 要求 ★ 类**按职责段拆讲**（段1/段2…），拆分后没有任何单块含类声明 → 本项静默跳过、
      打印"0 个★类"并 PASS（**真空通过**）。实测全库 60 份批次里 6 份命中，其中 4 份一个类都没查过。
  ③ 注释密度：按 §6.1.1「关键行」口径算
      (a) 无注释连段 <8 行  (b) 教学注释条数 ≥ 关键行数÷12  (c) ★类每个方法签名行或相邻行有注释
      —— 抓"只贴 `// :Lnn` 裸行号、没有一句讲解"。
  ④ 行号一致性（2026-09-15 新增）：`// :Lnn` 标了行号、且该行内容能在源文件里**唯一定位**时，
      nn 必须就是那一行。指错行号 = FAIL（比少注释更误导初学者）。
  ⑤ 用法与接入（2026-09-16 新增）：讲清"这份代码怎么被用、怎么被接上"，抓
      "每行都讲了、读者仍不知道怎么用"（§6.4 ⑥ 第 5 层要求）：
      (a) 每个 6.x 逐件小节必须有 **【怎么用】**（调用现场：谁在哪个类哪个方法哪一行调它、传什么形态拿回什么）；
      (b) 每个 6.x 逐件小节必须有 **【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）；
      (c) 件内代码块出现 `interface` / `abstract class` 的，必须有 **【怎么接】**（实现/继承要覆写什么、
          最小可编译实现、注册装配路径、扩展步骤、类型陷阱）；
      (d) 批级必须有 **⑦.5 扩展与接入路径**（含 ≥3 条编号步骤）。
      2.14：**件段不得越过一级节标题**——⑥ 之后的小节（⑧ 穿透卡 / ⑨ No-Framework / ⑩ 反例）
      里的手写 `interface` 骨架与【怎么接】标记不再被算进"最后一个 6.x 件"（血证 H24）。
      标题带【历史版本示例】的小节免检（旧版代码只做快照核验，不要求讲用法）。

免检小节：标题含 手写 / No-Framework / 不用框架 / 等价实现 / 反例 / 对照 的代码块不参与 ①②，
但会被统计并打印（防止借"反例"之名夹带未核实代码）。
用法片段：位于 `**【怎么用】/【怎么接】/【扩展步骤】/【上下游】` 标记之下的代码块属**教学合成片段**
（照抄式调用示例、实现骨架），不参与 ①②③④；**但带行号标注的块不豁免**——标了行号即声明"这是源码原文"，
必须逐字核验。行号标注**两种格式都算**：`// :Lnn`（现行）与 `// :N`（已作废但存量仍在用）。
历史版本块：小节标题含「历史版本 / 历史快照 / 已被阶段」的块，**必须**用快照核验——块内每行都要在
快照里找到（没声明快照 = 直接 FAIL），这样"标历史版本"就不能当免检后门用。
"""
import io
import os
import re
import sys
import json
import math
import tarfile
import subprocess
import collections

GATE_VERSION = "2.14"    # 2.14：⑤ 的**件段不得越过一级节标题**（原实现让最后一个 6.x 件的段延伸到 EOF，
                         #       把 ⑧//⑩ 里的手写 interface 与【怎么接】算到它头上：10 件 iface 误判 / 6 件 wire 误判，血证 H24）
                         # 2.13：② ★ 类的类名归属加「★ 标题链兜底」+ 同类去重（原实现只认块内类声明，
                         #       ★ 类按职责段拆讲时 ② 静默跳过 → 真空通过，血证 H23）
                         # 2.12：③ 注释密度的 need 加 key_n 上限（原式对"关键行<5 的 ★ 块"不可满足，血证 H22）
                         # 2.5：免检护栏认两种行号格式（`// :Lnn` 与作废的 `// :N`），堵住"标了行号却能免检"的漏洞
                         # 2.6：⓪ 增围栏**配对**体检（原只查奇偶；配对错位会让整段正文被吞进代码块却仍 PASS）
                         # 2.7：⑤ 增**位置**判据（【怎么用】必须在「逐行要点表」之后、件内 `---` 之前，否则读者会把它读成下一节）
                         # 2.8：新增 ⑥ **散文符号真实性**（正文里的 文件:行 引用 / 件标题声明的 .java / 本仓类.方法；
                         #      反引号符号走白名单+待确认清单。血证 H16：① 只管代码块，正文提到不存在的东西它一个字都不查）
                         # 2.9：⓪ 的占位判据扩到**含中文的 `__占位__`**（原只认 TODO/FIXME/CONT-/<<<SRC:；
                         #      血证 H18：填空白骨架能一路全绿——"还没写"与"已写好"在闸门眼里没有区别）
                         # 2.10：⑯ 段是否写明当前判据版本 → **报告项**（不计 FAIL）。实测只有 6/78 份写明，
                         #      直接判 FAIL 会让"绿"清零；先靠 sync_gate_result.py 补存量，再升 FAIL（血证 H15）

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
HIST = re.compile(r"(【历史版本|历史版本示例|历史快照|已被阶段\s*\d+)", re.I)
CJK_LANGS = {"java", "sql", "yaml", "yml", "xml", "properties", "lua", "st", "json"}
SKIP_DIRS = {"target", "node_modules", ".git", ".tmp_audit", ".tmp_lecture", ".workbuddy"}
SPLIT_DECL = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Z][A-Za-z0-9_]*)")
SNAP_DECL = re.compile(r"(?:源码依据|源码快照|snapshot)[^\n]{0,40}?([0-9a-f]{7,40})")
# 2.9 占位符（含中文的 `__xxx__`）：只扫围栏内。**要求占位里含汉字**，这样 Python 的 `__init__`
# 这类 dunder 与 `__main__` 不会误报（全库实测：78 份讲解 + 2 份样例 = 0 处，只有模板自身命中）
PLACEHOLDER = re.compile(r"__[^_\n]*[\u4e00-\u9fff][^_\n]*__")

# ── 快照状态（进程级） ────────────────────────────────────────────────────
SNAPSHOT = None          # commit sha
SNAP_TAR = None          # git archive 出来的 tar 字节
SNAP_UNION = None        # 快照里所有 .java 的归一化代码行集合
_snap_file_cache = {}


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
def heading_chain(lines, start):
    """从 start 往上取**真正的祖先标题链**（外层 → 最近）。
    只收"层级严格更高"的标题：同级标题（如上一个 `### 6.5 Xxx★`）不属于本块的祖先，
    否则 ★ 会串到别的节去（2026-09-15 修）。"""
    chain, min_lv = [], 7
    for i in range(start - 2, -1, -1):
        m = re.match(r"^(#{2,5}) (.*)$", lines[i])
        if m:
            lv = len(m.group(1))
            if lv < min_lv:
                chain.append(m.group(2).strip())
                min_lv = lv
        if lines[i].startswith("# "):
            break
    chain.reverse()
    return chain


def parse_blocks(path):
    """返回 (全部行, [(起始行号, 语言, 行列表, 所属小节标题, 所属一级节标题, 类名线索, 标题链, 用法标记)])"""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    out, cur, lang, start = [], None, None, 0
    hint, hint_cur = {}, ""
    for i, l in enumerate(lines):
        if re.match(r"^#{2,5} ", l):
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", l)
                   if not re.fullmatch(r"L\d+", w)]
            if ids:
                hint_cur = " ".join(ids)
        hint[i + 1] = hint_cur
    # 用法/接入标记：块前最近的 `**【怎么用】**` 之类粗体标记；换标题即清空。
    # 命中标记的块视为**教学合成片段**（照抄式用法/实现骨架），免 ① 保真核验——
    # 但带 `// :Lnn` 行号标注的块例外（标了行号即声明"这是源码原文"，必须核验）。
    mk, mk_cur = {}, ""
    for i, l in enumerate(lines):
        if re.match(r"^#{2,5} ", l):
            mk_cur = ""
        elif re.match(r"^\*\*(【怎么用】|【怎么接】|【扩展步骤】|【上下游】)", l):
            mk_cur = l.strip()[:24]
        mk[i + 1] = mk_cur
    for i, l in enumerate(lines):
        m = re.match(r"^(\s*)(`{3,})\s*([A-Za-z0-9_+-]*)\s*$", l)
        if cur is None:
            if m:
                cur, lang, start = [], (m.group(3) or "").lower(), i + 2
        else:
            if re.match(r"^\s*`{3,}\s*$", l):
                s3 = sect_of(lines, start, (3, 4, 5))
                s2 = sect_of(lines, start, (2,))
                out.append((start, lang, cur, s3 if s3 != "?" else s2, s2,
                            hint.get(start, ""), heading_chain(lines, start), mk.get(start, "")))
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


def line_variants(n):
    """讲解行的等价形态：原样 / 去掉行尾注释（教材旧格式形如 `代码  // 中文说明`）"""
    yield n
    head = n.split("//")[0].strip()
    if head and head != n:
        yield head


def line_ok_in(path, n):
    """该行是否属于源文件：先逐行比（含"去掉行尾注释"的等价形态），再退化为"去空白子串"（容忍折行）"""
    sset = src_code_set(path)
    for v in line_variants(n):
        if v in sset:
            return True
        ns = re.sub(r"\s+", "", v)
        if len(ns) >= 8 and ns in _ns(path):
            return True
    return False


def attribute(code, classes, by_class, rev):
    """返回 (最佳源文件, 真·不命中行列表)；先按类名，再按内容回退"""
    pool_files = []
    for c in classes:
        pool_files += by_class.get(c, [])
    if not pool_files:
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


# ── 快照（本批声明的源码 commit） ─────────────────────────────────────────
def load_snapshot(sha):
    """把该 commit 的所有 .java 读成一个 tar 与"代码行并集"，用于区分「源码演进」与「编造」"""
    global SNAPSHOT, SNAP_TAR, SNAP_UNION
    data = subprocess.run(["git", "archive", "--format=tar", sha],
                          cwd=ROOT, capture_output=True).stdout
    if not data:
        SNAPSHOT, SNAP_TAR, SNAP_UNION = sha, None, None
        return False
    union = set()
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.endswith(".java"):
                continue
            for l in tf.extractfile(m).read().decode("utf-8", "replace").split("\n"):
                n = norm_code(l)
                if n and not CMT_LINE.match(n):
                    union.add(n)
    SNAPSHOT, SNAP_TAR, SNAP_UNION = sha, data, union
    return True


def resolve_snapshot(lines, explicit=None):
    """快照来源：命令行 --snapshot > 批头声明「源码依据：commit <sha>」"""
    if explicit:
        return explicit, "命令行"
    head = "\n".join(lines[:80])
    m = SNAP_DECL.search(head)
    return (m.group(1), "批头声明") if m else (None, None)


def snap_file_lines(rel):
    """快照里某个文件的代码行（按需从 tar 取，带缓存）"""
    if rel in _snap_file_cache:
        return _snap_file_cache[rel]
    got = None
    if SNAP_TAR:
        want = rel.replace("\\", "/")
        with tarfile.open(fileobj=io.BytesIO(SNAP_TAR)) as tf:
            for m in tf.getmembers():
                if m.isfile() and m.name == want:
                    got = tf.extractfile(m).read().decode("utf-8", "replace").split("\n")
                    break
    _snap_file_cache[rel] = got
    return got


# ── 检查 ①：正向保真度 ───────────────────────────────────────────────────
L_ANNO = re.compile(r"//\s*:L?\d+")   # 两种格式都算"标了行号"：`// :Lnn`（现行）与 `// :N`（作废但存量 36 文件/7315 处在用）。
                                      # 2.5 修：此前只认带 L 的格式，旧格式标了行号却能混进免检（护栏漏洞，实测当时 0 个块命中）


def is_exempt(sect, h2, mk="", bl=None):
    """免检判定：小节名或所属一级节名命中免检词，或属于 ⑨ No-Framework 节下的 ### 9.x，
    或块位于 `**【怎么用】/【怎么接】/【扩展步骤】/【上下游】` 标记之下（教学合成片段）。
    例外：命中标记但块内带行号标注（`// :Lnn` 或作废的 `// :N`）= 声明自己是源码原文 → 不豁免，照常核验。"""
    if EXEMPT.search(sect or "") or EXEMPT.search(h2 or ""):
        return True
    if re.match(r"^#{3,5}\s*9\.", sect or ""):
        return True
    if mk and not any(L_ANNO.search(x) for x in (bl or [])):
        return True
    return False


def is_hist(sect, chain=None):
    """历史版本块：必须用快照核验（不能当免检后门）。
    判定只看"块自身标题或任一祖先标题"是否显式声明历史版本（如【历史版本示例】/ 已被阶段N 重写）。"""
    if HIST.search(sect or ""):
        return True
    return any(HIST.search(h) for h in (chain or []))


def check_fidelity(blocks, by_class, rev):
    rows = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java":
            continue
        text = "\n".join(bl)

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
        # 快照分类：只在快照里命中 = 源码演进；两处都不在 = 候选编造
        snap_lost = None
        if lost is not None and SNAP_UNION is not None:
            snap_lost = [c for c in lost if c not in SNAP_UNION]
        hist = is_hist(sect, chain)
        rows.append(dict(start=start, sect=sect, h2=h2, lang=lang, classes=classes,
                         n_code=len(code), exempt=is_exempt(sect, h2, mk, bl), hist=hist,
                         cand=os.path.relpath(cand, ROOT) if cand else None,
                         lost=len(lost) if lost is not None else None,
                         lost_samples=(lost[:4] if lost else []),
                         snap_lost=len(snap_lost) if snap_lost is not None else None,
                         snap_lost_samples=(snap_lost[:4] if snap_lost else []),
                         evolve=(len(lost) - len(snap_lost)) if (lost is not None and snap_lost is not None) else None))
    return rows


def block_star(sect, chain):
    """该块是否算 ★ 类：块自己标题带 ★，或任意父标题带 ★（2026-09-15 修：此前只看最近标题，
    ★ 标在 `### 6.5 Xxx★` 而块在 `#### 6.5.A` 下时，② 会静默空转）"""
    return "★" in (sect or "") or any("★" in h for h in (chain or []))


# ── 检查 ②：反向完整度（★类） ────────────────────────────────────────────
def star_class_fallback(sect, hint, chain, by_class):
    """★ 块的类名归属兜底（判据 2.13，血证 H23）：块自身没有类声明时，从 **★ 标题链**里取类名。

    **为什么必须有这条兜底**：⑥ 明确要求 ★ 类**按职责段拆讲**（段 1 / 段 2 …）。拆分之后
    **没有任何单块含类声明**，而原实现写的是 `if not classes: continue` —— 于是本项静默跳过、
    打印「0 个★类」并 PASS。**这是一次真空通过，不是核验过**：读者看到 PASS，会以为
    "★ 类的每一行都被讲解覆盖了"，实际上一行都没查。

    实测（2026-09-16，全库 60 份批次文件）：6 份命中该盲区（阶段9 四批 + 阶段10批次1 +
    阶段6批次1），其中 4 份属于"有 ★ 块但一个类都没查"。补上兜底后 17/50 份转 FAIL，
    逐份人工验伪：缺失行**都是真缺口**（`@Slf4j` / 类声明 / 依赖字段 / 私有方法确实没在讲解里出现过），
    **误报 0** —— 所以这是一次"把真空变成实检"，不是收紧门槛。

    取名优先级：块自身标题 → （倒序）祖先标题链里最近一个带 ★ 的标题 → 最近含类名的标题。
    只接受 `by_class` 里真实存在的类（避免把 `Comparator` 这类 JDK 类型当成本仓类）。
    **类名长度 ≥3 即可**（`[A-Z][A-Za-z0-9_]{2,}`）：别处 `_ids` 用的是 `{3,}`（≥4 字符），
    照抄会让 `Dao` / `Rrf` / `Foo` 这类短名解析不出来 → 又退回真空通过（自检当场抓到）。
    """
    ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{2,}", sect or "") if not re.fullmatch(r"L\d+", w)]
    for h in reversed(chain or []):
        if "★" in h:
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{2,}", h)
                   if not re.fullmatch(r"L\d+", w)] + ids
    if not ids:
        ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{2,}", hint or "") if not re.fullmatch(r"L\d+", w)]
    for c in ids:
        if by_class.get(c):
            return c
    return None


def check_reverse(blocks, lines, by_class):
    """★类 = 标题（自身或任一父标题）带 ★ 的 java 代码块，**按类去重**后逐类算覆盖。

    2.13 两处改动（血证 H23）：
      ① 类名归属加 `star_class_fallback()` 兜底——★ 类按职责段拆讲时不再静默跳过；
      ② 同一 ★ 类只出一条记录：覆盖是拿**全批所有块的并集**算的（`lect_all`），
         段1/段2… 各自算一遍会得到完全相同的数字，重复行只会把"3 个★类"报成"15 个"。
    """
    rows = []
    seen_cls = set()
    lect_all = set()
    for blk in blocks:
        for x in blk[2]:
            n = norm_code(x)
            if n:
                lect_all.add(n)
    lect_ns = [re.sub(r"\s+", "", v) for v in lect_all]
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java" or not block_star(sect, chain):
            continue
        if is_exempt(sect, h2, mk, bl):
            continue          # 样例节选 / 手写版 / 用法片段等免检块不参与 ★完整性（它们本就不是整文件）
        if is_hist(sect, chain):
            continue          # 历史版本块由 ① 按快照核验，不拿当前树做反向覆盖
        classes = find_classes("\n".join(bl))
        if not classes:
            # 2.13 兜底：段拆块不含类声明时，从 ★ 标题链取类名（否则本项真空通过）
            c = star_class_fallback(sect, hint, chain, by_class)
            classes = [c] if c else []
        if not classes:
            continue
        for c in classes[:1]:
            if c in seen_cls:
                continue
            cands = by_class.get(c)
            if not cands:
                continue
            seen_cls.add(c)
            p = cands[0]
            real, miss = 0, []
            for sl in src_lines(p):
                t = norm_code(sl)
                if not t or CMT_LINE.match(t) or t.startswith(("import ", "package ")) or PUNCT_ONLY.match(t):
                    continue
                real += 1
                if t in lect_all:
                    continue
                # 容忍等价形态：折行拼接 / 行尾带教材注释
                ts = re.sub(r"\s+", "", t)
                if len(ts) >= 8 and any(ts in v for v in lect_ns):
                    continue
                miss.append(t)
            cov = (real - len(miss)) / real if real else 1.0
            rows.append(dict(cls=c, src=os.path.relpath(p, ROOT), sect=sect,
                             real=real, miss=len(miss), cov=round(cov, 4),
                             samples=miss[:3]))
    return rows


# ── 检查 ③：注释密度 ─────────────────────────────────────────────────────
SIG = re.compile(r"^\s*(?:(?:public|protected|private|static|final|synchronized|abstract|default|native)\s+)+"
                 r"[\w<>\[\],\.\?]+\s+(\w+)\s*\([^;]*\)\s*(?:throws\s+[\w\s,\.]+)?\{\s*$")


def method_names_of(path):
    """源文件里的方法名（只认"带修饰符 + 返回类型 + 名 + 参数 + {"的行；故意宽松以少误报）"""
    out = []
    for l in src_lines(path):
        c, _ = strip_anno(l)
        m = SIG.match(c)
        if m:
            out.append(m.group(1))
    return list(dict.fromkeys(out))


def check_density(blocks, by_class=None, rev=None):
    rows = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang not in CJK_LANGS or len(bl) < 5:
            continue
        exempt = is_exempt(sect, h2, mk, bl)
        in_lic, seen_pkg = False, False
        keys = []
        tb = mark_text_block_lines(bl)
        for idx, ln in enumerate(bl):
            code, _ = strip_anno(ln)
            if code.strip().startswith(("package ", "import ")):
                seen_pkg = True
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
        cmts = sum(1 for _, ok in keys if ok)
        star = block_star(sect, chain)
        # 2.12（血证 H22）：`max(5, …)` 对 ★ 块无条件取 5，而注释只能落在**关键行**上——
        # 于是"关键行 < 5 的 ★ 块"要求 5 条注释却最多只能有 key_n 条，**数学上不可满足**。
        # 实测全库 245 个 ③ 不达标块里有 27 个（11%）属于这种；用 min(key_n, …) 封顶。
        need = min(key_n, max(5, math.ceil(key_n / 12))) if star else math.ceil(key_n / 12)
        rows.append(dict(start=start, sect=sect, exempt=exempt, key_lines=key_n,
                         comments=cmts, max_run=mx, bad_runs=runs,
                         need=need, star=star))
    return rows


def star_classes(blocks, by_class):
    """本批的 ★ 类清单（自身或父标题带 ★；类名来自块内声明或标题）"""
    out = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java" or not block_star(sect, chain) or is_exempt(sect, h2, mk, bl):
            continue
        names = find_classes("\n".join(bl))
        if not names:
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", sect) if not re.fullmatch(r"L\d+", w)] or \
                  [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", hint) if not re.fullmatch(r"L\d+", w)]
            names = ids
        for c in names[:1]:
            if c not in out and by_class.get(c):
                out.append(c)
    return out


def check_sig(blocks, by_class):
    """③c ★类方法签名覆盖（**按类、跨块**判定）：★类每个方法至少有一条注释落在签名行或相邻行。
    注意是"整类"口径——★类允许拆成多个职责段块，只要全篇合起来每个方法都被讲到即可。"""
    covered = []          # [(norm_line, 下一行是否带中文注释)]
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java":
            continue
        for j, ln in enumerate(bl):
            covered.append((norm_code(ln), has_cjk_comment(ln),
                            has_cjk_comment(bl[j + 1]) if j + 1 < len(bl) else False))
    rows = []
    for c in star_classes(blocks, by_class):
        p = by_class[c][0]
        miss = []
        for nm in method_names_of(p):
            hit = any((nm + "(") in n and (ok or nxt) for n, ok, nxt in covered)
            if not hit:
                miss.append(nm)
        if miss:
            rows.append(dict(cls=c, src=os.path.relpath(p, ROOT), missing=miss))
    return rows


# ── 检查 ④：行号一致性 ───────────────────────────────────────────────────
def check_lineno(blocks, by_class, rev):
    """`// :Lnn` 的行号是否指向该行内容真正所在的行。
    只在"该行内容能在源文件里唯一定位"时才判定（折行/压缩行、重复行、公共符号行跳过）。"""
    rows = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java" or is_exempt(sect, h2, mk, bl):
            continue
        classes = SPLIT_DECL.findall("\n".join(bl))
        if not classes:
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", sect) if not re.fullmatch(r"L\d+", w)]
            if not ids:
                ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", hint) if not re.fullmatch(r"L\d+", w)]
            classes = ids
        code = [norm_code(x) for x in bl]
        code = [c for c in code if c and not CMT_LINE.match(c)]
        if len(code) < 5:
            continue
        cand, _ = attribute(code, classes, by_class, rev)
        if cand is None:
            continue
        base = None
        if is_hist(sect, chain) and SNAPSHOT:
            base = snap_file_lines(os.path.relpath(cand, ROOT))
        src = base if base is not None else src_lines(cand)
        idx = collections.defaultdict(list)
        for i, l in enumerate(src):
            n = norm_code(l)
            if n:
                idx[n].append(i + 1)
        bad = []
        checked = 0
        for x in bl:
            m = ANNO.search(x)
            if not m:
                continue
            n = norm_code(x)
            if len(n) < 8 or PUNCT_ONLY.match(n):
                continue
            where = idx.get(n, [])
            if len(where) != 1:
                continue                       # 无法唯一定位 → 不判定（折行/重复行）
            checked += 1
            want = int(m.group(1).split("-")[0])
            if want != where[0]:
                bad.append((want, where[0], n[:70]))
        rows.append(dict(start=start, sect=sect, src=os.path.relpath(cand, ROOT),
                         checked=checked, bad=len(bad), samples=bad[:3]))
    return rows


# ── 检查 ⓪：结构（A 组：节数 / 围栏 / 占位残留 / ⑫ 八条·八段·自指·薄条·回链） ──
FENCE_LINE = re.compile(r"^(\s*)(`{3,})\s*([A-Za-z0-9_+-]*)\s*$")


def fence_scan(lines):
    """围栏**配对**体检（2.6 新增）。口径与 parse_blocks 完全一致：
    块外任意围栏行都算"开始"（可带语言标签，也可不带）；块内只有**不带语言标签**的围栏行才闭合，
    带标签的行会被当成正文追加——这正是"前一个块没闭合"的症状。
    返回 ([问题三元组], 结束时是否仍在块内)。
    为什么需要它：⓪ 原来只查"围栏数量为偶数"，而**删除一对围栏中的一半、或把闭合栅栏与开始栅栏互换**，
    数量仍是偶数 → 一整段正文被吞进代码块却照样 PASS（真实事故见血证 H14）。
    只判 A（块内出现带标签围栏）/ D（结束时未闭合）/ H3（`### ` 级标题落在块内）三类——
    `## ` 级不判：合法 prompt 模板的正文里会出现 `## 1. xxx`（当前仅 1 个文件 7 处，属正常）。"""
    inside = False
    bad = []
    for i, l in enumerate(lines):
        m = FENCE_LINE.match(l)
        if m:
            if not inside:
                inside = True
            else:
                if m.group(3):
                    bad.append(("块内又出现带语言标签的围栏（前一个代码块未闭合）", i + 1, l.strip()[:36]))
                else:
                    inside = False
            continue
        if inside and re.match(r"^### ", l):
            bad.append(("标题落在代码块内（正文被吞）", i + 1, l.strip()[:36]))
    return bad, inside


def vib_depth(seg):
    """⑫ 内容深度（判据 2.11）——**⑫ 是整份教材里唯一能跨项目复用的那一节，也是唯一产生过
    "内容编造"级血证（H16）的那一节**；而 2.10 之前闸门对它只有"容器检查"（数条数/数标签/数行数），
    旧八条与现行八条同样全绿（实测：阶段7批次2 旧八条形态一路全绿）。

    本函数把 §6.2.1 的**可判定实质**测出来。分两档（先测误报率再收判据的落地）：
      FAIL 档（4 项，全库通过率 82%~91%，且都是 §6.2.1 的旧有明文）：
        A 八个条目标题必须命中 8 类语义（真实需求/现状勘察/方案比较/增量实现/提示词/产出后审查/验证反馈循环/最终沉淀）
        B 第 5 条必须含完整八段提示词骨架（≥6/8 个标签）
        C 第 5 条必须讲"设计要点"（为什么这么写）——只给一个提示词不算讲完
        D 第 6 条必须是 ≥6 项的审查清单
      报告档（其余维度只统计不判 FAIL，供存量工单与记分卡用）。
    """
    heads = list(re.finditer(r"^#{3,4}\s*\d+[\.、]\s*(.+)$", seg, re.M))
    titles = [h.group(1).strip() for h in heads]
    bodies = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(seg)
        bodies.append(seg[h.end():end])
    hit, cls_of = [], []
    for t in titles:
        c = None
        for name, pat in VIB_CLASSES:
            if re.search(pat, t):
                c = name
                break
        cls_of.append(c)
        if c and c not in hit:
            hit.append(c)
    by = {}
    for c, b in zip(cls_of, bodies):
        if c and c not in by:
            by[c] = b
    r2 = by.get("现状勘察", "")
    r3 = by.get("方案比较", "")
    r4 = by.get("增量实现", "")
    r5 = by.get("提示词", "")
    r6 = by.get("产出后审查", "")
    r7 = by.get("验证反馈循环", "")
    r8 = by.get("最终沉淀", "")
    tables = [m.group(0).strip().count("\n") + 1
              for m in re.finditer(r"(?:^\|.*\|\s*$\n?)+", seg, re.M)]
    labels = len(vib_prompt_segments(r5))
    r6_tbl = [m.group(0).strip().count("\n") + 1
              for m in re.finditer(r"(?:^\|.*\|\s*$\n?)+", r6, re.M)]
    # 审查清单可以是表、编号列表、或 `- [ ]` 勾选项——三种都算（实测误报来源：
    # 早期批次用 `- [ ] …？` 勾选式清单，只数表格会把 9 项清单判成 0 项）
    r6_list = (len(re.findall(r"^\s*\d+[\.、)]\s", r6, re.M))
               + len(re.findall(r"^\s*[-*]\s", r6, re.M)))
    audit_items = max(r6_tbl + [r6_list] or [0])
    return dict(
        titles=titles, hit=hit,
        miss_class=[n for n, _ in VIB_CLASSES if n not in hit],
        labels=labels,
        design=bool(re.search(
            r"设计要点|设计说明|八段结构对照|为什么这么写|为什么这样写|为什么给|"
            r"为什么第\s*\d|为何这么写", r5)),
        audit_items=audit_items,
        # 报告档
        r2_prompt="```" in r2,
        r2_items=len(re.findall(r"^\s*\d+[\.、)]\s", r2, re.M)),
        r2_pitfall=len(re.findall(r"不先看|没先看|不看|不确认|不查|不想清楚|不核对|不先确认|不验|翻车|后果是", r2)),
        r3_table=any(m.group(0).strip().count("\n") + 1 >= 3
                     for m in re.finditer(r"(?:^\|.*\|\s*$\n?)+", r3, re.M)),
        r3_reject=bool(re.search(r"为什么不是|不选|落选|否决|不用它|为什么不选", r3)),
        r4_steps=max([m.group(0).strip().count("\n") + 1
                      for m in re.finditer(r"(?:^\|.*\|\s*$\n?)+", r4, re.M)] or [0]),
        r4_bound=bool(re.search(r"不(应)?触碰|不动 |不要动|不改 |禁止改|不引入", r4)),
        r5_rounds=len(re.findall(r"第\s*\d\s*轮|轮\s*\d|turn\s*\d+", r5, re.I)),
        r6_method=bool(re.search(r"怎么查|检查方法|如何查|核对|通过判据|验证方法|依据|落点|grep", r6)),
        r7_rounds=min(len(re.findall(r"现象", r7)), len(re.findall(r"定位|根因", r7)),
                      len(re.findall(r"教训|沉淀", r7))),
        r8_rules=len(re.findall(r"^\s*\d+[\.、)]\s", r8, re.M)),
    )


def check_structure(lines, has_blocks):
    """has_blocks=True 才判"教材批"的结构（总览/索引/记录类文件跳过）"""
    txt = "\n".join(lines)
    sec = len([l for l in lines if re.match(r"^## ", l)])
    fences = len([l for l in lines if re.match(r"^\s*`{3,}", l)])
    fence_bad, fence_open = fence_scan(lines)
    # 占位符只在**代码块内**统计（正文里"残留检查：TODO 0"这类描述句不该误报）
    # 2.9 起也认**含中文的 `__占位__`**（填空白骨架/草稿不得冒充达标批，血证 H18）
    inblock, residual = False, 0
    for l in lines:
        if re.match(r"^\s*`{3,}", l):
            inblock = not inblock
            continue
        if inblock and (re.search(r"<<<SRC:|CON" + r"T-|TO" + r"DO|FIX" + r"ME", l) or PLACEHOLDER.search(l)):
            residual += 1
    m = re.search(r"^## ⑫\s", txt, re.M)
    m2 = re.search(r"^## ⑬\s", txt, re.M)
    eight = prompt = selfref = back = 0
    thin = []
    if m:
        seg = txt[m.end(): m2.start() if m2 else len(txt)]
        eight = len(re.findall(r"^#{3,4}\s*\d+[\.、]\s*", seg, re.M))
        bodies = re.split(r"^#{3,4}\s*\d+[\.、]", seg, flags=re.M)[1:]
        for i, b in enumerate(bodies):
            if len([x for x in b.split("\n") if x.strip()]) <= 2:
                thin.append(i + 1)
        prompt = len(re.findall(r"^【[^】]+】", seg, re.M))
        selfref = len(re.findall(r"本批|本阶段|教材第|答案卷|阶段[0-9]|批次[0-9]", seg))
        back = len(re.findall(r"^- 「", seg, re.M))
    return dict(sections=sec, fences=fences, residual=residual, eight=eight, prompt=prompt,
                selfref=selfref, back=back, thin=thin, is_batch=has_blocks,
                fence_bad=fence_bad, fence_open=fence_open,
                vib=vib_depth(seg) if m else None)


# ── 检查 ⑥：散文符号真实性（⓪~⑤ 之外最容易漏的一类错误：正文里提到的东西根本不存在） ──
# 血证 H16：批次1 的 ⑫ 整段描述了从未实现过的类/方法（ListItemBlock / MarkdownVisitor /
# ParseProfile.of …），六组全绿——因为 ① 只管代码块，正文一个字都不查。
# 判据取舍依据实测：**只留误报率≈0 的三条**——
#   R1  `Xxx.java:NN` 引用 → 文件必须存在且行号在范围内        （全库实测 0 处误报）
#   R4  件标题里声明的 `Xxx.java` 必须存在                     （78 文件 / 185 件标题实测 0 处）
#   R2''`本仓类.method(` → 方法名必须在本仓任意源码里出现过      （实测 2 处，1 真错 1 同名碰撞）
# R3（反引号里的 CamelCase 符号是否存在）**实测 371 处里 ~95% 是合法提及**——
#   第三方库类型（RedisTemplate/AsyncContext/各 *Exception）、教学示例类（Tiny*/Mini*/Immutable*）、
#   以及"本仓尚未实现"的规划名（MilvusVectorStoreService 等）。因此 **降级为报告清单，不判 FAIL**；
#   白名单见 spec/散文符号白名单.txt，稳定后再考虑升级。
PROSE_CALL = re.compile(r"`([A-Z][A-Za-z0-9_]*)\.([a-zA-Z][A-Za-z0-9_]*)\(")
PROSE_FILE = re.compile(r"`?([A-Za-z0-9_]+\.java)[:：](\d+)(?:-(\d+))?`?")
PROSE_TITLE = re.compile(r"^#{3,6}\s*6\.\d[\d\.]*\s*.*?`([A-Za-z0-9_]+\.java)`")
PROSE_CAMEL = re.compile(r"`([A-Z][a-z][A-Za-z0-9_]{1,})`")
_PROSE = {}


def prose_index(root):
    """惰性构建：文件名→路径 / import 过的外部类型 / 全部源码文本（判"方法名是否出现过"）"""
    if _PROSE:
        return _PROSE
    files, imported, srcs = {}, set(), []
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            if not fn.endswith(".java"):
                continue
            p = os.path.join(dp, fn)
            files.setdefault(fn, p)
            t = open(p, encoding="utf-8", errors="replace").read()
            srcs.append(t)
            for m in re.finditer(r"^import\s+(?:static\s+)?([\w.]+);", t, re.M):
                imported.add(m.group(1).split(".")[-1])
    _PROSE.update(files=files, imported=imported, src="\n".join(srcs))
    return _PROSE


def load_prose_whitelist():
    """spec/散文符号白名单.txt：一行一条；`#` 开头为注释；支持 `前缀*` 通配"""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spec", "散文符号白名单.txt")
    rules, exact = [], set()
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            l = l.strip()
            if not l or l.startswith("#"):
                continue
            if l.endswith("*"):
                rules.append(l[:-1])
            else:
                exact.add(l)
    return rules, exact


def check_prose(lines, by_class, root):
    """⑥ 散文符号真实性（只扫代码围栏之外的行）"""
    idx = prose_index(root)
    wl_prefix, wl_exact = load_prose_whitelist()
    r1, r2, r4, r3 = [], [], [], []
    inside = False
    for i, l in enumerate(lines):
        if FENCE_LINE.match(l):
            inside = not inside
            continue
        if inside:
            continue
        n = i + 1
        m = PROSE_TITLE.match(l)
        if m and m.group(1) not in idx["files"]:
            r4.append((n, "件标题声明的 %s 不存在" % m.group(1)))
        for mm in PROSE_FILE.finditer(l):
            f, a, b = mm.group(1), int(mm.group(2)), mm.group(3)
            if f not in idx["files"]:
                r1.append((n, "无此文件 %s" % f))
                continue
            tot = len(open(idx["files"][f], encoding="utf-8", errors="replace").read().split("\n"))
            if a > tot or (b and int(b) > tot):
                r1.append((n, "%s:%s 越界（该文件共 %d 行）" % (f, mm.group(2) + ("-" + b if b else ""), tot)))
        for mm in PROSE_CALL.finditer(l):
            cls, meth = mm.group(1), mm.group(2)
            if cls in by_class and not re.search(r"\b" + meth + r"\b", idx["src"]):
                if (cls + "." + meth) in wl_exact:
                    continue
                r2.append((n, "%s.%s() —— 全仓源码里没有 %s 这个方法" % (cls, meth, meth)))
        for mm in PROSE_CAMEL.finditer(l):
            s = mm.group(1)
            if s in by_class or s in idx["imported"] or s in wl_exact:
                continue
            if any(s.startswith(x) for x in wl_prefix):
                continue
            if re.search(r"\b" + s + r"\b", idx["src"]):
                continue
            r3.append((n, s))
    return dict(r1=r1, r2=r2, r4=r4, r3=r3)


# ── 检查 ⑤：用法与接入（⑥ 每件的调用现场 / 上下游 / 实现注册 + 批级 ⑦.5 扩展路径） ──
ITEM_RE = re.compile(r"^(#{3,6})\s*(6\.\d[\d\.]*)\s*(.*)$")
TBL_ANCHOR = re.compile(r"逐行要点表|^\|\s*行\s*\|")   # 2.7：⑤ 的定位锚——「怎么用」必须排在它之后
USE_MARKS = ("【怎么用】", "【调用现场】")
WIRE_MARKS = ("【怎么接】", "【实现与注册】")
IO_MARKS = ("【上下游】", "【上下游契约】")

# ⑫ 的八类语义（判据 2.11 / §6.2.1）+ 八段提示词的八个标签。
# 只匹配"语义"，不匹配"标题措辞"——同一件事写成"现状勘察"或"代码勘察"都算，
# 但写成"依赖（上游接口与既有代码）"不算（那是"谁给我什么"，不是"我该先读什么、不读会怎样"）。
VIB_CLASSES = (
    ("真实需求", r"真实需求|需求澄清|真实开发任务"),
    ("现状勘察", r"现状勘察|代码勘察|勘察"),
    ("方案比较", r"方案比较|选型"),
    ("增量实现", r"增量实现|拆分"),
    ("提示词", r"提示词|提示模板"),
    ("产出后审查", r"审查"),
    ("验证反馈循环", r"反馈循环|迭代过程|反馈"),
    ("最终沉淀", r"沉淀|可迁移|教训|踩过的坑"),
)
VIB_LABELS = ("【任务】", "【依赖】", "【要新增的类】", "【核心约束】",
              "【注释要求】", "【验收标准】", "【禁止】", "【输出格式】")
# 八段的"段名"识别：同一段写成 `【任务】` 或 `任务：` 都算——**只认一种写法就是把"形式"当"实质"**，
# 会把成型的中式标签提示词（`任务：/背景：/约束：/验收标准：/输出格式：`）误判成"没有骨架"。
VIB_SEG = (("任务", r"任务|目标"),
           ("依赖", r"依赖|背景|已有|上游"),
           ("要新增的类", r"要新增的类|新增类|要新增|文件清单|产出物"),
           ("核心约束", r"核心约束|约束|红线|必须遵守"),
           ("注释要求", r"注释要求|注释|代码注释"),
           ("验收标准", r"验收标准|验收|测试要求|测试约束"),
           ("禁止", r"禁止|反例|不要"),
           ("输出格式", r"输出格式|输出|交付格式"))


def vib_prompt_segments(r5):
    """第 5 条里识别出的提示词段名集合（两种写法都认）。"""
    hits = set()
    for name, pat in VIB_SEG:
        if re.search(r"【\s*(?:%s)\s*】" % pat, r5):
            hits.add(name)
    for m in re.finditer(r"^\s*([^\n【】:：]{1,12}?)\s*[:：]", r5, re.M):
        lab = m.group(1)
        for name, pat in VIB_SEG:
            if re.fullmatch(pat, lab):
                hits.add(name)
    return hits
IFACE_RE = re.compile(r"^\s*(?:public\s+|abstract\s+|sealed\s+|static\s+)*(?:interface|abstract\s+class)\s+\w+")
EXT_HEAD_RE = re.compile(r"^#{3,6}\s*(?:⑦\.5|.*(?:扩展与接入|接入与扩展|扩展路径))")


def ver_marker(lines):
    """2.10（**报告项，不计 FAIL**）：⑯ 段有没有写明判据版本 → 返回 (是否标过任何版本, 标的版本, 是否当前版)。

    两问分开的用意：**"从没标过"才是真缺陷**（⑯ 里的数字没人知道按哪版跑的，血证 H15 就是复述旧结论）；
    "标了但不是当前版"只是**提示复核**——判据每升一版就让所有旧标注变成"不达标"是跑步机，不是质量。
    实测：78 份里 6 份写过版本；升到 2.10 后那 6 份也变"非当前版"——正说明两问必须分开。"""
    txt = "\n".join(lines)
    m = re.search(r"^## ⑯", txt, re.M)
    if not m:
        return False, None, False
    seg = txt[m.start():]
    vs = re.findall(r"判据\s*v?([\d]+\.[\d]+)", seg) or re.findall(r"\bv([\d]+\.[\d]+)\b", seg)
    return bool(vs), (vs[-1] if vs else None), GATE_VERSION in seg


def check_usage(lines):
    """⑤ 用法与接入：切出每个 6.x 件，检查【怎么用】/【上下游】/（抽象件）【怎么接】与批级扩展小节。"""
    idx = [i for i, l in enumerate(lines) if ITEM_RE.match(l)]
    items = []
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        # 2.14（血证 H24）：件段**不得越过一级节标题**。原实现里"最后一个 6.x 件"的段一直延伸到
        # 文件末尾——于是 ⑧ 穿透卡 / ⑨ No-Framework / ⑩ 反例里的手写 `interface Xxx {` 骨架与
        # 【怎么接】标记都被算到那个件头上。实测全库：**10 件 iface 误判为真**（该件凭空要多写
        # 【怎么接】）、**6 件 wire 误判为真**（后文有【怎么接】就算它写了）。件段到自己所属一级节
        # 结束为止，这才是"件内"的字面意思。
        stops = [j for j in range(i + 1, end) if lines[j].startswith("## ")]
        if stops:
            end = stops[0]
        m = ITEM_RE.match(lines[i])
        seg = lines[i:end]
        body = "\n".join(seg)
        # 2.7 新增：⑤ 在件内的**位置**（顺序错了，读者会把"怎么用"当成下一节的内容）
        u = next((j for j, x in enumerate(seg) if any(mk in x for mk in USE_MARKS)), None)
        pos_bad = []
        if u is not None:
            t = next((j for j, x in enumerate(seg) if TBL_ANCHOR.search(x)), None)
            if t is not None and u < t:
                pos_bad.append("【怎么用】出现在「逐行要点表」之前（:L%d）" % (i + 1 + u))
            r = next((j for j, x in enumerate(seg) if x.strip() == "---"), None)
            if r is not None and u > r:
                pos_bad.append("件内 `---` 出现在【怎么用】之前（:L%d）" % (i + 1 + r))
        items.append(dict(
            no=m.group(2), title=m.group(3).strip()[:52], at=i + 1,
            hist=bool(re.search(r"历史版本|历史快照|已被阶段", m.group(3))),
            iface=any(IFACE_RE.match(l) for l in seg),
            use=any(x in body for x in USE_MARKS),
            wire=any(x in body for x in WIRE_MARKS),
            io=any(x in body for x in IO_MARKS),
            pos_bad=pos_bad))
    ext = [i for i, l in enumerate(lines) if EXT_HEAD_RE.match(l)]
    steps = 0
    if ext:
        seg = "\n".join(lines[ext[0]: ext[0] + 160])
        steps = len(re.findall(r"^\s*\d+[\.、)]\s*\S", seg, re.M))
    return items, dict(at=(ext[0] + 1 if ext else 0), steps=steps)


# ── 主流程 ───────────────────────────────────────────────────────────────
def main():
    global ROOT
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    lec = sys.argv[1]
    root = "."
    verbose = "--verbose" in sys.argv
    explicit_snap = None
    if "--src" in sys.argv:
        root = sys.argv[sys.argv.index("--src") + 1]
    if "--snapshot" in sys.argv:
        explicit_snap = sys.argv[sys.argv.index("--snapshot") + 1]
    jout = None
    if "--json" in sys.argv:
        jout = sys.argv[sys.argv.index("--json") + 1]
    ROOT = os.path.abspath(root)

    if not os.path.isfile(lec):
        print("找不到讲解文件：", lec)
        return 2
    lines, blocks = parse_blocks(lec)
    by_class, rev_index = index_sources(ROOT)

    sha, how = resolve_snapshot(lines, explicit_snap)
    snap_ok = load_snapshot(sha) if sha else False

    print("=" * 96)
    print("批次讲解闸门（§6.4 C 组）v%s:" % GATE_VERSION, os.path.basename(lec))
    print("源码根目录:", ROOT)
    if sha:
        print("源码快照: %s（%s）%s" % (sha, how, "" if snap_ok else "  ⚠️ 读取失败，退回只比当前树"))
    else:
        print("源码快照: 未声明（批头应写「源码依据：commit <sha>」）→ 无法区分「源码演进」与「编造」")
    print("=" * 96)

    # ⓪ 结构（A 组）
    st = check_structure(lines, any(b[1] == "java" and len(b[2]) >= 5 for b in blocks))
    print("\n⓪ 结构（A 组 · §6.4 三十六节规范 + ⑫ 形态）")
    s_reasons = []
    if not st["is_batch"]:
        print("   （非教材批：无 java 代码块，跳过结构判定）")
    else:
        if st["sections"] != 17:
            s_reasons.append(f"节数 {st['sections']} ≠ 17（①~⑯ + 索引，§6.4 定义）")
        if st["fences"] % 2:
            s_reasons.append(f"代码围栏 {st['fences']} 个 = 奇数（markdown 语法：有未闭合的块）")
        if st["residual"]:
            s_reasons.append(f"占位符残留 {st['residual']} 处")
        if st["eight"] != 8:
            s_reasons.append(f"⑫ 八条 = {st['eight']} ≠ 8（§6.2.1 定义）")
        if st["prompt"] != 8:
            # 2.11 起不再判 FAIL：这条只数 `^【…】` 行总数，**把形式当实质**——
            # 实测两类误报：① 合法写两份八段提示词的节（阶段10批次2 = 16）被误杀；
            # ② 用中式标签（`任务：/约束：/验收标准：`）写成的成型提示词（阶段13批次2 = 0）被误杀。
            # 改由下面 2.11 的"提示词段"判据（两种写法都认、且只看"有没有骨架"）承担。
            pass
        if st["selfref"]:
            s_reasons.append(f"⑫ 教材自指 {st['selfref']} 处（§6.2 写作视角铁律：必须 0）")
        if st["back"] == 0:
            s_reasons.append("⑫ 无「提问→引出」回链（§6.4 ⑫ 要求 ≥1，常见 4~6）")
        if st["thin"]:
            s_reasons.append(f"⑫ 八条中 {len(st['thin'])} 条内容过薄（≤2 行 = 一句话带过）：第 {st['thin']} 条")
        v = st.get("vib")
        if v:
            if v["miss_class"]:
                s_reasons.append("⑫ 条目未覆盖这些语义类：%s（§6.2.1 八条：%s）"
                                 % ("、".join(v["miss_class"]),
                                    "、".join(n for n, _ in VIB_CLASSES)))
            if v["labels"] == 0:
                s_reasons.append("⑫ 第 5 条找不到任何提示词段（任务/依赖/约束/验收标准/禁止/输出格式…）"
                                 "——§6.2.1：第 5 条必须给出**可直接使用的完整提示词骨架**，"
                                 "不能只描述『要做什么』")
            if not v["design"]:
                s_reasons.append("⑫ 第 5 条缺「设计要点」（只给一个提示词不算讲完——"
                                 "必须解释这份提示词为什么这么写，读者才学得会而不是只会抄）")
            if v["audit_items"] < 6:
                s_reasons.append("⑫ 第 6 条审查清单只有 %d 项（§6.2.1：≥6 项，"
                                 "且每项要有『怎么查』）" % v["audit_items"])
        for kind, ln, t in st["fence_bad"][:6]:
            s_reasons.append(f"围栏配对：{kind}（:L{ln}  {t}）")
        if len(st["fence_bad"]) > 6:
            s_reasons.append(f"围栏配对：另有 {len(st['fence_bad']) - 6} 处")
        if st["fence_open"]:
            s_reasons.append("围栏未闭合：文件结束时仍处于代码块内（后面的正文全被吞进代码块）")
        if not s_reasons:
            print(f"   节数={st['sections']} 围栏={st['fences']}(偶/配对OK) 占位={st['residual']} "
                  f"⑫八条={st['eight']} 八段={st['prompt']} 自指={st['selfref']} 回链={st['back']} "
                  f"薄条={len(st['thin'])}")
    v = st.get("vib")
    if v:
        print("   ⑫ 深度（2.11 · FAIL 档）：语义类 %d/8 ｜ 提示词段 %d/8 ｜ 设计要点 %s ｜ 审查清单 %d 项"
              % (len(v["hit"]), v["labels"], "有" if v["design"] else "无", v["audit_items"]))
        if v["labels"] and v["labels"] < 6:
            print("        ↳ 提示词段只成型 %d/8（八段齐全仍是 §6.2.1 要求；本项暂列报告档，"
                  "存量清到 ≤5 份后再升 FAIL）" % v["labels"])
        miss_rep = []
        if not v["r2_prompt"] and v["r2_items"] < 5:
            miss_rep.append("现状勘察既无勘察 prompt 块、编号项也只有 %d<5" % v["r2_items"])
        if v["r2_pitfall"] < 3:
            miss_rep.append("『不先看会怎样』翻车场景 %d<3" % v["r2_pitfall"])
        if not v["r3_table"]:
            miss_rep.append("方案比较无对比表")
        if not v["r3_reject"]:
            miss_rep.append("方案比较无『为什么不是其他方案』")
        if v["r4_steps"] < 6:
            miss_rep.append("增量实现步表 %d<6 行" % v["r4_steps"])
        if not v["r4_bound"]:
            miss_rep.append("缺『不应触碰的边界』")
        if v["r5_rounds"] < 3:
            miss_rep.append("提示词不是多轮序列（轮次标记 %d<3）" % v["r5_rounds"])
        if not v["r6_method"]:
            miss_rep.append("审查项缺『怎么查』")
        if v["r7_rounds"] < 1:
            miss_rep.append("验证反馈循环无完整四段（现象/定位/修正/教训）")
        elif v["r7_rounds"] < 3:
            miss_rep.append("四段迭代只有 %d<3 轮" % v["r7_rounds"])
        if v["r8_rules"] < 5:
            miss_rep.append("最终沉淀 %d<5 条" % v["r8_rules"])
        print("   ⑫ 深度报告档（**不计 FAIL**，供存量工单与记分卡）：%s"
              % ("；".join(miss_rep) if miss_rep else "全部达标"))
    for r in s_reasons:
        print("   [FAIL] " + r)
    print(f"   → {'PASS' if not s_reasons else 'FAIL'}")

    # ① 正向
    fid = check_fidelity(blocks, by_class, rev_index)
    chk = [r for r in fid if not r["exempt"]]
    tot = sum(r["n_code"] for r in chk)
    # FAIL 基准：有快照时看"两处都没有"的行；无快照时退回"当前树不命中"
    def fail_lines(r):
        if r["lost"] is None:
            return r["n_code"]
        if is_hist(r["sect"], None) and r["snap_lost"] is not None:
            return r["snap_lost"]
        return r["snap_lost"] if r["snap_lost"] is not None else r["lost"]

    lost = sum(fail_lines(r) for r in chk)
    drift = sum((r["lost"] or 0) - (r["snap_lost"] or 0) for r in chk
                if r["lost"] is not None and r["snap_lost"] is not None)
    unattr = [r for r in chk if r["lost"] is None]
    print(f"\n① 正向保真度：{len(chk)} 个代码块 / {tot} 行代码 → 候选不符 {lost} 行 "
          f"= 保真度 {100.0*(tot-lost)/tot if tot else 100:.1f}%  "
          f"{'PASS' if lost == 0 and not unattr else 'FAIL'}")
    if drift:
        print(f"   （其中 {drift} 行属【源码演进】：只在本批快照里命中，当前树已重写——不计 FAIL，但需在小节标题标【历史版本示例】）")
    for r in chk:
        if r["lost"] is None:
            print(f"   ! 无法归属源文件  {os.path.basename(lec)}:{r['start']}  {r['sect']}")
        elif fail_lines(r):
            print(f"   ! 候选不符 {fail_lines(r)}/{r['n_code']} 行  :{r['start']}  {r['sect']}"
                  + ("  【历史版本块，按快照核验】" if r["hist"] else ""))
            print(f"     归属 = {r['cand']}")
            why = "源码与快照里都没有" if r["snap_lost"] is not None else "源码里没有（未声明快照，无法判断是演进还是编造）"
            for s in (r["snap_lost_samples"] or r["lost_samples"]):
                print(f"       {why}: {s[:88]}")
    ex = [r for r in fid if r["exempt"]]
    if ex:
        print(f"   （免检小节 {len(ex)} 个代码块 / {sum(r['n_code'] for r in ex)} 行："
              f"{', '.join(sorted({r['sect'] for r in ex}))[:110]}）")

    # ② 反向
    rev_rows = check_reverse(blocks, lines, by_class)
    print(f"\n② 反向完整度（★类）：{len(rev_rows)} 个★类（★ 标在父标题同样计入）")
    bad_rev = [r for r in rev_rows if r["cov"] < 0.995]
    for r in rev_rows:
        tag = "OK " if r["cov"] >= 0.995 else "FAIL"
        print(f"   [{tag}] {r['cls']:<34} 有效行={r['real']:<4} 缺失={r['miss']:<4} 覆盖={r['cov']*100:.1f}%")
        for s in r["samples"]:
            print(f"          缺失: {s[:82]}")
    print(f"   → {'PASS' if not bad_rev else 'FAIL'}")

    # ③ 密度
    den = check_density(blocks, by_class, rev_index)
    sig = check_sig(blocks, by_class)
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
    for r in sig:
        print(f"   [FAIL] ★类方法签名无注释：{r['cls']}（{r['src']}）→ "
              f"{len(r['missing'])} 个：{', '.join(r['missing'][:8])}")
    for r, reasons in sorted(bad_den, key=lambda x: -x[0]["max_run"])[:25]:
        print(f"   [FAIL] :{r['start']:<6} 关键行={r['key_lines']:<4} 注释={r['comments']:<4} "
              f"最长无注释={r['max_run']:<4} {r['sect'][:44]}")
        print(f"          → {'; '.join(reasons)}")
    if len(bad_den) > 25:
        print(f"   ...另有 {len(bad_den)-25} 个不达标块")
    print(f"   → {'PASS' if not (bad_den or sig) else 'FAIL'}")

    # ④ 行号一致性
    ln_all = check_lineno(blocks, by_class, rev_index)
    ln_rows = [r for r in ln_all if r["bad"]]
    print(f"\n④ 行号一致性（`// :Lnn` ↔ 真实行号）：可判定 {sum(r['checked'] for r in ln_all)} 处"
          f" → 漂移 {sum(r['bad'] for r in ln_all)} 处")
    for r in sorted(ln_rows, key=lambda x: -x["bad"])[:15]:
        print(f"   [FAIL] :{r['start']:<6} 漂移 {r['bad']:>3}/{r['checked']:<3}  {r['sect'][:44]}")
        for want, real_no, s in r["samples"]:
            print(f"          标 :L{want} → 实际第 {real_no} 行: {s}")
    if len(ln_rows) > 15:
        print(f"   ...另有 {len(ln_rows)-15} 个块存在行号漂移")
    print(f"   → {'PASS' if not ln_rows else 'FAIL'}")

    # ⑤ 用法与接入
    u_items, u_ext = check_usage(lines)
    u_live = [r for r in u_items if not r["hist"]]
    bad_use = [r for r in u_live if not r["use"]]
    bad_io = [r for r in u_live if not r["io"]]
    iface = [r for r in u_live if r["iface"]]
    bad_wire = [r for r in iface if not r["wire"]]
    bad_pos = [r for r in u_live if r["pos_bad"]]
    bad_ext = (not u_ext["at"]) or u_ext["steps"] < 3
    print(f"\n⑤ 用法与接入（⑥ 每件：调用现场 + 上下游；抽象件：实现与注册；批级 ⑦.5 扩展路径）")
    if not st["is_batch"]:
        print("   （非教材批：跳过用法与接入判定）")
        bad_use = bad_io = bad_wire = bad_pos = []
        bad_ext = False
    else:
        print(f"   逐件={len(u_live)}（另历史版本小节 {len(u_items)-len(u_live)} 个免检）"
              f" 【怎么用】={len(u_live)-len(bad_use)}/{len(u_live)}"
              f" 【上下游】={len(u_live)-len(bad_io)}/{len(u_live)}"
              f" 抽象件={len(iface)} 【怎么接】={len(iface)-len(bad_wire)}/{len(iface)}"
              f" 位置OK={len(u_live)-len(bad_use)-len(bad_pos)}/{len(u_live)-len(bad_use)}"
              f" ⑦.5扩展小节={'有' if u_ext['at'] else '无'}(步骤{u_ext['steps']})")
        for tag, rows in (("缺【怎么用】", bad_use), ("缺【上下游】", bad_io), ("缺【怎么接】", bad_wire)):
            for r in rows[:12]:
                print(f"   [FAIL] {tag}：{r['no']} {r['title']}  （:L{r['at']}）")
            if len(rows) > 12:
                print(f"          ...另有 {len(rows)-12} 个")
        for r in bad_pos[:12]:
            print(f"   [FAIL] ⑤ 位置：{r['no']} {r['title']} → {'；'.join(r['pos_bad'])}")
        if bad_ext:
            why = "缺 ⑦.5 扩展与接入路径小节" if not u_ext["at"] else f"⑦.5 只有 {u_ext['steps']} 条编号步骤（<3）"
            print(f"   [FAIL] {why}（:L{u_ext['at']}）")
    print(f"   → {'PASS' if not (bad_use or bad_io or bad_wire or bad_pos or bad_ext) else 'FAIL'}")

    # ⑥ 散文符号真实性（血证 H16：① 只管代码块，正文提到不存在的类/方法它一个字都不查）
    prose = check_prose(lines, by_class, ROOT)
    p_bad = prose["r1"] + prose["r4"] + prose["r2"]
    print(f"\n⑥ 散文符号真实性（正文里的 文件:行 引用 / 件标题声明的文件 / 本仓类.方法）")
    print(f"   文件:行 引用不成立={len(prose['r1'])} ｜ 件标题文件不存在={len(prose['r4'])}"
          f" ｜ 本仓类.方法 全仓无此方法={len(prose['r2'])} ｜ 反引号符号待确认={len(prose['r3'])}（不计 FAIL）")
    for tag, rows in (("文件:行 引用不成立", prose["r1"]), ("件标题声明的文件不存在", prose["r4"]),
                      ("本仓类.方法 全仓无此方法", prose["r2"])):
        for n, s in rows[:12]:
            print(f"   [FAIL] {tag}：:L{n}  {s}")
        if len(rows) > 12:
            print(f"          ...另有 {len(rows)-12} 处")
    if prose["r3"]:
        seen = []
        for n, s in prose["r3"]:
            if s not in seen:
                seen.append(s)
        print(f"   （待人工确认 {len(prose['r3'])} 处 / {len(seen)} 种符号；多为第三方库类型、教学示例类"
              f"（Tiny*/Mini*/Immutable*）与「本仓尚未实现」的规划名——确认后可加进 spec/散文符号白名单.txt）")
        print(f"    例：{', '.join(seen[:12])}")
    print(f"   → {'PASS' if not p_bad else 'FAIL'}")

    ok = (not s_reasons and lost == 0 and not unattr and not bad_rev and not bad_den and not sig and not ln_rows
          and not bad_use and not bad_io and not bad_wire and not bad_pos and not bad_ext and not p_bad)

    print("\n⓪~⑤ 之外的残留引用自查（闸门盲区，SKILL §6.4「⑥ 节之外的残留引用检查」必做清单，需人工过）：")
    print("   ②多步示意（是否漏步/顺序反）｜⑦调用链表（方法名·字段名·两跳顺序）｜⑦边界条件表（行为是否与真实分支一致）")
    print("   ⑧穿透卡 L3·L4（异常类型是否与真实 throw/测试断言一致）｜⑩反例的 ✅ 代码（API 是否真实存在）")
    print("   ⑪测试表（方法名·构造实参·assertThrows 异常类 —— 逐条打开真实测试文件核对）｜⑯自检表（是否复述旧结论）")
    # 2.10（报告项，不计 FAIL）：⑯ 段有没有写明判据版本 —— 从没标过 = 数字不知道按哪版跑的（血证 H15）
    has_v, which, is_cur = ver_marker(lines)
    if not has_v:
        note = f"**从没写明判据版本**（⑯ 的数字不知道按哪版跑的）"
    elif not is_cur:
        note = f"标的是 v{which}（当前 v{GATE_VERSION} → 建议复核一遍数字）"
    else:
        note = f"已写明 v{GATE_VERSION} ✅"
    print(f"   ⑯ 判据版本标注（**报告项，不计 FAIL**）：{note}"
          f"　→ 一键补齐：`python scripts/sync_gate_result.py <本文件> --src <仓库根> --apply`")
    print("\n" + "=" * 96)
    print("总判定:", "PASS ✅" if ok else "FAIL ❌（C 组任一不过 = 当场修）")
    print("=" * 96)

    if jout:
        json.dump(dict(fidelity=fid, reverse=rev_rows, density=den, lineno=ln_rows,
                       usage=dict(items=u_items, ext=u_ext),
                       snapshot=sha, ver_marked=(ver_marker(lines)[2]), pass_=ok),
                  open(jout, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("明细已写:", jout)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
