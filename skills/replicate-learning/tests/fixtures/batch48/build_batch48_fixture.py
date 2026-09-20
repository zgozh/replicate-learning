#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""重建 batch48 回归夹具（方案 §3.1 第 2 条：用当前第48批建回归夹具，录制**输入**与**结论**）。

**数据来源（只读，不修改任何原始资料）**：
  · 源码 8 件：`D:\\ragent-official\\rag\\src\\main\\java\\com\\nageoffer\\ai\\ragent\\core\\chunk\\blockaware\\*.java`
  · 清单 `b48_manifest.json`、首轮/修复后注释计划、5 份分片：`D:\\ragent-official\\logs\\_tools_20260920\\`
  · **首轮**注释计划（注入前那一版，后来被覆盖）：只在会话导出 `test.md` 里留了一份——
    本脚本从该导出的 write 调用里把它取回来（`test.md` 是用户原始记录，本脚本只读）。
  · 期望结论 `expectations.json`：取自同一导出的闸门实跑输出（★ 签名缺口 3 个 + 密度连段 5 处）。

**为什么夹具要重启一遍就能重建**：夹具一旦"只有结果没有来源"，下一个人无法判断它是否还代表真实批次。
本脚本把"从哪来、怎么取"写成代码；`--check` 只比对现状，不写盘。

用法：
    python build_batch48_fixture.py [--ragent D:\\ragent-official] [--export ../../../../../test.md] [--check]
