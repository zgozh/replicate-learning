#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""lecture_checks.py —— 单批检查结果的**统一 schema 与规则登记表**（方案 §3.4 的公共模块）。

**为什么要有它**：改造前，`gate_lecture.py --json` 的顶层只有一个 `pass_`，多个聚合对象各自为政、
没有稳定规则 ID、没有"检查了多少个对象"、也没有绑定被检查文件的哈希；`sync_gate_result.py`
只好**重跑一次闸门**、再用正则从展示文本里扒数字。于是同一批事实存在两套口径（JSON 一套、文本一套），
而"零对象 PASS"（一个对象都没查却绿灯）无法与"真查过"区分。

本模块只做三件事，不含任何判据实现：
  1. **状态词表**：`PASS / FAIL / REPORT / NOT_CHECKED / ERROR` —— 五个状态是**互斥**的；
     `NOT_CHECKED`（没对象可查）与 `ERROR`（检查器崩了/输入读不到）**都不算 PASS**。
  2. **规则 ID 登记**：把每个检查组映射到 `spec/00-质量契约.json` 的条目 ID（SSOT 单一来源），
     并提供 `unknown_contract_ids()` 做"登记表不许指向不存在的条款"的自校验。
  3. **结果构造与渲染**：`make_result()` / `make_check()` / `render()` / `validate_result()`，
     供 `batch_preflight.py`、`gate_lecture.py --json`、`sync_gate_result.py --result-json` 共用。
     机器结果里同时带 `lecture_sha256` 与 `source_manifest_sha256`——盖章（写入 ⑯）前先验这两个哈希，
     杜绝"用旧结果给改动过的正文背书"（血证 H15 家族）。
