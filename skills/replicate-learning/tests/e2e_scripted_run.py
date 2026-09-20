"""端到端脚本化试运行：用真实批次48 素材 + py_mini 夹具跑完整第二轮流水线，并记录分步实测耗时。

用法（在仓库根目录执行；需要先 `pip` 之外的零依赖环境，只用标准库）：

    python skills/replicate-learning/tests/e2e_scripted_run.py [--work <输出目录>]

口径（**诚实说明，别把它读成"整批一小时变几秒"**）：
  · 本脚本只测**脚本化步骤**：清单校验/预检/脚手架/组装/注入/门禁/盖章/发布/复验；
  · **模型写作（investigate/write）不在其中**——那部分要操作者按秒表，报表里单列为"未记录阶段"；
  · 材料是真实批次48 的 8 件 Java 源码 + 真实注释计划 + 5 份真实分片，输出写在临时目录，
    **不改 ragent 的任何教材**；缺 ragent-official 时自动跳过依赖真实教材的两步（会打印说明）。

产物：`<work>/report.json`（分步耗时 + batch_trace 聚合报表）、`<work>/trace.jsonl`（原始计时记录）。
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


def run(cmd, cwd=None):
    p = subprocess.run([sys.executable, '-B'] + cmd, capture_output=True, text=True,
                       encoding='utf-8', errors='replace', cwd=cwd or REPO)
    return p.returncode, (p.stdout or ''), (p.stderr or '')


def tool(name):
    return os.path.join(SK, name)


def main():
    ap = argparse.ArgumentParser(description='端到端脚本化试运行（脚本侧步骤计时）')
    ap.add_argument('--work', default=os.path.join(REPO, '.replicate-learning-log', 'e2e-scripted'))
    a = ap.parse_args()
    work = os.path.abspath(a.work)
    if os.path.isdir(work):
        shutil.rmtree(work)
    os.makedirs(work)
    trace = os.path.join(work, 'trace.jsonl')
    results = []
    have_real = os.path.isfile(REAL_LEC)

    def phase(name, fn, note=''):
        BT.phase_begin(trace, name, note=note or None)
        t0 = time.perf_counter()
        rc, out, err = fn()
        ms = (time.perf_counter() - t0) * 1000.0
        BT.phase_end(trace, name)
        results.append(dict(phase=name, rc=rc, ms=round(ms, 1), note=note,
                            head=(out or err or '').strip().split('\n')[-1][:120]))
        return rc, out, err

    BT.append_record(trace, BT.start_record('e2e-scripted', model='(未采集：脚本化试运行)',
                                            contract_version='2.30'))

    # ── prepare：清单校验 + 预检（首轮计划应报缺口；修复后应干净）──
    phase('prepare', lambda: run([tool('batch_manifest.py'), 'check', '--src', SRC48,
                                  '--manifest', MANIFEST]), '源文件哈希清单校验')
    phase('prepare', lambda: run([tool('batch_preflight.py'), '--src', SRC48, '--plan', PLAN_R1,
                                  '--manifest', MANIFEST, '--json', os.path.join(work, 'pre_r1.json')]),
          '预检：首轮计划（预期 FAIL：3 ★签名 + 5 密度连段）')
    phase('repair', lambda: run([tool('batch_preflight.py'), '--src', SRC48, '--plan', PLAN_FIXED,
                                 '--manifest', MANIFEST, '--json', os.path.join(work, 'pre_fixed.json')]),
          '预检：修复后计划（预期 PASS）')

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
          '脚手架：17 节骨架 + 8 个稳定槽位')
    st = json.load(io.open(state, encoding='utf-8'))
    st['parts_dir'] = parts
    st['out'] = os.path.join(work, '批次48.md')
    io.open(state, 'w', encoding='utf-8', newline='').write(json.dumps(st, ensure_ascii=False, indent=1))
    phase('inject', lambda: run([tool('batch_build.py'), '--batch', state]),
          '组装（真实分片）+ 注入（槽位/兼容旧格式）')
    phase('inject', lambda: run([tool('batch_build.py'), '--batch', state, '--check']),
          '重复构建 → 与磁盘一致（幂等）')

    # ── gate / verify / publish：有真实教材时跑完整闭环（在临时项目副本上盖章与发布）──
    if have_real:
        phase('gate', lambda: run([tool('gate_lecture.py'), st['out'], '--src', SRC48,
                                   '--json', os.path.join(work, 'gate_built.json')]),
              '门禁（重建产物）')
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
              '门禁（真实批次48 教材副本）')
        phase('verify', lambda: run([tool('sync_gate_result.py'), lec_copy, '--src', RAGENT,
                                     '--result-json', os.path.join(work, 'gate_proj.json'), '--apply',
                                     '--final-json', os.path.join(proj, 'NOTES', 'b48.final.json')]),
              '盖章 ⑯ + 复跑终检')
        record = {
            "schema_version": 1, "project_root": proj, "batch_id": "stage3-b48", "batch_no": 48,
            "next_batch": "stage3-b49", "title": "智能切片策略", "book": 1,
            "lecture": "NOTES/教学讲解/批次48-智能切片.md",
            "gate_final": "NOTES/b48.final.json",
            "teaching": [{"file": "rag/src/main/java/TableChunker.java", "role": "主讲"}],
            "targets": [
                {"file": "NOTES/覆盖矩阵.md", "op": "insert_before_anchor", "anchor": "| 旧件 | 已讲 |",
                 "idempotent_key": "批次48", "text": "| rag/.../TableChunker.java | 已讲（阶段3批次48） |"},
                {"file": "NOTES/状态.md", "op": "replace_anchor", "anchor": "下一批：阶段3批次48",
                 "expect": "阶段3批次48", "idempotent_key": "下一批：阶段3批次49",
                 "text": "下一批：阶段3批次49"}],
        }
        rec_path = os.path.join(work, 'batch_record.json')
        io.open(rec_path, 'w', encoding='utf-8', newline='').write(
            json.dumps(record, ensure_ascii=False, indent=1))
        phase('publish', lambda: run([tool('publish_batch.py'), '--record', rec_path]),
              '发布预览（dry-run）')
        phase('publish', lambda: run([tool('publish_batch.py'), '--record', rec_path, '--apply']),
              '发布（写盘）')
        phase('publish', lambda: run([tool('publish_batch.py'), '--record', rec_path, '--apply']),
              '重复发布（应零变化）')
    else:
        print('[SKIP] 没找到 %s —— 跳过依赖真实教材的门禁/盖章/发布三步（设 RAGENT_ROOT 可指定）'
              % REAL_LEC)

    # ── Python 侧 ──
    phase('prepare', lambda: run([tool('batch_preflight.py'), '--src', PY_SRC, '--plan', PY_PLAN,
                                  '--json', os.path.join(work, 'pre_py.json')]),
          'Python 侧预检（密度等为报告档）')
    phase('gate', lambda: run([tool('gate_lecture.py'),
                               os.path.join(PY_SRC, 'app', 'sample.py'), '--src', PY_SRC,
                               '--json', os.path.join(work, 'gate_py.json')]),
          'Python 文件（非教材：应为 NOT_CHECKED，不得真空 PASS）')

    rep = BT.report(BT.read_records(trace))
    report = dict(steps=results, trace=rep)
    io.open(os.path.join(work, 'report.json'), 'w', encoding='utf-8', newline='').write(
        json.dumps(report, ensure_ascii=False, indent=1) + '\n')
    out = io.open(os.path.join(work, 'report.txt'), 'w', encoding='utf-8', newline='')
    out.write(BT.render(rep) + '\n\n')
    for s in results:
        out.write('%-10s rc=%s %8.1f ms  %s\n' % (s['phase'], s['rc'], s['ms'], s['note']))
    out.close()
    print('端到端脚本化试运行完成：%d 步（含预期 FAIL 的预检步骤）→ %s'
          % (len(results), os.path.join(work, 'report.txt')))
    print('  分步耗时与聚合报表：%s' % os.path.join(work, 'report.json'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
