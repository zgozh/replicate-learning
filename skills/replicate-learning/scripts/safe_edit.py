# -*- coding: utf-8 -*-
"""围栏安全编辑助手（血证 H14 的直接产物）——改讲解文件只用这两种操作，杜绝"围栏被替换掉"。

**为什么它随技能发布、而不是留在某个会话的临时目录里**：
改讲解最自然的动作是"把这一段整体换成新的"，而 H14 那次事故正是整段替换把开闭栅栏一起吃掉：
围栏**总数仍是偶数** → 闸门 ⓪ 只查奇偶照样 PASS；被吞的正文 lang 为空 → ①②③④ 整体跳过 →
**六组全绿，但第 4 节正文全被吞进一个代码块**。护栏必须比"人的记性"更先到场。

核心护栏：`safe_replace_range()` 比对"被替换区间"与"替换体"的**围栏事件序列**
（每行是开 / 闭 / 块内带标签，各带语言标签）；两者不一致**直接拒绝执行**并打印差异。

库用法（写驱动脚本时）：
    from safe_edit import load, save, insert_before, safe_replace_range
    lines = load(LEC)
    insert_before(lines, "### 6.2 ", block)      # 首选：只插入，不碰任何旧行
    save(lines, LEC)                             # tmpnew → os.replace

命令行用法（**默认 dry-run，加 --apply 才写盘**）：
    python safe_edit.py --check FILE
    python safe_edit.py --file FILE --insert-before "### 6.2 " --block block.txt [--apply]
    python safe_edit.py --file FILE --replace 120 180 --block block.txt [--apply]

--apply 会先留一份 `FILE.bak`（只在不存在时写，保住"第一次编辑之前"的原样），写盘后立即复检围栏配对。
"""
import argparse
import os
import re
import sys

FENCE = re.compile(r"^(\s*)(`{3,})\s*([A-Za-z0-9_+-]*)\s*$")
H3 = re.compile(r"^###\s")


def fence_seq(lines):
    """返回该行序列的围栏"事件序列" [(行序号, 'open'/'close'/'open?', 语言标签)] 与"结束时是否在块内"。

    'open?' = 块内又出现带语言标签的围栏行 —— 这本身就是破损态（H14 的 A 类），也参与比对。
    """
    inside = False
    out = []
    for i, l in enumerate(lines):
        m = FENCE.match(l)
        if not m:
            continue
        if not inside:
            inside = True
            out.append((i, "open", m.group(3)))
        else:
            if m.group(3):
                out.append((i, "open?", m.group(3)))     # 块内带标签 → 异常态
            else:
                inside = False
                out.append((i, "close", ""))
    return out, inside


def scan_fences(lines):
    """围栏配对体检：返回 (问题列表, 事件序列)。三类与闸门 ⓪ 的 `fence_scan` 同口径——
    A 块内又出现带语言标签的围栏 / D 结束时仍未闭合 / H3 `### ` 标题落在块内。
    （权威判定仍以 `gate_lecture.py` 的 ⓪ 为准；本函数用于改完立即自检，不必等闸门跑完。）"""
    issues = []
    events = []
    inside = False
    opened_at = 0
    for i, l in enumerate(lines, 1):
        m = FENCE.match(l)
        if m:
            if not inside:
                inside, opened_at = True, i
                events.append((i, "open", m.group(3)))
            elif m.group(3):
                issues.append("A 块内又出现带语言标签的围栏  :%d  %s" % (i, l.strip()[:60]))
                events.append((i, "open?", m.group(3)))
            else:
                inside = False
                events.append((i, "close", ""))
            continue
        if inside and H3.match(l):
            issues.append("H3 `### ` 标题落在代码块内  :%d  %s" % (i, l.strip()[:60]))
    if inside:
        issues.append("D 文件结束时围栏仍未闭合（块从 :%d 开始）" % opened_at)
    return issues, events


def load(path):
    return open(path, encoding="utf-8").read().split("\n")


def save(lines, path, backup=True):
    """tmpnew → os.replace（禁止直接 open(path,'w') 写长内容：中断会留下半截文件）。"""
    if backup:
        bak = path + ".bak"
        if not os.path.exists(bak):
            with open(bak, "wb") as f:
                f.write(open(path, "rb").read())
    tmp = path + ".tmpnew"
    open(tmp, "w", encoding="utf-8", newline="").write("\n".join(lines))
    os.replace(tmp, path)


