# replicate-learning 第二轮提速重构 · 变更说明与实测数据

> 日期：2026-09-20；仓库：`D:\develop\workspace\replicate-learningV2`。
> 依据：《replicate-learning-批次48复盘与第二轮提速重构实施方案.md》§3.1–§3.5、§4、§5。
> 状态：**阶段 1–5 已实现并提交**；§3.6（内容契约实验）**未实施**，理由见 §6。判据版本仍是 **v2.30，未改动任何质量判据**。
> 第五轮（§11）修掉批次49 实录的四处工具链缺陷（版本门 / 清单覆盖 / 批次配置 / 重建护栏）——同样不动判据；
> §13 追加"版本门第二次收紧"（声明不被后续说明覆盖）与随之暴露的批次3 工单。

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
| §4 文档整理 | SKILL 保持 58 行短入口；执行协议/操作手册/质量卡/质量细则/REFERENCES README/根 README 同步 | `skill_selfcheck` 92 项 0 失败（该阶段值；四轮审查后的终值为 105 项，见 §9.3） | `python scripts/skill_selfcheck.py` |

新增 4 个工具 + 1 个公共模块（`batch_trace` / `batch_preflight` / `batch_build` / `publish_batch` / `lecture_checks`），
新增 5 个行为自测（`test_batch_trace` / `test_batch_preflight` / `test_batch_slots` / `test_gate_result` / `test_publish_batch`），
`skill_selfcheck` 78 → **92 项**、单测 14 → **82 项**（§3.1–§3.5 阶段值）；四轮审查修复后 105 项 / 112 项（§9.3）；第五轮（§11）后 **112 项 / 137 项**。

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
| `3de53c0` | fix(review3): 结论字段必须存在且值明确合格 |
| 见 §9.3 | fix(review4): verdict 只认确切写法；最终记录类型与取值严格核对 |

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
python scripts/skill_selfcheck.py          # 期望：检查项 105，失败 0 → PASS
python scripts/v2_selfcheck.py             # 期望：PASS (6 contract entries)
python -m unittest discover -s scripts -p "test_*.py" -t scripts   # 期望：112 项 OK

# 预检：首轮计划必须报出 3 个 ★ 签名缺口 + 5 处密度连段；修复后计划必须 0 缺口
python scripts/batch_preflight.py --src tests/fixtures/batch48/project \
    --plan tests/fixtures/batch48/b48_inject_plan_r1.json --manifest tests/fixtures/batch48/b48_manifest.json
python scripts/batch_preflight.py --src tests/fixtures/batch48/project \
    --plan tests/fixtures/batch48/b48_inject_plan_fixed.json --manifest tests/fixtures/batch48/b48_manifest.json

# 槽位与可重复构建（骨架 → 分片 → 注入 → 重复构建；骨架与终稿必须两个不同文件）
python scripts/new_batch.py --stage 3 --batch 48 --title "智能切片策略" --classes "TableChunker★" \
    --sha 16984b9 --out /tmp/批次48.md --skeleton /tmp/skeleton.md --src tests/fixtures/batch48/project \
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
    --out <批次.md> --skeleton <骨架.md> --src <项目根> --plan <注释计划.json> \
    --batch-json <batch.json> --manifest <清单.json>
python scripts/batch_preflight.py --src <项目根> --plan <注释计划.json> \
    --manifest <清单.json>            # 清单须覆盖本批全部源文件；多份清单就多次 --manifest
#   …写 parts/*.md …
python scripts/batch_build.py --batch <batch.json>
python scripts/gate_lecture.py <批次.md> --src <项目根> --manifest <清单.json> --json <结果.json>
python scripts/sync_gate_result.py <批次.md> --src <项目根> --result-json <结果.json> \
    --manifest <清单.json> --apply     # 与闸门用**同一份** --manifest
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

### 9.3 第四轮审查（判定只认确切写法 + 类型严格）

