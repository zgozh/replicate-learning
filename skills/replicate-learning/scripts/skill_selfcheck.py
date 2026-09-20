#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
skill_selfcheck.py —— 技能文档一致性自检（2026-09-16 新增 · A 档止血）

为什么要它：技能语料有 ~3800 行规则，同一条要求同时活在 SKILL.md、references 模板、
gate_lecture.py 与 examples 样例里。没有这层检查时，实测已发生两类漂移：
  ① SKILL §6 还写着旧的"每批 1~12 项"清单（既没有 17 节，也没有"用法与接入"）；
  ② 某批次的自检脚本还在用已作废的 `// :[0-9]` 行号格式。
**改完技能、同步副本之前必须先跑本脚本，全绿才算改完。**

用法：
    python scripts/skill_selfcheck.py            # 在技能根目录下运行，或直接给路径
    退出码 0 = 全绿；1 = 有不一致（按输出逐条修）
"""
import io
import os
import re
import sys
import json
import shutil
import subprocess
import tempfile

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯'

# 本脚本依赖的 gate 对外符号（check_tools 会逐条校验存在性——本脚本自己也受同一条规矩约束）
GATE_API = ['USE_MARKS', 'WIRE_MARKS', 'IO_MARKS']


def read(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.isfile(p):
        return None
    text = io.open(p, encoding='utf-8').read()
    if rel == 'SKILL.md':
        # The short entry routes execution; the preserved detail still carries
        # the existing SSOT anchors and section definitions.
        detail = os.path.join(ROOT, 'references', '第一册质量细则.md')
        text += '\n' + io.open(detail, encoding='utf-8').read()
    return text


def scan_files():
    """所有规则类文档（不含 gate 源码本身）"""
    out = []
    for rel in ['SKILL.md', 'docs/复刻式学习方法-通用.md']:
        t = read(rel)
        if t is not None:
            out.append((rel, t))
    for sub in ('references', 'examples'):
        d = os.path.join(ROOT, sub)
        for fn in sorted(os.listdir(d)):
            if fn.endswith('.md'):
                out.append((sub + '/' + fn, read(sub + '/' + fn)))
    return out


class Report:
    def __init__(self):
        self.bad = 0
        self.n = 0

    def ok(self, msg):
        self.n += 1
        print('  [OK ] ' + msg)

    def fail(self, msg):
        self.n += 1
        self.bad += 1
        print('  [FAIL] ' + msg)


def check_version(r):
    """① gate 必须声明版本号（判据变更要有版本可追）"""
    g = read('scripts/gate_lecture.py') or ''
    m = re.search(r'^GATE_VERSION\s*=\s*"([^"]+)"', g, re.M)
    if m:
        r.ok('gate 版本号 = %s（gate_lecture.py: GATE_VERSION）' % m.group(1))
    else:
        r.fail('scripts/gate_lecture.py 缺 GATE_VERSION 常量（判据变更无法追溯）')


def check_markers(r):
    """② 用法/接入标记必须在 SKILL、批次模板、gate 三处一致。
    口径：gate 每类标记的**首个**写法是规范写法（docs 必须出现），其余是 gate 容忍的别名（不要求 docs 出现，
    但别名表必须包含规范写法，否则文档与判据会各认一套）。"""
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402  （有 __main__ 守卫，可安全 import）
    groups = {'【怎么用】': G.USE_MARKS, '【怎么接】': G.WIRE_MARKS, '【上下游】': G.IO_MARKS}
    for canon, alias in groups.items():
        if alias and alias[0] != canon:
            r.fail('gate 别名表首位不是规范写法：%s vs %s' % (alias[0], canon))
        else:
            r.ok('gate 别名表以规范写法开头：%s（别名 %s）' % (canon, '/'.join(alias[1:]) or '无'))
    canon_all = list(groups) + ['【扩展步骤】', '⑦.5']
    skill = read('SKILL.md') or ''
    tpl = read('references/批次讲解全文模板.md') or ''
    for mk in canon_all:
        where = []
        if mk not in skill:
            where.append('SKILL.md')
        if mk not in tpl:
            where.append('references/批次讲解全文模板.md')
        if where:
            r.fail('标记 %s 在 %s 中缺失（gate 按它判 ⑤，缺了就会误判）' % (mk, '、'.join(where)))
        else:
            r.ok('标记 %s 三处一致' % mk)


def check_sections(r):
    """③ 17 节骨架：SKILL §6.4 与批次模板的节号集合必须一致（①~⑯ + 索引）"""
    skill = read('SKILL.md') or ''
    tpl = read('references/批次讲解全文模板.md') or ''
    s_ids = set(re.findall(r'^#{4}\s*([' + CIRCLED + r'])\s', skill, re.M))
    t_ids = set(re.findall(r'^#{3,4}\s*([' + CIRCLED + r'])\s', tpl, re.M))
    if s_ids == t_ids == set(CIRCLED):
        r.ok('节号集合一致：①~⑯ 共 16 节（+索引）在 SKILL 与模板中齐备')
    else:
        miss_s = set(CIRCLED) - s_ids
        miss_t = set(CIRCLED) - t_ids
        r.fail('节号不一致：SKILL 缺 %s；模板缺 %s'
               % ('、'.join(sorted(miss_s)) or '无', '、'.join(sorted(miss_t)) or '无'))
    # §6 概要清单必须指向 §6.4（防止再出现"两套节数"）
    m = re.search(r'^## 6\. 批次教材结构(.*?)^### 6\.1 ', skill, re.M | re.S)
    body = m.group(1) if m else ''
    if '§6.4' in body:
        r.ok('§6 概要已指向 §6.4（节序唯一权威）')
    else:
        r.fail('§6 概要清单没有指向 §6.4 —— 会与 §6.4 的 17 节形成两套节数')
    if '12. 验证证据、已知限制、复习问答与索引' in body:
        r.fail('§6 仍保留旧的 12 项清单文本')
    else:
        r.ok('§6 无旧 12 项清单残留')


def check_deprecated(r):
    """④ 作废写法扫描：出现即 FAIL，除非该行本身在说明"已作废" """
    pats = [
        (r'//\s*:\[?0-9', '旧行号格式 `// :N`（应为 `// :L<真实行号>`）'),
        (r'【教材补注】', '旧补注写法 `// 【教材补注】`（应为 `←教材：`）'),
        (r'连续\s*5\s*行', '旧密度判据"连续 5 行"（应为"关键行连续 ≥8 行"）'),
        (r'行号\s*>?\s*0\s*即合格', '旧口径"行号>0 即合格"（应为以 C 组 ④ 为准）'),
    ]
    for rel, txt in scan_files():
        for i, line in enumerate(txt.split('\n'), 1):
            # 说明"已作废/禁止再用"的行是合法的（那正是废止声明本身）
            if re.search(r'作废|已废弃|旧写法|旧的|禁止|不再使用', line):
                continue
            for pat, desc in pats:
                if re.search(pat, line):
                    r.fail('%s:%d 出现%s → %s' % (rel, i, desc, line.strip()[:70]))
    if not r.bad:
        r.ok('无作废写法残留（`// :N` / 【教材补注】 / 连续 5 行 / 行号>0 即合格）')


def check_refs(r):
    """⑤ 交叉引用与文件引用必须存在（指向不存在的 §x.y / 文件 = 执行者按错的那份做）"""
    skill = read('SKILL.md') or ''
    known = set()
    for txt in (skill, read('references/批次讲解全文模板.md') or ''):
        for m in re.finditer(r'^#{3,4}\s*(6\.\d(?:\.\d)?)\s', txt, re.M):
            known.add(m.group(1))
    bad = []
    for m in re.finditer(r'§(6\.\d(?:\.\d)?)', skill):
        if m.group(1) not in known:
            bad.append('§' + m.group(1))
    if bad:
        r.fail('SKILL 引用了不存在的章节：%s' % '、'.join(sorted(set(bad))))
    else:
        r.ok('SKILL 中 §6.x 交叉引用全部有落点')

    miss, skipped = [], []
    for rel, txt in scan_files():
        for m in re.finditer(r'`((?:references|examples|scripts|docs|NOTES)/[^`\s]+?\.(?:md|py))`', txt):
            tgt = m.group(1)
            if os.path.isfile(os.path.join(ROOT, tgt)):
                continue
            # docs/ 与 NOTES/ 前缀可能是**宿主项目**内的路径（如 docs/阶段0-开工清单.md），不是技能自带资产 → 不校验
            if tgt.startswith(('docs/', 'NOTES/')):
                skipped.append(tgt)
            else:
                miss.append('%s → %s' % (rel, tgt))
    if miss:
        r.fail('引用了不存在的技能内文件：%s' % '；'.join(sorted(set(miss))[:6]))
    else:
        r.ok('技能内文件引用（references/ examples/ scripts/）全部存在'
             + ('；跳过 %d 处宿主项目路径（docs/ NOTES/）' % len(set(skipped)) if skipped else ''))


def check_ssot(r):
    """⑥ SSOT 对账（2026-09-16 B1 新增）：质量契约 ↔ SKILL ↔ 模板 ↔ gate 四处一致。
    这是"规则零丢失"的机械保障：SSOT 里声明的要求，必须在文档里有正文锚点；
    文档里的写法，必须在 gate 里有对应实现锚点（或显式标 '-' 表示由人判）。"""
    p = os.path.join(ROOT, 'spec', '00-质量契约.json')
    if not os.path.isfile(p):
        r.fail('缺 spec/00-质量契约.json（SSOT）')
        return
    ssot = json.load(io.open(p, encoding='utf-8'))
    skill = read('SKILL.md') or ''
    tpl = read('references/批次讲解全文模板.md') or ''
    # 实现锚点的搜索范围 = gate_lecture.py + scripts/ 下所有工具（V3 之后有些条目由工具实现，如 GATE_API）
    gate = read('scripts/gate_lecture.py') or ''
    tool_src = {}
    for fn in sorted(os.listdir(HERE)):
        if fn.endswith('.py'):
            tool_src[fn] = read('scripts/' + fn) or ''
    gate_all_txt = '\n'.join(tool_src.values())
    # SSOT 声明的层级只能是 L1/L2/L3
    bad_layer = [e['id'] for e in ssot['entries'] if e.get('layer') not in ('L1', 'L2', 'L3')]
    if bad_layer:
        r.fail('SSOT 条目层级非法（只能 L1/L2/L3）：%s' % '、'.join(bad_layer))
    else:
        r.ok('SSOT 条目 %d 条，层级齐备（L1 %d / L2 %d / L3 %d）' % (
            len(ssot['entries']),
            sum(1 for e in ssot['entries'] if e['layer'] == 'L1'),
            sum(1 for e in ssot['entries'] if e['layer'] == 'L2'),
            sum(1 for e in ssot['entries'] if e['layer'] == 'L3')))
    # 版本必须与 gate 一致
    gm = re.search(r'^GATE_VERSION\s*=\s*"([^"]+)"', gate, re.M)
    if gm and gm.group(1) == str(ssot.get('version')):
        r.ok('SSOT 版本与 gate 一致：%s' % ssot['version'])
    else:
        r.fail('SSOT 版本 %s ≠ gate GATE_VERSION %s' % (ssot.get('version'), gm.group(1) if gm else '缺'))
    miss_doc = [e['id'] for e in ssot['entries']
                if e.get('doc') and e['doc'] != '-' and e['doc'] not in skill]
    miss_tpl = [e['id'] for e in ssot['entries']
                if e.get('tpl') and e['tpl'] != '-' and e['tpl'] not in tpl]
    miss_gate = [e['id'] for e in ssot['entries']
                 if e.get('gate') and e['gate'] != '-' and e['gate'] not in gate
                 and e['gate'] not in gate_all_txt]
    for tag, ids, where in (('SKILL.md', miss_doc, '文档锚点'), ('模板', miss_tpl, '模板锚点'),
                            ('gate', miss_gate, '实现锚点')):
        if ids:
            r.fail('SSOT 条目在 %s 中找不到%s：%s（规则丢失或改了措辞没同步）'
                   % (tag, where, '、'.join(ids)))
        else:
            r.ok('SSOT 全部条目的%s都能在 %s 里找到' % (where, tag))
    # spec/ 下每个文件都要被 SKILL 引用（防止"有文件没人读"）
    specdir = os.path.join(ROOT, 'spec')
    orphan = [fn for fn in sorted(os.listdir(specdir))
              if fn != 'README.md' and ('spec/' + fn) not in skill]
    if orphan:
        r.fail('spec/ 下文件未被 SKILL.md 引用（写了也没人读）：%s' % '、'.join(orphan))
    else:
        r.ok('spec/ 下文件均被 SKILL.md 的必读清单引用')


def check_tools(r):
    """⑦ 工具随技能发布（契约 V3 / 血证 H17）：
    ① `scripts/` 下不留孤儿——每个工具都必须被 SKILL.md 或 spec/ 下某份文档引用
       （否则"规程里写着要做的步骤，其执行工具没人知道在哪"，等于没有）；
    ② 凡是 import 了 gate_lecture 的工具，必须声明 `GATE_API`（+可选 `GATE_GLOBALS_SET`），
       且声明的符号在 gate 里确实存在——判据改动动了内部结构时，这里立刻报红，
       而不是等下一个会话用错工具（`fix_lineno.py` 会**写回 NOTES 的行号**）。"""
    gate_src = read('scripts/gate_lecture.py') or ''
    docs = [('SKILL.md', read('SKILL.md') or '')]
    specdir = os.path.join(ROOT, 'spec')
    for fn in sorted(os.listdir(specdir)):
        docs.append(('spec/' + fn, read('spec/' + fn) or ''))
    tools = [fn for fn in sorted(os.listdir(HERE)) if fn.endswith('.py') and not fn.startswith('test_')]
    orphan = [fn for fn in tools if not any(fn in t for _n, t in docs)]
    if orphan:
        r.fail('scripts/ 下有工具没被任何文档引用（有工具没人知道 = 等于没有）：%s' % '、'.join(orphan))
    else:
        r.ok('scripts/ 下 %d 个工具均被 SKILL.md 或 spec/ 引用（无孤儿）' % len(tools))

    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402
    bad = []
    for fn in tools:
        src = read('scripts/' + fn) or ''
        if 'import gate_lecture' not in src:
            continue
        api = re.search(r'^GATE_API\s*=\s*\[(.*?)\]', src, re.M | re.S)
        glb = re.search(r'^GATE_GLOBALS_SET\s*=\s*\[(.*?)\]', src, re.M | re.S)
        if not api:
            bad.append('%s 用了 gate 却没声明 GATE_API' % fn)
            continue
        names = re.findall(r"'([A-Za-z_][A-Za-z0-9_]*)'", api.group(1))
        miss = [n for n in names if not hasattr(G, n)]
        if glb:
            for n in re.findall(r"'([A-Za-z_][A-Za-z0-9_]*)'", glb.group(1)):
                if not re.search(r'^\s*global\s+%s\b' % n, gate_src, re.M):
                    miss.append(n + '(缺 global 声明)')
        if miss:
            bad.append('%s → gate 里找不到 %s' % (fn, '、'.join(miss)))
    if bad:
        r.fail('工具依赖的 gate 符号对不上（判据改动动了内部结构）：%s' % '；'.join(bad))
    else:
        r.ok('声明了 GATE_API 的工具，其依赖符号在 gate 中全部存在')


def check_safe_edit(r):
    """⑧ safe_edit 护栏负向自测（血证 H14）：用当初**真实失败的做法**验证它会被拒绝。
    这是"护栏本身也要被验证"的落地——否则它就是一句口号。合成用例，不依赖宿主项目。"""
    sys.path.insert(0, HERE)
    import safe_edit as S             # noqa: E402
    base = ['# 标题', '```java', 'int a = 1;', '```', '尾部']

    # ① 跨围栏区间替换成"纯内容"——H14 的原始错误做法，必须被拒
    try:
        S.safe_replace_range(list(base), 2, 4, 'int a = 1;')
        r.fail('safe_edit 护栏失效：跨围栏区间被替换成纯内容时未拒绝（血证 H14 会重演）')
    except SystemExit:
        r.ok('safe_edit 护栏生效：跨围栏替换成纯内容 → 拒绝执行')

    # ② 替换体写回围栏 → 必须通过，且结果与原内容一致
    try:
        got = list(base)
        S.safe_replace_range(got, 2, 4, '```java\nint a = 1;\n```')
        if got == base:
            r.ok('safe_edit 正确替换体：带围栏的替换体通过且内容不变')
        else:
            r.fail('safe_edit 替换结果与预期不一致：%r' % (got,))
    except SystemExit as e:
        r.fail('safe_edit 误拒了带围栏的正确替换体：%s' % str(e)[:80])

    # ③ 锚点不唯一 → 必须拒绝（防止插错位置）
    try:
        S.insert_before(['a', 'a'], 'a', 'x')
        r.fail('safe_edit insert_before 锚点不唯一时未拒绝')
    except SystemExit:
        r.ok('safe_edit insert_before：锚点命中 ≠1 处 → 拒绝执行')

    # ④ insert_before 不得改动任何旧行（insert-only 的核心承诺）
    got = list(base)
    S.insert_before(got, '尾部', 'X\nY')
    if got[:4] == base[:4] and got.count('尾部') == 1:
        r.ok('safe_edit insert_before：只插入、旧行逐字节不变')
    else:
        r.fail('safe_edit insert_before 改动了旧行：%r' % (got,))

    # ⑤ --check 的体检函数必须能报出未闭合围栏
    issues, _ev = S.scan_fences(['```java', 'int a = 1;'])
    if issues:
        r.ok('safe_edit --check：未闭合围栏能被报出（%s…）' % issues[0][:28])
    else:
        r.fail('safe_edit --check 漏报未闭合围栏')

    # ⑥ 整节重写（H19）：引入**更多**代码块必须通过——这正是 safe_replace_range 做不到的事
    body = '# 标题2\n```java\nint a = 1;\n```\n中间\n```java\nint b = 2;\n```\n尾部'
    try:
        got = list(base)
        S.safe_replace_section(got, 1, 5, body)
        if len([l for l in got if l.startswith('```')]) == 4 and got[0] == '# 标题2':
            r.ok('safe_edit 整节重写：代码块 1 个 → 2 个仍通过（H19 的核心诉求）')
        else:
            r.fail('safe_edit 整节重写结果不符预期：%r' % (got,))
    except SystemExit as e:
        r.fail('safe_edit 整节重写误拒了合法替换：%s' % str(e)[:80])

    # ⑦ 整节重写 S1：区间起点落在代码块内 → 必须拒绝（否则会截断代码块）
    try:
        S.safe_replace_section(list(base), 3, 5, '纯文本')
        r.fail('safe_edit 整节重写未拒绝"起点在块内"的区间（S1 失效）')
    except SystemExit:
        r.ok('safe_edit 整节重写 S1：区间起点在代码块内 → 拒绝执行')

    # ⑧ 整节重写 S3：替换体围栏不闭合 → 必须拒绝
    try:
        S.safe_replace_section(list(base), 1, 5, '# 标题2\n```java\nint a = 1;')
        r.fail('safe_edit 整节重写未拒绝"替换体围栏不闭合"（S3 失效，H14 会重演）')
    except SystemExit:
        r.ok('safe_edit 整节重写 S3：替换体围栏不闭合 → 拒绝执行')


def check_vib_depth(r):
    """⑪ ⑫ 内容深度判据（S12 / H20）的正向 + 负向自测——**判据本身也要被验证**，否则它只是一句口号。
    合成用例，不依赖宿主项目；三种形态：旧八条（必须被认出） / 现行八条合格样本（不许误拒） / 空壳（必须拦下）。"""
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402

    def seg(items, item5="", item6=""):
        out = ['## ⑫ Vibecoding 视角']
        for i, t in enumerate(items, 1):
            out.append('#### %d. %s' % (i, t))
            body = item5 if i == 5 else (item6 if i == 6 else '')
            out.append(body or '正文一\n正文二\n正文三')
        return '\n'.join(out)

    NEW8 = ['真实需求（`开发任务`）', '现状勘察（`AI 协作过程`）', '方案比较（`开发任务`）',
            '增量实现（`开发任务`）', '可直接使用的提示词（`AI 协作过程`）',
            'AI 产出后的审查（`AI 协作过程`）', '验证反馈循环（`AI 协作过程`）', '最终沉淀（`开发任务`）']
    OLD8 = ['真实需求（开发任务）', '依赖（上游接口与既有代码）', '要新增的类（按依赖顺序）',
            '核心约束（不可动摇的红线）', '给 AI 的提示词模板（八段式）', '迭代过程（三轮修正）',
            '踩过的坑（四个）', '最终沉淀（开发任务）']
    PROMPT = ('【任务】做一件事\n【依赖】A / B\n【要新增的类】C\n【核心约束】D\n'
              '【注释要求】E\n【验收标准】F\n【禁止】G\n【输出格式】H')
    AUDIT = ('| # | 审查项 | 怎么查 |\n|---|---|---|\n'
             + '\n'.join('| %d | x | grep 看什么 |' % i for i in range(1, 7)))

    v = G.vib_depth(seg(OLD8, PROMPT, AUDIT))
    if v['miss_class']:
        r.ok('⑫ 深度判据：旧八条形态被认出缺 %d 类语义（%s…）'
             % (len(v['miss_class']), '、'.join(v['miss_class'][:3])))
    else:
        r.fail('⑫ 深度判据失效：旧八条（依赖 / 要新增的类 / 迭代过程…）竟被认作覆盖全八类')

    v = G.vib_depth(seg(NEW8, PROMPT + '\n**设计要点**：为什么这么写。', AUDIT))
    if not v['miss_class'] and v['labels'] == 8 and v['design'] and v['audit_items'] >= 6:
        r.ok('⑫ 深度判据：现行八条 + 八段 + 设计要点 + 6 项审查 → 四项全过（不误拒合格样本）')
    else:
        r.fail('⑫ 深度判据误拒了合格样本：%r' % (
            {k: v[k] for k in ('miss_class', 'labels', 'design', 'audit_items')},))

    v = G.vib_depth(seg(NEW8))
    if v['labels'] == 0 and not v['design'] and v['audit_items'] == 0:
        r.ok('⑫ 深度判据：只有标题、无提示词 / 无设计要点 / 无审查清单 → 三项全红（空壳拦得住）')
    else:
        r.fail('⑫ 深度判据漏过空壳 ⑫：labels=%d design=%s audit=%d'
               % (v['labels'], v['design'], v['audit_items']))

    # 中式标签写法（`任务：`）同样要认——只认 `【任务】` 就是"把形式当实质"（实测误报来源）
    v = G.vib_depth(seg(NEW8, '任务：做一件事\n依赖：A / B\n要新增的类：C\n核心约束：D\n'
                                '注释要求：E\n验收标准：F\n禁止：G\n输出格式：H\n设计要点：为什么这么写。', AUDIT))
    if v['labels'] >= 6 and v['design']:
        r.ok('⑫ 深度判据：中式标签（`任务：` / `验收标准：`）写法同样被认（%d 段）' % v['labels'])
    else:
        r.fail('⑫ 深度判据只认 `【…】` 一种写法：中式标签被误判（labels=%d design=%s）'
               % (v['labels'], v['design']))

    # ⑤ 边界钉桩（**故意断言"机械判据拦不住空话"**）：
    #    判据只能判"有没有"，判不了"好不好"；判据越形式化，越容易被形式满足。
    #    这份"空话版"满足全部四项机械判据 → FAIL 档放行，**这是已知盲区，必须让读者知道，
    #    否则他会误信绿灯**；与此同时报告档必须报出 ≥8 条缺口（下限层+报告层的分工就在这里）。
    #    将来若判据收紧到能拦住它，这条会失败 → 提示"盲区已收窄，请同步文档与存量工单"。
    VACUOUS = ('【任务】实现功能\n【依赖】用现有的\n【要新增的类】几个类\n【核心约束】注意质量\n'
               '【注释要求】写注释\n【验收标准】测试通过\n【禁止】不要出错\n【输出格式】给我代码\n'
               '**设计要点**：这样写更好，因为更清晰。')
    VAC_AUDIT = ('| # | 审查项 | 怎么查 |\n|---|---|---|\n'
                 + '\n'.join('| %d | 检查一下 | grep 看看 |' % i for i in range(1, 7)))
    v = G.vib_depth(seg(NEW8, VACUOUS, VAC_AUDIT))
    passes_fail = ((not v['miss_class']) and v['labels'] > 0
                   and v['design'] and v['audit_items'] >= 6)
    gaps = sum([v['r2_pitfall'] < 3, (not v['r2_prompt'] and v['r2_items'] < 5),
                not v['r3_table'], not v['r3_reject'], v['r4_steps'] < 6, not v['r4_bound'],
                v['r5_rounds'] < 3, not v['r6_method'], v['r7_rounds'] < 1, v['r8_rules'] < 5])
    if passes_fail and gaps >= 8:
        r.ok('⑫ 深度判据的**已知盲区已钉桩**：空话版仍过 FAIL 档（质量主体在人工审读），'
             '但报告档报出 %d 条缺口兜住' % gaps)
    elif not passes_fail:
        r.fail('⑫ 深度判据已收紧到能拦住"空话版"——盲区收窄了（好消息）！'
               '请同步 SKILL §6.2.1、操作手册 §9 与存量工单')
    else:
        r.fail('⑫ 报告档漏报过多：空话版只被抓出 %d 条缺口（应 ≥8）' % gaps)


def check_new_batch(r):
    """⑨ 新批次脚手架与模板**同源**（契约 V4）：骨架的节标题必须来自模板，且结构项由构造保证。
    这既是新工具的验收测试，也是"模板改了脚手架没跟"的报警器（血证 H9 那类"两套节数"的病）。"""
    sys.path.insert(0, HERE)
    try:
        import new_batch as N              # noqa: E402
    except Exception as e:                 # pragma: no cover
        r.fail('scripts/new_batch.py 无法导入：%s' % e)
        return
    tpl = read('references/批次讲解全文模板.md') or ''
    tpl_secs = [m.group(1).strip() for m in re.finditer(r'^###\s+(.+)$', tpl, re.M)]
    try:
        skel = N.skeleton_lines(notes=[])
    except SystemExit as e:
        r.fail('new_batch 生成骨架时中止：%s' % e)
        return
    skel_secs = [l[3:].strip() for l in skel if re.match(r'^## ', l)]
    if skel_secs != tpl_secs:
        r.fail('骨架节标题与模板不一致：模板 %d 个 / 骨架 %d 个（模板改了，脚手架没跟）'
               % (len(tpl_secs), len(skel_secs)))
    else:
        r.ok('骨架 %d 节与模板 `### ` 节标题逐一同源（①~⑯ + 索引）' % len(skel_secs))
    text = '\n'.join(skel)
    m12 = re.search(r'^## ' + CIRCLED[11] + r'\s', text, re.M)
    m13 = re.search(r'^## ' + CIRCLED[12] + r'\s', text, re.M)
    seg12 = text[m12.end(): m13.start() if m13 else len(text)]
    for tag, cond in (('批级 ⑦.5', '#### ⑦.5' in text),
                      ('⑫ 八条 = 8', len(re.findall(r'^#### \d+\.', seg12, re.M)) == 8),
                      ('⑫ 八段提示词 = 8', len(re.findall(r'^【[^】]+】', seg12, re.M)) == 8)):
        (r.ok if cond else r.fail)('骨架 %s' % tag if cond else '骨架缺 %s' % tag)


def check_inject_source(r):
    """⑩ 源码块注入器端到端自测（H17/H18 的主力工具）：在临时目录里造一个迷你仓库 + 讲解 + plan，
    验证 ① 注入后每行带**真实行号**且逐字来自源文件 ② 源文件不存在时**拒绝写盘**（文件保持原样）。"""
    tool = os.path.join(HERE, 'inject_source.py')
    tmp = tempfile.mkdtemp(prefix='inj_selfcheck_')
    try:
        pkg = os.path.join(tmp, 'mod', 'src', 'main', 'java', 'demo')
        os.makedirs(pkg)
        src_rel = 'mod/src/main/java/demo/Foo.java'
        io.open(os.path.join(tmp, src_rel), 'w', encoding='utf-8', newline='').write(
            'package demo;\n\npublic class Foo {\n    public void run() {\n        int a = 1;\n    }\n}\n')
        lec = os.path.join(tmp, 'batch.md')
        io.open(lec, 'w', encoding='utf-8', newline='').write(
            '# 批次\n\n### 6.1 Foo\n\n```java\n占位\n```\n\n尾注\n')
        plan = os.path.join(tmp, 'plan.json')
        io.open(plan, 'w', encoding='utf-8').write(json.dumps({
            "blocks": [{"anchor": "6.1 Foo", "src": src_rel, "start": 3, "end": 5,
                        "anno": {"4": "唯一入口方法"}}]}))
        p = subprocess.run([sys.executable, tool, lec, plan, '--src', tmp],
                           capture_output=True, text=True,
                           encoding='utf-8', errors='replace')
        text = io.open(lec, encoding='utf-8').read()
        ok = (p.returncode == 0 and 'public class Foo {  // :L3' in text
              and '←教材：唯一入口方法' in text and 'public void run()' in text)
        (r.ok if ok else r.fail)('注入器：逐字取码 + 真实行号 + `←教材：` 注（rc=%s）' % p.returncode
                                if ok else '注入器端到端失败 rc=%s\n     %s' % (p.returncode, (p.stderr or '')[:300]))

        before = io.open(lec, encoding='utf-8').read()
        io.open(plan, 'w', encoding='utf-8').write(json.dumps({
            "blocks": [{"anchor": "6.1 Foo", "src": 'no/such/File.java', "start": 1, "end": 3}]}))
        p2 = subprocess.run([sys.executable, tool, lec, plan, '--src', tmp],
                            capture_output=True, text=True,
                            encoding='utf-8', errors='replace')
        unchanged = io.open(lec, encoding='utf-8').read() == before
        (r.ok if (p2.returncode != 0 and unchanged) else r.fail)(
            '注入器：源文件不存在 → 拒绝写盘（rc=%s，文件未被改动=%s）' % (p2.returncode, unchanged)
            if (p2.returncode != 0 and unchanged) else
            '注入器护栏失效：rc=%s，文件未被改动=%s' % (p2.returncode, unchanged))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_reverse_fallback(r):
    """⑫ ② 反向完整度的「★ 标题链兜底」自测（判据 2.13 / 血证 H23）。

    **为什么这条必须有**：② 原实现只认「块自身含类声明」，而 ⑥ 要求 ★ 类**按职责段拆讲**——
    拆分后没有任何单块含类声明 → ② 静默跳过、打印「0 个★类」并 PASS。**真空通过**最难被发现，
    因为它长得跟真通过一模一样。所以这里用合成用例把它钉死：
      正例 = 段拆块（无类声明）必须被算出覆盖率、且缺行必须被报出；
      反例 = 若哪天有人把兜底删掉（rows 变空），本自检必须 FAIL 而不是继续绿。
    另外钉一条"不许误拒"：整类逐字贴全时覆盖率必须是 100%。
    """
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402
    import tempfile
    import os as _os

    SRC = ('package demo;\n'
           'public class Foo {\n'
           '    private int a;\n'
           '    private int b;\n'
           '    public int sum() {\n'
           '        return a + b;\n'
           '    }\n'
           '    public int diff() {\n'
           '        return a - b;\n'
           '    }\n'
           '}\n')
    tmp = tempfile.mkdtemp(prefix="gate_rev_")
    p = _os.path.join(tmp, "Foo.java")
    open(p, "w", encoding="utf-8").write(SRC)
    by_class = {"Foo": [p]}
    saved = (getattr(G, "ROOT", None), G.SNAPSHOT, G.SNAP_TAR, G.SNAP_UNION)
    G.ROOT, G.SNAPSHOT, G.SNAP_TAR, G.SNAP_UNION = tmp, None, None, None
    try:
        # —— 正例：段拆块（块内没有类声明），★ 只在标题上
        bl = ['    public int sum() {', '        return a + b;', '    }']
        blocks = [(10, "java", bl, "### 6.1 Foo★（按职责段拆讲）", "## ⑥ 逐件讲解",
                   "Foo", ["## ⑥ 逐件讲解"], "")]
        rows = G.check_reverse(blocks, [], by_class)
        if len(rows) == 1 and rows[0]["cls"] == "Foo" and rows[0]["cov"] < 0.995 and rows[0]["miss"] > 0:
            r.ok('② 兜底生效：★ 类按职责段拆讲（块内无类声明）时仍被算出覆盖率 '
                 '（真实缺 %d 行，cov=%.2f）' % (rows[0]["miss"], rows[0]["cov"]))
        elif not rows:
            r.fail('② 又回到「真空通过」：★ 块没有类声明时一个类都没核验（血证 H23 复发）——'
                   '段拆讲是 ⑥ 要求的写法，这种块必须能归属到 ★ 标题里的类')
        else:
            r.fail('② 兜底结果不符预期：%r' % (rows[0],))

        # —— 钉桩反例：整类逐字贴全时，覆盖率必须 100%（兜底不许把"贴全了"判成缺行）
        bl2 = [l for l in SRC.split("\n") if l.strip()]
        blocks2 = [(10, "java", bl2, "### 6.1 Foo★（整文件）", "## ⑥ 逐件讲解",
                    "Foo", ["## ⑥ 逐件讲解"], "")]
        rows2 = G.check_reverse(blocks2, [], by_class)
        if len(rows2) == 1 and rows2[0]["miss"] == 0 and rows2[0]["cov"] == 1.0:
            r.ok('② 不误拒：★ 类整文件逐字贴全 → 覆盖 100%（兜底没把"贴全"判成缺行）')
        else:
            r.fail('② 误拒了整文件贴全的 ★ 类：%r' % (rows2[0] if rows2 else None,))

        # —— 同类去重：同一个 ★ 类被拆成多个段块时，只出一条记录（否则"3 个★类"会被报成"15 个"）
        blocks3 = [(10, "java", bl, "### 6.1 Foo★（段1）", "## ⑥ 逐件讲解", "Foo", ["## ⑥ 逐件讲解"], ""),
                   (40, "java", ['    public int diff() {', '        return a - b;', '    }'],
                    "### 6.1 Foo★（段2）", "## ⑥ 逐件讲解", "Foo", ["## ⑥ 逐件讲解"], "")]
        rows3 = G.check_reverse(blocks3, [], by_class)
        if len(rows3) == 1:
            r.ok('② 同类去重：同一 ★ 类的 2 个段块只出 1 条记录（★类数不再被段数放大）')
        else:
            r.fail('② 同类没去重：2 个段块出了 %d 条记录（"N 个★类"会被段数放大）' % len(rows3))
    finally:
        G.ROOT, G.SNAPSHOT, G.SNAP_TAR, G.SNAP_UNION = saved
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)


def check_usage_boundary(r):
    """⑬ ⑤ 的「件段不得越过一级节标题」自测（判据 2.14 / 血证 H24）。

    **为什么钉它**：原实现里"最后一个 6.x 件"的段一直延伸到文件末尾，于是 ⑨ No-Framework 里那段
    手写的 `interface Scorer { … }` 骨架被算进那个件 → 它凭空多出"抽象件"身份、被要求写【怎么接】。
    这种误判**看不出来**：人只会觉得"这个件确实有接口啊"，然后去补一个语义上不该有的小节。
    """
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402

    head = ["## ⑥ 逐件讲解", "### 6.1 Foo —— 唯一的件（10 行）", "正文一", "正文二",
            "**【怎么用】调用现场**", "正文三", "**【上下游】**", "正文四", "---",
            "## ⑨ No-Framework：不用框架怎么手写", "", "```java",
            "interface Scorer { List<Score> score(String question); }", "```",
            "", "**【怎么接】** 写在后面一节里，不该算到 6.1 头上"]
    items, _ext = G.check_usage(head)
    if len(items) == 1 and items[0]["iface"] is False and items[0]["wire"] is False:
        r.ok('⑤ 件段边界（2.14）：后面一级节里的 `interface` 骨架与【怎么接】不再算进末件 '
             '（iface=False / wire=False，均由本节自己决定）')
    else:
        r.fail('⑤ 件段越界（H24 复发）：末件把后面小节的内容算进自己 → %r'
               % ({k: items[0][k] for k in ("iface", "wire")} if items else items,))

    # 反向钉桩：**本节内**真的有 interface 骨架时，必须仍然认出来（别把边界修成"永不判抽象"）
    own = ["## ⑥ 逐件讲解", "### 6.1 Bar —— 真抽象件（10 行）", "正文一", "正文二", "```java",
           "public interface Bar { void run(); }", "```", "**【怎么用】** 用法", "**【上下游】** 上下游",
           "**【怎么接】** 实现与注册", "---", "## ⑦ 调用链"]
    items2, _ = G.check_usage(own)
    if len(items2) == 1 and items2[0]["iface"] is True and items2[0]["wire"] is True:
        r.ok('⑤ 件段边界（2.14）：件内自己的 `interface` 骨架仍被认出（iface/wire 都为真）')
    else:
        r.fail('⑤ 边界修过头了：件内自带的 interface 没被认出 → %r'
               % ({k: items2[0][k] for k in ("iface", "wire")} if items2 else items2,))


def check_section_form(r):
    """⑭ 一级节标题规范形态自测（判据 2.15 / 血证 H25）。

    **为什么钉它**：⑫/⑯ 等节靠 `^## ⑫\\s` 这类带圈数字正则定位；带圈数字在部分落盘链路会**静默丢失**
    （本文件自己就丢过两处：⑨ 与 ⑫，存活数周无人发现——这正是 H25 的原件）。标题变形后，
    那一节的所有检查被整体跳过却照样打印 PASS。「找不到段」必须是 FAIL，不许静默跳过。
    """
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402

    # 正例：17 节规范标题全齐 → 不缺、不变形
    good = ['# 批'] + ['## %s 节%d' % (c, i) for i, c in enumerate(G.CIRCLED16, 1)] + ['## 索引']
    miss, deform, _heads = G.section_form_check(good)
    if not miss and not deform:
        r.ok('节标题形态：17 节规范标题全部命中（①~⑯ + 索引）')
    else:
        r.fail('节标题形态误拒规范标题：缺 %s / 变形 %s' % (miss, deform))

    # 负例 1：⑫ 的带圈数字丢失（标题还在，首字符没了）→ 必须报缺失 ⑫
    bad1 = ['# 批'] + ['## %s 节%d' % (c, i) for i, c in enumerate(G.CIRCLED16, 1) if c != '⑫'] \
        + ['## Vibecoding 视角', '## 索引']
    miss, deform, _heads = G.section_form_check(bad1)
    if '⑫' in miss:
        r.ok('节标题形态：⑫ 带圈数字丢失 → 报缺失（不再静默跳过该节）')
    else:
        r.fail('节标题形态漏报：⑫ 丢失却未报缺失（miss=%s deform=%s）' % (miss, deform))

    # 负例 2：`##  ⑫`（## 后多一个空格）→ 宽松命中但规范形态不命中 → 必须报变形并带原文
    bad2 = ['# 批'] + ['## %s 节%d' % (c, i) for i, c in enumerate(G.CIRCLED16, 1) if c != '⑫'] \
        + ['##  ⑫ Vibecoding 视角', '## 索引']
    miss, deform, _heads = G.section_form_check(bad2)
    if any(c == '⑫' and '##  ⑫' in h for c, h in deform):
        r.ok('节标题形态：`##  ⑫`（多余空格）→ 报变形并打印实际原文')
    else:
        r.fail('节标题形态漏报：`##  ⑫` 多余空格未报变形（miss=%s deform=%s）' % (miss, deform))

    # 负例 3：缺索引节 → 必须报缺失「索引」
    bad3 = ['# 批'] + ['## %s 节%d' % (c, i) for i, c in enumerate(G.CIRCLED16, 1)]
    miss, deform, _heads = G.section_form_check(bad3)
    if '索引' in miss:
        r.ok('节标题形态：缺索引节 → 报缺失')
    else:
        r.fail('节标题形态漏报：索引节缺失未报（miss=%s）' % (miss,))


def check_vib_retro(r):
    """⑮ ⑫ 回顾语判据自测（2.16 / 血证 H26）：从零构建视角的机械兜底。

    **为什么钉它**：⑫ 旧框架（"回顾性重构声明"）曾是模板原文、被照抄进 26 份批次；
    新框架要求"从零构建视角"。这条判据管"时态"（自指禁令管"指称"）。
    必须钉住两个边界：旧声明要命中；合规的"逆向重建"诚实声明**不许**误伤。"""
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402

    # 正例：从零构建叙事 + 合规的逆向重建声明 → 不命中（"逆向重建"/"当时的"不在词表）
    good = ['## ⑫ Vibecoding 视角（八条）', '',
            '> 声明：本节开发过程为按最终代码逆向重建的叙事，而非声称这是当时的真实对话。',
            '#### 1. 真实需求', '你接到一个工单：为结算组加定时对账。', '', '## ⑬ 验证证据']
    st = G.check_structure(good, True)
    if not st['retro']:
        r.ok('⑫ 回顾语：从零构建叙事 + 合规逆向重建声明 → 不误报（逆向重建 / 当时的 不在词表）')
    else:
        r.fail('⑫ 回顾语误伤合规声明：%s' % (st['retro'],))

    # 负例 1：旧框架声明 → 命中并给出词名与次数
    bad1 = ['## ⑫ Vibecoding 视角', '> **回顾性重构声明**：本节的开发过程是回顾性重构。', '## ⑬ 验证证据']
    st = G.check_structure(bad1, True)
    if any(w == '回顾性重构' for w, _ in st['retro']):
        r.ok('⑫ 回顾语：旧框架声明（回顾性重构）→ 命中 FAIL 档')
    else:
        r.fail('⑫ 回顾语漏报旧框架声明（回顾性重构）')

    # 负例 2：典型回顾表述 → 命中
    bad2 = ['## ⑫ Vibecoding 视角', '回看这一批，当时我们已经写完三件套。', '## ⑬ 验证证据']
    st = G.check_structure(bad2, True)
    hit = {w for w, _ in st['retro']}
    if {'回看这一批', '当时我们', '已经写完'} <= hit:
        r.ok('⑫ 回顾语：回看这一批 / 当时我们 / 已经写完 → 全部命中')
    else:
        r.fail('⑫ 回顾语漏报典型回顾表述（命中 %s）' % sorted(hit))


def check_core_sections_sc(r):
    """⑯ ⓪b 每批必含内容自测（2.17 / 血证 H26）：① 架构图 / ⑦.1 编号链 / ⑧ L0-L3。

    口径全部经过全库实测校准（60 份批次）：① 命中 10 份、⑦.1 命中 44 份、⑧ 命中约 31 份——
    命中即真缺（散文链/无图/无省略段），16 份编号链批次 0 误伤。"""
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402
    import tempfile                   # noqa: E402

    with tempfile.TemporaryDirectory() as td:
        for name in ('AlphaService', 'BetaGateway', 'GammaClient'):
            io.open(os.path.join(td, name + '.java'), 'w', encoding='utf-8').write(
                'public class %s { void go(){} }\n' % name)
        by_class, _ = G.index_sources(td)

        DIA = ['## ① 全景', '```text', '┌─ AlphaService ─────────┐',
               '│        │ go()          │', '│        ▼               │',
               '│   BetaGateway ──► GammaClient │', '│        │               │',
               '└────────┼───────────────┘', '         ▼ 出站', '```']
        CHAIN = ['#### ⑦.1 调用链（编号列表带行号）', '',
                 '1  入口.handle()', '2   → AlphaService.go()        AlphaService.java:1',
                 '3     → BetaGateway.go()       BetaGateway.java:1',
                 '4       → GammaClient.go()     GammaClient.java:1',
                 '5     ← 返回                   BetaGateway.java:1',
                 '6   → 渲染                     View.java:1', '', '#### ⑦.2 数据流']
        DRILL = ['## ⑧ 穿透卡', '- **L0 源码证据**：x', '- **L1 机制拆解**：x',
                 '- **L2 等价实现**：x', '**省略了什么生产边界**：分布式锁/持久化', '- **L3 设计取舍**：x']

        good = DIA + ['## ⑦ 调用链'] + CHAIN + ['## ⑧ 穿透卡'] + DRILL[1:] + ['## ⑨ x']
        c = G.check_core_sections(good, by_class, td)
        if not any(c.values()):
            r.ok('⓪b 合规批次（图 + 编号链 + L0-L3+省略段）→ 三项全过')
        else:
            r.fail('⓪b 误伤合规批次：%s' % ({k: v for k, v in c.items() if v},))

        no_dia = ['## ① 全景', '```text', '本批有三个类，互相协作完成工作。', '```'] + good[10:]
        c = G.check_core_sections(no_dia, by_class, td)
        r.ok('① 无架构图 → sec1 命中（图 <5 行连接线）') if c['sec1'] else r.fail('① 无图未命中')

        fake_dia = ['## ① 全景', '```text', '┌─ Service ──┐', '│    │       │',
                    '│    ▼       │', '│  Mapper    │', '│    │       │',
                    '└────┼───────┘', '     ▼', '  Controller', '```'] + good[10:]
        c = G.check_core_sections(fake_dia, by_class, td)
        r.ok('① 图内只有通用词（Service/Mapper/Controller）→ 标识符 <3 命中') if c['sec1'] and '标识符' in c['sec1'] \
            else r.fail('① 空盒子通用词未命中')

        prose_chain = ['## ① 全景'] + DIA[1:] + ['## ⑦ 调用链', '#### ⑦.1 调用链', '',
                       '入口先调 AlphaService（AlphaService.java:1），再转给 BetaGateway（BetaGateway.java:1），'
                       '随后是 GammaClient（GammaClient.java:1），最后渲染返回（View.java:1）。',
                       '#### ⑦.2 数据流'] + ['## ⑧ 穿透卡'] + DRILL[1:] + ['## ⑨ x']
        c = G.check_core_sections(prose_chain, by_class, td)
        r.ok('⑦.1 散文式箭头链 → chain 命中（编号跳 <5）') if c['chain'] else r.fail('⑦.1 散文链未命中')

        no_ln = ['## ① 全景'] + DIA[1:] + ['## ⑦ 调用链', '#### ⑦.1 调用链', '',
                 '1  → AlphaService.go()', '2   → BetaGateway.go()', '3     → GammaClient.go()',
                 '4       → 渲染', '5     ← 返回', '#### ⑦.2 数据流'] + ['## ⑧ 穿透卡'] + DRILL[1:] + ['## ⑨ x']
        c = G.check_core_sections(no_ln, by_class, td)
        r.ok('⑦.1 有编号跳但无行号 → chain 命中（带行号 <5）') if c['chain'] else r.fail('⑦.1 无行号未命中')

        no_l2 = ['## ① 全景'] + DIA[1:] + ['## ⑦ 调用链'] + CHAIN + ['## ⑧ 穿透卡',
                 '- **L0 源码证据**：x', '- **L1 机制拆解**：x', '- **L3 设计取舍**：x', '## ⑨ x']
        c = G.check_core_sections(no_l2, by_class, td)
        r.ok('⑧ 缺 L2 层级标签 → drill 命中') if c['drill'] and '层级标签' in c['drill'] else r.fail('⑧ 缺层级未命中')

        no_omit = ['## ① 全景'] + DIA[1:] + ['## ⑦ 调用链'] + CHAIN + ['## ⑧ 穿透卡',
                   '- **L0 源码证据**：x', '- **L1 机制拆解**：x', '- **L2 等价实现**：x',
                   '- **L3 设计取舍**：x', '## ⑨ x']
        c = G.check_core_sections(no_omit, by_class, td)
        r.ok('⑧ 有 L0-L3 但无「省略了什么」段 → drill 命中') if c['drill'] and '省略' in c['drill'] \
            else r.fail('⑧ 缺省略段未命中')

        # ⑦.1 标题的另一种存量形态 `### 7.1`（无带圈数字）也要认得
        alt = ['## ① 全景'] + DIA[1:] + ['## ⑦ 调用链'] + [
            ('### 7.1 调用链' if l.startswith('#### ⑦.1') else l) for l in CHAIN] + ['## ⑧ 穿透卡'] + DRILL[1:] + ['## ⑨ x']
        c = G.check_core_sections(alt, by_class, td)
        r.ok('⑦.1 标题写成 `### 7.1`（存量形态）→ 不误报缺小节') if c['chain'] is None else r.fail('⑦.1 替代标题误报')


def check_pedagogy_sc(r):
    """⑰ ⓪c 教材自足与构造手法自测（2.18 / H26，报告档）：白话开场与构造/手法点名。"""
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402

    # 白话开场：块前有中文开场行 → 不缺；块上方最近非空行无中文且非表格 → 缺
    lines = ['## ⑥ 逐件讲解', '', '### 6.1 `XxxService`', '',
             '**白话开场**：这段把上游的原始文本切成可检索的块，看完能答"切块边界怎么定"。', '',
             '```java', 'class A {}', '```', '',
             'plain english note, no intro sentence', '',
             '```java', 'class B {}', '```']
    import tempfile, os
    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, 't.md')
        io.open(p, 'w', encoding='utf-8').write('\n'.join(lines))
        ls, blocks = G.parse_blocks(p)
        ped = G.check_pedagogy(ls, blocks)
        if ped['blocks_total'] == 2 and ped['blocks_no_intro'] == 1:
            r.ok('⓪c 白话开场：有中文开场句的块不算缺、上方只有纯英文行的块算缺（1/2）')
        else:
            r.fail('⓪c 白话开场统计错：%s' % ped)

        # 表格行紧邻代码块 = 表格本身就是说明，不算缺（口径防呆）
        lines_t = ['## ⑥ 逐件讲解', '### 6.1 `A`', '| 行 | 讲解 |', '|---|---|', '| 1 | x |',
                   '```java', 'class A {}', '```']
        pt = os.path.join(td, 'tt.md')
        io.open(pt, 'w', encoding='utf-8').write('\n'.join(lines_t))
        lst, bt = G.parse_blocks(pt)
        pedt = G.check_pedagogy(lst, bt)
        if pedt['blocks_no_intro'] == 0:
            r.ok('⓪c 白话开场：表格行紧邻代码块不算缺开场（表格本身就是说明）')
        else:
            r.fail('⓪c 表格行被误判缺开场：%s' % pedt)

        # 构造方式/手法：6.x 件正文点名 → 不缺；缺则计数
        lines2 = ['## ⑥ 逐件讲解', '### 6.1 `A`', '',
                  '由 `BFactory` 在启动时 new 出来并注册进容器，生命周期为应用级单例。', '```java', 'class A {}', '```', '',
                  '### 6.2 `B`', '', '逐行说明……（只讲每行在干什么）', '```java', 'class B {}', '```']
        p2 = os.path.join(td, 't2.md')
        io.open(p2, 'w', encoding='utf-8').write('\n'.join(lines2))
        ls2, blocks2 = G.parse_blocks(p2)
        ped2 = G.check_pedagogy(ls2, blocks2)
        if ped2['items_total'] == 2 and ped2['items_no_construct'] == 1 and ped2['items_no_technique'] == 2:
            r.ok('⓪c 构造/手法：点名构造方式的件不算缺（1/2 缺构造、2/2 缺手法）')
        else:
            r.fail('⓪c 构造/手法统计错：%s' % ped2)

        # 件段越节保护：## ⑧ 里的"模式"字样不能算到 ⑥ 最后一个件头上
        lines3 = ['## ⑥ 逐件讲解', '### 6.1 `A`', '', '只讲每行是什么。', '```java', 'class A {}', '```', '',
                  '## ⑧ 穿透卡', '这一节讨论责任链模式与权衡。']
        p3 = os.path.join(td, 't3.md')
        io.open(p3, 'w', encoding='utf-8').write('\n'.join(lines3))
        ls3, blocks3 = G.parse_blocks(p3)
        ped3 = G.check_pedagogy(ls3, blocks3)
        if ped3['items_total'] == 1 and ped3['items_no_technique'] == 1:
            r.ok('⓪c 件段越节保护：⑧ 节的"模式"字样不算 ⑥ 件的手法（沿用 2.14 教训）')
        else:
            r.fail('⓪c 件段越节保护失效：%s' % ped3)



def check_lecture_class_sc(r):
    """⑱ 教材类文件判定自测（2.20）：封堵「没有 java 代码块就跳过结构判定」的真空通过。

    为什么钉它：判据只在「能识别出对象」时才生效，于是**改变对象的语言或形态就能绕过它**（H23/H25 同族）；
    实测：examples/黄金样例-python.md（无 java 块）曾被整体跳过结构判定并打印 PASS。"""
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402
    C = G.CIRCLED16

    java_blocks = [(0, 'java', ['public class A {'] + ['    int x%d = 1;' % i for i in range(6)] + ['}'], '', '', '', [], '')]
    ok, why = G.is_lecture(['# x'], java_blocks)
    if ok:
        r.ok('教材判定：含 java 代码块 → 教材（老口径仍成立）')
    else:
        r.fail('教材判定漏报 java 批次：%s' % why)

    ref = ['# 黄金样例（节选）', '',
           '> **形态状态（2.20 复检）**：本文档是深度基准存档。',
           '## ' + C[0] + ' 在系统全景中的位置']
    ok2, why2 = G.is_lecture(ref, [])
    if not ok2:
        r.ok('教材判定：声明位写「形态状态」 → 参照物豁免（不误伤）')
    else:
        r.fail('教材判定误伤参照物（未豁免）：%s' % why2)

    synth = ['# 阶段1 · 批次1', '', '> **本批一句话**：合成。', '> **源码依据**：commit `16984b9`。',
             '', '## ' + C[0] + ' 在系统全景中的位置', '', '## ' + C[1] + ' 业务场景',
             '', '## ' + C[2] + ' 文件清单', '', '#### 6.1 Foo —— 示例', '', '正文。']
    ok3, why3 = G.is_lecture(synth, [])
    if ok3:
        r.ok('教材判定：无 java 块但教材标志 >=3 项 → 仍判教材（**真空通过已封堵**）')
    else:
        r.fail('教材判定漏报：无 java 块的教材类文件仍被当普通文档（%s）' % why3)

    plain = ['# 能力账本', '', '## 1. 能力清单', '', '| a | b |', '|---|---|', '| 1 | 2 |']
    ok4, why4 = G.is_lecture(plain, [])
    if not ok4:
        r.ok('教材判定：普通档案文档（无标志）→ 非教材（不误伤）')
    else:
        r.fail('教材判定误伤普通文档：%s' % why4)

    head_hist = ['# 阶段1 · 批次1', '', '> **本批一句话**：。', '> **源码依据**：commit `16984b9`。',
                 '', '> 若当前树已重写，见 ⑥ 的【历史版本示例】与「当前实现」小节。']
    ok5, why5 = G.is_lecture(head_hist, java_blocks)
    if ok5:
        r.ok('教材判定：批头提到【历史版本示例】不误判为参照物（声明位才认）')
    else:
        r.fail('教材判定：批头的【历史版本示例】把批次误判成参照物（%s）' % why5)


def check_sync_idempotent(r):
    """⑳ `sync_gate_result.py` 实测块替换的幂等性（2.29 / BUG-S1）。

    血证（2026-09-18 实测）：旧 `end` 只走一步——HEAD 行下一行恒是空行，循环立即退出，
    于是**只替换了 HEAD 那一行**，旧表格与旧说明全部留下 → 每跑一次多堆一张表。
    受害 11 批：批次37 堆到 11 张、批次33/1 各 3 张、批次9/10/34/35/36/38 各 2 张；
    同一份 ⑯ 里并存 v2.24 / v2.25 / v2.28 三套互相矛盾的数字——正好违背本工具的存在理由。
    本检查用一段**含两张叠表**的样本钉死：block_end 必须吃到最后一张表的说明行，且连做两次替换后
    HEAD 只剩 1 个。
    """
    sys.path.insert(0, HERE)
    import sync_gate_result as S      # noqa: E402
    NOTE = ('> 本表由 `scripts/sync_gate_result.py` 从闸门实跑输出生成，'
            '**不是复述旧结论**（血证 H15）；判据版本以本表首行的 v%s 为准。')
    blocks = ['| # | 闸门组 | 实测值 | 结论 |', '|---|---|---|---|', '| ⓪ | 结构 | 旧 | 通过 |']
    lines = ['## ⑯ 教材质量自检',
             '**七组闸门实测**（判据 v2.24，`gate_lecture.py` 单条命令退出码 0）**：', '']
    lines += blocks + ['', NOTE % '2.24', '']
    lines += blocks + ['', NOTE % '2.21', '']
    lines += ['**判据版本：v2.21**（本批按此版判据验收）', '', '## 索引节']
    end = S.block_end(lines, 1)
    if end != 13:
        r.fail('⑳ block_end 未吃掉历史叠表：返回 %d（应为 13 = 第二张表的说明行）——'
               '旧实现只吃到 HEAD 行 → 每跑一次多堆一张表（批次37 堆到 11 张）' % end)
        return
    r.ok('⑳ block_end 吃满历史叠表（HEAD + 2 张表 + 2 条说明 → 末行 :14）')
    new = '**七组闸门实测**（判据 v2.99，`gate_lecture.py` 单条命令退出码 0）**：\n\n' \
          + '\n'.join(blocks) + '\n\n' + NOTE % '2.99' + '\n'
    for _ in range(2):
        i = next((k for k, l in enumerate(lines) if S.MARK_RE.match(l)), None)
        if i is None:
            r.fail('⑳ 幂等自测中找不到 HEAD 行（替换把标题吃掉了）')
            return
        S.safe_replace_range(lines, i + 1, S.block_end(lines, i) + 1, new)
    heads = sum(1 for l in lines if S.MARK_RE.match(l))
    stale = sum(1 for l in lines if S.NOTE_RE.match(l.strip()))
    if heads == 1 and stale == 1:
        r.ok('⑳ 连做两次替换后 HEAD=1 / 说明行=1（幂等成立，不再堆表）')
    else:
        r.fail('⑳ 幂等失败：HEAD=%d / 说明行=%d（都应为 1）——旧表会一直堆下去' % (heads, stale))


def check_record_shape_sc(r):
    """⑲ 记录类形态自测（2.21）：整理批 / 进行中记录既不按 17 节判，也不能没人管。"""
    sys.path.insert(0, HERE)
    import gate_lecture as G          # noqa: E402
    Cc = G.CIRCLED16

    ok, why = G.is_record(["# x"], "批次0-整理批.md")
    if ok:
        r.ok('记录类识别：文件名含「整理批」→ 记录类')
    else:
        r.fail('记录类识别漏报：%s' % why)

    good = ['# 整理批', '', '> 状态：进行中（2026-09-17）', '', '## 未完成项',
            '', '1. 补齐旧批次的回链', '2. 回写能力账本', '', '- [ ] 跑一次全量闸门']
    b1 = G.check_record_shape(good)
    if not b1:
        r.ok('记录类形态：有状态行 + 未完成清单 → 0 违规')
    else:
        r.fail('记录类形态误报合规文件：%s' % b1)

    b2 = G.check_record_shape(['# 草稿', '', '正文。'])
    h = " ".join(b2)
    if "R1" in h and "R2" in h:
        r.ok('记录类形态：无状态行 + 无清单 → R1/R2 均命中')
    else:
        r.fail('记录类形态漏报 R1/R2：%s' % b2)

    fake = (['# 批次1', '', '> 状态：已完成']
            + ['## ' + Cc[i] + ' 节' for i in range(3)] + ['#### 6.1 Foo —— 示例', '', '正文。'])
    b3 = G.check_record_shape(fake)
    if any(x.startswith("R3") for x in b3):
        r.ok('记录类形态：带成品批迹且不写未完成/草稿 → R3 命中')
    else:
        r.fail('记录类形态：伪装成品未命中 R3：%s' % b3)

    vs = G.declared_at_least(['> 判据版本：v2.21'], G.RECORD_FAIL_SINCE)
    vr = G.declared_at_least(['> 无版本声明'], G.RECORD_FAIL_SINCE)
    if vs and not vr:
        r.ok('记录类档位：声明 v2.21 → FAIL 档；未声明 → 报告档（不追溯存量）')
    else:
        r.fail('记录类档位异常：strict=%s report=%s' % (vs, vr))

def main():
    print('=' * 88)
    print('技能文档一致性自检（skill_selfcheck.py）  根目录:', ROOT)
    print('=' * 88)
    r = Report()
    print('\n① 判据版本号')
    check_version(r)
    print('\n② ⑤ 用法与接入标记（SKILL / 模板 / gate 三处一致）')
    check_markers(r)
    print('\n③ 17 节骨架与 §6 概要指向')
    check_sections(r)
    print('\n④ 作废写法扫描')
    check_deprecated(r)
    print('\n⑤ 交叉引用与文件引用')
    check_refs(r)
    print('\n⑥ SSOT 对账（spec/00-质量契约.json ↔ SKILL ↔ 模板 ↔ gate/工具）')
    check_ssot(r)
    print('\n⑦ 工具随技能发布（V3 / H17）：无孤儿 + 依赖符号存在')
    check_tools(r)
    print('\n⑧ safe_edit 护栏负向自测（H14 / H19）')
    check_safe_edit(r)
    print('\n⑨ 新批次脚手架与模板同源（V4）')
    check_new_batch(r)
    print('\n⑩ 源码块注入器端到端自测（H17 / H18）')
    check_inject_source(r)
    print('\n⑪ ⑫ 内容深度判据自测（S12 / H20）+ 已知盲区钉桩')
    check_vib_depth(r)
    print('\n⑫ ② 反向完整度的 ★ 标题链兜底自测（2.13 / H23）+ 真空通过钉桩')
    check_reverse_fallback(r)
    print('\n⑬ ⑤ 件段边界自测（2.14 / H24）：后面小节的内容不许算进末件')
    check_usage_boundary(r)
    print('\n⑭ 一级节标题规范形态自测（2.15 / H25）：找不到段 = FAIL，不许静默跳过')
    check_section_form(r)
    print('\n⑮ ⑫ 回顾语判据自测（2.16 / H26）：从零构建视角，旧框架声明必命中、合规声明不误伤')
    check_vib_retro(r)
    print('\n⑯ ⓪b 每批必含内容自测（2.17 / H26）：① 图 / ⑦.1 编号链 / ⑧ L0-L3+省略段')
    check_core_sections_sc(r)
    print('\n⑰ ⓪c 教材自足与构造手法自测（2.18 / H26，报告档）')
    check_pedagogy_sc(r)
    print('\n⑱ 教材类文件判定自测（2.20）：不许「换语言就跳过结构判定」')
    check_lecture_class_sc(r)
    print('\n⑲ 记录类形态自测（2.21）：整理批/进行中记录也要自证状态')
    check_record_shape_sc(r)
    print('\n⑳ sync_gate_result 实测块替换幂等（2.29 / BUG-S1）：不许每跑一次堆一张旧表')
    check_sync_idempotent(r)
    print('\n' + '=' * 88)
    print('检查项 %d，失败 %d → %s' % (r.n, r.bad, 'PASS ✅' if r.bad == 0 else 'FAIL ❌'))
    print('=' * 88)
    return 1 if r.bad else 0


if __name__ == '__main__':
    sys.exit(main())
