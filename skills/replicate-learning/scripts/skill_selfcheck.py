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

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯'


def read(rel):
    p = os.path.join(ROOT, rel)
    return io.open(p, encoding='utf-8').read() if os.path.isfile(p) else None


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
    gate = read('scripts/gate_lecture.py') or ''
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
                 if e.get('gate') and e['gate'] != '-' and e['gate'] not in gate]
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
    print('\n⑥ SSOT 对账（spec/00-质量契约.json ↔ SKILL ↔ 模板 ↔ gate）')
    check_ssot(r)
    print('\n' + '=' * 88)
    print('检查项 %d，失败 %d → %s' % (r.n, r.bad, 'PASS ✅' if r.bad == 0 else 'FAIL ❌'))
    print('=' * 88)
    return 1 if r.bad else 0


if __name__ == '__main__':
    sys.exit(main())