| # | 审查意见 | 复现 | 修复 | 回归测试 |
|---|---|---|---|---|
| 8 | **`verdict` 靠子串匹配**（`lecture_checks.py`） | `BYPASS`（含 `PASS`、无 `FAIL`）被判为通过 | 新增 `verdict_is_pass()`：只认 `PASS` / `PASS ✅` / `总判定: PASS` / `总判定: PASS ✅`（去 ✅、去前缀、去句末标点后**必须整串等于 `PASS`**）；`BYPASS` / `PASSED` / `NOT PASS` / `PASSFAIL` / 空值 / 非字符串一律拒绝 | `VerdictStrictnessTests`：8 种合法写法接受、13 种近似/失败写法拒绝、`BYPASS` 结果无法盖章 |
| 9 | **类型与取值未严格校验**（`publish_batch.py`） | `exit_code=true`、`pass=1`、`rolled_back=0`、`contract_version=2.3` 等类型冒充被接受 | 六个字段按类型分别核对：布尔字段要求 `isinstance(v, bool) and v is True/False`；`exit_code` 要求 `isinstance(v, int) and not isinstance(v, bool) and v == 0`；`contract_version` / `final_lecture_sha256` 要求是字符串且**逐字相等**（不做 `str()` 归一） | `test_gate_final_type_confusion_is_refused`（20 组类型/取值冒充逐一审）、`test_gate_final_with_exact_types_is_accepted`；`skill_selfcheck` ㉓ 加 1 条、㉔ 加 5 条 |

定向复现（本次修复后，CLI/库函数实跑）：

```text
verdict='PASS' → PASS ｜ '总判定: PASS ✅' → PASS
verdict='BYPASS' → 拒绝 ｜ '总判定: BYPASS ✅' → 拒绝 ｜ 'PASSED' → 拒绝 ｜ '总判定: FAIL ❌' → 拒绝
最终记录：健康（真布尔 / 真整数 0）rc=0
  exit_code=True/False/'0'/0.0/1 → 全部 rc=1
  pass=1 / 'true' → rc=1 ｜ stamp_did_not_break_anything=1 → rc=1
  rolled_back=0 / 'false' → rc=1 ｜ contract_version=2.3 → rc=1 ｜ final_lecture_sha256=12345 → rc=1
```

验证（第四轮修复后复跑）：`skill_selfcheck` **105 项 0 失败**、单测 **112 项 OK**、`v2_selfcheck` PASS、
端到端脚本化试运行 17 步期望全中；`gate_lecture.py` 自 `c03baca` 起未改动（判据回归 11/11 继续成立）。

## 10. 审查通过后的同步（2026-09-20）

审查通过后按 §6.6 DoD 把技能同步到各安装副本；同步的是**同一份字节**：源仓 `skills/replicate-learning/`
（99 个文件，排除 `__pycache__`）逐个文件 SHA256 比对，四处副本全部 **列表差异 0 / 内容差异 0**。

| 位置 | 路径 | 状态 |
|---|---|---|
| 源仓库 | `D:\develop\workspace\replicate-learningV2` → `origin/master` | 已推送 `afcf8f7..eb2d28d`（+ 本文件的文档提交） |
| WorkBuddy | `C:\Users\13610\.workbuddy\skills\replicate-learning` | 已覆盖 |
| Codex | `D:\codexData\skills\replicate-learning`（`~/.codex/skills` 的落地目录） | 已覆盖 |
| dsh-toolkit（工具快照库，私有 git） | `D:\Agent_Learnings\lg-ocr\文档\ocr\dsh-toolkit\skills\replicate-learning` | 提交 `ea26fcb` + `0b43f7d`，已推送 `origin/main` |
| DSH 用户技能库 | `C:\Users\13610\.agents\skills\replicate-learning` | **新增**（该目录此前没有本技能；装后 DSH 会话的技能目录立即出现 `replicate-learning`，即该路径确实是 DSH 的用户级技能根） |

**安装位实跑校验**（四处逐个跑，均在各自目录下执行）：

```text
python scripts/skill_selfcheck.py   # 检查项 105，失败 0 → PASS ✅
python scripts/v2_selfcheck.py      # V2 self-check: PASS (6 contract entries)
```

**同轮修掉的文档失真**（本轮四轮修复把自检从 92 项加到 105 项、单测加到 112 项，两处文档没跟上）：

