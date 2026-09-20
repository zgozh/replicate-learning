#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把闸门的**实跑结果**写进批次的 ⑯ 段（机器生成，杜绝"复述旧结论"）。

**为什么需要它**：⑯ 的自检表历史上是手写的，血证 H15 的事故恰恰是"⑯ 复述两版之前的结论"——
判据已经 2.9 了，表里还写着六项、数字还是旧的。判据 2.10 起，⑯ 段**必须出现当前 `GATE_VERSION`**，
本工具让这条要求变成一条命令：跑一次闸门 → 把实测数字渲染成表格 → 插进/更新 ⑯ 段。

**方案 §3.4 之后（推荐用法）**：不再"再跑一次闸门 + 正则扒展示文本"，而是消费**结构化结果**：

    python gate_lecture.py <批次.md> --src <仓库根> --json gate-result.json
    python sync_gate_result.py <批次.md> --src <仓库根> --result-json gate-result.json --apply
        [--manifest <本批清单.json>] [--final-json gate-result.final.json]

盖章前先验：结果 schema / 契约版本 / **被检查正文的 sha256** / manifest sha256 / 必需检查项是否齐全；
**旧结果不得给改动过的正文背书**（正文在检查之后被改过 → 拒绝盖章）。盖章后**再跑一次完整闸门**校验
最终成品，并把最终哈希写进独立结果文件（`--final-json`，缺省 `<result>.final.json`）——
这样"盖章前的哈希"与"最终成品的哈希"是两条分开的记录，不会互相冒充。

