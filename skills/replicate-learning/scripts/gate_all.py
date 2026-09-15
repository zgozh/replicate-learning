#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全库记分卡：用官方闸门把**所有**讲解文件跑一遍，产出一张可比对的清单（JSON + 终端表）。

**为什么它随技能发布**：SKILL §6.6 规定"判据有变时必须证明**回归集判定不变**"。
执行那一步的工具如果只是某个会话的临时脚本，下个会话它就没了 —— 那这条规程就退化成口头声明。
所以这张记分卡随技能发布，JSON 可存成基线，`--baseline` 逐字段比"不该变的判定一字不变"。

用法：
    python gate_all.py --root <讲解目录> --src <源码根>                  # 打印 + 写 <root>/../gate_all.json
    python gate_all.py --root … --src … --out /tmp/gate_all_v28.json
    python gate_all.py --root … --src … --baseline gate_all_v27.json    # 判据回归：任何字段变化即 FAIL
    python gate_all.py --root … --src … --all                           # 连"没问题"的文件也列

行 schema（**不要随意改**，基线文件靠它比对）：rel / blocks / code / lost / evolve / fidelity /
unattr / snap / rev_bad / den_bad / den_blocks / sig_bad / struct / ln_bad / ln_blocks / usage{}
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import gate_lecture as G  # noqa: E402

# 本脚本依赖的 gate 对外符号（skill_selfcheck 逐条校验存在性）
GATE_API = ['index_sources', 'parse_blocks', 'resolve_snapshot', 'load_snapshot',
            'check_fidelity', 'check_density', 'check_sig', 'check_structure', 'check_reverse',
            'check_lineno', 'check_usage', 'SNAPSHOT', 'SNAP_TAR', 'SNAP_UNION', '_snap_file_cache']
# ROOT 由 gate 的 main() 内 `global` 声明、必须由调用方写入（影响 os.path.relpath 的基准）
GATE_GLOBALS_SET = ['ROOT']


def check_gate_api():
    miss = [n for n in GATE_API if not hasattr(G, n)]
    gate_src = io.open(os.path.join(HERE, 'gate_lecture.py'), encoding='utf-8').read()
    miss += [n for n in GATE_GLOBALS_SET if not re.search(r'^\s*global\s+%s\b' % n, gate_src, re.M)]
    if miss:
        raise SystemExit('[ABORT] gate_lecture 缺少本脚本依赖的符号：%s\n'
                         '   → 判据改动动了内部结构，请同步更新 gate_all.py 的 GATE_API。' % '、'.join(miss))


def reset_snap(sha):
    if sha:
        G.load_snapshot(sha)
    else:
        G.SNAPSHOT = G.SNAP_TAR = G.SNAP_UNION = None
        G._snap_file_cache.clear()


def fail_lines(r):
    if r["lost"] is None:
        return r["n_code"]
    if r["hist"] and r["snap_lost"] is not None:
        return r["snap_lost"]
    return r["snap_lost"] if r["snap_lost"] is not None else r["lost"]


