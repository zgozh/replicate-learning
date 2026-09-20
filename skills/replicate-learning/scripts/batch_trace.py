#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""batch_trace.py —— 批次分步计时器（零依赖 JSONL · 方案 §3.1 阶段1）。

**为什么需要它**：第48批的导出（`test.md`）里只有消息时间戳，而且有集中赋值/上下文压缩迹象——
从它反推"每步耗时"会得到假数字（能确认的只有 Maven 自身约 28 秒、后台任务约 34 秒）。
没有分步实测，任何"提速了 / 变慢了"都只是猜。本工具把阶段（prepare / investigate / write /
inject / repair / gate / verify / publish）的开始、结束与批次级事实各写一行 JSON，交给 `report` 汇总。

**它不做什么**（边界即安全）：
  · 只落盘**枚举字段**：阶段名、时间戳、耗时、计数、门禁版本与失败规则 ID、验证命令与耗时；
  · **不落**完整提示词、不落环境变量、不落密钥——`set` 只接受白名单键，值里出现密钥形态直接拒绝；
  · 不把 LLM 耗时变成"自动采集"：模型调用时间由操作者按秒表（`begin`/`end`）+ `note` 写明口径。
    脚本采集不到的东西标"未实测"，不编造。

用法：
    python batch_trace.py --file <trace.jsonl> start --batch-id stage3-b48 [--model <名>]
    python batch_trace.py --file <trace.jsonl> begin --phase write [--note "口径：从落笔到分片写完"]
    python batch_trace.py --file <trace.jsonl> end   --phase write
    python batch_trace.py --file <trace.jsonl> set   --phase gate --key gate_version --value 2.30
    python batch_trace.py --file <trace.jsonl> set   --phase gate --key gate_failed_rules --value D1,D3
    python batch_trace.py --file <trace.jsonl> report [--json out.json]

