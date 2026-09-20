# replicate-learning 第二轮提速重构 · 变更说明与实测数据

> 日期：2026-09-20；仓库：`D:\develop\workspace\replicate-learningV2`。
> 依据：《replicate-learning-批次48复盘与第二轮提速重构实施方案.md》§3.1–§3.5、§4、§5。
> 状态：**阶段 1–5 已实现并提交**；§3.6（内容契约实验）**未实施**，理由见 §6。判据版本仍是 **v2.30，未改动任何质量判据**。

## 0. 一句话结论

把"可确定的工作"收归了工具：**开批前预检**（用闸门同一套函数，注入前就报缺口）、**稳定源码槽位**（块身份不再靠猜 `contains`）、
**一条命令重建终稿**、**结构化门禁结果 + 从结果盖章 ⑯**、**一份批次记录更新全部派生视图**。
判据一条没放宽；11 份既有样本的判定**逐字未变**。

同时得到一个必须说清楚的实测结论：**脚本侧根本不是那一小时的瓶颈**。整条脚本化流水线（清单→预检→组装→注入→门禁→盖章→发布）
在真实批次48 素材上跑完只需 **约 8 秒工具时间**（下表）。所以本次提速的价值在**减少模型的返工与猜规则**（预检提前暴露缺口、
块身份稳定、冲突零写入），而不是"把一小时压成几分钟"——具体降幅仍须真实批次对照测量（见 §5）。

## 1. 交付清单（按方案的五个提交）

| 方案节 | 实现 | 关键证据 | 复跑命令 |
|---|---|---|---|
| §3.1 基线计时与冲突清理 | `scripts/batch_trace.py`；`tests/fixtures/`（batch48 真实夹具 + py_mini）；文档 16/17 节与"开批三读"冲突清理 | 分步实测（§4）；夹具含**首轮**注释计划（只在 `test.md` 的 write 调用里留过副本，已取回） | `python scripts/batch_trace.py --file t.jsonl report` |
| §3.2 开批预检 | `scripts/batch_preflight.py` + `scripts/lecture_checks.py`（结果 schema 与规则 ID 登记表） | 批次48 首轮计划 → **★ 签名缺口 3 个 + 密度连段 5 处**（8/10/10/8/10），修复后 → 0 缺口 | `python scripts/batch_preflight.py --src tests/fixtures/batch48/project --plan tests/fixtures/batch48/b48_inject_plan_r1.json --manifest tests/fixtures/batch48/b48_manifest.json` |
| §3.3 稳定槽位与可重复构建 | `new_batch.py --plan/--batch-json`；`inject_source.py` 槽位寻址；`scripts/batch_build.py` | 连注两次逐字节幂等；源文件 hash 漂移 → 拒绝写入；旧分片 → 退回 anchor 并告警 | `python scripts/batch_build.py --batch <batch.json> --check` |
| §3.4 结构化门禁与盖章 | `gate_lecture.py --json` 结构化结果；`sync_gate_result.py --result-json/--final-json` | 11 份样本判定逐字不变（§3）；五种拒绝路径（哈希/版本/缺项/阻塞/真空 PASS） | `python scripts/gate_lecture.py <批次.md> --src <项目根> --json r.json && python scripts/sync_gate_result.py <批次.md> --src <项目根> --result-json r.json --apply` |
| §3.5 单一记录与安全归档 | `scripts/publish_batch.py` + `batch_record.json` | 第二处冲突 → 全部目标不动；重复发布零变化；`--git-add` 只加点名文件 | `python scripts/publish_batch.py --record <batch_record.json>`（缺省 dry-run） |
| §4 文档整理 | SKILL 保持 58 行短入口；执行协议/操作手册/质量卡/质量细则/REFERENCES README/根 README 同步 | `skill_selfcheck` 92 项 0 失败 | `python scripts/skill_selfcheck.py` |

新增 4 个工具 + 1 个公共模块（`batch_trace` / `batch_preflight` / `batch_build` / `publish_batch` / `lecture_checks`），
新增 4 个行为自测（`test_batch_trace` / `test_batch_preflight` / `test_batch_slots` / `test_gate_result` / `test_publish_batch`），
`skill_selfcheck` 78 → **92 项**，单测 14 → **82 项**。

