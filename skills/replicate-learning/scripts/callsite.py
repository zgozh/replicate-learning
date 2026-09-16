#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""调用点提取器：给定类型名/方法名，从源码里找出「谁在什么地方用它」。

**为什么它随技能发布**：⑤ 要求每个 6.x 件写明 `**【怎么用】**`，且调用现场必须指名
`类:方法 :Lnn`。靠回忆写这个字段是错的来源（实测已发生：讲解里描述了源码中根本不存在的方法与类）。
本脚本把"调用现场"变成**可重跑复现的证据**，不靠印象、不靠编。

输出三段：
    声明      —— 类/接口/记录/枚举 的声明位置
    使用/调用点 —— 真正在用它（`Xxx v = …` / `new Xxx(` / `.method(`）的位置，附**所在方法**与其声明行
    仅提及     —— 类型引用、字段声明、注释里提到等（不足以当调用证据）

用法：
    python callsite.py VectorSpaceId                     # 默认在 --src（缺省=当前目录）下自动找源码根
    python callsite.py ChunkingService --src D:\\proj --roots rag,framework
    python callsite.py ChunkingService --src . --json out.json
    python callsite.py ChunkingService --src . --out callsite_ChunkingService.txt

源码根=自动发现：任何形如 `<模块>/src/{main,test}/java` 或 `.../python` 的目录都会被收录，
因此 Maven 多模块、Gradle 多模块、单模块项目都能直接用，无需改编。
"""
import argparse
import io
import json
import os
import re
import sys

SKIP_DIRS = {'.git', 'node_modules', 'target', 'build', 'out', 'dist', '.idea', '.vscode',
             '__pycache__', '.tmp_usage', '.tmp_audit', '.venv', 'venv'}

JAVA_METHOD = re.compile(
    r'^\s{0,8}(?:@\w+\s*)*(?:public|private|protected|static|final|synchronized|default|abstract|\s)*'
    r'[\w<>,\[\]\.\? ]+\s+(\w+)\s*\([^;]*\)\s*(?:throws [\w, \.]+)?\s*\{\s*$')
JAVA_TYPE = re.compile(r'^\s*(?:public |final |abstract |sealed |non-sealed |static )*'
                       r'(class|interface|record|enum)\s+(\w+)')
PY_DEF = re.compile(r'^(\s*)(?:async\s+)?def\s+(\w+)\s*\(')
PY_TYPE = re.compile(r'^(\s*)class\s+(\w+)')


def discover_roots(src, only=None):
    """自动发现源码根：返回 {模块名: [目录, …]}。只收录 src/{main,test}/{java,python} 形态。"""
    found = {}
    only = set(only or [])
    for dp, dns, _fns in os.walk(src):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        parts = dp.replace('\\', '/').split('/')
        if (os.path.basename(dp) in ('java', 'python') and len(parts) >= 2
                and parts[-2] in ('main', 'test') and len(parts) >= 3 and parts[-3] == 'src'):
            mod = parts[-4] if len(parts) >= 4 else os.path.basename(src.rstrip('\\/')) or 'root'
            if only and mod not in only:
                dns[:] = []
                continue
            found.setdefault(mod, []).append(dp)
            dns[:] = []                      # 不再往下走
    return found


def rel_of(p, src):
    try:
        return os.path.relpath(p, src)
    except ValueError:
        return p


def enclosing(lines, idx, ext):
    """向上找最近的方法/函数签名；找不到就退到类声明。返回 (名字, 声明行号)。"""
    for j in range(idx, max(-1, idx - 500), -1):
        l = lines[j]
        if ext == 'java':
            m = JAVA_METHOD.match(l)
            if m and ' new ' not in l and not l.lstrip().startswith('//'):
                return m.group(1), j + 1
            t = JAVA_TYPE.match(l)
            if t:
                return '<%s %s>' % (t.group(1), t.group(2)), j + 1
        else:
            d = PY_DEF.match(l)
            if d:
                return d.group(2), j + 1
            t = PY_TYPE.match(l)
            if t:
                return '<class %s>' % t.group(2), j + 1
    return '?', 0


def collect(src, sym, only=None):
    roots = discover_roots(src, only)
    files = []
    for mod, dirs in sorted(roots.items()):
        for d in dirs:
            for dp, dns, fns in os.walk(d):
                dns[:] = [x for x in dns if x not in SKIP_DIRS]
                for fn in fns:
                    if fn.endswith(('.java', '.py')):
                        files.append(os.path.join(dp, fn))
    decl, uses, mention = [], [], []
    for p in sorted(files):
        ext = 'java' if p.endswith('.java') else 'py'
        try:
            lines = io.open(p, encoding='utf-8').read().splitlines()
        except Exception:
            continue
        rel = rel_of(p, src)
        for i, l in enumerate(lines):
            if sym not in l:
                continue
            if re.search(r'\b(class|interface|record|enum)\s+' + re.escape(sym) + r'\b', l) \
                    or re.search(r'^\s*def\s+' + re.escape(sym) + r'\b', l):
                decl.append((rel, i + 1, l.strip()))
                continue
            receiver = re.search(re.escape(sym) + r'\s+\w+\s*=[^;]*$', l) or ('new ' + sym) in l
            callish = re.search(r'\.\w+\s*\(', l) or re.search(r'^[\w\.]*' + re.escape(sym) + r'\s*\(', l)
            row = (rel, i + 1, l.strip(), ext)
            (uses if (receiver or callish) else mention).append(row)
    return roots, decl, uses, mention, files, src


def render(src, sym, roots, decl, uses, mention, files, max_mention):
    out = ['符号: %s' % sym,
           '源码根: %s' % src,
           '模块: %s' % ', '.join('%s(%d 目录)' % (m, len(d)) for m, d in sorted(roots.items())),
           '', '=== 声明 (%d) ===' % len(decl)]
    for r in decl:
        out.append('  %s:%d  %s' % r)
    out += ['', '=== 使用/调用点 (%d) ===' % len(uses)]
    for p in sorted(files):
        rel = rel_of(p, src)
        hits = [u for u in uses if u[0] == rel]
        if not hits:
            continue
        try:
            lines = io.open(p, encoding='utf-8').read().splitlines()
        except Exception:
            continue
        out.append('-- %s' % rel)
        for _rel, ln, code, ext in hits:
            mname, mline = enclosing(lines, ln - 1, ext)
            out.append('   :L%-5d in %s()  [声明 :L%d]  %s' % (ln, mname, mline, code))
    out += ['', '=== 仅提及（类型引用/字段声明等，%d）===' % len(mention)]
    for r in mention[:max_mention]:
        out.append('  %s:%d  %s' % (r[0], r[1], r[2]))
    if len(mention) > max_mention:
        out.append('  …（其余 %d 处省略）' % (len(mention) - max_mention))
    return '\n'.join(out)


def main():
    ap = argparse.ArgumentParser(description='调用点提取（⑤ 补【怎么用】的证据来源）')
    ap.add_argument('symbol')
    ap.add_argument('--src', default=os.getcwd(), help='项目根目录（缺省=当前目录）')
    ap.add_argument('--roots', help='只看这些模块，逗号分隔（缺省=自动发现的全部）')
    ap.add_argument('--out', help='把完整清单写到文件')
    ap.add_argument('--json', help='另存一份 JSON')
    ap.add_argument('--max-mentions', type=int, default=80)
    a = ap.parse_args()

    src = os.path.abspath(a.src)
    only = [x for x in a.roots.split(',') if x] if a.roots else None
    roots, decl, uses, mention, files, src = collect(src, a.symbol, only)
    if not roots:
        print('[FAIL] 在 %s 下没找到源码根（应有 <模块>/src/{main,test}/{java,python}）' % src)
        return 1
    text = render(src, a.symbol, roots, decl, uses, mention, files, a.max_mentions)
    print(text if len(text) < 8000 else text[:8000] + '\n…（更长，见 --out）')
    if a.out:
        io.open(a.out, 'w', encoding='utf-8').write(text)
        print('\n→ 已写 %s' % a.out)
    if a.json:
        json.dump(dict(symbol=a.symbol, src=src, decl=decl, uses=uses, mention=mention),
                  io.open(a.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    if not decl and not uses:
        print('\n[提醒] 既无声明也无调用点：确认符号名拼写，或该类型本仓尚未实现（那就写「本仓库尚未实现」，不许编）')
    return 0


if __name__ == '__main__':
    sys.exit(main())
