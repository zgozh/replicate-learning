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

    # 方案 §3.3：给每件生成**稳定源码槽位**（块身份 = 槽位 ID + 源路径，不再靠标题/contains 猜）
    python new_batch.py --stage 3 --batch 48 --title "…" --classes "…" --sha 16984b9 \\
        --out "…/批次48-….md" --src <仓库根> \\
        --plan logs/b48_inject_plan.json --batch-json logs/b48_batch.json \\
        --manifest logs/b48_manifest.json [--manifest logs/b48_manifest2.json]

`--out` 是**终稿**路径，本命令**不写它**——骨架写到 `--skeleton`（缺省 `<out 同目录>/skeleton.md`），
终稿由 `batch_build.py` 从「骨架 + 分片 + annotations.json」重建（2.30 修复：两者同路径会让"重建"
退化成就地改旧正文，见 `batch_build.py` 顶部说明）。`--out` 与 `--skeleton` 相同即拒绝。

产出：批头（一句话/核心类/验收结果/源码依据 commit）+ ①~⑯ + 索引，共 **17 个 `## ` 节**，
其中 `⑦.5`、⑯ 六项空表、⑫ 八条与八段提示词标签都已就位；正文占位符沿用模板的 `__xxx__` 写法。
带 `--plan` 时，⑥ 按计划逐件生成"件标题 + 槽位标记 + 空围栏"，槽位标记写明源路径、行段与
源文件 sha256——**重复构建靠它寻址，不靠 `contains` 里那些注入后就消失的占位串**；
同一份计划还会派生**唯一一份可编辑注释计划** `annotations.json`（`batch_build` 只认它）。

