#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""源码块注入器 —— 把讲解里指定的代码块替换成仓库源文件的**逐字**内容（自动带 `// :L<真实行号>`）。

**为什么它是"写新批次"的主力工具**（而不只是修复用）：① 正向保真 100% 与 ④ 行号零漂移，
在正确的流程里是**注入出来的**，不是事后修出来的——由脚本从源文件逐行取码、逐行打真实行号，
"手打行号打错"这件事从源头不发生。
血证 H17：它原本住在宿主项目的 `NOTES/` 下（NOTES 不入 git、换项目即无），而"整块重注入"是
写新批次和修旧批次都会反复用到的动作 → 随技能发布。

用法：
    python inject_source.py <讲解.md> <plan.json> --src <仓库根> [--dry]

plan.json 结构：
{
  "blocks": [
    {
      "anchor": "6.2 BlockAwareChunkerDispatcher",   # 代码块所属**小节标题**的片段（必须唯一命中）
      "contains": "public class Foo",                 # 可选：块体内必须也含这个片段
                                                      #   —— 加 ⑤ 之后同一小节常有两块（源码块 + 【怎么用】合成片段），
                                                      #      标题锚点就不够用了，用它把目标块钉死
      "lang": "java",                                 # 代码围栏语言，缺省 java
      "src": "rag/src/main/java/.../Foo.java",        # 仓库相对路径（必须真实存在）
      "start": 17,                                    # 起始行（1-based，含）；省略 = 整文件
      "end": 103,                                     # 结束行（1-based，含）；省略 = 整文件
      "anno": {"40": "交给 Spring 管理，构造器参数由容器注入"}   # 源文件行号 -> 教材注释（写成 ←教材：…）
    }
  ]
}

硬约束（防编造 + 防 H14）：
  - 代码内容 **100% 来自 src 文件**，本脚本不接受任何手写代码；
  - 每个块的每一行（去掉我们自己加的标注后）必须仍逐字来自 src 的第 no 行，否则拒绝写入；
  - 替换走 `safe_edit.safe_replace_range`（比对围栏事件序列）——区间跨围栏而替换体没把围栏写回 → 直接拒绝
    （血证 H14：整段替换把开闭栅栏吃掉，围栏总数仍是偶数，闸门 ⓪ 照样 PASS）；
  - 写入 tmpnew → 三道校验（行数未骤降 / 围栏配对无问题 / 注入内容确实落盘）→ `os.replace`。