阶段名固定为 `PHASES`；写错阶段名当场报错（否则报表里会静默少一段，看起来"这步不花时间"）。
`report` 会同时列出**没有记录的阶段**——"没测"与"零耗时"必须能分开。
"""
import argparse
import datetime
import io
import json
import os
import re
import statistics
import sys
import time

PHASES = ("prepare", "investigate", "write", "inject", "repair", "gate", "verify", "publish")

# 允许落盘的键（白名单）。**不含**任何自由文本提示词字段。
FACT_KEYS = ("model", "contract_version", "source_files", "source_lines", "injected_lines",
             "model_chars", "model_calls", "tool_calls", "gate_version", "gate_failed_rules",
             "repair_count", "verify_cmd", "verify_ms", "batch_files", "batch_lines", "gate_ms")
# 值里出现这些形态 = 拒绝写入（宁可少一条数据，也不落密钥）
SECRET_RE = re.compile(r"(sk-[A-Za-z0-9]|api[_-]?key|secret|passwd|password|BEGIN [A-Z ]*PRIVATE KEY|ghp_)", re.I)
NOTE_MAX = 300


def now_dt():
    return datetime.datetime.now(datetime.timezone.utc)


def iso(dt):
    return dt.astimezone(datetime.timezone.utc).isoformat(timespec="seconds")


def _guard_value(key, value):
    if key not in FACT_KEYS:
        raise SystemExit("[ABORT] 不认识的键 %r；允许的键：%s\n"
                         "   → 本工具只落**枚举字段**，不落提示词/环境变量/密钥（方案 §3.1）"
                         % (key, "、".join(FACT_KEYS)))
    text = str(value)
    if SECRET_RE.search(text):
        raise SystemExit("[ABORT] 值里出现疑似密钥形态，拒绝落盘：%s" % key)
    return text


def append_record(path, obj):
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    with io.open(path, "a", encoding="utf-8", newline="") as f:
        f.write(json.dumps(obj, ensure_ascii=False, sort_keys=True) + "\n")


def read_records(path):
    if not os.path.isfile(path):
        return []
    out = []
    for lineno, line in enumerate(io.open(path, encoding="utf-8"), 1):
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError as exc:
            raise SystemExit("[ABORT] %s:%d 不是合法 JSON 行：%s" % (path, lineno, exc))
    return out


def check_phase(phase):
    if phase not in PHASES:
        raise SystemExit("[ABORT] 阶段名 %r 不在 %s 之内（写错会让报表静默少一段）"
                         % (phase, "/".join(PHASES)))
    return phase


def start_record(batch_id, dt=None, **facts):
    rec = {"kind": "batch", "batch_id": batch_id, "started_at": iso(dt or now_dt())}
    for k, v in facts.items():
        if v is not None:
            rec[k] = _guard_value(k, v)
    return rec


def phase_begin(path, phase, dt=None, ms=None, note=None):
    check_phase(phase)
    dt = dt or now_dt()
    ms = time.time() * 1000.0 if ms is None else ms
    if note is not None and len(str(note)) > NOTE_MAX:
        raise SystemExit("[ABORT] note 超过 %d 字（note 只写测量口径，不贴提示词/正文）" % NOTE_MAX)
    if note is not None and SECRET_RE.search(str(note)):
        raise SystemExit("[ABORT] note 里出现疑似密钥形态，拒绝落盘")
    rec = {"kind": "phase", "event": "begin", "phase": phase, "at": iso(dt), "_ms": ms}
    if note:
        rec["note"] = str(note)
    append_record(path, rec)
    return rec


def phase_end(path, phase, dt=None, ms=None):
    check_phase(phase)
    dt = dt or now_dt()
    ms = time.time() * 1000.0 if ms is None else ms
    seen = [r for r in read_records(path)
            if r.get("kind") == "phase" and r.get("phase") == phase]
    if not seen:
        raise SystemExit("[ABORT] 阶段 %s 没有对应的 begin —— 不能凭空产生一条耗时" % phase)
    open_begin = seen[-1] if seen[-1].get("event") == "begin" else None
    if open_begin is None:
        raise SystemExit("[ABORT] 阶段 %s 的 begin 已经 end 过（重复 end 会造出假耗时）" % phase)
    duration = max(0, int(round(ms - float(open_begin.get("_ms", ms)))))
    rec = {"kind": "phase", "event": "end", "phase": phase, "at": iso(dt), "duration_ms": duration}
    append_record(path, rec)
    return rec


def set_fact(path, phase, key, value, dt=None):
    check_phase(phase)
    value = _guard_value(key, value)
    numeric = None
    if key in ("source_files", "source_lines", "injected_lines", "model_chars", "model_calls",
               "tool_calls", "repair_count", "verify_ms", "batch_files", "batch_lines", "gate_ms"):
        try:
            numeric = int(value)
        except ValueError:
            raise SystemExit("[ABORT] 键 %s 需要整数，收到 %r" % (key, value))
    rec = {"kind": "fact", "phase": phase, "key": key, "at": iso(dt or now_dt())}
    rec["value"] = numeric if numeric is not None else value
    append_record(path, rec)
    return rec


def report(records):
    batch = next((r for r in records if r.get("kind") == "batch"), {})
    phases = {}
    for rec in records:
        if rec.get("kind") != "phase" or rec.get("event") != "end":
            continue
        phases.setdefault(rec["phase"], []).append(int(rec.get("duration_ms", 0)))
    facts = {}
    for rec in records:
        if rec.get("kind") == "fact":
            facts[rec["key"]] = rec["value"]
    for key in ("model", "contract_version"):
        if key in batch:
            facts.setdefault(key, batch[key])
    per_phase = {}
    for phase, values in phases.items():
        per_phase[phase] = {"count": len(values), "total_ms": sum(values),
                            "median_ms": int(statistics.median(values)), "last_ms": values[-1]}
    stamps = [r.get("at") or r.get("started_at") for r in records if r.get("at") or r.get("started_at")]
    wall_ms = None
    if stamps:
        try:
            first = datetime.datetime.fromisoformat(sorted(stamps)[0])
            last = datetime.datetime.fromisoformat(sorted(stamps)[-1])
            wall_ms = int((last - first).total_seconds() * 1000)
        except ValueError:
            wall_ms = None
    return {
        "batch_id": batch.get("batch_id"),
        "started_at": batch.get("started_at"),
        "phases": per_phase,
        "measured_phases": [p for p in PHASES if p in per_phase],
        "unmeasured_phases": [p for p in PHASES if p not in per_phase],
        "facts": facts,
        "recorded_wall_ms": wall_ms,
    }


def render(rep):
    lines = ["批次计时报告：%s（起始 %s）" % (rep["batch_id"] or "?", rep["started_at"] or "?")]
    lines.append("  阶段           次数     合计ms      中位ms      末次ms")
    for phase in PHASES:
        row = rep["phases"].get(phase)
        if row:
            lines.append("  %-14s %3d %10d %11d %11d"
                         % (phase, row["count"], row["total_ms"], row["median_ms"], row["last_ms"]))
    if rep["unmeasured_phases"]:
        lines.append("  未记录阶段（**没测 ≠ 零耗时**）：%s" % "、".join(rep["unmeasured_phases"]))
    if rep["facts"]:
        lines.append("  批次事实：%s" % "；".join("%s=%s" % (k, v) for k, v in sorted(rep["facts"].items())))
    lines.append("  记录墙钟（首末记录时间差，仅供粗看，含等待审批与人工停顿）：%s"
                 % ("未测得" if rep["recorded_wall_ms"] is None else "%d ms" % rep["recorded_wall_ms"]))
    lines.append("  注：LLM 生成耗时来自操作者秒表口径，不由本工具自动采集；未记阶段请如实报「未实测」。")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="批次分步计时器（JSONL）")
    ap.add_argument("--file", required=True, help="trace JSONL 路径（追加写）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="记录批次开始")
    p_start.add_argument("--batch-id", required=True)
    p_start.add_argument("--model")
    p_start.add_argument("--contract-version", dest="contract_version")

    for name in ("begin", "end"):
        p = sub.add_parser(name, help="阶段%s" % ("开始" if name == "begin" else "结束"))
        p.add_argument("--phase", required=True)
        if name == "begin":
            p.add_argument("--note", help="测量口径（≤%d 字，不写提示词）" % NOTE_MAX)

    p_set = sub.add_parser("set", help="写一条批次事实（白名单键）")
    p_set.add_argument("--phase", required=True)
    p_set.add_argument("--key", required=True)
    p_set.add_argument("--value", required=True)

    p_rep = sub.add_parser("report", help="汇总报告")
    p_rep.add_argument("--json", help="同时把结构化报告写到该路径")

    a = ap.parse_args()
    if a.cmd == "start":
        rec = start_record(a.batch_id, model=a.model, contract_version=a.contract_version)
        append_record(a.file, rec)
        print("已记录批次 %s（%s）→ %s" % (a.batch_id, rec["started_at"], a.file))
    elif a.cmd == "begin":
        rec = phase_begin(a.file, a.phase, note=a.note)
        print("begin %s @%s" % (a.phase, rec["at"]))
    elif a.cmd == "end":
        rec = phase_end(a.file, a.phase)
        print("end   %s duration=%d ms" % (a.phase, rec["duration_ms"]))
    elif a.cmd == "set":
        rec = set_fact(a.file, a.phase, a.key, a.value)
        print("set   %s.%s = %s" % (a.phase, rec["key"], rec["value"]))
    else:
        rep = report(read_records(a.file))
        print(render(rep))
        if a.json:
            io.open(a.json, "w", encoding="utf-8", newline="").write(
                json.dumps(rep, ensure_ascii=False, indent=1) + "\n")
            print("→ 已写 %s" % a.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
