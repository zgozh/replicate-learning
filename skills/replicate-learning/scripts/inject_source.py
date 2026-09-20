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
      "slot": "source:90d042e8:6.8",                  # 【首选】稳定槽位 ID（new_batch.py --plan 生成）
      "anchor": "6.2 BlockAwareChunkerDispatcher",   # 旧寻址：代码块所属**小节标题**的片段（必须唯一命中）
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

**两种寻址方式（方案 §3.3）**：
  · **槽位（首选）**：讲解里有一行槽位标记
    `<!-- src-slot id="source:90d042e8:6.8" path="rag/.../Foo.java" lines="17-103" sha256="…" -->`
    紧跟一个代码块占位。块的**身份 = 槽位 ID + 源路径**；标题、`contains`、块内已替换过的文本都不参与寻址，
    因此"注释计划补几条再重注入"不需要再去猜旧的占位串，也不会因为标题改了字就找不到块。
    注入前核对标记里的 `path`/`lines`/`sha256`：与计划不符、或源文件 hash 已变 → **拒绝写入**（fail closed），
    不会"悄悄把旧行号套到改了内容的源码上"。
  · **旧寻址（anchor/contains）**：兼容既有批次。若讲解里没有该槽位标记，但计划里给了 anchor，
    自动退回旧逻辑并**打印告警**（提示这是兼容路径，不是本次设计的用法）。

硬约束（防编造 + 防 H14）：
  - 代码内容 **100% 来自 src 文件**，本脚本不接受任何手写代码；
  - 每个块的每一行（去掉我们自己加的标注后）必须仍逐字来自 src 的第 no 行，否则拒绝写入；
  - 替换走 `safe_edit.safe_replace_range`（比对围栏事件序列）——区间跨围栏而替换体没把围栏写回 → 直接拒绝
    （血证 H14：整段替换把开闭栅栏吃掉，围栏总数仍是偶数，闸门 ⓪ 照样 PASS）；
  - 写入 tmpnew → 三道校验（行数未骤降 / 围栏配对无问题 / 注入内容确实落盘）→ `os.replace`。