- `skills/replicate-learning/docs/安装与执行边界.md`：92 项 / 单测 82 项 → **105 项 / 112 项**，并加一句"项数随版本增长，以脚本实际输出为准"（防下一次同类漂移）；
- 根 `README.md`：徽章 92 → **105**、§二 "78 项技能自检" → **105 项**、§八/§九 "92 项" → **105 项**、单元测试 "81 项" → **112 项**、目录 "（16 个脚本）" → **（21 个脚本）**（实际 `scripts/` = 21 个工具 + 10 个 `test_*.py`）；
- 本文件 §1 的两处阶段值（92 项 / 82 项）保留为历史，加注"终值见 §9.3"；同时修正 "新增 4 个行为自测" → **5 个**（列出的确实是 5 个）。

> 判据 / 工具行为 / SSOT 均未改动，`GATE_VERSION` 仍为 v2.30；上述仅为文档数字与实跑对齐。
> 未同步的地方也如实说明：`~/.claude/skills/replicate-learning` 不存在（Claude Code 的用户级技能目录只有
> `find-skills` / `learned` / `new-project-bootstrap` / `skill-creator` / `ui-ux-pro-max` 五项），本次未新建；
> `~/.dsh/memories/pending-skills/` 下的技能建议是待确认队列、不是安装副本，未改动；
> `~/.agents/.skill-lock.json` 只登记"从 GitHub 源安装"的技能（`find-skills` 等），本技能是本地作者技能，无需登记（装后 DSH 已能直接识别）；
> 宿主项目 `D:\ragent-official` 内没有技能脚本副本，因此"宿主项目内脚本副本"这一处本次为空。

## 11. 第五轮：批次49 实录的四处工具链缺陷（2026-09-20）

用户导出批次49 全程会话（`test2.md`，72 分钟）后按时间戳分段，指出**主要额外耗时不在模型写正文**：
准备 14 分钟 / 写 4 个分片 10 分钟 / 组装与首轮修稿 12 分钟 / **盖章与工具排障约 22 分钟** / 项目测试与归档约 12 分钟。
其中四处是可复现的工具缺陷，本轮逐条修掉。

### 11.1 版本门：同一份正文，首跑报告档、盖章后 FAIL 档

**症状**：⑯ 已写 `判据版本：v2.30`，首跑闸门 ⓪e/⓪f 落"报告档"（缺口只报不判红，退出码 0）；
盖章后同一份正文的同一批缺口升 FAIL 档 —— 看起来"盖章把正文改坏了"，实际一个字没改。

**根因**：版本门有两套口径。⑯ 的规范字段是 `**判据版本：v2.30**`，而 `style_scope()` 自带的正则只认
「判据 vX.Y」；`sync_gate_result` 写进 ⑯ 的表头恰好是 `**七组闸门实测**（判据 v2.30…）`，于是**盖章后才被认出来**。
（H27 同族：判据只在它能识别的形态上生效 ⇒ 换个写法就能绕过它。）

**修法**：版本只有一个来源 —— `gate_lecture.find_versions()`（规范字段优先、`vX.Y` 兜底），
`core_scope` / `form_scope` / `snip_scope` / `style_scope` 四门全部走它。判据文本未变，`GATE_VERSION` 不动。

**A/B 实测**（真实批次48 素材 + 一条人造结构缺口：⑦.4「不变式」被改词）：

| 文件 | 旧闸门 | 新闸门 |
|---|---|---|
| 未盖章（只有规范版本字段），无缺口 | rc=0 PASS（报告档） | rc=0 PASS（**FAIL 档**，识别生效且不误伤） |
| 未盖章 + 缺口 | rc=0 **PASS（缺口被报告档吞掉 ← 缺陷）** | rc=1 **FAIL ❌（1 条 `[FAIL]`）← 首跑即报全量错误** |
| 盖章后 + 同一缺口 | rc=1 FAIL ❌ | rc=1 FAIL ❌（与首跑一致） |

**回归**（"不该变的判定一字不变"）：ragent 批次1/33/40/43/47/48/49 + 4 份仓内样例，改造前后
**退出码与 `[FAIL]` 行数全部一致**；另外对 48 份 ragent 批次逐份比对新旧版本档位，**翻转 0 份**
（存量批次都已盖章、表头能被旧正则认出，所以只有"新批首跑"这一路径受影响——正是要修的那条）。

### 11.2 预检 P-HASH：清单只覆盖 1/8 也算通过

批次49 把 4 个源文件**分别** `batch_manifest.py prepare` 成 4 份清单，只把其中一份传给预检：
`P-HASH` 核对那 1 个文件哈希正确 → PASS，而本批另外 3 个源文件**根本没被钉住**。