"""
import argparse
import hashlib
import io
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCKAWARE = os.path.join("rag", "src", "main", "java", "com", "nageoffer", "ai", "ragent",
                          "core", "chunk", "blockaware")
B48_FILES = ["CodeChunker.java", "HeadingChunker.java", "HeadingHandler.java", "HtmlTableChunker.java",
             "ImageChunker.java", "ListChunker.java", "ParagraphChunker.java", "TableChunker.java"]

# 首轮闸门实跑（b48 会话导出中的工具输出，逐字抄录的结论，不是本次重算）
EXPECTED = {
    "source": "ragent-official 批次48 会话导出（test.md）中注入后首跑闸门的实跑输出",
    "signature_gaps": {"block": "6.8 TableChunker★", "methods": ["appendRow", "sanitizeCell", "appendSeparator"]},
    "density_runs": [
        {"item": "6.3 ParagraphChunker", "max_run": 8},
        {"item": "6.4 CodeChunker", "max_run": 10},
        {"item": "6.5 ListChunker", "max_run": 10},
        {"item": "6.6 ImageChunker", "max_run": 8},
        {"item": "6.8 TableChunker★", "max_run": 10},
    ],
    "note": "闸门口径：无中文注释的关键行连段 ≥8 即 FAIL（契约 D1）。修复后的计划（*_fixed）应零缺口。",
}


def sha256(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


def extract_r1_plan(export_path):
    """从会话导出里取回**首轮**注释计划（write 调用的 content 字段）。"""
    doc = json.load(io.open(export_path, encoding="utf-8"))
    found = {}

    def walk(node):
        if isinstance(node, dict):
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and '"blocks"' in node and "__INJECT" in node:
            try:
                found[len(node)] = json.loads(node)
            except ValueError:
                pass

    walk(doc)
    if not found:
        raise SystemExit("[ABORT] 导出里找不到注释计划（write content 含 \"blocks\" 与 __INJECT）")
    # 首轮 = 项数最少的那一份（修复后版本会多出若干 anno；本批次为 24 vs 29）
    key = min(found, key=lambda n: sum(len(b.get("anno", {})) for b in found[n]["blocks"]))
    return found[key], {n: sum(len(b.get("anno", {})) for b in v["blocks"]) for n, v in found.items()}


def main():
    ap = argparse.ArgumentParser(description="重建 batch48 回归夹具（只读原始资料）")
    ap.add_argument("--ragent", default=r"D:\ragent-official")
    ap.add_argument("--export", default=os.path.join(HERE, "..", "..", "..", "..", "..", "test.md"))
    ap.add_argument("--check", action="store_true", help="只校验夹具现状，不写盘")
    a = ap.parse_args()

    src_dir = os.path.join(a.ragent, BLOCKAWARE)
    logs = os.path.join(a.ragent, "logs", "_tools_20260920")
    project = os.path.join(HERE, "project", BLOCKAWARE)
    parts_dir = os.path.join(HERE, "parts")

    missing = [p for p in (src_dir, logs) if not os.path.isdir(p)]
    if missing:
        raise SystemExit("[ABORT] 找不到原始资料：%s\n   → 本夹具来自 ragent-official 批次48；"
                         "换机器请用 --ragent 指向该项目，或直接用已提交的夹具（不必重建）"
                         % "、".join(missing))

    if a.check:
        bad = []
        for fn in B48_FILES:
            want = sha256(os.path.join(src_dir, fn))
            got = sha256(os.path.join(project, fn))
            if want != got:
                bad.append(fn)
        print("夹具源码与 ragent-official 现状：%s" % ("一致（%d 件）" % len(B48_FILES) if not bad
                                                  else "不一致：%s" % "、".join(bad)))
        return 1 if bad else 0

    os.makedirs(project, exist_ok=True)
    os.makedirs(parts_dir, exist_ok=True)
    manifest = json.load(io.open(os.path.join(logs, "b48_manifest.json"), encoding="utf-8"))
    files = {}
    for rel, meta in manifest["files"].items():
        base = os.path.basename(rel)
        src = os.path.join(src_dir, base)
        if not os.path.isfile(src):
            raise SystemExit("[ABORT] 源文件缺失：%s" % src)
        digest = sha256(src)
        if digest != meta["sha256"]:
            raise SystemExit("[ABORT] %s 的 sha256 与批次48 清单不一致——源码已演进，"
                             "夹具不能再声称是那一版（请另取快照）" % base)
        shutil.copyfile(src, os.path.join(project, base))
        # 夹具根（= `project/`）刻意镜像 ragent 仓库根：注释计划里的 `src` 字段是
        # `rag/src/main/java/...`（相对 ragent 根）。原批次清单是以 `<ragent>/rag` 为根建的
        # （键无 `rag/` 前缀）——两种根在批次48 里本就并存；夹具统一到 ragent 根，故补回 `rag/`。
        key = rel if rel.startswith("rag/") else "rag/" + rel
        files[key] = {"sha256": digest, "bytes": meta["bytes"]}
    io.open(os.path.join(HERE, "b48_manifest.json"), "w", encoding="utf-8", newline="").write(
        json.dumps({"schema_version": 1, "source_root": ".",
                    "source_revision": manifest.get("source_revision"),
                    "note": "source_root 由 D:\\ragent-official 改写为 '.'（夹具是拷贝，根目录结构镜像 ragent）；"
                            "清单键补回 `rag/` 前缀，使清单与注释计划的 `src` 用同一个根；"
                            "source_revision 保留原批次声明",
                    "files": dict(sorted(files.items()))}, ensure_ascii=False, indent=2) + "\n")

    r1, sizes = extract_r1_plan(a.export)
    io.open(os.path.join(HERE, "b48_inject_plan_r1.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(r1, ensure_ascii=False, indent=1) + "\n")
    shutil.copyfile(os.path.join(logs, "b48_inject_plan.json"),
                    os.path.join(HERE, "b48_inject_plan_fixed.json"))
    for fn in os.listdir(logs):
        if fn.startswith("b48_part") and fn.endswith(".md"):
            shutil.copyfile(os.path.join(logs, fn), os.path.join(parts_dir, fn))

    annos = sum(len(b.get("anno", {})) for b in r1["blocks"])
    EXPECTED["plan_anno_counts"] = sizes
    EXPECTED["first_round_plan_annos"] = annos
    io.open(os.path.join(HERE, "expectations.json"), "w", encoding="utf-8", newline="").write(
        json.dumps(EXPECTED, ensure_ascii=False, indent=1) + "\n")

    print("夹具已重建：%s" % HERE)
    print("  源码 %d 件 / 首轮计划 anno %d 条（导出里的各版本 anno 数：%s）" % (len(files), annos, sizes))
    return 0


if __name__ == "__main__":
    sys.exit(main())