## 2. 五个提交

| 提交 | 内容 |
|---|---|
| `a4287cf` | feat(trace): 分步计时器 + 回归夹具 + 文档冲突清理（§3.1） |
| `a7e219b` | feat(preflight): 开批预检（§3.2） |
| `560ff0c` | feat(slots): 稳定源码槽位 + `batch_build` 可重复构建（§3.3） |
| `c03baca` | feat(gate-json): 结构化单批门禁结果 + 从结果盖章（§3.4） |
| `1a83bbc` | feat(publish): 一份批次记录更新全部派生视图（§3.5） |
| `6c39f83` | docs: 文档同步与交付说明 + `gate_all` 崩溃缺陷修复 |
| `8da47e4` | test(e2e): 端到端脚本化试运行 |
| `8a57300` | fix(review): 审查 4 处缺陷（归档覆盖 / 盖章校验 / 复检回滚 / 验收脚本） |
| `ef7c2fe` | fix(review2): 发布入口改用完整结论校验；复检异常路径也回滚 |
| 见 §9.2 | fix(review3): 结论字段必须存在且值明确合格 |

## 3. 判据回归：改造前后判定必须一字不变

方法：`git show HEAD:skills/replicate-learning/scripts/gate_lecture.py` 取**改造前**的闸门，
与改造后各跑一遍，逐份比对「退出码 + `总判定` 行 + `[FAIL]` 行集合」。

| 样本 | 退出码 旧→新 | 判定 旧→新 | FAIL 行 |
|---|---|---|---|
| ragent 阶段1批次1（RagentApplication★…） | 0→0 | PASS→PASS | 一致 |
| ragent 阶段3批次33（LightRAG） | 0→0 | PASS→PASS | 一致 |
| ragent 阶段3批次40（VectorChunkSink…） | 0→0 | PASS→PASS | 一致 |
| ragent 阶段3批次43（Csv/Excel 解析族） | 0→0 | PASS→PASS | 一致 |
| ragent 阶段3批次47（智能切片前半） | 0→0 | PASS→PASS | 一致 |
| ragent 阶段3批次48（智能切片策略） | 0→0 | PASS→PASS | 一致 |
| `references/十七节黄金样例-py`（参照物） | 0→0 | PASS→PASS | 一致 |
| `references/结构密度样例.md` | 1→1 | FAIL→FAIL | 12 条一致 |
| `examples/黄金样例.md` | 1→1 | FAIL→FAIL | 一致 |
| `examples/黄金样例-python.md` | 0→0 | PASS→PASS | 一致 |
| `references/六节九子块样例`（参照物） | 0→0 | PASS→PASS | 一致 |

**合计 11/11 逐字不变**（另有 1 份因文件名写错被跳过，非判定差异）。同时新结果里没有任何「核验对象 0 却写 PASS」的检查项。

补充（第二轮审查后）：`git diff c03baca -- …/gate_lecture.py` 为空——**判据实现自 §3.4 提交后再未改动**，
故上述 11/11 结论对本轮修复依然成立（本轮只动 `lecture_checks/publish_batch/sync_gate_result` 与测试）。

## 4. 脚本化流水线实测（真实批次48 素材）

素材 = 批次48 的 8 件真实 Java 源码 + 真实注释计划 + 5 份真实分片；输出写在临时目录，未改 ragent 任何教材。
每一步都带**显式期望断言**（退出码 + 输出关键串，见下表"期望"列）：期望不符 → 脚本退出码 1 并列出不符项。