修法：① `--manifest` 可重复传，多份清单合并后判覆盖率；② **清单必须覆盖注释计划里的全部源文件**，
缺件直接 FAIL 并逐个点名（`覆盖计划源文件 1/8`）。测试 `test_batch_preflight.ManifestCoverageTests`
（4 项：8/8 通过、1/8 拒绝并点名、8 份单文件清单合并通过、hash 漂移仍拒绝）。

### 11.3 批次配置：annotations 指回原始计划，槽位要靠手补

`new_batch.py` 已派生带槽位的 `annotations.json`，但批次配置被指回原始注入计划，
随后手补槽位与行段；且 `--manifest` 只收最后一个值（多份清单只记下一份）。

修法：`new_batch` ① `--manifest` 可重复，`batch.json` 记 `manifests` 全量；② `--batch-json` 必须配 `--plan`，
否则拒绝（没有计划就派生不出可编辑的注释计划）；③ 写完自断言 `annotations.json` 存在且含槽位；
④ 明确打印"**可编辑的注释计划只有这一份**，`plan_source` 只是输入"；
⑤ `batch_build` 拒绝 `annotations == plan_source`，以及"骨架有槽位、计划 0 槽位"的错配。

### 11.4 batch_build：同一路径的"重建"、缺分片的旧内容、盖章后的假差异

批次49 的 `skeleton` 与 `out` 是同一路径，于是：
省略 ⑥ 分片时**旧 ⑥ 内容原样留在"重建"结果里**（旧正文冒充派生产物）；
终稿盖章后跑 `--check` 又报约 48 行差异并提示"先跑一次构建"。

修法（四条 fail-closed + 一条比对口径）：

| 护栏 | 拦住的形态 |
|---|---|
| `skeleton` ≠ `out` | 就地重建（旧正文冒充派生产物） |
| `annotations` 必须存在且 ≠ `plan_source` | 槽位寻址静默退化成旧 `anchor/contains` |
| 分片目录不能为空（`--allow-no-parts` 才放行） | 指错目录时"重建"只是把骨架抄一遍 |
| 没有任何一节仍是模板占位原文 | 缺分片（那一节没有任何输入覆盖它） |
| `--check` 排除 ⑯ 的机器盖章块与判据版本行 | 盖章后的 48 行假差异 |

另：`new_batch.py --out` 语义改为**终稿路径**，骨架写到 `--skeleton`（缺省 `<out 同目录>/skeleton.md`），
两者相同即拒绝 —— 工具本身不再生成"就地重建"的配置（批次49 是在 e2e 里手工改 `out` 绕过的，现已不需要）。
测试 `test_batch_slots.BuildGuardTests`（11 项）。

### 11.5 另外两处"两套口径"（同轮修掉）

- **清单哈希缺陷**：`gate_lecture --json` 的 `source_manifest_sha256` 取的是**位置契约清单**
  （`<讲稿名>.blocks.json`），而 `sync_gate_result --manifest` 核对的是**批次源码清单**——名字像、内容不同，
  于是盖章永远 ABORT。修法：闸门新增 `--manifest <本批源码清单>`（并在文本输出里打印用的是哪一份、
  结果里记 `manifest_source`），`sync_gate_result` 在清单哈希不符时**直接把两者的取值与来源打出来**。
- **零对象检查崩溃**（该修复在批次49 现场改在工作区、未提交）：`manifest` 在但正文没有可核对对象时，
  `PASS(checked=0)` 被 `make_check` 拒绝 → `--json` 路径抛 ValueError。现降级为 `NOT_CHECKED` 并附说明。

### 11.6 本轮的验证与仍然没解决的事

```text
python scripts/skill_selfcheck.py        # 检查项 112，失败 0 → PASS ✅（+7 项：清单覆盖 / 版本门同源 /
                                         #   两条"假重建"护栏 / SYNC_API 依赖符号存在性）
python scripts/v2_selfcheck.py           # PASS (6 contract entries)
python -m unittest discover -s scripts -p "test_*.py" -t scripts   # Ran 137 tests OK（+25 项）
python tests/e2e_scripted_run.py         # 26 步期望全中（+9 步：4 条负向 + 档位一致 + 盖章后 --check）
```