"""
import argparse
import io
import tokenize
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from safe_edit import load, save, safe_replace_range, scan_fences, FENCE  # noqa: E402

# ── 注释前缀按语言取（2.22，工具修） ─────────────────────────────────────────
# 为什么必须按语言取：原实现把前缀**写死成 `//`**，于是把它用在 Python / Shell / YAML 上会产出
# **非法语法**——例如 `PORT="${1:-60}"  // :L17`：在 bash 里 `//` 不是注释，是"执行一个叫 `//` 的命令"。
# 实测（deer-flow，2026-09-16）首跑即撞上，只能临时改用项目内的替代注入器；
# 本处修正是把它收回技能内（"每个新项目都得重建一遍替代件"正是血证 H17 的同一个坑）。
HASH_LANGS = {"bash", "sh", "shell", "zsh", "python", "py", "yaml", "yml", "toml", "conf", "ini",
              "dockerfile", "dotenv", "makefile", "mk", "make", "text", "plaintext", "txt"}
DASH_LANGS = {"sql", "haskell", "lua"}
NO_ANNO_LANGS = {"cmd", "bat", "batch"}   # cmd 的 `rem`/`& rem` 插进 `for (...)` 块内会破坏解析


def anno_prefix(lang):
    """按语言返回注释前缀；返回 None 表示该语言**不做内联标注**（加了会改变语义）。"""
    l = (lang or "").lower()
    if l in NO_ANNO_LANGS:
        return None
    if l in HASH_LANGS:
        return "#"
    if l in DASH_LANGS:
        return "--"
    return "//"          # 缺省（C 系与未知语言沿用旧行为，保证存量 JAVA 批次一字不变）


def read_lines(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split("\n")


def python_string_lines(lines):
    """Return source lines inside multiline Python strings (including docstrings)."""
    protected = set()
    fstring_start = None
    try:
        tokens = tokenize.generate_tokens(io.StringIO("\n".join(lines)).readline)
        for token in tokens:
            if token.type == tokenize.STRING and token.end[0] > token.start[0]:
                protected.update(range(token.start[0], token.end[0] + 1))
            elif token.type == getattr(tokenize, "FSTRING_START", -1):
                fstring_start = token.start[0]
            elif token.type == getattr(tokenize, "FSTRING_END", -1) and fstring_start is not None:
                if token.end[0] > fstring_start:
                    protected.update(range(fstring_start, token.end[0] + 1))
                fstring_start = None
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # An incomplete source file can still be quoted faithfully; omit inline notes.
        return set(range(1, len(lines) + 1))
    return protected


def parse(path):
    """返回 (全部行, [(开围栏索引0based, 语言, 内容行, 最近标题)])"""
    lines = read_lines(path)
    out, cur, lang, start = [], None, None, 0
    for i, l in enumerate(lines):
        m = FENCE.match(l)
        if cur is None:
            if m:
                cur, lang, start = [], (m.group(3) or "").lower(), i
        else:
            if m and not m.group(3):
                title = ""
                for j in range(start - 1, -1, -1):
                    if re.match(r"^#{2,5} ", lines[j]):
                        title = lines[j]
                        break
                out.append((start, lang, cur, title))
                cur = None
            else:
                cur.append(l)
    return lines, out


def build_block(src_root, rel, a, b, anno_in, lang):
    """从源文件逐行取码 → 生成带真实行号的代码块"""
    src = os.path.join(src_root, rel)
    if not os.path.isfile(src):
        raise SystemExit("[ABORT] 源文件不存在：%s" % src)
    lines = read_lines(src)
    if a is None:
        a, b = 1, len(lines)
        while b > a and lines[b - 1].strip() == "":
            b -= 1
    if not (1 <= a <= b <= len(lines)):
        raise SystemExit("[ABORT] 行范围非法：%s %s-%s（文件共 %d 行）" % (rel, a, b, len(lines)))
    # anno 的键必须是**单行号**；区间标注（`// :L21-25`）取首行、非法键告警跳过（别让一个坏键崩掉注入）
    anno = {}
    for k, v in (anno_in or {}).items():
        ks = str(k).split("-")[0].strip()
        if ks.isdigit():
            anno[ks] = v
        else:
            print("   ⚠ anno 键 %r 不是行号（区间请写首行号），已忽略" % k)
    stray = [k for k in anno if not (a <= int(k) <= b)]
    if stray:
        print("   ⚠ anno 里有 %s 不在注入范围 %d-%d 内，这些注释会被忽略（检查是否写错了行号）"
              % ("、".join(sorted(stray)), a, b))
    body = lines[a - 1:b]
    while body and body[-1].strip() == "":
        body.pop()
    prefix = anno_prefix(lang)
    protected = python_string_lines(lines) if (lang or "").lower() in {"python", "py"} else set()
    out, skipped = [], 0
    for off, ln in enumerate(body):
        no = a + off
        if ln.strip() == "":
            out.append(ln)
            continue
        # 两种"不能标"的情况（2.22 新增，均为实测踩到）：
        # ① 该语言不支持行尾注释（cmd）：标了会破坏 `for (...)` 块的解析；
        # ② 行尾是反斜杠续行（shell/bash/ts 的常见写法）：bash **先处理续行再处理注释**，
        #    追加任何字符都会让续行断裂、改变语义（实测 serve.sh 有 12 行、dev-entrypoint.sh 有 10 行）。
        # 这两种行仍然**逐字注入**（保真不受影响），只是不带行号标注与教材注释。
        if prefix is None or ln.rstrip().endswith("\\") or no in protected:
            out.append(ln)
            skipped += 1
            continue
        note = anno.get(str(no))
        out.append("%s  %s :L%d  ←教材：%s" % (ln, prefix, no, note) if note
                   else "%s  %s :L%d" % (ln, prefix, no))
    if skipped:
        print("   [INFO] %s：%d 行不做内联标注（语言限制、反斜杠续行或 Python 多行字符串）" % (rel, skipped))
    return ["```" + lang] + out + ["```"], [(rel, a + off, ln) for off, ln in enumerate(body)]


def main():
    ap = argparse.ArgumentParser(description="把讲解里的代码块替换成源文件逐字内容（带真实行号）")
    ap.add_argument("lecture")
    ap.add_argument("plan")
    ap.add_argument("--src", default=os.getcwd(), help="仓库根目录（缺省=当前目录）")
    ap.add_argument("--dry", action="store_true", help="只报告将要替换什么")
    ap.add_argument("--skip-verify", action="store_true",
                    help="跳过「每行确实来自源文件」的逐行复核（不推荐，仅用于排查）")
    a = ap.parse_args()
    src_root = os.path.abspath(a.src)
    md = a.lecture if os.path.isabs(a.lecture) else os.path.join(src_root, a.lecture)
    plan = json.load(open(a.plan, encoding="utf-8"))
    lines, blocks = parse(md)
    before = scan_fences(lines)

    repl = []
    for spec in plan["blocks"]:
        lang = spec.get("lang", "java")
        hits = [k for k, b in enumerate(blocks)
                if spec["anchor"] in b[3] and b[1] == lang
                and (not spec.get("contains") or spec["contains"] in "\n".join(b[2]))]
        if len(hits) != 1:
            raise SystemExit("[ABORT] anchor %r%s 命中 %d 个 %s 代码块（应为 1）\n   候选小节：%s"
                             % (spec["anchor"], (" + contains %r" % spec["contains"]) if spec.get("contains") else "",
                                len(hits), lang,
                                [blocks[k][3].strip()[:60] for k in hits] or ["（无：检查 anchor/lang/contains）"]))
        k = hits[0]
        new_block, src_lines = build_block(src_root, spec["src"], spec.get("start"), spec.get("end"),
                                           spec.get("anno"), lang)
        if not a.skip_verify:
            srclines = read_lines(os.path.join(src_root, spec["src"]))
            for rel, no, ln in src_lines:
                if ln not in srclines[no - 1]:
                    raise SystemExit("[ABORT] 行号错位：%s:%d\n   注入：%r\n   原文：%r"
                                     % (rel, no, ln, srclines[no - 1]))
        repl.append((k, new_block, len(blocks[k][2]), spec["src"]))

    # 从后往前替换（用 safe_edit 的围栏护栏；低索引不受高索引改动影响）
    out_lines = list(lines)
    for k, new_block, _old_len, src in sorted(repl, key=lambda x: -x[0]):
        a0 = blocks[k][0]                                  # 开围栏索引（0based）
        b0 = a0 + 1 + len(blocks[k][2])                    # 闭围栏索引（0based）
        safe_replace_range(out_lines, a0 + 1, b0 + 1, "\n".join(new_block))

    if a.dry:
        print("[dry] 将替换 %d 个代码块（未写盘）：" % len(repl))
        for k, nb, old_len, src in repl:
            print("   %-56s %2d 行 → %2d 行  %s"
                  % (blocks[k][3].strip()[:54], old_len, len(nb) - 2, src))
        return 0

    # 三道校验
    if len(out_lines) < len(lines) * 0.5:
        raise SystemExit("[ABORT] 新文件行数骤降，疑似截断")
    after = scan_fences(out_lines)
    if after[0]:
        raise SystemExit("[ABORT] 改后围栏配对有问题：\n   " + "\n   ".join(after[0][:6]))
    text = "\n".join(out_lines)
    for k, nb, _o, src in repl:
        if nb[1].strip() and nb[1].strip() not in text:
            raise SystemExit("[ABORT] 注入内容未落盘：" + src)

    save(out_lines, md, backup=True)
    print("已注入 %d 个代码块 → %s" % (len(repl), os.path.basename(md)))
    for k, nb, old_len, src in repl:
        print("   %-54s %2d 行 → %2d 行  %s"
              % (blocks[k][3].strip()[:52], old_len, len(nb) - 2, src))
    print("总行数 %d → %d；围栏事件 %d → %d"
          % (len(lines), len(out_lines), len(before[1]), len(after[1])))
    print("下一步：python scripts/gate_lecture.py %s --src %s" % (os.path.basename(md), src_root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