| 步骤 | 阶段 | 实测 | 期望（脚本断言） | 结论 |
|---|---|---:|---|---|
| 清单 prepare（自建副本） | prepare | 268 ms | rc=0，`prepared 8 source files` | 通过 |
| 清单 check（同根副本） | prepare | 149 ms | rc=0，`PASS: 8 source files match` | 通过 |
| 清单 check（夹具清单，`source_root` 不同） | prepare | 143 ms | **rc=1**，`source root differs` | 已知夹具条件，**显式断言为预期失败**（不再静默返回 0） |
| 预检：**首轮**计划 | prepare | 267 ms | **rc=1**，含 appendRow/sanitizeCell/appendSeparator 与"最长无中文注释连段" | ★ 签名缺口 3 + 密度连段 5（8/10/10/8/10） |
| 预检：修复后计划 | repair | 259 ms | rc=0，`→ PASS` | 0 缺口 |
| 脚手架：17 节 + 8 槽位 | prepare | 209 ms | rc=0，`节数 = 17`、`8 个源码槽位` | 通过 |
| 组装（真实分片）+ 注入 | inject | 185 ms | rc=0，`注入 8 块`、`节数=17` | 8 块命中；旧格式分片走兼容 `anchor` 并告警 |
| 重复构建 `--check` | inject | 182 ms | rc=0，`一致` | 逐字节幂等 |
| 门禁（重建产物） | gate | 526 ms | rc=0，`总判定: PASS` | 通过 |
| 门禁（真实 156KB 教材副本） | gate | 2639 ms | rc=0，`总判定: PASS` | 16 条检查（PASS 14 / REPORT 1 / NOT_CHECKED 1） |
| 盖章 ⑯ + 复跑终检 | verify | 2190 ms | rc=0，`盖章后复跑闸门通过` | 最终哈希单独记录 |
| 发布预览 / 发布 / 重复发布 | publish | 143 / 152 / 139 ms | rc=0，`未写盘` / `已更新 2 个文件` / `重复发布零变化` | 2 个视图；重复发布零变化 |
| 同一文件两条更新（内容断言） | publish | — | 两条都在文件里 | 按文件分组、串行叠加 |
| Python 侧预检 | prepare | 223 ms | rc=0，`→ PASS` | P-PY = REPORT（核验 1 个对象） |
| Python 文件过闸门 | gate | 190 ms | rc=0，`NOT_CHECKED` | 0 PASS / 10 NOT_CHECKED（**没有真空 PASS**） |

**合计 17 步，期望不符 0 项；脚本侧工具时间约 8 秒**（记录墙钟 8000 ms）。
**这只是脚本侧基线，不是"一小时已缩短"的结论**：模型写作（investigate/write）无法由脚本采集，
报表里单列为"未记录阶段"，本文件不预估降幅（见 §6）。

对照：第48批会话导出里是 **105 次工具调用**（68 次 bash）、一次 Maven 约 **28 秒**、整批用户体感约 **一小时**。
结论：**脚本工具时间不是瓶颈**；能省的是"猜规则 → 试错 → 重注入 → 手写归档"这条模型侧回路。

## 5. Java / Python 对照数据表

| 维度 | Java（真实批次48） | Python（py_mini 合成夹具） |
|---|---|---|
| 预检可判项 | P-DENSITY / P-SIG / P-REVERSE 均为 **FAIL 档** | P-DENSITY 等 = `NOT_CHECKED`（无 java 块）；P-PY = **REPORT**（契约 S24：py 密度/行号为报告档） |
| 首轮缺口 → 修复 | ★ 签名 3 + 密度连段 5 → 0 | 合法计划 0 缺口 |
| 坏注释键 | 越界 / 非数字（合成用例） | **字符串内部行**、**反斜杠续行**、越界、非数字（四种都报） |
| 注入安全 | 行尾 `//` 注释；多行文本块内部不标注 | tokenize 判定多行字符串；续行不加字符；内存 `compile()` 校验（不落 `.pyc`） |
| 槽位注入幂等 | 连注两次逐字节一致 | 同（Python 块同样走槽位） |
| 门禁判定 | 真实批次48：PASS（16 条检查） | `.py` 非教材：10 项 NOT_CHECKED、0 项真空 PASS |
| 起点/终点样本 | ragent 第一册 11 份回归逐字不变；批次48 端到端通过 | 夹具范围内通过 |

**诚实记录的限制**：本机只有 ragent-official 一个项目的**完整第一册（Java）**。
方案 §5 要求的"Python 跨模块批对照"**没有真实素材**，因此 Python 侧结论只限夹具范围，不外推；
拿到真实 Python 项目批次后应按同一套命令补测（`tests/fixtures/README.md` 已写明）。