旧 CLI（不给 `--result-json`）保留可用：它自己跑一次闸门再解析展示文本；输出里会提示改用新路径。
写入一律走 `safe_edit`（围栏事件序列护栏 + tmpnew→os.replace + `.bak`），**失败不动原稿**。
"""
import argparse
import datetime
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from safe_edit import load, save, insert_at, safe_replace_range, scan_fences  # noqa: E402
import lecture_checks as LC                                                  # noqa: E402


def contract_version():
    """当前判据版本 —— 取自 SSOT（`spec/00-质量契约.json` 的 version），
    与 `gate_lecture.GATE_VERSION` 由 skill_selfcheck 断言一致，故不必再 import 闸门。"""
    return LC.load_contract().get('version')

HEAD = '**七组闸门实测**'
MARK_RE = re.compile(r'^\*\*七组闸门实测')
NOTE_RE = re.compile(r'^>\s*本表由\s*`scripts/sync_gate_result\.py`')
VERLINE_RE = re.compile(r'^\*\*判据版本：v?[\d.]+\*\*')

# 盖章所需的最低检查集合：少任何一项都说明结果不完整（不许拿半份报告盖章）
REQUIRED_CHECKS = ("G-STRUCT", "G-FIDELITY", "G-REVERSE", "G-DENSITY", "G-LINENO", "G-USAGE", "G-PROSE")

STATUS_ZH = {LC.PASS: "通过", LC.FAIL: "**不通过**", LC.REPORT: "报告档",
             LC.NOT_CHECKED: "未检查", LC.ERROR: "**检查器出错**"}


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
        n, u, un, io_, ion, ifc, w, wn, pos, posn, ext, steps = r['use'].groups()
        L.append('| ⑤ | 用法与接入 | 逐件 %s：`【怎么用】` %s/%s、`【上下游】` %s/%s、抽象件 `【怎么接】` %s/%s、位置 %s/%s、批级 ⑦.5 %s（%s 步） | 通过 |'
                 % (n, u, un, io_, ion, w, wn, pos, posn, ext, steps))
    if r['pro']:
        a, b, c, d = r['pro'].groups()
        L.append('| ⑥ | 散文符号真实性 | 三类引用不成立 %s/%s/%s 处；反引号符号**待人工确认 %s 处**（不计 FAIL） | 通过 |' % (a, b, c, d))
    L.append('')
    L.append('> 本表由 `scripts/sync_gate_result.py` 从闸门实跑输出生成，**不是复述旧结论**（血证 H15）；'
             '判据版本以本表首行的 v%s 为准。' % r['ver'])
    return '\n'.join(L)


def render_from_result(result):
    """从**结构化结果**渲染 ⑯ 表（方案 §3.4：不再从展示文本猜数字）。"""
    ver = result.get('contract_version')
    checks = result.get('checks', [])
    ok = not LC.blocking_checks(result)
    L = ["%s（判据 v%s，结构化结果 schema v%d，%s）**："
         % (HEAD, ver, result.get('schema_version', LC.SCHEMA_VERSION),
            "无阻塞项" if ok else "**有阻塞项**")]
    L.append('')
    L.append('| 规则 ID | 检查组 | 核验对象 | 结论 |')
    L.append('|---|---|---|---|')
    for c in checks:
        n = c.get('checked', 0)
        L.append('| `%s` | %s | %s | %s |'
                 % (c.get('id'), (c.get('title') or '')[:38], n if n else '—',
                    STATUS_ZH.get(c.get('status'), c.get('status'))))
    L.append('')
    fails = [c['id'] + '：' + (c.get('findings') or [{}])[0].get('message', '')[:60]
             for c in checks if c.get('status') in LC.BLOCKING]
    if fails:
        L.append('阻塞项：%s' % '；'.join(fails[:6]))
        L.append('')
    L.append('> 本表由 `scripts/sync_gate_result.py` 从**结构化结果**（`--result-json`，schema v%d）渲染，'
             '**不是复述旧结论**（血证 H15）；判据版本 v%s；被检查正文 sha256=`%s`。'
             '核验对象为「—」的检查记 `未检查`，**不计通过**。'
             % (result.get('schema_version', LC.SCHEMA_VERSION), ver,
                (result.get('lecture_sha256') or '?')[:16]))
    return '\n'.join(L)


def write_block(lecture, block, ver, apply):
    lines = load(lecture)
    before = scan_fences(lines)
    i16 = next((k for k, l in enumerate(lines) if re.match(r'^## ⑯', l)), None)
    if i16 is None:
        raise SystemExit('[ABORT] 没有 `## ⑯` 段——本工具只更新既有 ⑯，不替你造结构')
    old = next((k for k in range(i16, min(i16 + 60, len(lines))) if MARK_RE.match(lines[k])), None)
    print('判据 v%s ｜ ⑯ 段 :%d ｜ %s'
          % (ver, i16 + 1, '替换既有实测块 :%d' % (old + 1) if old is not None else '在 ⑯ 标题后插入'))
    if not apply:
        print('（dry-run，未写盘；确认后加 --apply）')
        print('—— 将写入的内容 ——')
        print(block)
        return 0
    if old is not None:
        end = block_end(lines, old)
        print('   ↳ 实测块 :%d-:%d（%d 行，含历史堆叠表）' % (old + 1, end + 1, end - old + 1))
        safe_replace_range(lines, old + 1, end + 1, block)
    else:
        insert_at(lines, i16 + 2, block)
    for k in range(old + 1 if old is not None else i16 + 1, len(lines)):
        if lines[k].startswith('## '):
            break
        if VERLINE_RE.match(lines[k].strip()):
            lines[k] = VERLINE_RE.sub('**判据版本：v%s**' % ver, lines[k].strip(), count=1)
            print('   ↳ 判据版本行 :%d 已刷为 v%s' % (k + 1, ver))
            break
    after = scan_fences(lines)
    if after[0]:
        raise SystemExit('[ABORT] 围栏配对异常：%s' % (after[0][:3],))
    save(lines, lecture)
    print('→ 已写盘 %s（围栏事件 %d → %d）' % (os.path.basename(lecture), len(before[1]), len(after[1])))
    return 0


def verify_final(lecture, src, final_json, result):
    """盖章后**再跑一次完整闸门**校验最终成品，并把最终哈希写进独立记录。"""
    jout = lecture + '.gate-final.json'
    p = subprocess.run([sys.executable, os.path.join(HERE, 'gate_lecture.py'), lecture,
                        '--src', src, '--json', jout],
                       capture_output=True, text=True, encoding='utf-8', errors='replace')
    final = None
    if os.path.isfile(jout):
        final = json.load(io.open(jout, encoding='utf-8'))
        os.unlink(jout)
    verdict = None
    for line in (p.stdout or '').split('\n'):
        if line.startswith('总判定:'):
            verdict = line.strip()
    rec = {
        'schema_version': LC.SCHEMA_VERSION,
        'stamped_at': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
        'contract_version': (final or {}).get('contract_version'),
        'before_lecture_sha256': (result or {}).get('lecture_sha256'),
        'final_lecture_sha256': LC.sha256_file(lecture),
        'exit_code': p.returncode,
        'verdict': verdict,
        'pass': (final or {}).get('pass'),
        'checks': [{'id': c['id'], 'status': c['status'], 'checked': c['checked']}
                   for c in (final or {}).get('checks', [])],
        'stamp_did_not_break_anything': bool(final and final.get('pass')),
    }
    if final_json:
        io.open(final_json, 'w', encoding='utf-8', newline='').write(
            json.dumps(rec, ensure_ascii=False, indent=1) + '\n')
        print('→ 最终成品校验记录已写 %s（final sha256=%s）'
              % (final_json, (rec['final_lecture_sha256'] or '')[:16]))
    if not rec['stamp_did_not_break_anything']:
        print('[FAIL] 盖章后复跑闸门未通过（退出码 %s）——盖章动作本身破坏了成品，请回滚 .bak' % p.returncode)
        return 1
    print('[OK ] 盖章后复跑闸门通过（退出码 0），最终哈希已记录')
    return 0


def main():
    LC.configure_stdio()
    ap = argparse.ArgumentParser(description='把闸门实跑结果写进 ⑯ 段')
    ap.add_argument('lecture')
    ap.add_argument('--src', default=os.getcwd())
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--result-json', dest='result_json',
                    help='gate_lecture.py --json 产出的**结构化结果**（推荐：只从合格结果渲染 ⑯）')
    ap.add_argument('--manifest', help='本批源文件清单（有则校验结果里的 manifest 哈希与它一致）')
    ap.add_argument('--final-json', dest='final_json',
                    help='盖章后复跑闸门的最终记录（缺省 <result-json>.final.json）')
    ap.add_argument('--no-verify-final', dest='verify_final', action='store_false',
                    help='跳过"盖章后复跑完整闸门"（不推荐）')
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    lec = a.lecture if os.path.isabs(a.lecture) else os.path.join(src, a.lecture)
    if not os.path.isfile(lec):
        raise SystemExit('[ABORT] 找不到讲解文件：%s' % lec)
    final_json = a.final_json or ((a.result_json + '.final.json') if a.result_json else None)

    if a.result_json:
        result = LC.load_result(a.result_json)
        manifest_sha = LC.sha256_file(a.manifest) if a.manifest else None
        problems = LC.validate_result(
            result,
            expect_lecture_sha256=LC.sha256_file(lec),
            expect_manifest_sha256=manifest_sha,
            expect_contract_version=contract_version(),
            required_ids=REQUIRED_CHECKS)
        print('结构化结果：%s（契约 v%s，%d 条检查）'
              % (a.result_json, result.get('contract_version'), len(result.get('checks', []))))
        if problems:
            print('[ABORT] 结果不能用于盖章：')
            for p in problems:
                print('   - ' + p)
            print('   → 重新跑一次 gate_lecture.py --json 生成**针对当前正文**的结果，再盖章。')
            return 1
        blocking = LC.blocking_checks(result)
        if blocking:
            print('[ABORT] 结果里有阻塞项，不允许盖章：%s'
                  % '、'.join('%s(%s)' % (c['id'], c['status']) for c in blocking))
            return 1
        block, ver = render_from_result(result), result.get('contract_version')
    else:
        print('（旧路径：自己跑一次闸门并解析展示文本；推荐改用 '
              '`gate_lecture.py --json` + `--result-json`）')
        r = run_gate(lec, src)
        block, ver = render(lec, r), r['ver']

    rc = write_block(lec, block, ver, a.apply)
    if rc or not a.apply or not a.verify_final:
        return rc
    return verify_final(lec, src, final_json, result if a.result_json else None)


if __name__ == '__main__':
    sys.exit(main())