"""
import hashlib
import io
import json
import os
import sys

SCHEMA_VERSION = 1

PASS = "PASS"
FAIL = "FAIL"
REPORT = "REPORT"
NOT_CHECKED = "NOT_CHECKED"
ERROR = "ERROR"
STATUSES = (PASS, FAIL, REPORT, NOT_CHECKED, ERROR)
BLOCKING = (FAIL, ERROR)

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)


def configure_stdio():
    """把 stdout/stderr 固定成 UTF-8（errors=replace），**并返回是否成功**。

    为什么工具必须先做这一步（2026-09-20 实测缺陷）：这些脚本的正文里到处是 ⓪①②…★ 与中文，
    而 Windows 的默认代码页是 GBK。一旦 stdout 被**重定向到文件或管道**（`> log.txt`、
    `subprocess.run(capture_output=True)`、CI 采集），Python 会按 cp936 编码，遇到 ⑫（\\u246b）
    直接 `UnicodeEncodeError` **崩在打印上**——实测 `gate_lecture.py` 正是这样崩的，
    而第48批的会话里它是靠 `| grep` 管道用的：换成任何采集式调用就会整批卡住。
    修法是每个 CLI 入口先调本函数（不是靠人记得设 PYTHONIOENCODING）。
    """
    ok = True
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            ok = False
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            ok = False
    return ok

# ── 规则登记表：检查组 → SSOT 条款 ID ────────────────────────────────────────
# 口径：ID 一律取自 `spec/00-质量契约.json`，不在本文件另立一套编号。
# `F4`：SSOT 里 ⑤ 用法与接入的**首条**（【怎么用】）用的 id 是 `F4`（gate 锚 = USE_MARKS），
#   而后续三条是 `U2`/`U3`/`U4`——即 ⑤ 组实际是 F4+U2+U3+U4，契约里没有 `U1`。
#   历史记录（血证 H4 行）也按 `F4/U2/U3/U4` 引用，故本表沿用 `F4`，**不改契约 ID**。
# `S22b`：SSOT 里 `S22` 出现两次（① 记录类形态（2.21）② 节数与节标题只在正文里数（2.22））。
#   判据变更史只按 ID 记录了 2.22 的那条，故 `S22` 保留给正文计数，记录类形态在本表记 `S22b`；
#   **不改契约本身**（改 ID 会让已有引用与历史记录对不上），只在这里显式区分，待判据升版时统一。
CHECK_GROUPS = {
    # 预检（batch_preflight.py）
    "P-PLAN": ("注释计划结构（键/范围/重复）", ["S3", "S10", "A1"]),
    "P-HASH": ("源文件哈希与清单一致", ["F1", "F2"]),
    "P-DENSITY": ("注释密度（关键行连段/条数）", ["D1", "D2", "A1"]),
    "P-SIG": ("★类方法签名注释覆盖", ["D3"]),
    "P-REVERSE": ("★类源码行反向覆盖", ["R1", "R2"]),
    "P-PY": ("Python 注入安全与语法", ["A1", "S24"]),
    "P-SNIP": ("教学合成片段静态校验", ["F4", "U3"]),
    "P-SCOPE": ("本批适用清单（结构/⑫形态/证据等级）", ["S1", "S4", "S5", "A2", "A3"]),
    "P-ADDR": ("源码块寻址唯一性（槽位/anchor）", ["S1", "A1"]),
    # 单批门禁（gate_lecture.py）
    "G-STRUCT": ("⓪ 结构（17 节/围栏/占位/⑫八条）",
                 ["S1", "S2", "S9", "S3", "S10", "S13", "S4", "S5", "S6", "S7", "S8"]),
    "G-CORE": ("⓪b 每批必含内容（①图/⑦.1链/⑧省略段）", ["S15", "S16", "S17", "S20"]),
    "G-FORM": ("⓪d 形态质量（②⑤⑥⑭）", ["S18", "S19", "R2"]),
    "G-SNIP": ("⓪d ⑥ 可复制性（E12/E13）", ["F4", "U3"]),
    "G-STYLE": ("⓪e 结构密度与排版", ["S12", "A4", "A5", "A6"]),
    "G-BATCH3": ("⓪f 批次3 结构基准门", ["S18", "S16", "S19", "U2"]),
    "G-FIDELITY": ("① 正向保真度", ["F1", "F2", "F3"]),
    "G-REVERSE": ("② 反向完整度（★类）", ["R1", "R2"]),
    "G-DENSITY": ("③ 注释密度与签名", ["D1", "D2", "D3"]),
    "G-LINENO": ("④ 行号一致性", ["N1"]),
    "G-USAGE": ("⑤ 用法与接入", ["F4", "U2", "U3", "U4", "U5", "U6", "U7", "U8"]),
    "G-PROSE": ("⑥ 散文符号真实性", ["P1", "P2"]),
    "G-PY": ("非 Java 语言实检（2.24）", ["S23", "S24"]),
    "G-RECORD": ("记录类形态（2.21）", ["S22b"]),
    "G-LECTURE": ("教材类文件判定（2.20）", ["S21"]),
}


def load_contract(path=None):
    p = path or os.path.join(SKILL_ROOT, "spec", "00-质量契约.json")
    return json.load(io.open(p, encoding="utf-8"))


def unknown_contract_ids(contract=None):
    """登记表里指向**契约中不存在**的条款 ID（自校验用；`S22b` 是登记表内的显式区分，允许）。"""
    contract = contract or load_contract()
    known = {e.get("id") for e in contract.get("entries", [])}
    bad = []
    for group, (_title, ids) in CHECK_GROUPS.items():
        for cid in ids:
            if cid == "S22b":
                if "S22" not in known:
                    bad.append("%s → S22b（契约里连 S22 都没有）" % group)
                continue
            if cid not in known:
                bad.append("%s → %s" % (group, cid))
    return bad


def sha256_file(path):
    if not path or not os.path.isfile(path):
        return None
    h = hashlib.sha256()
    with io.open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def make_finding(message, where=None, line=None, part_id=None, severity=FAIL, source=None):
    f = {"message": message}
    if where:
        f["where"] = where
    if line is not None:
        f["line"] = line
    if part_id:
        f["part_id"] = part_id
    if source:
        f["source"] = source
    if severity != FAIL:
        f["severity"] = severity
    return f


def make_check(cid, status, checked=0, findings=None, title=None, note=None, applicable=True):
    """构造一条检查结果。`checked` = **本次真正核验过的对象数**（不是"能查的"数）。"""
    if status not in STATUSES:
        raise ValueError("非法状态：%r（只能是 %s）" % (status, "/".join(STATUSES)))
    if status == PASS and not applicable:
        raise ValueError("不适用的检查不许写成 PASS（应写 NOT_CHECKED）")
    if status == PASS and checked == 0:
        raise ValueError("检查对象为 0 不许写成 PASS（写 NOT_CHECKED：0 对象 PASS 是真空通过）")
    title_default, contract_ids = CHECK_GROUPS.get(cid, (cid, []))
    return {
        "id": cid,
        "title": title or title_default,
        "contract": list(contract_ids),
        "status": status,
        "applicable": bool(applicable),
        "checked": int(checked),
        "findings": list(findings or []),
        **({"note": note} if note else {}),
    }


def make_result(producer, checks, contract_version=None, lecture_sha256=None,
                source_manifest_sha256=None, source_root=None, extra=None):
    contract = load_contract()
    result = {
        "schema_version": SCHEMA_VERSION,
        "producer": producer,
        "contract_version": contract_version or contract.get("version"),
        "contract_sha256": sha256_file(os.path.join(SKILL_ROOT, "spec", "00-质量契约.json")),
        "lecture_sha256": lecture_sha256,
        "source_manifest_sha256": source_manifest_sha256,
        "checks": list(checks),
    }
    if source_root:
        result["source_root"] = source_root
    if extra:
        result.update(extra)
    result["pass"] = not any(c.get("status") in BLOCKING for c in result["checks"])
    return result


def blocking_checks(result):
    return [c for c in result.get("checks", []) if c.get("status") in BLOCKING]


def render(result, verbose=True):
    lines = ["检查结果（producer=%s · 契约 v%s · schema v%s）→ %s"
             % (result.get("producer"), result.get("contract_version"),
                result.get("schema_version"), "PASS ✅" if result.get("pass") else "FAIL ❌")]
    if result.get("lecture_sha256"):
        lines.append("  被检查文件 sha256=%s" % result["lecture_sha256"][:16])
    if result.get("source_manifest_sha256"):
        lines.append("  源码清单 sha256=%s" % result["source_manifest_sha256"][:16])
    width = max([len(c.get("id", "")) for c in result.get("checks", [])] + [4])
    for c in result.get("checks", []):
        lines.append("  [%-11s] %-*s %-34s 核验 %d 个对象%s"
                     % (c.get("status"), width, c.get("id"), (c.get("title") or "")[:34],
                        c.get("checked", 0),
                        "（条款 %s）" % ",".join(c.get("contract") or []) if c.get("contract") else ""))
        if c.get("note"):
            lines.append("        ↳ %s" % c["note"])
        if verbose:
            for f in c.get("findings", []):
                where = f.get("where") or ""
                line = (":%s" % f["line"]) if f.get("line") else ""
                lines.append("        - %s%s %s" % (where, line, f.get("message", "")))
    return "\n".join(lines)


def validate_result(result, *, expect_lecture_sha256=None, expect_manifest_sha256=None,
                    expect_contract_version=None, required_ids=None):
    """盖章前的自检：结果必须与"现在要盖章的这份内容"对得上。返回错误列表（空 = 可盖章）。"""
    problems = []
    if result.get("schema_version") != SCHEMA_VERSION:
        problems.append("结果 schema_version=%r，本工具只认 %d"
                        % (result.get("schema_version"), SCHEMA_VERSION))
    if expect_contract_version and str(result.get("contract_version")) != str(expect_contract_version):
        problems.append("结果契约版本 v%s ≠ 当前 v%s（旧结果不得给新正文背书）"
                        % (result.get("contract_version"), expect_contract_version))
    if expect_lecture_sha256:
        if not result.get("lecture_sha256"):
            problems.append("结果里没有 lecture_sha256——无法证明它检查的就是这份正文")
        elif result["lecture_sha256"] != expect_lecture_sha256:
            problems.append("结果 lecture_sha256=%s… ≠ 当前正文 %s…（正文在检查之后被改过）"
                            % (result["lecture_sha256"][:12], expect_lecture_sha256[:12]))
    if expect_manifest_sha256 and result.get("source_manifest_sha256") != expect_manifest_sha256:
        problems.append("结果 source_manifest_sha256=%s… ≠ 当前清单 %s…（源码清单变了）"
                        % (str(result.get("source_manifest_sha256"))[:12], expect_manifest_sha256[:12]))
    have = {c.get("id") for c in result.get("checks", [])}
    for cid in required_ids or ():
        if cid not in have:
            problems.append("结果缺少必需检查 %s（不完整的报告不能盖章）" % cid)
    if not result.get("checks"):
        problems.append("结果里一条检查都没有")
    for c in result.get("checks", []):
        if c.get("status") not in STATUSES:
            problems.append("检查 %s 的状态 %r 非法" % (c.get("id"), c.get("status")))
        if c.get("status") == PASS and not c.get("checked"):
            problems.append("检查 %s 写 PASS 但核验对象数为 0（真空通过）" % c.get("id"))
    return problems


def load_result(path):
    return json.load(io.open(path, encoding="utf-8"))