## 6. 未实施 / 已知限制

1. **§3.6 内容契约实验（`experimental-book1`）未实施**。方案本身要求它"另建第六个独立提交，需 A/B 评测通过再决定是否进入默认"，
   而本会话**没有盲评读者、也没有真实批次的对照运行**——此时改字数阈值只能得到"看起来更快"的不可验证结论，
   正是方案 §1 与 §5 反复警告的做法。要做的最小前置：真实批次 ×≥3 次的端到端对照（同模型档位、同源码范围）+
   不看版本标签的读者盲评。**未做就是未做，本文件不预估降幅。**
2. **快照读取失败仍记 `G-SNAPSHOT=REPORT`（可见但不判红）**，不是 `FAIL`。原因：把"声明了快照却读不到"从
   通过改成失败是**判据变更**，需要递增 `GATE_VERSION` + 回归证据 + 存量工单；本轮不动判据。
   但它在结构化结果里**不再可能被读成 PASS**，终端也会打印醒目告警。
3. **SSOT 两处历史 ID 缺陷保持原样**：⑤ 组首条实际是 `F4`（不是 `U1`），`S22` 出现两次（记录类形态 / 正文计数）。
   改 ID 会让已有引用与历史记录对不上，故只在 `lecture_checks.CHECK_GROUPS` 里显式区分（`S22b`）并写明理由。
4. **`batch_manifest.py check` 对夹具报 FAIL**：它严格比对清单里的绝对 `source_root`；夹具是拷贝，
   预检因此对 hash 用相对路径比对并输出 `[WARN]`。真实项目里 `--src` 与清单同根时不存在这个问题。
   端到端脚本现在**两条都跑**：自建同根副本断言 `PASS`，夹具清单断言 `rc=1 + source root differs`（预期失败必须显式声明）。
5. **`gate_all.py` 的一处崩溃缺陷已顺带修掉**：记录类文件声明判据版本 ≥2.21 时 `s_bad` 未定义 → `NameError` 崩掉整个记分卡
   （新增回归测试）。这属于工具缺陷修复，不改变任何判定结果。
6. `test.md`（用户原始会话导出）**只读、未改动、未纳入提交**；其他安装副本（dsh-toolkit/Codex）**未同步**——等审查通过后再同步。
7. **方案 §5 列出的对照场景里，有三种本轮没有真实素材，未测就是未测**：
   ① "另一批 Java 小文件"——用合成迷你夹具覆盖了机制（同节双块/多行字符串/续行），但不是真实小批次；
   ② "Python 跨模块批"——本机没有真实 Python 项目第一册（见 §5 限制）；
   ③ "无法启动外部服务"——属于真实批次的项目测试场景，本轮没有跑真实批次，故无数据。
   拿到真实项目批次后按 §7 的命令补测，并把分步耗时填回 `batch_trace` 报表。

## 7. 复跑命令（自带夹具，无需 ragent 项目）

```bash
cd skills/replicate-learning

# 全量自检与单测
python scripts/skill_selfcheck.py          # 期望：检查项 99，失败 0 → PASS
python scripts/v2_selfcheck.py             # 期望：PASS (6 contract entries)
python -m unittest discover -s scripts -p "test_*.py" -t scripts   # 期望：107 项 OK

# 预检：首轮计划必须报出 3 个 ★ 签名缺口 + 5 处密度连段；修复后计划必须 0 缺口
python scripts/batch_preflight.py --src tests/fixtures/batch48/project \
    --plan tests/fixtures/batch48/b48_inject_plan_r1.json --manifest tests/fixtures/batch48/b48_manifest.json
python scripts/batch_preflight.py --src tests/fixtures/batch48/project \
    --plan tests/fixtures/batch48/b48_inject_plan_fixed.json --manifest tests/fixtures/batch48/b48_manifest.json

# 槽位与可重复构建（骨架 → 分片 → 注入 → 重复构建）
python scripts/new_batch.py --stage 3 --batch 48 --title "智能切片策略" --classes "TableChunker★" \
    --sha 16984b9 --out /tmp/skeleton.md --src tests/fixtures/batch48/project \
    --plan tests/fixtures/batch48/b48_inject_plan_fixed.json --batch-json /tmp/batch.json
python scripts/batch_build.py --batch /tmp/batch.json --dry-run
python scripts/batch_build.py --batch /tmp/batch.json --check

# 重建夹具（有 ragent-official 时；只读原资料，--check 只校验不写盘）
python tests/fixtures/batch48/build_batch48_fixture.py --check

# 端到端脚本化试运行（本轮 §4 数据的来源；缺 ragent-official 时自动跳过三步并打印说明）
python tests/e2e_scripted_run.py --work /tmp/e2e
```