"""
import argparse
import hashlib
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


# ── 稳定源码槽位（方案 §3.3） ────────────────────────────────────────────────
SLOT_RE = re.compile(r"<!--\s*src-slot\s+([^>]*?)-->")
# 属性名允许数字（`sha256`）——第一版写成 `[a-zA-Z_]+`，于是 sha256 静默读不出来、
# 源文件改动检查形同虚设（自测 `test_drifted_source_hash_refuses_the_write` 抓到）。
SLOT_ATTR_RE = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*)="([^"]*)"')


def parse_slot_line(line):
    m = SLOT_RE.search(line)
    if not m:
        return None
    attrs = dict(SLOT_ATTR_RE.findall(m.group(1)))
    return attrs if attrs.get("id") else None


class SlotMissing(SystemExit):
    """槽位标记**找不到**——这一种可以退回 anchor 旧寻址（兼容旧分片）。

    与"找到了但核对不过"（`verify_slot` 抛的普通 SystemExit）严格区分：
    **源文件 hash 已变、路径/行段不符，绝不允许降级成旧寻址继续写**——
    那正是"悄悄把旧行号套到改过的源码上"的形态（方案 §3.3 明确禁止）。
    """


def find_slot(lines, slot_id):
    """定位槽位标记（只认**围栏外**的标记行）→ (0based 行号, 属性)。零命中/重名 = fail closed。"""
    inside, hits = False, []
    for i, l in enumerate(lines):
        if FENCE.match(l):
            inside = not inside
            continue
        if inside:
            continue
        attrs = parse_slot_line(l)
        if attrs and attrs["id"] == slot_id:
            hits.append((i, attrs))
    if len(hits) != 1:
        raise SlotMissing("[ABORT] 槽位 %r 命中 %d 处（应为 1）——槽位 ID 是块身份，"
                          "重名或落空都必须先修骨架/分片" % (slot_id, len(hits)))
    return hits[0]


def slot_fence_span(lines, marker_index):
    """槽位标记之后紧跟的那个代码块 → (开围栏 0based, 闭围栏 0based)。找不到 = fail closed。"""
    open_at = None
    for j in range(marker_index + 1, len(lines)):
        if lines[j].strip() == "":
            continue
        if FENCE.match(lines[j]):
            open_at = j
        break
    if open_at is None:
        raise SystemExit("[ABORT] 槽位标记 :%d 之后不是代码块（骨架/分片被改坏了——"
                         "标记必须紧跟它要注入的那个围栏块）" % (marker_index + 1))
    for k in range(open_at + 1, len(lines)):
        m = FENCE.match(lines[k])
        if m and not m.group(3):
            return open_at, k
    raise SystemExit("[ABORT] 槽位标记 :%d 之后的代码块没有闭合围栏" % (marker_index + 1))


def verify_slot(spec, attrs, src_root):
    """核对槽位标记与计划：路径/行段/hash 三者不符即拒绝写入（防"悄悄套旧行号"）。"""
    problems = []
    rel = spec["src"]
    if attrs.get("path") and attrs["path"] != rel:
        problems.append("槽位标记 path=%s ≠ 计划 src=%s" % (attrs["path"], rel))
    want_lines = "%s-%s" % (spec.get("start") or 1, spec.get("end") or len(read_lines(os.path.join(src_root, rel))))
    if attrs.get("lines") and attrs["lines"] != want_lines:
        problems.append("槽位标记 lines=%s ≠ 计划行段=%s" % (attrs["lines"], want_lines))
    if attrs.get("sha256"):
        real = hashlib.sha256(open(os.path.join(src_root, rel), "rb").read()).hexdigest()
        if real != attrs["sha256"]:
            problems.append("源文件 hash 已变（槽位记录 %s… / 实际 %s…）——"
                            "拒绝把旧行号悄悄套到改过的源码上" % (attrs["sha256"][:12], real[:12]))
    if problems:
        raise SystemExit("[ABORT] 槽位 %s 与计划不一致：\n   - %s" % (attrs.get("id"), "\n   - ".join(problems)))


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


def parse_lines(lines):
    """返回 (全部行, [(开围栏索引0based, 语言, 内容行, 最近标题)])。

    内存版：`batch_build.py` 要在**不落中间文件**的前提下解析"刚组装出来的正文"，
    所以把解析与读文件分开——同一套围栏/标题规则，只有一处实现。
    """
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


def parse(path):
    """返回 (全部行, [(开围栏索引0based, 语言, 内容行, 最近标题)])"""
    return parse_lines(read_lines(path))


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


def plan_replacements(lines, blocks, plan, src_root, skip_verify=False):
    """把计划解析成一串替换动作（**不改动 lines**）。

    返回 (repl, legacy_fallback)：repl 每项是 (mode, 开围栏 0based, 闭围栏 0based, 新块行, 源路径, 标签)。
    抽成函数是为了让 `batch_build.py` 复用同一套寻址/校验——预检、构建、注入若各写一套，
    就又回到"两套口径"的老问题（方案 §3.3 的核心诉求）。
    """
    repl, legacy_fallback = [], []
    for spec in plan["blocks"]:
        lang = spec.get("lang", "java")
        label = spec.get("slot") or spec.get("anchor") or "?"
        new_block, src_lines = build_block(src_root, spec["src"], spec.get("start"), spec.get("end"),
                                           spec.get("anno"), lang)
        if not skip_verify:
            srclines = read_lines(os.path.join(src_root, spec["src"]))
            for rel, no, ln in src_lines:
                if ln not in srclines[no - 1]:
                    raise SystemExit("[ABORT] 行号错位：%s:%d\n   注入：%r\n   原文：%r"
                                     % (rel, no, ln, srclines[no - 1]))
        if spec.get("slot"):
            try:
                mi, attrs = find_slot(lines, spec["slot"])
                verify_slot(spec, attrs, src_root)
                o0, c0 = slot_fence_span(lines, mi)
                repl.append(("slot", o0, c0, new_block, spec["src"], label))
                continue
            except SlotMissing as exc:
                if not spec.get("anchor"):
                    raise
                # 兼容旧批：讲解里**没有**槽位标记（分片是旧格式）→ 按旧寻址并告警，不静默换口径。
                # 注意只接 SlotMissing：verify_slot 的 hash/路径不符必须硬失败（不降级）。
                legacy_fallback.append((spec["slot"], str(exc).split("\n")[0]))
        anchor = spec.get("anchor")
        if not anchor:
            raise SystemExit("[ABORT] 计划块 %r 既没有 slot 也没有 anchor——无法定位要注入的围栏块" % label)
        hits = [k for k, b in enumerate(blocks)
                if anchor in b[3] and b[1] == lang
                and (not spec.get("contains") or spec["contains"] in "\n".join(b[2]))]
        if len(hits) != 1:
            raise SystemExit("[ABORT] anchor %r%s 命中 %d 个 %s 代码块（应为 1）\n   候选小节：%s"
                             % (anchor, (" + contains %r" % spec["contains"]) if spec.get("contains") else "",
                                len(hits), lang,
                                [blocks[k][3].strip()[:60] for k in hits] or ["（无：检查 anchor/lang/contains）"]))
        k = hits[0]
        a0 = blocks[k][0]                                  # 开围栏索引（0based）
        b0 = a0 + 1 + len(blocks[k][2])                    # 闭围栏索引（0based）
        repl.append(("anchor", a0, b0, new_block, spec["src"], label))
    return repl, legacy_fallback


def apply_replacements(lines, repl):
    """从后往前替换**整个围栏块**（含开闭栅栏）→ 新行列表（不改动入参）。

    `safe_replace_range` 会比对围栏事件序列：少写回一个栅栏就当场拒绝（血证 H14）；
    从后往前替换保证低索引不受高索引改动影响。
    """
    out_lines = list(lines)
    for _mode, o0, c0, new_block, _src, _label in sorted(repl, key=lambda x: -x[1]):
        safe_replace_range(out_lines, o0 + 1, c0 + 1, "\n".join(new_block))
    return out_lines


def main():
    from lecture_checks import configure_stdio      # stdout 被重定向时按 GBK 编码会崩在打印上
    configure_stdio()
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

    repl, legacy_fallback = plan_replacements(lines, blocks, plan, src_root, a.skip_verify)
    for slot, why in legacy_fallback:
        print("   ⚠ 槽位 %s 在讲解里找不到 → 退回 anchor/contains 旧寻址（兼容旧分片）：%s"
              % (slot, why[:110]))

    out_lines = apply_replacements(lines, repl)

    if a.dry:
        print("[dry] 将替换 %d 个代码块（未写盘）：" % len(repl))
        for mode, o0, c0, nb, src, label in repl:
            print("   [%s] %-44s %2d 行 → %2d 行  %s"
                  % (mode, str(label)[:44], max(0, c0 - o0 - 1), len(nb) - 2, src))
        return 0

    # 三道校验
    if len(out_lines) < len(lines) * 0.5:
        raise SystemExit("[ABORT] 新文件行数骤降，疑似截断")
    after = scan_fences(out_lines)
    if after[0]:
        raise SystemExit("[ABORT] 改后围栏配对有问题：\n   " + "\n   ".join(after[0][:6]))
    text = "\n".join(out_lines)
    for _mode, _o, _c, nb, src, _label in repl:
        if nb[1].strip() and nb[1].strip() not in text:
            raise SystemExit("[ABORT] 注入内容未落盘：" + src)

    save(out_lines, md, backup=True)
    print("已注入 %d 个代码块 → %s（槽位 %d 个 / 旧寻址 %d 个）"
          % (len(repl), os.path.basename(md),
             sum(1 for r in repl if r[0] == "slot"), sum(1 for r in repl if r[0] == "anchor")))
    for mode, o0, c0, nb, src, label in repl:
        print("   [%-6s] %-42s %2d 行 → %2d 行  %s"
              % (mode, str(label)[:42], max(0, c0 - o0 - 1), len(nb) - 2, src))
    print("总行数 %d → %d；围栏事件 %d → %d"
          % (len(lines), len(out_lines), len(before[1]), len(after[1])))
    print("下一步：python scripts/gate_lecture.py %s --src %s" % (os.path.basename(md), src_root))
    return 0


def main_with(argv):
    """以给定 argv 调 main()（首位是程序名占位）——测试与编排脚本复用同一条入口，不再另写一套。"""
    old = sys.argv
    sys.argv = list(argv)
    try:
        return main()
    finally:
        sys.argv = old


if __name__ == "__main__":
    sys.exit(main())
