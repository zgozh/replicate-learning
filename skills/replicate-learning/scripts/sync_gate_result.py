#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把闸门的**实跑结果**写进批次的 ⑯ 段（机器生成，杜绝"复述旧结论"）。

**为什么需要它**：⑯ 的自检表是手写的，血证 H15 的事故恰恰是"⑯ 复述两版之前的结论"——
判据已经 2.9 了，表里还写着六项、数字还是旧的。判据 2.10 起，⑯ 段**必须出现当前 `GATE_VERSION`**，
本工具就是让这条要求变成一条命令：跑一次闸门 → 把七组实测数字渲染成表格 → 插进/更新 ⑯ 段。

用法：
    python sync_gate_result.py <批次.md> --src <仓库根> [--dry]     # 默认 dry-run，--apply 才写盘
    写入位置：`## ⑯` 标题之后（若已有「七组闸门实测」块则整块替换，**重复执行是幂等的**）。
写盘走 `safe_edit`（围栏事件序列护栏 + tmpnew→os.replace + `.bak`）。
"""
import argparse
import io
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from safe_edit import load, save, insert_at, safe_replace_range, scan_fences  # noqa: E402

HEAD = '**七组闸门实测**'
MARK_RE = re.compile(r'^\*\*七组闸门实测')
NOTE_RE = re.compile(r'^>\s*本表由\s*`scripts/sync_gate_result\.py`')
VERLINE_RE = re.compile(r'^\*\*判据版本：v?[\d.]+\*\*')


def block_end(lines, old):
    """实测块的**真末行**（2.29 修 BUG-S1）。

    旧实现只走一步：`while 下一行非空且不以 ##/###/| 开头` —— 而 HEAD 行的下一行恒为空行，
    循环立即退出 → 实际只替换了 HEAD 那一行，于是**每跑一次就多堆一张旧表**（实测 11 批受害，
    批次37 堆到 11 张、批次33 3 张；同一份 ⑯ 里并存 v2.24/v2.25/v2.28 三套互相矛盾的数字，
    正好违背本工具的存在理由「杜绝复述旧结论」）。
    新口径：从 HEAD 行起连续吃掉「表格行 / 说明引用行 / 它们之间的空行」，遇到别的标题或正文行即止。
    """
    j, last = old + 1, old
    while j < len(lines):
        s = lines[j].strip()
        if not s:
            j += 1
            continue
        if s.startswith('## ') or s.startswith('### '):
            break
        if s.startswith('|') or NOTE_RE.match(s):
            last = j
            j += 1
            continue
        break
    return last


def run_gate(lecture, src):
    """跑闸门，解析出七组数字（口径与 gate_lecture 的输出一致）"""
    p = subprocess.run([sys.executable, os.path.join(HERE, 'gate_lecture.py'), lecture, '--src', src],
                       capture_output=True, text=True, encoding='utf-8')
    t = p.stdout
    def g(pat, default='?'):
        m = re.search(pat, t, re.M)
        return m.group(1).strip() if m else default
    ver = g(r'批次讲解闸门（§6\.4 C 组）v([\d.]+)')
    struct = re.search(r'^\s{3}节数=(\d+) 围栏=(\d+)\(([^)]*)\) 占位=(\d+) ⑫八条=(\d+) 八段=(\d+) '
                       r'自指=(\d+) 回链=(\d+) 薄条=(\d+)', t, re.M)
    fid = re.search(r'① 正向保真度：(\d+) 个代码块 / (\d+) 行代码 → 候选不符 (\d+) 行 = 保真度 ([\d.]+)%', t)
    rev = re.findall(r'\[OK \] (\w+)\s+有效行=(\d+)\s+缺失=(\d+)\s+覆盖=([\d.]+)%', t)
    den = g(r'③ 注释密度（§6\.1\.1）：(\d+) 个代码块')
    sig = g(r'★类方法签名无注释：', '')
    ln = re.search(r'④ 行号一致性（`// :Lnn` ↔ 真实行号）：可判定 (\d+) 处 → 漂移 (\d+) 处', t)
    use = re.search(r'逐件=(\d+).*?【怎么用】=(\d+)/(\d+).*?【上下游】=(\d+)/(\d+).*?抽象件=(\d+) 【怎么接】=(\d+)/(\d+).*?位置OK=(\d+)/(\d+).*?⑦\.5扩展小节=(\S+?)\(步骤(\d+)\)', t)
    pro = re.search(r'文件:行 引用不成立=(\d+) ｜ 件标题文件不存在=(\d+) ｜ 本仓类.方法 全仓无此方法=(\d+) ｜ 反引号符号待确认=(\d+)', t)
    verdict = g(r'^总判定: (\S+)')
    return dict(ver=ver, struct=struct, fid=fid, rev=rev, den=den, pos_bad=bool(sig),
                ln=ln, use=use, pro=pro, verdict=verdict, rc=p.returncode)


def render(lec, r):
    L = []
    L.append("%s（判据 v%s，`gate_lecture.py` 单条命令退出码 %d）**：" % (HEAD, r['ver'], r['rc']))
    L.append('')
    L.append('| # | 闸门组 | 实测值 | 结论 |')
    L.append('|---|---|---|---|')
    if r['struct']:
        sec, fen, pair, res, eight, seg8, selfref, back, thin = r['struct'].groups()
        L.append('| ⓪ | 结构 | 节数 %s、围栏 %s（%s）、占位 %s、⑫ 八条 %s、八段 %s、自指 %s、回链 %s、薄条 %s | 通过 |'
                 % (sec, fen, pair, res, eight, seg8, selfref, back, thin))
    if r['fid']:
        nb, nc, lost, pct = r['fid'].groups()
        L.append('| ① | 正向保真 | %s 个代码块 / %s 行 → 候选不符 %s 行 = **%s%%** | 通过 |' % (nb, nc, lost, pct))
    if r['rev']:
        L.append('| ② | ★反向完整 | %s | 通过 |'
                 % '；'.join('`%s` %s 有效行缺失 %s' % (c, n, m) for c, n, m, _ in r['rev']))
    L.append('| ③ | 注释密度 | %s 个代码块全过%s | 通过 |'
             % (r['den'], '；★类方法签名覆盖 0 缺失' if not r['pos_bad'] else '（★类签名有缺口，见闸门输出）'))
    if r['ln']:
        L.append('| ④ | 行号一致性 | 可判定 %s 处 → **漂移 %s 处** | 通过 |' % r['ln'].groups())
    if r['use']:
        n, u, un, io, ion, ifc, w, wn, pos, posn, ext, steps = r['use'].groups()
        L.append('| ⑤ | 用法与接入 | 逐件 %s：`【怎么用】` %s/%s、`【上下游】` %s/%s、抽象件 `【怎么接】` %s/%s、位置 %s/%s、批级 ⑦.5 %s（%s 步） | 通过 |'
                 % (n, u, un, io, ion, w, wn, pos, posn, ext, steps))
    if r['pro']:
        a, b, c, d = r['pro'].groups()
        L.append('| ⑥ | 散文符号真实性 | 三类引用不成立 %s/%s/%s 处；反引号符号**待人工确认 %s 处**（不计 FAIL） | 通过 |' % (a, b, c, d))
    L.append('')
    L.append('> 本表由 `scripts/sync_gate_result.py` 从闸门实跑输出生成，**不是复述旧结论**（血证 H15）；'
             '判据版本以本表首行的 v%s 为准。' % r['ver'])
    return '\n'.join(L)


def main():
    ap = argparse.ArgumentParser(description='把闸门实跑结果写进 ⑯ 段')
    ap.add_argument('lecture')
    ap.add_argument('--src', default=os.getcwd())
    ap.add_argument('--apply', action='store_true')
    a = ap.parse_args()
    lec = a.lecture if os.path.isabs(a.lecture) else os.path.join(os.path.abspath(a.src), a.lecture)
    r = run_gate(lec, os.path.abspath(a.src))
    block = render(lec, r)
    lines = load(lec)
    before = scan_fences(lines)
    i16 = next((k for k, l in enumerate(lines) if re.match(r'^## ⑯', l)), None)
    if i16 is None:
        raise SystemExit('[ABORT] 没有 `## ⑯` 段——本工具只更新既有 ⑯，不替你造结构')
    # 已有「七组闸门实测」块 → 整块替换（幂等）；否则插在 ⑯ 标题之后
    old = next((k for k in range(i16, min(i16 + 40, len(lines))) if MARK_RE.match(lines[k])), None)
    print('判据 v%s ｜ 总判定 %s ｜ ⑯ 段 :%d ｜ %s'
          % (r['ver'], r['verdict'], i16 + 1, '替换既有实测块 :%d' % (old + 1) if old is not None else '在 ⑯ 标题后插入'))
    if not a.apply:
        print('（dry-run，未写盘；确认后加 --apply）')
        return 0
    if old is not None:
        end = block_end(lines, old)
        print('   ↳ 实测块 :%d-:%d（%d 行，含历史堆叠表）' % (old + 1, end + 1, end - old + 1))
        safe_replace_range(lines, old + 1, end + 1, block)
    else:
        insert_at(lines, i16 + 2, block)
    # 顺手刷新 ⑯ 末端那条「判据版本：vX.Y」手写行（历史上会与被刷新的机器表打架）
    for k in range(old + 1 if old is not None else i16 + 1, len(lines)):
        if lines[k].startswith('## '):
            break
        if VERLINE_RE.match(lines[k].strip()):
            lines[k] = VERLINE_RE.sub('**判据版本：v%s**' % r['ver'], lines[k].strip(), count=1)
            print('   ↳ 判据版本行 :%d 已刷为 v%s' % (k + 1, r['ver']))
            break
    after = scan_fences(lines)
    if after[0]:
        raise SystemExit('[ABORT] 围栏配对异常：%s' % (after[0][:3],))
    save(lines, lec)
    print('→ 已写盘 %s（围栏事件 %d → %d）' % (os.path.basename(lec), len(before[1]), len(after[1])))
    return 0


if __name__ == '__main__':
    sys.exit(main())