对真实项目的一批：

```bash
python scripts/batch_trace.py --file <批次目录>/trace.jsonl start --batch-id <本批号>
python scripts/batch_manifest.py prepare --src <项目根> --file <相对路径> --out <清单.json>
python scripts/new_batch.py --stage N --batch M --title "…" --classes "…" --sha <sha> \
    --out <批次.md> --src <项目根> --plan <注释计划.json> --batch-json <batch.json> --manifest <清单.json>
python scripts/batch_preflight.py --src <项目根> --plan <注释计划.json> --manifest <清单.json>
#   …写 parts/*.md …
python scripts/batch_build.py --batch <batch.json>
python scripts/gate_lecture.py <批次.md> --src <项目根> --json <结果.json>
python scripts/sync_gate_result.py <批次.md> --src <项目根> --result-json <结果.json> --apply
python scripts/publish_batch.py --record <batch_record.json>          # 预览 → --apply
python scripts/batch_trace.py --file <批次目录>/trace.jsonl report
```

## 8. 判定与口径变更说明（提交前必读）

- **判据版本不变**：`GATE_VERSION` 仍是 `2.30`，`spec/00-质量契约.json` 未改。新增的全部是**工具与结果表达**，
  不是质量判据。
- **`gate_lecture.py --json` 的字段变了**：旧字段（`fidelity`/`reverse`/`density`/`lineno`/`usage`/`form`/`struct`/
  `snapshot`/`ver_marked`/`pass_`）**全部保留**，新增 `schema_version`/`contract_version`/`lecture_sha256`/
  `source_manifest_sha256`/`checks[]`/`pass`。依据旧字段做的基线比对不受影响。
- **`inject_source.py` 新增槽位寻址**：优先用槽位；旧 `anchor`/`contains` 仍可用。**源文件 hash 不符时一律拒绝**，
  不会退回旧寻址。
- **`sync_gate_result.py` 默认行为**：不给 `--result-json` 时仍是旧路径（自己跑闸门 + 解析文本），只多打印一行建议。
- **`safe_edit.save(backup=True)`**：目标文件不存在时不再尝试读它（原来会 `FileNotFoundError`）。
- **`gate_all.py`**：`s_bad` 初始化位置修正（崩溃缺陷），判定结果不变。

## 9. 审查意见的处理（第二轮）

第一轮审查（独立复跑单测/自检 + 定向构造用例）提出 4 项，逐条处理如下；**审查没有改动仓库文件**。