def insert_before(lines, anchor_prefix, block):
    """【首选操作】在锚点行之前插入；只插入，不碰任何旧行。锚点必须唯一命中。"""
    hits = [i for i, l in enumerate(lines) if l.startswith(anchor_prefix)]
    if len(hits) != 1:
        raise SystemExit("[ABORT] 锚点 %r 命中 %d 处（应为 1）" % (anchor_prefix[:40], len(hits)))
    at = hits[0]
    while at > 0 and lines[at - 1].strip() == "":
        del lines[at - 1]
        at -= 1
    lines[at:at] = block.strip("\n").split("\n") + [""]


def safe_replace_range(lines, a, b, body):
    """替换 [a,b]（1-based，闭区间）。护栏：围栏事件序列必须与替换体一致，否则拒绝执行。"""
    old = lines[a - 1:b]
    new = body.strip("\n").split("\n")
    so, oo = fence_seq(old)
    sn, on = fence_seq(new)
    if [x[1:] for x in so] != [x[1:] for x in sn] or oo != on:
        raise SystemExit(
            "[ABORT] 围栏序列不一致，拒绝替换（血证 H14）\n"
            "   被替换区间 :%d-%d 的围栏事件 = %s（结束时%s）\n"
            "   替换体的围栏事件     = %s（结束时%s）\n"
            "   → 若区间跨了围栏，替换体必须原样把开闭栅栏写回；否则请改用 insert_before()"
            % (a, b, [x[1:] for x in so], "在块内" if oo else "块外",
               [x[1:] for x in sn], "在块内" if on else "块外"))
    lines[a - 1:b] = new


def _report(path, before, after):
    print("   围栏事件：改前 %d 个 → 改后 %d 个" % (len(before[1]), len(after[1])))
    if after[0]:
        print("   ⚠ 改后仍有配对问题：")
        for x in after[0][:8]:
            print("      " + x)
    elif len(after[0]) > len(before[0]):
        print("   ⚠ 问题数增加了，建议回滚（.bak 在旁）")
    else:
        print("   ✓ 围栏配对无问题")


def main():
    ap = argparse.ArgumentParser(description="围栏安全编辑 / 体检（默认 dry-run）")
    ap.add_argument("--file")
    ap.add_argument("--check", metavar="FILE")
    ap.add_argument("--insert-before", metavar="锚点前缀")
    ap.add_argument("--replace", nargs=2, type=int, metavar=("A", "B"))
    ap.add_argument("--block", metavar="替换体文本文件")
    ap.add_argument("--apply", action="store_true", help="真正写盘（缺省只预览）")
    a = ap.parse_args()

    if a.check:
        lines = load(a.check)
        issues, events = scan_fences(lines)
        print("== 围栏体检 %s：围栏事件 %d 个（开 %d / 闭 %d）"
              % (os.path.basename(a.check), len(events),
                 sum(1 for e in events if e[1] == "open"), sum(1 for e in events if e[1] == "close")))
        if issues:
            print("   [FAIL] %d 处：" % len(issues))
            for x in issues:
                print("      " + x)
            return 1
        print("   [OK ] 配对无问题（权威判定仍以 gate_lecture ⓪ 为准）")
        return 0

    if not a.file or (not a.insert_before and not a.replace):
        ap.error("需要 --file 加 --insert-before 或 --replace（或单独用 --check）")
    if not a.block:
        ap.error("需要 --block <替换体文本文件>")
    block = open(a.block, encoding="utf-8").read()
    lines = load(a.file)
    before = scan_fences(lines)

    if a.insert_before:
        hits = [i for i, l in enumerate(lines) if l.startswith(a.insert_before)]
        print("== 在 :%s 之前插入 %d 行（锚点命中 %d 处）"
              % (hits[0] + 1 if len(hits) == 1 else "?", block.strip().count("\n") + 1, len(hits)))
        insert_before(lines, a.insert_before, block)
    else:
        x, y = a.replace
        print("== 替换 :%d-%d（%d 行）→ %d 行" % (x, y, y - x + 1, block.strip().count("\n") + 1))
        safe_replace_range(lines, x, y, block)

    after = scan_fences(lines)
    _report(a.file, before, after)
    print("   预览（前 12 行）：")
    for l in block.strip("\n").split("\n")[:12]:
        print("      " + l[:100])
    if not a.apply:
        print("   （dry-run：未写盘。确认无误后加 --apply）")
        return 0
    save(lines, a.file)
    print("   → 已写盘（备份 %s.bak）" % os.path.basename(a.file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
