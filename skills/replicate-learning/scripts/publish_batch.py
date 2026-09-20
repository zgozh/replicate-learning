#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""publish_batch.py —— 一份批次记录，更新所有派生视图；安全、可预览、可回滚（方案 §3.5）。

**为什么需要它**：改造前，同一批事实要手工写到**八处**（覆盖矩阵 / 总索引 / 阶段页 / 精简状态 /
能力账本 / 笔记 / …），第48批还额外写了一个 10k 字符的一次性归档脚本、逐处找锚点。
同一批事实抄八遍的代价不只是慢：**抄错一处就出现互相矛盾的状态**，而冲突发生在第五处时，
前四处已经写下去了——留下半套状态，比不写更糟。

本工具把"这批到底发生了什么"收敛成**一份 `batch_record.json`**，由它渲染所有派生更新：

    python publish_batch.py --record <batch_record.json> --dry-run      # 将要改哪些文件、确切差异
    python publish_batch.py --record <batch_record.json> --apply [--git-add]

`--apply` 的顺序（**全部校验通过才写第一个字节**）：
  1. 路径必须在声明的项目目录内（拒绝 `..` 与绝对路径逃逸）；
  2. 讲义存在、哈希与记录一致；门禁**最终记录**存在且 `pass=true`、其 `final_lecture_sha256`
     与讲义当前哈希一致（不许拿"盖章前的哈希"冒充"最终成品已核验"）；
  3. 主讲文件不可重复；下一批号不得回退；清单里的源文件哈希仍与会话记录一致；
  4. 逐文件校验旧内容锚点与预期状态；**任一不满足 → 打印差异并中止，一个文件都不动**；
  5. 全部通过后才逐文件写入（每个文件先留 `.bak`、写走 tmp → os.replace）；中途失败按备份**回滚**
     已写入的文件，不留半套状态；
  6. `--git-add` 只 `git add --` 本批记录里的文件（**绝不 `git add -A`**）。