| # | 审查意见 | 复现 | 修复 | 回归测试 |
|---|---|---|---|---|
| 1 | 同一文件的多条归档更新互相覆盖（`publish_batch.py`） | 两条更新同一个状态文件 → 只留第二条 | `plan_updates` 改为**按文件分组、串行叠加**（维护"当前文本"，最后每个文件只落一次盘；差异按"原文 → 最终"整体展示） | `test_two_updates_on_the_same_file_both_land`、`test_three_updates_on_the_same_file_are_sequential`、`test_same_file_conflict_in_the_second_update_leaves_the_file_untouched`；`skill_selfcheck` ㉔ 组新增同文件双更新断言 |
| 2 | 失败的门禁结果可能通过盖章前校验（`lecture_checks.py`） | 构造 `pass=false / verdict=FAIL` 而各项 PASS 的结果 → 校验返回空错误列表 | `validate_result` 增查**顶层 `pass` / `pass_` / `verdict`** 三个结论字段，并做交叉一致性（`pass=true` 有阻塞项、`pass=false` 无阻塞项都拒绝） | `test_self_reported_failure_cannot_be_stamped`、`test_rendered_top_level_confusing_pass_flags`、`test_result_with_contradictory_conclusion_is_refused`；`skill_selfcheck` ㉓ 组新增"顶层自述失败 → 拒绝" |
| 3 | 盖章后复检失败不会自动还原讲义（`sync_gate_result.py`） | 盖章 → 复检 FAIL → 只打印"请手动回滚" | 盖章前留存原稿字节；复检失败 → **自动回滚**并把 `rolled_back=true` 写进最终记录，工具退出码 1。此外最终复检判定改为**退出码为 0 且 `pass=true`**（两者都要） | `test_rolls_back_when_post_stamp_verification_fails`（真实场景：结果自洽但正文过不了闸门）、`test_final_verification_requires_zero_exit_code`（模拟"闸门崩了但旧结果文件还在"） |
| 4 | 验收脚本自相矛盾（`tests/e2e_scripted_run.py`） | 清单校验 rc=1，脚本整体仍返回 0 | 每步**显式声明期望**（退出码 + 输出关键串），不符即退出码 1 并列明；清单校验改为两条（自建同根副本断言 PASS；夹具清单断言 rc=1 + `source root differs`）；新增同文件双更新内容断言；报表与终端都写明"只覆盖脚本化步骤，不构成真实批次总时长结论" | 脚本自身：**17 步，期望不符 0 项**（见 §4） |

判据回归不受影响：本轮只动 `lecture_checks.py` / `publish_batch.py` / `sync_gate_result.py` 与其测试，
**`gate_lecture.py` 未改**，故 §3 的 11/11 逐字不变结论继续成立。

验证（修复后复跑）：`skill_selfcheck` **94 项 0 失败**（㉓㉔ 各新增一条断言）、单测 **90 项 OK**、`v2_selfcheck` PASS、
端到端脚本化试运行 17 步期望全中。

### 9.1 第二轮审查（发布入口 + 异常回滚）

| # | 审查意见 | 复现 | 修复 | 回归测试 |
|---|---|---|---|---|
| 5 | **发布入口没有使用完整结论校验**（`publish_batch.py`） | ① `gate_result` 写 `pass=false`/`verdict=FAIL` 但检查列表无阻塞项 → 被接受；② `gate_final` 写 `pass=true` 但 `exit_code=1`（哪怕 `rolled_back=true`）→ 被接受 | `check_evidence` 重写：**`gate_final`** 逐项要求 `pass=true`、`exit_code=0`、`rolled_back` 不为真、`stamp_did_not_break_anything` 不为假、`final_lecture_sha256` 等于讲义当前哈希、`contract_version` 等于当前版本、无 `verification_error`/`result_read_error`；**`gate_result`（旧直接入口）** 改调 `lecture_checks.validate_result` 做完整校验（schema/契约/正文哈希/清单哈希/必需检查项/无阻塞/顶层结论自洽）。必需检查清单收敛为 `lecture_checks.REQUIRED_RESULT_CHECKS`，盖章与发布**共用同一份**，避免两处漂移 | `test_gate_final_with_nonzero_exit_code_is_refused`、`test_gate_final_marked_rolled_back_is_refused`、`test_gate_final_with_verification_error_is_refused`、`test_gate_final_with_stale_contract_version_is_refused`、`test_healthy_gate_final_is_accepted`、`test_direct_gate_result_entry_uses_full_validation`、`test_direct_gate_result_entry_accepts_a_healthy_result`、`test_direct_gate_result_entry_needs_the_required_checks`；`skill_selfcheck` ㉔ 组加 exit_code / rolled_back 两条拒绝断言 |
| 6 | **复检异常路径会绕过回滚**（`sync_gate_result.py`） | 复检读到损坏 JSON（或复检自身抛异常）→ 异常向上冒泡，讲义留在**已盖章**状态 | `verify_final` 读取结果文件改为 `try/except (ValueError, OSError)` → 记 `result_read_error` 并按"复检失败"处理（不抛）；`main` 再把整个复检包进 `try/except BaseException`，任何异常都走回滚；`restore()` 失败**不再抛异常**而是返回 False，并打印"请立刻从 `.bak` 恢复"，最终记录带 `rollback_ok` | `test_rolls_back_even_when_verification_itself_raises`（打桩让复检抛 `OSError` → 断言字节级回滚 + `verification_error` 入档）、`test_corrupt_final_result_file_is_treated_as_failure`（半截 JSON → 不抛、判失败、`result_read_error` 入档）、`test_restore_reports_failure_instead_of_raising` |

