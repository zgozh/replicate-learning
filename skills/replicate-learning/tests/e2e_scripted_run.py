"""端到端脚本化试运行：用真实批次48 素材 + py_mini 夹具跑完整第二轮流水线，并记录分步实测耗时。

用法（在仓库根目录执行；零依赖，只用标准库）：

    python skills/replicate-learning/tests/e2e_scripted_run.py [--work <输出目录>]

口径（**诚实说明，别把它读成"整批一小时变几秒"**）：
  · 本脚本只测**脚本化步骤**：清单校验/预检/脚手架/组装/注入/门禁/盖章/发布/复验；
  · **模型写作（investigate/write）不在其中**——那部分要操作者按秒表，报表里单列为"未记录阶段"；
  · 因此本脚本的耗时**不构成"真实批次总时长已缩短"的结论**，它给的是脚本侧基线与回归护栏；
  · 材料是真实批次48 的 8 件 Java 源码 + 真实注释计划 + 5 份真实分片，输出写在临时目录，
    **不改 ragent 的任何教材**；缺 ragent-official 时跳过依赖真实教材的三步并打印说明。

每一步都带**显式期望**（退出码 + 输出关键串）：期望不符 → 脚本整体退出码 1 并列出不符项。
"预检首轮必须 FAIL、修复后必须 PASS"这类断言是回归护栏；不允许"某步失败了但脚本照样返回 0"。

产物：`<work>/report.json`（分步耗时 + batch_trace 聚合报表）、`<work>/trace.jsonl`、`<work>/report.txt`。
参考实测值见根目录 `replicate-learning-第二轮提速重构-交付说明.md` §4。
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'skills', 'replicate-learning', 'scripts'))
import batch_trace as BT            # noqa: E402

SK = os.path.join(REPO, 'skills', 'replicate-learning', 'scripts')
FIX = os.path.join(REPO, 'skills', 'replicate-learning', 'tests', 'fixtures')
SRC48 = os.path.join(FIX, 'batch48', 'project')
PLAN_R1 = os.path.join(FIX, 'batch48', 'b48_inject_plan_r1.json')
PLAN_FIXED = os.path.join(FIX, 'batch48', 'b48_inject_plan_fixed.json')
MANIFEST = os.path.join(FIX, 'batch48', 'b48_manifest.json')
PY_SRC = os.path.join(FIX, 'py_mini', 'project')
PY_PLAN = os.path.join(FIX, 'py_mini', 'plan.json')
RAGENT = os.environ.get('RAGENT_ROOT', r'D:\ragent-official')
REAL_LEC = os.path.join(RAGENT, 'NOTES', '教学讲解', '第一册-项目源码与工程实现', '阶段3-问答业务域',
                        '批次48-智能切片策略（TableChunker★+HtmlTableChunker+六切分件）.md')
B48_FILES = ["CodeChunker.java", "HeadingChunker.java", "HeadingHandler.java", "HtmlTableChunker.java",
             "ImageChunker.java", "ListChunker.java", "ParagraphChunker.java", "TableChunker.java"]
REL_DIR = os.path.join('rag', 'src', 'main', 'java', 'com', 'nageoffer', 'ai', 'ragent', 'core',
                       'chunk', 'blockaware')


def run(cmd, cwd=None):
    p = subprocess.run([sys.executable, '-B'] + cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=cwd or REPO)
    return p.returncode, (p.stdout or ''), (p.stderr or '')


def tool(name):
    return os.path.join(SK, name)


def main():
    ap = argparse.ArgumentParser(description='端到端脚本化试运行（脚本侧步骤计时 + 期望断言）')
    ap.add_argument('--work', default=os.path.join(REPO, '.replicate-learning-log', 'e2e-scripted'))
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if os.path.isdir(work):
        shutil.rmtree(work)
    os.makedirs(work)
    trace = os.path.join(work, 'trace.jsonl')
    steps, mismatches = [], []
    have_real = os.path.isfile(REAL_LEC)

    def phase(name, fn, note, expect_rc=0, expect_out=()):
        """跑一步并**断言**结果：退出码属于 expect_rc，且输出含 expect_out 里的每个关键串。"""
        BT.phase_begin(trace, name, note=note)
        t0 = time.perf_counter()
        rc, out, err = fn()
        ms = (time.perf_counter() - t0) * 1000.0
        BT.phase_end(trace, name)
        blob = (out or '') + (err or '')
        rcs = expect_rc if isinstance(expect_rc, (tuple, list)) else (expect_rc,)
        problems = []
        if rc not in rcs:
            problems.append('退出码 %s ∉ %s' % (rc, list(rcs)))
        for token in expect_out:
            if token not in blob:
                problems.append('输出里没有预期串 %r' % token)
        steps.append(dict(phase=name, rc=rc, ms=round(ms, 1), note=note,
                          expect_rc=list(rcs), expect_out=list(expect_out),
                          ok=not problems, problems=problems,
                          head=blob.strip().split('\n')[-1][:140]))
        if problems:
            mismatches.append('%s（%s）：%s' % (note, name, '；'.join(problems)))
        return rc, out, err

    BT.append_record(trace, BT.start_record('e2e-scripted', model='(未采集：脚本化试运行)',
                                            contract_version='2.30'))

    # ── prepare：清单（自建副本，真校验）+ 预检（首轮应报缺口，修复后应干净）──
    proj_src = os.path.join(work, 'proj-src')
    os.makedirs(os.path.join(proj_src, REL_DIR))
    for fn in B48_FILES:
        shutil.copyfile(os.path.join(SRC48, REL_DIR, fn), os.path.join(proj_src, REL_DIR, fn))
    self_manifest = os.path.join(work, 'manifest_self.json')
    rel_files = [os.path.join(REL_DIR, fn).replace('\\', '/') for fn in B48_FILES]
    prepare_cmd = [tool('batch_manifest.py'), 'prepare', '--src', proj_src]
    for rel in rel_files:
        prepare_cmd += ['--file', rel]
    prepare_cmd += ['--out', self_manifest]
    phase('prepare', lambda: run(prepare_cmd), '清单 prepare：为夹具副本生成源文件哈希清单',
          expect_out=['prepared 8 source files'])
    phase('prepare', lambda: run([tool('batch_manifest.py'), 'check', '--src', proj_src,
                                  '--manifest', self_manifest]),
          '清单 check：同根比对（自建副本 → 应 PASS）', expect_out=['PASS: 8 source files match'])
    phase('prepare', lambda: run([tool('batch_manifest.py'), 'check', '--src', SRC48,
                                  '--manifest', MANIFEST]),
          '清单 check：夹具清单的 source_root 不同 → **预期 FAIL**（已知夹具条件，不是静默失败）',
          expect_rc=1, expect_out=['source root differs'])
    phase('prepare', lambda: run([tool('batch_preflight.py'), '--src', SRC48, '--plan', PLAN_R1,
                                  '--manifest', MANIFEST, '--json', os.path.join(work, 'pre_r1.json')]),
          '预检：首轮计划（**预期 FAIL**：3 个 ★签名缺口 + 5 处密度连段）', expect_rc=1,
          expect_out=['appendRow', 'sanitizeCell', 'appendSeparator', '最长无中文注释连段'])
    phase('repair', lambda: run([tool('batch_preflight.py'), '--src', SRC48, '--plan', PLAN_FIXED,
                                 '--manifest', MANIFEST, '--json', os.path.join(work, 'pre_fixed.json')]),
          '预检：修复后计划（预期 PASS）', expect_out=['→ PASS'])

    # ── inject：脚手架（槽位）→ 组装真实分片 → 注入 → 重复构建校验 ──
    skel = os.path.join(work, 'skeleton.md')
    state = os.path.join(work, 'batch.json')
    parts = os.path.join(work, 'parts')
    os.makedirs(parts)
    for fn in os.listdir(os.path.join(FIX, 'batch48', 'parts')):
        shutil.copyfile(os.path.join(FIX, 'batch48', 'parts', fn), os.path.join(parts, fn))
    phase('prepare', lambda: run([tool('new_batch.py'), '--stage', '3', '--batch', '48',
                                  '--title', '智能切片策略', '--classes', 'TableChunker★',
                                  '--sha', '16984b9', '--out', skel, '--src', SRC48,
                                  '--plan', PLAN_FIXED, '--batch-json', state]),
          '脚手架：17 节骨架 + 8 个稳定槽位', expect_out=['节数 = 17', '8 个源码槽位'])
    st = json.load(io.open(state, encoding='utf-8'))
    st['parts_dir'] = parts
    st['out'] = os.path.join(work, '批次48.md')
    io.open(state, 'w', encoding='utf-8', newline='').write(json.dumps(st, ensure_ascii=False, indent=1))
    phase('inject', lambda: run([tool('batch_build.py'), '--batch', state]),
          '组装（真实分片）+ 注入（槽位/兼容旧格式）', expect_out=['注入 8 块', '节数=17'])
    phase('inject', lambda: run([tool('batch_build.py'), '--batch', state, '--check']),
          '重复构建 → 与磁盘一致（幂等）', expect_out=['一致'])

    # ── gate / verify / publish：有真实教材时跑完整闭环（在临时项目副本上盖章与发布）──
    if have_real:
        phase('gate', lambda: run([tool('gate_lecture.py'), st['out'], '--src', SRC48,
                                   '--json', os.path.join(work, 'gate_built.json')]),
              '门禁（重建产物）', expect_out=['总判定: PASS'])
        proj = os.path.join(work, 'proj')
        os.makedirs(os.path.join(proj, 'NOTES', '教学讲解'))
        lec_copy = os.path.join(proj, 'NOTES', '教学讲解', '批次48-智能切片.md')
        shutil.copyfile(REAL_LEC, lec_copy)
        io.open(os.path.join(proj, 'NOTES', '覆盖矩阵.md'), 'w', encoding='utf-8', newline='').write(
            '# 覆盖矩阵\n\n| 文件 | 状态 |\n|---|---|\n| 旧件 | 已讲 |\n')
        io.open(os.path.join(proj, 'NOTES', '状态.md'), 'w', encoding='utf-8', newline='').write(
            '# 状态\n\n下一批：阶段3批次48\n')
        phase('gate', lambda: run([tool('gate_lecture.py'), lec_copy, '--src', RAGENT,
                                   '--json', os.path.join(work, 'gate_proj.json')]),
              '门禁（真实批次48 教材副本）', expect_out=['总判定: PASS'])
        phase('verify', lambda: run([tool('sync_gate_result.py'), lec_copy, '--src', RAGENT,
                                     '--result-json', os.path.join(work, 'gate_proj.json'), '--apply',
                                     '--final-json', os.path.join(proj, 'NOTES', 'b48.final.json')]),
              '盖章 ⑯ + 复跑终检', expect_out=['盖章后复跑闸门通过'])
        record = {
            "schema_version": 1, "project_root": proj, "batch_id": "stage3-b48", "batch_no": 48,
            "next_batch": "stage3-b49", "title": "智能切片策略", "book": 1,
            "lecture": "NOTES/教学讲解/批次48-智能切片.md",
            "gate_final": "NOTES/b48.final.json",
            "teaching": [{"file": "rag/src/main/java/TableChunker.java", "role": "主讲"}],
            "targets": [
                {"file": "NOTES/覆盖矩阵.md", "op": "insert_before_anchor", "anchor": "| 旧件 | 已讲 |",
                 "idempotent_key": "批次48", "text": "| rag/.../TableChunker.java | 已讲（阶段3批次48） |"},
                # 同一文件两条更新：验证"按文件分组、串行叠加"（原实现会互相覆盖）
                {"file": "NOTES/状态.md", "op": "ensure_line", "idempotent_key": "批次48 已完成",
                 "text": "- 批次48 已完成"},
                {"file": "NOTES/状态.md", "op": "replace_anchor", "anchor": "下一批：阶段3批次48",
                 "expect": "阶段3批次48", "idempotent_key": "下一批：阶段3批次49",
                 "text": "下一批：阶段3批次49"}],
        }
        rec_path = os.path.join(work, 'batch_record.json')
        io.open(rec_path, 'w', encoding='utf-8', newline='').write(
            json.dumps(record, ensure_ascii=False, indent=1))
        phase('publish', lambda: run([tool('publish_batch.py'), '--record', rec_path]),
              '发布预览（dry-run）', expect_out=['未写盘'])
        phase('publish', lambda: run([tool('publish_batch.py'), '--record', rec_path, '--apply']),
              '发布（写盘，含同一文件两条更新）', expect_out=['已更新 2 个文件'])
        phase('publish', lambda: run([tool('publish_batch.py'), '--record', rec_path, '--apply']),
              '重复发布（应零变化）', expect_out=['重复发布零变化'])
        state_text = io.open(os.path.join(proj, 'NOTES', '状态.md'), encoding='utf-8').read()
        ok = '批次48 已完成' in state_text and '下一批：阶段3批次49' in state_text
        steps.append(dict(phase='publish', rc=0 if ok else 1, ms=0.0,
                          note='同一文件的两条更新都已落盘（内容断言）',
                          expect_rc=[0], expect_out=[], ok=ok,
                          problems=[] if ok else ['状态.md 里缺少某一条更新：%r' % state_text[-60:]],
                          head=''))
        if not ok:
            mismatches.append('同一文件两条更新未同时落盘：%r' % state_text[-60:])
    else:
        print('[SKIP] 没找到 %s —— 跳过依赖真实教材的门禁/盖章/发布步骤（设 RAGENT_ROOT 可指定）'
              % REAL_LEC)

    # ── Python 侧 ──
    phase('prepare', lambda: run([tool('batch_preflight.py'), '--src', PY_SRC, '--plan', PY_PLAN,
                                  '--json', os.path.join(work, 'pre_py.json')]),
          'Python 侧预检（密度等为报告档）', expect_out=['→ PASS'])
    phase('gate', lambda: run([tool('gate_lecture.py'), os.path.join(PY_SRC, 'app', 'sample.py'),
                               '--src', PY_SRC, '--json', os.path.join(work, 'gate_py.json')]),
          'Python 文件（非教材：应为 NOT_CHECKED，不得真空 PASS）', expect_out=['NOT_CHECKED'])

    rep = BT.report(BT.read_records(trace))
    report = dict(steps=steps, trace=rep, mismatches=mismatches,
                  note='只覆盖脚本化步骤；模型写作耗时不在其中，故不构成真实批次总时长的结论')
    io.open(os.path.join(work, 'report.json'), 'w', encoding='utf-8', newline='').write(
        json.dumps(report, ensure_ascii=False, indent=1) + '\n')
    out = io.open(os.path.join(work, 'report.txt'), 'w', encoding='utf-8', newline='')
    out.write(BT.render(rep) + '\n\n')
    for s in steps:
        out.write('[%s] %-10s rc=%s %8.1f ms  %s\n     期望 rc=%s 输出含 %s%s\n'
                  % ('OK  ' if s['ok'] else 'FAIL', s['phase'], s['rc'], s['ms'], s['note'],
                     s['expect_rc'], s['expect_out'] or '（无）',
                     '' if s['ok'] else '  ← ' + '；'.join(s['problems'])))
    out.write('\n注：本表只覆盖脚本化步骤；模型写作耗时不在其中，不能据此宣称真实批次总时长已缩短。\n')
    out.close()
    print('端到端脚本化试运行：%d 步，期望不符 %d 项 → %s'
          % (len(steps), len(mismatches), os.path.join(work, 'report.txt')))
    print('  注：只覆盖脚本化步骤，模型写作耗时不在其中（报表里单列"未记录阶段"）。')
    for m in mismatches:
        print('  [FAIL] %s' % m)
    return 1 if mismatches else 0


if __name__ == '__main__':
    sys.exit(main())