def scan(root, src):
    by_class, rev = G.index_sources(src)
    rows = []
    for dp, _dns, fns in os.walk(root):
        for fn in sorted(fns):
            if not fn.endswith(".md"):
                continue
            p = os.path.join(dp, fn)
            rel = os.path.relpath(p, root)
            lines, blocks = G.parse_blocks(p)
            sha, _how = G.resolve_snapshot(lines)
            reset_snap(sha)
            fid = [r for r in G.check_fidelity(blocks, by_class, rev) if not r["exempt"]]
            tot = sum(r["n_code"] for r in fid)
            lost = sum(fail_lines(r) for r in fid)
            evolve = sum((r["lost"] or 0) - (r["snap_lost"] or 0) for r in fid
                         if r["lost"] is not None and r["snap_lost"] is not None)
            den_all = G.check_density(blocks)
            sig = G.check_sig(blocks, by_class)
            st = G.check_structure(lines, any(b[1] == "java" and len(b[2]) >= 5 for b in blocks))
            s_bad = []
            if st["is_batch"]:
                if st["sections"] != 17:
                    s_bad.append("节数%d" % st["sections"])
                if st["fences"] % 2:
                    s_bad.append("围栏奇")
                if st["residual"]:
                    s_bad.append("占位%d" % st["residual"])
                if st["eight"] != 8:
                    s_bad.append("八条%d" % st["eight"])
                if st["prompt"] != 8:
                    s_bad.append("八段%d" % st["prompt"])
                if st["selfref"]:
                    s_bad.append("自指%d" % st["selfref"])
                if st["back"] == 0:
                    s_bad.append("无回链")
                if st["thin"]:
                    s_bad.append("薄条%d" % len(st["thin"]))
            rev_rows = [r for r in G.check_reverse(blocks, lines, by_class) if r["cov"] < 0.995]
            den = [r for r in den_all if not r["exempt"] and (r["max_run"] >= 8 or r["comments"] < r["need"])]
            ln = [r for r in G.check_lineno(blocks, by_class, rev) if r["bad"]]
            u_items, u_ext = G.check_usage(lines)
            u_live = [r for r in u_items if not r["hist"]]
            u_bad = dict(items=len(u_live),
                         use=sum(1 for r in u_live if not r["use"]),
                         io=sum(1 for r in u_live if not r["io"]),
                         iface=sum(1 for r in u_live if r["iface"]),
                         wire=sum(1 for r in u_live if r["iface"] and not r["wire"]),
                         ext=(0 if (u_ext["at"] and u_ext["steps"] >= 3) else 1),
                         ext_at=u_ext["at"], ext_steps=u_ext["steps"])
            if not st["is_batch"]:
                u_bad = dict(items=0, use=0, io=0, iface=0, wire=0, ext=0, ext_at=0, ext_steps=0)
            rows.append(dict(rel=rel, blocks=len(fid), code=tot, lost=lost, evolve=evolve,
                             fidelity=round(1 - lost / tot, 4) if tot else 1.0,
                             unattr=sum(1 for r in fid if r["lost"] is None),
                             snap=sha or "", rev_bad=len(rev_rows), den_bad=len(den),
                             den_blocks=len([r for r in den_all if not r["exempt"]]),
                             sig_bad=sum(len(r["missing"]) for r in sig),
                             struct=";".join(s_bad),
                             ln_bad=sum(r["bad"] for r in ln), ln_blocks=len(ln),
                             usage=u_bad))
    rows.sort(key=lambda r: (r["fidelity"], -r["ln_bad"]))
    return rows


def has_problem(r):
    u = r["usage"]
    return bool(r["lost"] or r["unattr"] or r["rev_bad"] or r["den_bad"] or r["ln_bad"]
                or r["sig_bad"] or r["struct"] or u["use"] or u["io"] or u["wire"] or u["ext"])


def table(rows, show_all=False):
    print(f"{'保真度':>7} {'演进':>5} {'候选不符':>7} {'孤块':>4} {'★反向挂':>6} {'密度挂':>9} {'签名缺':>6} "
          f"{'行号漂移':>7} {'用法缺(用/流/接)':>16} {'⑦.5':>4}  结构问题 / 文件")
    for r in rows:
        if not show_all and not has_problem(r):
            continue
        u = r["usage"]
        print(f"{r['fidelity']:>7.1%} {r['evolve']:>5} {r['lost']:>7} {r['unattr']:>4} "
              f"{r['rev_bad']:>6} {r['den_bad']:>4}/{r['den_blocks']:<4} {r['sig_bad']:>6} {r['ln_bad']:>7} "
              f"{u['use']:>5}/{u['io']:>3}/{u['wire']:>3}(共{u['items']:>3}) {('有' if not u['ext'] else '无'):>4}  "
              f"{r['struct'][:30]:<30} {r['rel']}")