定向复现（CLI 实跑，本次修复后）：

```text
健康最终记录（预期 rc=0）                                    rc=0
gate_final: pass=true 但 exit_code=1（预期拒绝）             rc=1  [ABORT] …exit_code=1…stamp_did_not_break_anything=false…
gate_final: rolled_back=true（预期拒绝）                     rc=1  [ABORT] …rolled_back=true（记录显示盖章后复检失败并已回滚）…
gate_result: pass=false/verdict=FAIL 无阻塞项（预期拒绝）     rc=1  [ABORT] 门禁结果不能作为发布依据（完整校验未通过）
gate_result: 健康结果（预期 rc=0）                           rc=0
```

验证（第二轮修复后复跑）：`skill_selfcheck` **96 项 0 失败**、单测 **101 项 OK**、`v2_selfcheck` PASS、
端到端脚本化试运行 17 步期望全中；`gate_lecture.py` 仍未改动（`git diff c03baca -- …/gate_lecture.py` 为空）。

### 9.2 第三轮审查（缺字段 = 不合格）

| # | 审查意见 | 复现 | 修复 | 回归测试 |
|---|---|---|---|---|
| 7 | **缺失的结论字段被当作合格**（`publish_batch.py` / `lecture_checks.py`） | ① 最终记录缺 `contract_version` 与 `stamp_did_not_break_anything` → 仍被接受；② 普通结果整段缺 `pass`/`pass_`/`verdict` → 仍被接受 | 判定从"存在且不合格才报错"改为**字段必须存在且值明确合格**：`check_evidence` 对 `pass/exit_code/rolled_back/stamp_did_not_break_anything/contract_version/final_lecture_sha256` 六个字段先查存在性（缺失或 `null` 一律拒绝）再查取值，并新增 `rollback_ok=false` 拒绝；`validate_result` 对 `pass`/`pass_`/`verdict` 三者要求存在且合格（`verdict` 认闸门的 `总判定: PASS ✅` 与构造函数的 `PASS` 两种写法，出现 FAIL 或空值即拒）；同时让 `make_result` **总是产出**这三个字段（否则工具自己造的结果会被自己的校验拒掉） | `test_gate_final_missing_required_fields_is_refused`（六个字段逐一审）、`test_gate_final_with_null_required_field_is_refused`、`test_gate_final_with_failed_rollback_is_refused`、`test_validate_result_requires_each_conclusion_field`、`test_validate_result_rejects_a_result_without_any_conclusion_fields`、`test_make_result_always_emits_the_conclusion_fields`；`skill_selfcheck` ㉓㉔ 各再加两条缺字段拒绝断言 |

定向复现（CLI 实跑，本次修复后）：

```text
健康最终记录（预期 rc=0）                                     rc=0
gate_final 缺 contract_version + stamp_did_not_break_anything  rc=1  [ABORT] …缺少字段 stamp_did_not_break_anything…缺少字段 contract_version…
gate_final 缺 rolled_back（预期拒绝）                          rc=1  [ABORT] …缺少字段 rolled_back（盖章失败后是否已回滚）…
gate_result 完全没有 pass/pass_/verdict（预期拒绝）             rc=1  [ABORT] 门禁结果不能作为发布依据（完整校验未通过）
gate_result 缺 pass_（预期拒绝）                               rc=1  [ABORT] 门禁结果不能作为发布依据（完整校验未通过）
gate_result 健康结果（预期 rc=0）                              rc=0
```

验证（第三轮修复后复跑）：`skill_selfcheck` **99 项 0 失败**、单测 **107 项 OK**、`v2_selfcheck` PASS、
端到端脚本化试运行 17 步期望全中。