幂等：记录里的 `targets[].idempotent_key` 已在文件中出现 = 这条已经发布过 → 跳过（重复运行零变化）。
"""
import argparse
import difflib
import io
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import lecture_checks as LC          # noqa: E402

DEFAULT_LOG_DIR = 'NOTES/.replicate-learning'


class Conflict(Exception):
    """校验不通过：必须中止，且**不得**写入任何文件。"""


def inside(base, rel):
    """把 rel 解析到 base 内；逃逸（`..` / 绝对路径 / 指向 base 外）一律拒绝。"""
    if os.path.isabs(rel):
        raise Conflict('路径是绝对路径，必须相对项目根：%s' % rel)
    full = os.path.normpath(os.path.join(base, rel))
    if not (full == os.path.normpath(base) or full.startswith(os.path.normpath(base) + os.sep)):
        raise Conflict('路径逃出项目目录：%s' % rel)
    return full


def load_record(path):
    rec = json.load(io.open(path, encoding='utf-8'))
    if rec.get('schema_version') != 1:
        raise Conflict('batch_record schema_version=%r（本工具只认 1）' % rec.get('schema_version'))
    return rec


def check_record(rec):
    """记录自身的结构校验（与文件系统无关的部分）。返回 (project_root, targets)。"""
    root = rec.get('project_root')
    if not root or not os.path.isdir(root):
        raise Conflict('project_root 不存在或未声明：%r' % root)
    root = os.path.abspath(root)
    if not rec.get('lecture'):
        raise Conflict('记录缺 lecture（本批讲义路径）')
    if rec.get('book') and int(rec['book']) != 1:
        raise Conflict('本工具只发布第一册（book=%r）；第二、三册需用户显式请求' % rec['book'])
    masters = [t['file'] for t in rec.get('teaching', []) if t.get('role') == '主讲']
    dup = sorted({f for f in masters if masters.count(f) > 1})
    if dup:
        raise Conflict('同一文件被列为多件主讲（同一文件只能有一份主讲）：%s' % '、'.join(dup))
    if not masters:
        raise Conflict('记录里没有一件「主讲」——本批范围不明确')
    bn, nb = rec.get('batch_no'), rec.get('next_batch')
    if bn is None or not nb:
        raise Conflict('记录缺 batch_no / next_batch')
    m = re.search(r'(\d+)\s*$', str(nb))
    if not m:
        raise Conflict('next_batch 里读不出批号：%r' % nb)
    if int(m.group(1)) <= int(bn):
        raise Conflict('下一批号 %s 不得小于或等于本批号 %s（防回退）' % (nb, bn))
    targets = rec.get('targets') or []
    if not targets:
        raise Conflict('记录里没有 targets——没有要更新的派生视图，等于没发布')
    for t in targets:
        if not t.get('file') or not t.get('op'):
            raise Conflict('target 缺 file/op：%r' % t)
        if t['op'] not in ('append_section', 'insert_before_anchor', 'replace_anchor', 'ensure_line'):
            raise Conflict('未知 op：%r' % t['op'])
        if t['op'] in ('insert_before_anchor', 'replace_anchor') and not t.get('anchor'):
            raise Conflict('%s 需要 anchor：%r' % (t['op'], t.get('file')))
    return root, targets


def check_evidence(rec, root):
    """讲义哈希 / 门禁最终记录 / 源文件清单 —— 三者都要与记录对得上。"""
    lec = inside(root, rec['lecture'])
    if not os.path.isfile(lec):
        raise Conflict('讲义不存在：%s' % rec['lecture'])
    lec_sha = LC.sha256_file(lec)
    if rec.get('lecture_sha256') and rec['lecture_sha256'] != lec_sha:
        raise Conflict('讲义哈希与记录不符（记录 %s… / 实际 %s…）——先复核再发布'
                       % (rec['lecture_sha256'][:12], lec_sha[:12]))
    if rec.get('gate_final'):
        gf = inside(root, rec['gate_final'])
        if not os.path.isfile(gf):
            raise Conflict('门禁最终记录不存在：%s（先跑 sync_gate_result --apply 生成）' % rec['gate_final'])
        final = json.load(io.open(gf, encoding='utf-8'))
        if not final.get('pass'):
            raise Conflict('门禁最终记录 pass=%r —— 未通过的批次不得发布' % final.get('pass'))
        if final.get('final_lecture_sha256') != lec_sha:
            raise Conflict('门禁最终哈希 %s… ≠ 讲义当前哈希 %s…（盖章后又改过正文）'
                           % (str(final.get('final_lecture_sha256'))[:12], lec_sha[:12]))
    elif rec.get('gate_result'):
        gr = inside(root, rec['gate_result'])
        if not os.path.isfile(gr):
            raise Conflict('门禁结果不存在：%s' % rec['gate_result'])
        data = LC.load_result(gr)
        if data.get('lecture_sha256') != lec_sha:
            raise Conflict('门禁结果不是针对当前讲义（哈希不符）')
        if LC.blocking_checks(data):
            raise Conflict('门禁结果有阻塞项：%s' % '、'.join(c['id'] for c in LC.blocking_checks(data)))
    else:
        raise Conflict('记录里既没有 gate_final 也没有 gate_result —— 无法证明本批通过门禁')
    if rec.get('manifest'):
        man = inside(root, rec['manifest'])
        if not os.path.isfile(man):
            raise Conflict('清单不存在：%s' % rec['manifest'])
        data = json.load(io.open(man, encoding='utf-8'))
        for rel, meta in (data.get('files') or {}).items():
            p = inside(root, rel)
            if not os.path.isfile(p):
                raise Conflict('清单里的源文件不存在：%s（源码已删改，先重跑清单）' % rel)
            if LC.sha256_file(p) != meta.get('sha256'):
                raise Conflict('清单里的源文件已变化：%s（本批发布的前提是源码未再改动）' % rel)
    return lec


def apply_target(text, t):
    """把一条 target 作用到文件文本上，返回 (新文本, 是否变化, 说明)。冲突抛 Conflict。"""
    key = t.get('idempotent_key')
    if key and key in text:
        return text, False, '已发布过（幂等跳过）'
    op = t['op']
    block = t.get('text') or ''
    if op == 'append_section':
        new = text if text.endswith('\n') else text + '\n'
        new = new + block.rstrip('\n') + '\n'
        return new, True, '追加一节（%d 行）' % (block.rstrip('\n').count('\n') + 1)
    if op == 'ensure_line':
        lines = text.split('\n')
        if any(l.strip() == block.strip() for l in lines):
            return text, False, '该行已存在（幂等跳过）'
        return text.rstrip('\n') + '\n' + block.strip('\n') + '\n', True, '补一行'
    anchor = t['anchor']
    hits = [i for i, l in enumerate(text.split('\n')) if anchor in l]
    if len(hits) != 1:
        raise Conflict('锚点命中 %d 处（应为 1）：%r @ %s' % (len(hits), anchor[:60], t['file']))
    at = hits[0]
    if op == 'insert_before_anchor':
        lines = text.split('\n')
        lines[at:at] = block.rstrip('\n').split('\n')
        return '\n'.join(lines), True, '在锚点前插入 %d 行' % (block.rstrip('\n').count('\n') + 1)
    if t.get('expect') and t['expect'] not in text.split('\n')[at]:
        raise Conflict('锚点行的预期状态不符：期望含 %r，实际 %r' % (t['expect'], text.split('\n')[at][:80]))
    lines = text.split('\n')
    lines[at] = block.rstrip('\n')
    return '\n'.join(lines), True, '替换锚点行'


def plan_updates(rec, root, targets):
    """只读地算出每个文件的新内容与差异；任何不满足都抛 Conflict（此时一个字节都没写）。"""
    plan = []
    for t in targets:
        path = inside(root, t['file'])
        if os.path.isfile(path):
            before = io.open(path, encoding='utf-8').read()
            is_new = False
        else:
            if t['op'] != 'append_section':
                raise Conflict('目标文件不存在，而 op=%s 无法建文件：%s' % (t['op'], t['file']))
            before, is_new = '', True
        after, changed, why = apply_target(before, t)
        if is_new and changed:
            why = '新建文件：' + why
        plan.append(dict(target=t, path=path, before=before, after=after,
                         changed=changed, why=why))
    return plan


def render_plan(plan, root):
    lines = []
    for item in plan:
        rel = os.path.relpath(item['path'], root)
        tag = 'CHANGE' if item['changed'] else 'SKIP  '
        lines.append('[%s] %s（%s）' % (tag, rel, item['why']))
        if not item['changed']:
            continue
        diff = list(difflib.unified_diff(item['before'].split('\n'), item['after'].split('\n'),
                                        fromfile=rel + '（当前）', tofile=rel + '（发布后）',
                                        lineterm='', n=1))
        lines.extend('    ' + d for d in diff[:40])
        if len(diff) > 40:
            lines.append('    …（差异共 %d 行，已截断）' % len(diff))
    return '\n'.join(lines)


def write_all(plan, root, apply=True):
    """原子性尽力而为：全部先写 tmp，再逐个 replace；任何一个失败 → 用备份回滚已写的。"""
    written, backups = [], {}
    try:
        for item in plan:
            if not item['changed']:
                continue
            path = item['path']
            if os.path.isfile(path):
                backups[path] = io.open(path, 'rb').read()
            else:
                backups[path] = None
            parent = os.path.dirname(path)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            tmp = path + '.tmpnew'
            io.open(tmp, 'w', encoding='utf-8', newline='').write(item['after'])
            os.replace(tmp, path)
            written.append(path)
            if backups[path] is not None:
                bak = path + '.bak'
                if not os.path.exists(bak):
                    io.open(bak, 'wb').write(backups[path])
    except Exception:
        for path in written:
            data = backups.get(path)
            if data is None:
                if os.path.exists(path):
                    os.unlink(path)
            else:
                io.open(path, 'wb').write(data)
        raise
    return written


def git_add(root, files, lecture):
    """只 stage 明确列出的文件（禁止 `git add -A`）。返回 (是否执行, 说明)。"""
    repo = subprocess.run(['git', '-C', root, 'rev-parse', '--show-toplevel'],
                          capture_output=True, text=True)
    if repo.returncode != 0:
        return False, '项目根不是 git 仓库（跳过 git add）'
    top = repo.stdout.strip()
    rels = []
    for f in [lecture] + list(files):
        rel = os.path.relpath(f, top).replace('\\', '/')
        if rel not in rels:
            rels.append(rel)
    # 嵌套仓库：只 add 属于该仓库的文件（`git -C <top> add -- <rel>` 本身就不会跨界）
    p = subprocess.run(['git', '-C', top, 'add', '--'] + rels, capture_output=True, text=True)
    if p.returncode != 0:
        return False, 'git add 失败：%s' % (p.stderr or '').strip()[:200]
    return True, '已 stage %d 个文件（仅本批记录内的文件，未使用 git add -A）' % len(rels)


def main():
    LC.configure_stdio()
    ap = argparse.ArgumentParser(description='按一份批次记录安全更新所有派生视图')
    ap.add_argument('--record', required=True, help='batch_record.json')
    ap.add_argument('--dry-run', dest='apply', action='store_false', default=False,
                    help='只预览差异（缺省行为）')
    ap.add_argument('--apply', dest='apply', action='store_true', help='真正写盘')
    ap.add_argument('--git-add', dest='git_add', action='store_true',
                    help='写盘后只 stage 本批记录里的文件（绝不 git add -A）')
    a = ap.parse_args()

    rec = load_record(a.record)
    try:
        root, targets = check_record(rec)
        lec = check_evidence(rec, root)
        plan = plan_updates(rec, root, targets)
    except Conflict as exc:
        print('[ABORT] %s' % exc)
        print('   → 校验未全部通过，**没有写任何文件**；修记录或修目标文件后重跑。')
        return 1

    print('批次 %s（book=%s，主讲 %d 件，目标视图 %d 个）→ %s'
          % (rec.get('batch_id'), rec.get('book'), len([t for t in rec.get('teaching', [])
                                                       if t.get('role') == '主讲']), len(plan), root))
    print(render_plan(plan, root))
    changed = [i for i in plan if i['changed']]
    if not changed:
        print('\n[OK ] 所有目标视图都已是最新（重复发布零变化，幂等成立）')
        if a.git_add:
            ok, why = git_add(root, [i['path'] for i in plan], lec)
            print(('   %s' % why) if ok else '   %s' % why)
        return 0
    if not a.apply:
        print('\n（dry-run：未写盘；确认后加 --apply）')
        return 0
    written = write_all(plan, root)
    print('\n→ 已更新 %d 个文件：%s' % (len(written), '、'.join(os.path.relpath(p, root) for p in written)))
    if a.git_add:
        ok, why = git_add(root, written, lec)
        print('   %s' % why)
    return 0


if __name__ == '__main__':
    sys.exit(main())
