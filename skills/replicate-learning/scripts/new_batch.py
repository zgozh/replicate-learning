#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新批次脚手架 —— 从 `references/批次讲解全文模板.md` 的**骨架区**生成一份可直接开写的批次文件。

**为什么它随技能发布**：新批次最常见的结构性缺陷是"漏项"——漏节、漏批级 `⑦.5`、漏批头快照声明、
⑫ 八条写成七条。这些都是**机械可判**的（闸门 ⓪ 与 ⑤ 会报），但"报出来再补"不如"从源头就长对"。
本工具让骨架与模板**同源**：节标题不是硬编码，而是每次从模板抽出来的——模板改了，脚手架跟着改，
不会再出现"两套节数"（血证 H9 的同一类病）。

用法：
    python new_batch.py --stage 8 --batch 1 \\
        --title "对话记忆滑窗（ConversationMemoryService★+JdbcConversationMemoryStore★）" \\
        --classes "ConversationMemoryService★, JdbcConversationMemoryStore★" \\
        --sha 6aef475 --out "NOTES/教学讲解/阶段8-.../批次1-....md" [--src <仓库根>] [--force]

产出：批头（一句话/核心类/验收结果/源码依据 commit）+ ①~⑯ + 索引，共 **17 个 `## ` 节**，
其中 `⑦.5`、⑯ 六项空表、⑫ 八条与八段提示词标签都已就位；正文占位符沿用模板的 `__xxx__` 写法。