不做的事：不生成任何讲解内容、不写任何代码、不跑闸门（跑闸门是下一步，命令会打印出来）。
"""
import argparse
import hashlib
import io
import json
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


def slot_id(rel, sha256, seg):
    """稳定槽位 ID：`source:<sha256 前 8 位>:<件号>`。

    身份 = 源码内容 hash + 件号：改源码 → hash 变 → 槽位身份变（旧行号不会被悄悄套用）；
    改标题/改 `contains`/重写正文 → 槽位不变（这正是第48批反复"猜旧占位串"的根因）。
    """
    return "source:%s:%s" % (sha256[:8], seg)


def slot_marker(rel, start, end, sha256, seg, lang="java"):
    return ('<!-- src-slot id="%s" path="%s" lines="%d-%d" sha256="%s" lang="%s" -->'
            % (slot_id(rel, sha256, seg), rel, start, end, sha256, lang))


def plan_section(out_lines, plan, src_root):
    """用注释计划重写 ⑥ 节：每件 = 件标题 + 三段开场 → 槽位标记 + 空围栏 → 逐行要点表…

    为什么由计划生成 ⑥ 而不是让模型手写件骨架：件标题里的 ★、件号（6.x）、以及"这一件对应哪个源文件、
    哪一段行"三者必须**一开始就一致**——第48批的代价之一就是靠 `contains` 里的 `__INJECT_0N__`
    把块钉住，注入后占位串消失，后续改动只能靠"类声明消歧"猜。

    **件内顺序不能改（2.30 修复 · 批次49 实录）**：模板的阅读顺序是
    「问题一句话 → 白话开场 → 构造方式与手法 → **源码块** → 逐行要点表 → 边界与副作用 → 件末三段」。
    本函数原先把槽位标记与空围栏直接排在件标题之后、把三段开场挤到代码块**下面**——
    模型照着骨架写，于是整批 ⑥ 的"代码块前的讲解"全跑到了代码块后面（批次49 四个件全部如此）。
    骨架是模板的可执行版本，**顺序必须与模板逐行一致**。
    """
    i6 = next(i for i, l in enumerate(out_lines) if re.match(r'^##\s*' + CIRCLED[5] + r'\s', l))
    i7 = next(i for i in range(i6 + 1, len(out_lines))
              if re.match(r'^##\s*' + CIRCLED[6] + r'\s', out_lines[i]))
    head = out_lines[i6 + 1:i7]
    # 保留模板给 ⑥ 的阅读顺序/注释归属等**指导语**（以 `> ` 开头的行），其余占位件由计划替换
    guidance = [l for l in head if l.startswith('> ')]
    body = ['']
    body += guidance + ['']
    made = []
    for n, spec in enumerate(plan.get("blocks", []), 1):
        seg = spec.get("seg") or ("6.%d" % n)
        rel = spec["src"]
        path = os.path.join(src_root, rel)
        if not os.path.isfile(path):
            raise SystemExit('[ABORT] 计划里的源文件不存在：%s（先修计划再生成骨架）' % rel)
        lines = io.open(path, encoding='utf-8').read().split('\n')
        start = spec.get("start") or 1
        end = spec.get("end") or (len(lines) - 1 if lines and lines[-1] == '' else len(lines))
        sha = hashlib.sha256(io.open(path, 'rb').read()).hexdigest()
        anchor = spec.get("anchor") or ("#### %s `%s`" % (seg, os.path.basename(rel)[:-5]))
        title = anchor if anchor.startswith('####') else ('#### %s' % anchor.lstrip('# '))
        lang = spec.get("lang", "java")
        body += [title, '',
                 # ① 三段开场必须在源码块**之前**（模板 196-200 行的顺序）
                 '**本文件要解决的一个问题**：__问题一句话__ + 输入/输出：__输入描述__；输出：__输出描述__。',
                 '', '**白话开场**：__这段代码解决什么、看完能答什么__', '',
                 '**构造方式与手法**：__谁 new/注入它、生命周期归谁管__ ｜ __模式/数据结构/算法 + 权衡__',
                 '',
                 # ② 槽位标记紧挨源码围栏（注入器按它寻址）
                 slot_marker(rel, start, end, sha, seg, lang), '',
                 '```' + lang,
                 '// __INJECT__（源码由 scripts/inject_source.py 按槽位注入；**不要手写代码**）',
                 '```', '',
                 # ③ 代码块之后才是逐行要点表 / 边界 / 件末三段
                 '**逐行要点表**：', '', '| 行 | 讲解 |', '|---|---|', '| __行号__ | __控制流/边界说明__ |', '',
                 '**边界与副作用**：__边界/副作用/风险点__', '',
                 '**【怎么用】**', '', '**【上下游】**', '', '**【怎么接】**', '', '---', '']
        made.append(dict(seg=seg, slot=slot_id(rel, sha, seg), src=rel, start=start, end=end, lang=lang))
    out_lines[i6 + 1:i7] = body
    return made


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
    from lecture_checks import configure_stdio      # stdout 被重定向时按 GBK 编码会崩在打印上
    configure_stdio()
    ap = argparse.ArgumentParser(description='从模板骨架生成一份新批次讲解文件')
    ap.add_argument('--stage', required=True)
    ap.add_argument('--batch', required=True)
    ap.add_argument('--title', required=True, help='批次主题（含 ★ 类名）')
    ap.add_argument('--classes', default='', help='本批核心类，逗号分隔')
    ap.add_argument('--sha', default='', help='批头源码快照 commit sha（⑦~⑧ 位十六进制）')
    ap.add_argument('--verify', default='', help='快照定位依据（缺省按提交信息推断）')
    ap.add_argument('--out', required=True, help='**终稿**路径（相对 --src 或绝对路径；本命令不写它，由 batch_build 重建）')
    ap.add_argument('--skeleton', help='骨架输出路径（缺省=<out 同目录>/skeleton.md；**必须与 --out 不同**）')
    ap.add_argument('--src', default=os.getcwd(), help='宿主仓库根目录（缺省=当前目录）')
    ap.add_argument('--force', action='store_true', help='覆盖已存在的骨架文件')
    ap.add_argument('--plan', help='注释计划 JSON：按它逐件生成⑥的槽位与件骨架（方案 §3.3）')
    ap.add_argument('--batch-json', dest='batch_json',
                    help='同时写一份批次状态 batch.json（供 batch_build.py 组装/注入/复建；需与 --plan 同用）')
    ap.add_argument('--parts-dir', dest='parts_dir', help='分片目录（缺省=<骨架同目录>/parts）')
    ap.add_argument('--manifest', action='append',
                    help='本批源文件清单 JSON（**可多次传**：一个文件一份清单时会全部记进 batch.json）')
    ap.add_argument('--print-skeleton', action='store_true', help='只打印骨架到标准输出（不写文件）')
    a = ap.parse_args()

    notes = []
    body = skeleton_lines(notes=notes)
    slots = []
    if a.plan:
        plan = json.load(io.open(a.plan, encoding='utf-8'))
        slots = plan_section(body, plan, os.path.abspath(a.src))
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

    # `--out` 是**终稿**路径；骨架写到 `--skeleton`（缺省 <out 同目录>/skeleton.md）。
    # 2.30 修复（批次49 实录）：此前骨架与终稿是同一个路径，于是 `batch_build` 的"重建"变成
    # **就地重建**——省略 ⑥ 分片时旧 ⑥ 内容原样留在结果里，"重建"成了假象。骨架必须是独立文件。
    out = a.out if os.path.isabs(a.out) else os.path.join(os.path.abspath(a.src), a.out)
    skel = a.skeleton if a.skeleton else os.path.join(os.path.dirname(out), 'skeleton.md')
    if not os.path.isabs(skel):
        skel = os.path.join(os.path.abspath(a.src), skel)
    if os.path.abspath(skel) == os.path.abspath(out):
        raise SystemExit('[ABORT] 骨架与终稿不能是同一个路径（%s）：终稿必须由「骨架 + 分片 + 注释计划」'
                         '派生，就地重建会拿旧正文冒充重建结果。' % out)
    if os.path.exists(skel) and not a.force:
        raise SystemExit('[ABORT] %s 已存在（要覆盖请加 --force）' % skel)
    os.makedirs(os.path.dirname(skel), exist_ok=True)
    tmp = skel + '.tmpnew'
    with io.open(tmp, 'w', encoding='utf-8', newline='') as fh:
        fh.write(text)
    os.replace(tmp, skel)

    secs = re.findall(r'^## (.+)$', text, re.M)
    i12 = next(i for i, l in enumerate(text.split('\n')) if re.match(r'^##\s*' + CIRCLED[11] + r'\s', l))
    seg12 = '\n'.join(text.split('\n')[i12:])
    seg12 = seg12.split('\n## ' + CIRCLED[12])[0]
    print('已生成骨架 %s' % skel)
    print('  终稿路径（重建目标，本次不写）：%s' % out)
    print('  节数 = %d（应为 17）｜⑦.5 = %s｜⑫ 八条 = %d｜八段提示词 = %d'
          % (len(secs), '有' if '#### ⑦.5' in text else '无',
             len(re.findall(r'^#### \d+\.', seg12, re.M)),
             len(re.findall(r'^【[^】]+】', seg12, re.M))))
    if slots:
        print('  ⑥ 按计划生成 %d 个源码槽位（块身份 = 槽位 ID + 源路径 + sha256，不再靠 contains 猜）：' % len(slots))
        for s in slots:
            print('     %-28s %s %d-%d' % (s['slot'], s['src'], s['start'], s['end']))
    if a.batch_json:
        if not a.plan:
            raise SystemExit('[ABORT] --batch-json 必须同时给 --plan：批次状态里的 `annotations` 是'
                             '**由计划派生出的、含槽位的那一份可编辑注释计划**，没有计划就派生不出来。')
        bj = a.batch_json if os.path.isabs(a.batch_json) else os.path.join(os.path.abspath(a.src), a.batch_json)
        os.makedirs(os.path.dirname(bj), exist_ok=True)
        # 槽位 ID 必须同时存在于**骨架**与**注释计划**里，否则注入器两边对不上。
        # 计划是注释的唯一来源，所以这里把解析出的 slot/行段写回一份 annotations.json（派生产物，
        # 与骨架同一次生成直接对应；原始计划文件不动）。
        ann = {"schema_version": 1, "from": os.path.abspath(a.plan), "blocks": []}
        by_seg = {s["seg"]: s for s in slots}
        for n, spec in enumerate(plan.get("blocks", []), 1):
            seg = spec.get("seg") or ("6.%d" % n)
            s = by_seg.get(seg, {})
            item = dict(spec)
            item.pop("seg", None)
            item["src"] = spec["src"]
            item["start"] = s.get("start")
            item["end"] = s.get("end")
            item["lang"] = spec.get("lang", "java")
            item["slot"] = s.get("slot")
            ann["blocks"].append(item)
        ann_path = os.path.join(os.path.dirname(bj), "annotations.json")
        io.open(ann_path, 'w', encoding='utf-8', newline='').write(
            json.dumps(ann, ensure_ascii=False, indent=1) + '\n')
        # 写完自断言：这一份必须存在且带槽位——`batch_build` 只认它（批次49 实录：
        # batch.json 指回原始计划 + 手补槽位，工具却在旁边悄悄少了一份可编辑计划）。
        if not os.path.isfile(ann_path):
            raise SystemExit('[ABORT] 注释计划没写成功：%s' % ann_path)
        _n_slot = len([b for b in ann["blocks"] if b.get("slot")])
        if slots and not _n_slot:
            raise SystemExit('[ABORT] 派生出的 annotations.json 里一个槽位都没有——'
                             '计划里的 src/行段没解析出来，先修计划再开批。')
        manifests = [os.path.abspath(m) for m in (a.manifest or [])]
        state = {
            "schema_version": 1,
            "batch_id": "stage%s-b%s" % (a.stage, a.batch),
            "title": a.title,
            "src": os.path.abspath(a.src),
            "skeleton": skel,
            "parts_dir": a.parts_dir or os.path.join(os.path.dirname(skel), 'parts'),
            "annotations": ann_path,
            "annotations_slots": _n_slot,
            "plan_source": os.path.abspath(a.plan),
            "manifest": (manifests[0] if manifests else None),
            "manifests": manifests,
            "out": out,
            "slots": slots,
            "contract_version": GATE_VERSION,
        }
        io.open(bj, 'w', encoding='utf-8', newline='').write(
            json.dumps(state, ensure_ascii=False, indent=1) + '\n')
        print('  批次状态已写 %s' % bj)
        print('  可编辑的注释计划**只有一份**：%s（含 %d 个槽位；原始计划 %s 是输入，不要拿它当 annotations）'
              % (ann_path, _n_slot, os.path.basename(state["plan_source"])))
        if manifests:
            print('  源文件清单 %d 份：%s' % (len(manifests), '、'.join(os.path.basename(m) for m in manifests)))
        print('  下一步：写分片到 %s → python scripts/batch_build.py --batch %s'
              % (state["parts_dir"], bj))
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