**没有解决的问题，如实写在下面**（不要把这轮修复读成"整批提速"）：

1. **模型写作耗时仍未采集**：`batch_trace` 里 `investigate` / `write` 两个阶段标着"未测量"。
   批次49 的 10 分钟写作是**按工具时间戳估算**的观察窗口，不是秒表实测。下一批开批时请用
   `batch_trace.py` 分段打点（或手工记 `investigate`/`write` 起止），否则"提速"永远只能说脚本侧。
2. **内容量本身没动**：17 节约 1900 行、④ 个分片的写作与手工归档仍要花时间；这轮只减少了"工具造成的返工"。
   若目标是大幅缩短整批时间，下一步必须对**讲解篇幅与重复内容**做真实批次对照 + 读者盲评（§3.6 的路线），
   不能仅凭脚本验收通过就宣称提速。
3. **`make_check` 的 0 对象 PASS 仍是硬断言**：本轮只修了 G-PY 一处调用点并加了测试；
   其余动态对象数的检查点若写出 `PASS(checked=0)` 仍会抛错（这是有意的编程错误护栏）。
4. **`publish_batch.py` 本轮没被用上**：批次49 仍写了约 16 KB 的一次性归档脚本。工具已就绪，
   下一批请直接用它（`--record` 一份记录更新覆盖矩阵/总索引/阶段页/状态，冲突零写入）。

## 12. 第五轮同步（2026-09-20）

按 §6.6 DoD 把第五轮的修改同步到全部安装副本；同步的是同一份字节：源仓 `skills/replicate-learning/`
（**100 个文件**，排除 `__pycache__`）逐文件 SHA256 比对，四处副本全部 **列表差异 0 / 内容差异 0**。

| 位置 | 路径 | 状态 |
|---|---|---|
| 源仓库 | `D:\develop\workspace\replicate-learningV2` → `origin/master` | 提交 `756dccc`，已推送 `a086afd..756dccc` |
| WorkBuddy | `C:\Users\13610\.workbuddy\skills\replicate-learning` | 已覆盖 |
| Codex | `D:\codexData\skills\replicate-learning` | 已覆盖 |
| DSH 用户技能库 | `C:\Users\13610\.agents\skills\replicate-learning` | 已覆盖 |
| dsh-toolkit（工具快照库） | `…\lg-ocr\文档\ocr\dsh-toolkit\skills\replicate-learning` | 提交 `8601d62`，已推送 `origin/main` |

安装位实跑（四处逐个跑，各自目录下）：`skill_selfcheck` **检查项 112，失败 0 → PASS ✅**；
`v2_selfcheck` **PASS (6 contract entries)**。

> 上一轮（§10）里的 `a086afd` 是你自己提交的闸门清单路径修复（`_manifest_path_for`）——本轮在其之上继续，
> 未回退它。另：`.gitignore` 补了 `test2.md`（与 `test.md` 同类会话素材），未改动任何已跟踪文件的内容。

**§13 之后的再同步（同一轮复查）**：源仓提交 `fd1d3a8`（已推送 `572fb35..fd1d3a8`），
dsh-toolkit 快照提交 `c701e47`（已推送 `origin/main`）；WorkBuddy / Codex / `~/.agents/skills` 三处覆盖，
四处仍是 **100 个文件逐文件 SHA256 零差异**，安装位实跑 `skill_selfcheck` **113 项 0 失败 → PASS ✅**、
`v2_selfcheck` PASS。

## 13. 版本门第二次收紧：声明不被后续说明覆盖（2026-09-20 复查）

### 13.1 复查发现的口子

§11.1 只解决了"认不认得出规范字段"，**没解决"谁在后面谁说了算"**：
`find_versions()` 返回 ⑯ 里的**全部**版本号，`ver_marker()` 取**最后一个**。于是

```markdown
**判据版本：v2.30**（本批按此版判据验收；判据变更见 references/第一册质量细则.md §6.6 变更登记）。
（历史判据 v2.17 仅供对照；本节数字仍按上面声明的那一版核对。）      ← 补这一句
```

实测（真实批次48 素材 + 一处 ⑦ 结构缺口「不变式」被改词 + `--manifest` 同一份）：