不做的事：不生成任何讲解内容、不写任何代码、不跑闸门（跑闸门是下一步，命令会打印出来）。
"""
import argparse
import io
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gate_lecture import GATE_VERSION   # 2.19 判据版本的单一来源
ROOT = os.path.dirname(HERE)
TPL = os.path.join(ROOT, 'references', '批次讲解全文模板.md')
CIRCLED = '①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯'
# 与 gate_lecture.check_structure 的 S6 完全同口径（⑫ 教材自指 = 0）
SELFREF = re.compile(r'本批|本阶段|教材第|答案卷|阶段[0-9]|批次[0-9]')
# 与 gate_lecture.VIB_RETRO（判据 2.16 / 血证 H26）完全同口径（⑫ 回顾语 = 0）
RETRO = ('回顾性重构', '回顾性重建', '本批已实现', '本批已经实现', '本批的代码', '本批代码',
         '本批实现', '回看这一批', '当时我们', '已经写完', '回述', '事后重建', '复刻出', '那一批')


def skeleton_lines(tpl_path=TPL, notes=None):
    """从模板抽出骨架区（`### ①` 起，到下一个一级 `## ` 止），并做三处**机械纠偏**：

    ① 节标题 H3 → H2（批次文件里节是一级 `## `）；`### 索引节` 同样降级——否则节数只有 16（实测踩过）。
    ② 剥离全部 `^> ` 指导语（它们是写给你看的写作须知，不是批次内容）。**必须剥**：⑫ 里那条
       "禁止教材自指（本批/本阶段/教材第/阶段N）"本身含这些词，抄进文件就让 ⓪ 的自指检查 FAIL（实测 6 处）。
       剥离的原文通过 `notes` 返回，由调用方打印，信息不丢。
    ③ ⑫ 第 5 条补上**八段提示词标签**（从模板那条硬要求里抽出来，不硬编码），第 6/7 条补到 ≥3 行防"薄条"。
    """
    text = io.open(tpl_path, encoding='utf-8').read()
    lines = text.split('\n')
    start = next(i for i, l in enumerate(lines) if re.match(r'^###\s*' + CIRCLED[0] + r'\s', l))
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith('## '))
    body = lines[start:end]
    while body and not body[-1].strip():
        body.pop()

    out = []
    for l in body:
        if l.startswith('> '):
            if notes is not None:
                notes.append(l)
            continue
        out.append('## ' + l[4:] if re.match(r'^###\s', l) else l)

    # ③-a 八段提示词标签（从模板的 ⑫ 硬要求行里抽，取的顺序即标签顺序）
    labels = re.findall(r'【[^】]+】', next((l for l in body if '八段完整模板' in l), ''))
    if len(labels) != 8:
        raise SystemExit('[ABORT] 从模板抽出的提示词标签不是 8 个（实为 %d）：%s' % (len(labels), labels))
    for i, l in enumerate(out):
        if l.startswith('#### 5. 可直接使用的提示词'):
            out[i + 1:i + 2] = ['%s__待填：本段的意图一句话__' % lab for lab in labels]
            break

    # ③-b ⑫ 内每条 ≥3 非空行（闸门 ⓪ 的"薄条"判据是 ≤2 行 = 一句话带过）
    i12 = next(i for i, l in enumerate(out) if re.match(r'^##\s*' + CIRCLED[11] + r'\s', l))
    i13 = next(i for i in range(i12 + 1, len(out)) if re.match(r'^##\s*' + CIRCLED[12] + r'\s', out[i]))
    k = i12 + 1
    while k < i13:
        if re.match(r'^#### \d+\.', out[k]):
            j = k + 1
            while j < i13 and not re.match(r'^#### \d+\.', out[j]) and not out[j].strip() == '---':
                j += 1
            n_body = len([x for x in out[k + 1:j] if x.strip()])
            if n_body <= 2:
                out[j:j] = ['- __待填：这一步的关键判断（写清"为什么"，不要只写"做了什么"）__',
                            '- 证据等级：__推断 / 事实-源码 / 实测__']
                j += 2
            k = j
        else:
            k += 1

    # ④ 教材自指清零 + **断言**：模板里的 `__批次1__` 这类占位符自带 `批次N`，抄进 ⑫ 就让 ⓪ FAIL（实测 2 处）。
    #    改写为 `__第1步__`，然后按闸门同口径复查 ⑫ 段；模板将来新增自指词会让本工具当场报错，而不是悄悄漏过。
    out = [re.sub(r'__批次(\d+)__', r'__第\1步__', l) for l in out]
    txt = '\n'.join(out)
    m12 = re.search(r'^## ' + CIRCLED[11] + r'\s', txt, re.M)
    m13 = re.search(r'^## ' + CIRCLED[12] + r'\s', txt, re.M)
    seg = txt[m12.end(): m13.start() if m13 else len(txt)]
    hits = SELFREF.findall(seg)
    if hits:
        raise SystemExit('[ABORT] 生成的骨架在 ⑫ 段仍有教材自指 %s\n'
                         '   → 模板里新增了自指词，请同步 new_batch.py 的清零规则' % sorted(set(hits)))
    # 判据 2.16（与 gate_lecture.VIB_RETRO 完全同口径）：⑫ 回顾语黑名单——
    # 模板的 ⑫ 骨架若带入回顾语，每个新批次都会带着它 FAIL；模板改了什么，这里当场报错。
    retro_hits = [w for w in RETRO if w in seg]
    if retro_hits:
        raise SystemExit('[ABORT] 生成的骨架在 ⑫ 段含回顾语 %s\n'
                         '   → 模板 ⑫ 的非指导语行引入了回顾语，请修 references/批次讲解全文模板.md'
                         % sorted(set(retro_hits)))
    return out


def header(stage, batch, title, classes, sha, verify):
    return [
        '# 阶段%s · 批次%s —— %s' % (stage, batch, title),
        '',
        '> **本批一句话**：__一句话说清这批把哪条链路推进了一步（谁因此受益）__。',
        '> **本批核心类**：%s' % (classes or '__★类 + 关键零件__'),
        '> **验收结果**：__待填（真实命令 + 真实输出；没跑就写"未实测"并说明为什么）__',
        '> **源码依据**：commit `%s`（%s）——本批代码块以此提交为准；若当前树已重写，见 ⑥ 的【历史版本示例】与「当前实现」小节。'
        % (sha or '<fill-sha>', verify or '定位依据：提交信息含 阶段%s批次%s' % (stage, batch)),
        '',
    ]


def main():
    ap = argparse.ArgumentParser(description='从模板骨架生成一份新批次讲解文件')
    ap.add_argument('--stage', required=True)
    ap.add_argument('--batch', required=True)
    ap.add_argument('--title', required=True, help='批次主题（含 ★ 类名）')
    ap.add_argument('--classes', default='', help='本批核心类，逗号分隔')
    ap.add_argument('--sha', default='', help='批头源码快照 commit sha（⑦~⑧ 位十六进制）')
    ap.add_argument('--verify', default='', help='快照定位依据（缺省按提交信息推断）')
    ap.add_argument('--out', required=True, help='输出路径（相对 --src 或绝对路径）')
    ap.add_argument('--src', default=os.getcwd(), help='宿主仓库根目录（缺省=当前目录）')
    ap.add_argument('--force', action='store_true', help='覆盖已存在的文件')
    ap.add_argument('--print-skeleton', action='store_true', help='只打印骨架到标准输出（不写文件）')
    a = ap.parse_args()

    notes = []
    body = skeleton_lines(notes=notes)
    text = '\n'.join(header(a.stage, a.batch, a.title, a.classes, a.sha, a.verify) + body) + '\n'

    # 2.19：在 ⑯ 标题后写明判据版本 —— 新批从第一次跑闸门就落在 ⓪b 三项的 FAIL 档（core_scope 只认自我声明的版本）。
    _lt = text.split('\n')
    _i16 = next(i for i, l in enumerate(_lt) if re.match(r'^##\s*' + CIRCLED[15] + r'\s', l))
    _lt[_i16 + 1:_i16 + 1] = ['', '**判据版本：v%s**（本批按此版判据验收；判据变更见 references/第一册质量细则.md §6.6 变更登记）。' % GATE_VERSION]
    text = '\n'.join(_lt)

    # 生成后自断言（判据 2.15 / 血证 H25）：17 个一级节标题必须全部按规范形态命中——
    # 带圈数字（⑨⑩⑫⑮⑯ 等）在某些落盘链路会静默丢失，标题一旦变形，gate 的 `^## ⑫` 定位
    # 就静默失效、整节检查被跳过。骨架在写出前必须是完好的；本断言失败 = 模板被改坏，先修模板。
    miss = [c for c in CIRCLED if not re.search(r'^## ' + c + r'(?=\s|$)', text, re.M)]
    if not re.search(r'^## 索引', text, re.M):   # 索引节允许带后缀（`## 索引节`/`## 索引与导航` 均规范）
        miss.append('索引')
    if miss:
        raise SystemExit('[ABORT] 生成的骨架有 %d 个一级节标题未按规范形态命中：%s\n'
                         '   → references/批次讲解全文模板.md 的节标题被改坏（带圈数字丢失或多余空格），'
                         '请先修模板再生成。' % (len(miss), '、'.join(miss)))
    if a.print_skeleton:
        print(text)
        return 0

    out = a.out if os.path.isabs(a.out) else os.path.join(os.path.abspath(a.src), a.out)
    if os.path.exists(out) and not a.force:
        raise SystemExit('[ABORT] %s 已存在（要覆盖请加 --force）' % out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    tmp = out + '.tmpnew'
    io.open(tmp, 'w', encoding='utf-8', newline='').write(text)
    os.replace(tmp, out)

    secs = re.findall(r'^## (.+)$', text, re.M)
    i12 = next(i for i, l in enumerate(text.split('\n')) if re.match(r'^##\s*' + CIRCLED[11] + r'\s', l))
    seg12 = '\n'.join(text.split('\n')[i12:])
    seg12 = seg12.split('\n## ' + CIRCLED[12])[0]
    print('已生成 %s' % out)
    print('  节数 = %d（应为 17）｜⑦.5 = %s｜⑫ 八条 = %d｜八段提示词 = %d'
          % (len(secs), '有' if '#### ⑦.5' in text else '无',
             len(re.findall(r'^#### \d+\.', seg12, re.M)),
             len(re.findall(r'^【[^】]+】', seg12, re.M))))
    print('  已从文件里剥离 %d 行模板指导语（写作须知，见下）——它们留在文件里会让 ⓪ 的自指检查 FAIL'
          % len(notes))
    for l in notes:
        print('     ' + l[:150])
    print('  接下来三步：')
    print('   1) 填 ①~⑤ 与 ⑥ 逐件讲解（源码块用 scripts/inject_source.py 注入，别手打行号）')
    print('   2) 每件的 ⑤：**【怎么用】**（调用现场取 scripts/callsite.py 实跑）+ **【上下游】**；'
          '抽象件再加 **【怎么接】**')
    print('   3) 跑闸门：python "%s" "%s" --src %s'
          % (os.path.join(HERE, 'gate_lecture.py'), out, os.path.abspath(a.src)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