def summary(rows):
    bad = [r for r in rows if has_problem(r)]
    print(f"\n合计 {len(rows)} 个文件；有问题的 {len(bad)} 个")
    print("⓪ 结构（A 组）不过:", sum(1 for r in rows if r["struct"]))
    for tag, key in (("节数≠17", "节数"), ("围栏奇", "围栏奇"), ("占位", "占位"), ("⑫八条≠8", "八条"),
                     ("⑫八段≠8", "八段"), ("⑫自指", "自指"), ("无回链", "无回链"), ("薄条", "薄条")):
        print("   其中 %s: %d" % (tag, sum(1 for r in rows if key in r["struct"])), end="")
    print()
    print("① 保真度<100%（候选不符）:", sum(1 for r in rows if r["fidelity"] < 1.0))
    print("①b 存在【源码演进】漂移的文件:", sum(1 for r in rows if r["evolve"]))
    print("② 有孤块(无法归属):", sum(1 for r in rows if r["unattr"]))
    print("③ ★反向不过:", sum(1 for r in rows if r["rev_bad"]))
    print("④ 密度不过:", sum(1 for r in rows if r["den_bad"]))
    print("③c ★类方法签名缺注释:", sum(1 for r in rows if r["sig_bad"]), "个文件 /",
          sum(r["sig_bad"] for r in rows), "个方法")
    print("⑤ 行号漂移:", sum(1 for r in rows if r["ln_bad"]), "个文件 /", sum(r["ln_bad"] for r in rows), "处")
    print("   其中保真度 100% 但行号漂移:", sum(1 for r in rows if r["ln_bad"] and r["fidelity"] == 1.0))
    print("⑥ 用法与接入不过:",
          sum(1 for r in rows if r["usage"]["use"] or r["usage"]["io"] or r["usage"]["wire"] or r["usage"]["ext"]),
          "个文件")
    print("   缺【怎么用】:", sum(r["usage"]["use"] for r in rows), "件 ｜ 缺【上下游】:",
          sum(r["usage"]["io"] for r in rows), "件 ｜ 抽象件缺【怎么接】:",
          sum(r["usage"]["wire"] for r in rows), "/", sum(r["usage"]["iface"] for r in rows),
          "件 ｜ 无 ⑦.5:", sum(r["usage"]["ext"] for r in rows), "个文件")
    print("   逐件小节总数:", sum(r["usage"]["items"] for r in rows), "；已写【怎么用】:",
          sum(r["usage"]["items"] - r["usage"]["use"] for r in rows))
    print("声明了源码快照的文件:", sum(1 for r in rows if r["snap"]))
    return bad


def diff(before, after):
    """逐字段比对两份记分卡：返回变化清单（判据回归的机械证据）"""
    bi = {r["rel"]: r for r in before}
    ai = {r["rel"]: r for r in after}
    changes = []
    for rel in sorted(set(bi) | set(ai)):
        if rel not in bi:
            changes.append((rel, "新增文件", "", ""))
            continue
        if rel not in ai:
            changes.append((rel, "文件消失", "", ""))
            continue
        a, b = bi[rel], ai[rel]
        for k in sorted(set(a) | set(b)):
            va, vb = a.get(k), b.get(k)
            if isinstance(va, dict) or isinstance(vb, dict):
                va, vb = json.dumps(va, sort_keys=True, ensure_ascii=False), json.dumps(vb, sort_keys=True, ensure_ascii=False)
            if va != vb:
                changes.append((rel, k, va, vb))
    return changes


def main():
    ap = argparse.ArgumentParser(description='全库记分卡 + 判据回归比对')
    ap.add_argument('--root', required=True, help='讲解文件目录（递归扫 *.md）')
    ap.add_argument('--src', required=True, help='源码根目录')
    ap.add_argument('--out', help='JSON 输出路径（缺省写到当前目录 gate_all.json）')
    ap.add_argument('--baseline', help='与此前的 JSON 逐字段比对；有变化则以退出码 1 结束')
    ap.add_argument('--all', action='store_true', help='连无问题的文件也列出')
    a = ap.parse_args()
    check_gate_api()
    G.ROOT = os.path.abspath(a.src)
    rows = scan(a.root, os.path.abspath(a.src))
    table(rows, a.all)
    bad = summary(rows)
    out = a.out or 'gate_all.json'
    json.dump(rows, io.open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1, default=str)
    print('→ 已写 %s' % out)

    rc = 0
    if a.baseline:
        before = json.load(io.open(a.baseline, encoding='utf-8'))
        changes = diff(before, rows)
        if changes:
            rc = 1
            print('\n[FAIL] 与基线 %s 有 %d 处字段变化（判据回归要求：不该变的判定一字不变）' % (a.baseline, len(changes)))
            for rel, k, va, vb in changes[:40]:
                print('   %-52s %-10s %s → %s' % (rel[:52], k, va, vb))
            if len(changes) > 40:
                print('   …（其余 %d 处省略）' % (len(changes) - 40))
        else:
            print('\n[OK ] 与基线 %s 逐字段完全一致（判据零附带影响）' % a.baseline)
    print('\n回归判定：%s' % ('FAIL ❌' if rc else
                            ('PASS ✅ 判据零附带影响' if a.baseline else '（未指定 --baseline，跳过）')))
    print('记分卡：%d/%d 个文件仍有问题（这是存量信息，不影响退出码）' % (len(bad), len(rows)))
    return rc


if __name__ == '__main__':
    sys.exit(main())