| 文件 | 修复前（`756dccc`） | 修复后（本轮） |
|---|---|---|
| `gap_only`：只有缺口 | rc=1 FAIL 档，1 条 `[FAIL]` | rc=1 FAIL 档，1 条 `[FAIL]`（不变） |
| `gap_history`：同一缺口 **+ 声明后补一句历史版本** | **rc=0 PASS、报告档、0 条 `[FAIL]` ← 口子** | **rc=1 FAIL 档、1 条 `[FAIL]` ← 堵住** |

退出码能靠一句说明文字翻转，说明版本门的"声明"还不够权威 —— 与 H27 同族：先是"换个字段写法"，
再是"在后面多说一句"，两次都绕过了同一道门。

### 13.2 修法：三级优先级，每级只取第一个匹配

| 优先级 | 形态 | 正则 | 例子 |
|---|---|---|---|
| ① 规范字段（行首声明） | `判据版本` + 可选 `：` + `vX.Y` | `^[^\w\n]*判据版本\s*[:：]?\s*v?(\d+\.\d+)` | `**判据版本：v2.30**（…）`、`> 判据版本：v2.21`、`判据版本 2.30` |
| ② 盖章表头 / 旧写法（**仅当 ① 不存在**） | `判据 vX.Y` | `判据\s*v?(\d+\.\d+)` | `**七组闸门实测**（判据 v2.30…）` |
| ③ 最宽兜底（**仅当 ①② 都不存在**） | 任意 `vX.Y` | `\bv(\d+\.\d+)\b` | `本批按 v2.27 判` |

`core_scope` / `form_scope` / `snip_scope` / `style_scope` 四门仍共用这一个来源；判据文本未改，`GATE_VERSION` 仍 v2.30。

### 13.3 副作用（必须说清楚）：批次3 由 PASS 变 FAIL

新口径下只有一份存量样本的判定发生变化，而它是**内容基准批**：

```text
ragent 批次3（统一响应与异常族）：
  ⓪ 里规范声明写的是  **判据版本：v2.29**（…本节数字均按这一版判据核对）
  ⓪ 里机器表头写的是  **七组闸门实测（判据 v2.21…）**      ← 两者本来就不一致
  按"声明优先" → ⓪d/⓪e/⓪f 由报告档转 FAIL 档
  → 实测浮出一条真实缺口：[FAIL] ⑥ 2/2 个★件缺「逐步回放」（6.1、6.2）
  → 该批 rc 由 0 变 1
```

这不是新增要求，而是**它自己声明的版本终于被当真**（⓪d 的「逐步回放」是 2.25 起的条款）。两条处置，请你定：

1. **补内容**（推荐）：给批次3 的 6.1/6.2 补 ★件「逐步回放」（真实输入 → 每行发生什么 → 真实输出，含一条失败路径）；
2. **改声明**：把该批 ⑯ 的声明改成它**实际**按哪一版核过（若确实是 2.21，就写 2.21 并如实标注"机器表按 2.21 生成"）——
   改声明等于承认当时的机器表口径，这条要有据可依，不能为了让 rc 变 0 而改。

其余 12 份样本（批次1/33/40/43/47/48/49 + 5 份仓内样例）退出码/总判定/`[FAIL]` 行数**逐字不变**；
另对 48 份 ragent 批次逐份比对新旧版本档位，只有批次3 一份变档（原因同上）。

### 13.4 本轮验证

```text
python -m unittest discover -s scripts -p "test_*.py" -t scripts   # Ran 143 tests OK（+6：
    DeclarationWinsTests：历史版本不降档 / 四门同源 / 同形态旧声明不生效 / 声明压过表头 /
    无声明时才用表头 / 旧"取最后一个"口径的反向断言）
python scripts/skill_selfcheck.py        # 检查项 113，失败 0 → PASS ✅（+1：历史版本不降档）
python tests/e2e_scripted_run.py         # 29 步期望全中（+3：CLI 负向"带缺口 → FAIL 档"、
                                         #   "加历史版本仍 FAIL 档"、以及两者档位一致的断言）
```

**仍然不变的那句话**：脚本验证通过不等于真实模型写作已缩短到目标时长。下一批请务必用
`batch_trace.py` 采集 `investigate` / `write` 两段（或手工按秒表），否则"提速"只能停在脚本侧。
