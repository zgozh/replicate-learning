# replicate-learning V2

`replicate-learning V2` 是一个面向 Codex/Agent 的项目深度学习与 AI 原生工程训练 Skill。

它的目标不是只生成一份源码说明，而是把一个真实代码库转化为一套可以持续阅读、验证、复盘和迁移的工程学习资产：

```text
陌生项目
  -> 项目考古
  -> 业务与架构建模
  -> 全文件源码教材
  -> Prediction / Evidence / Experiment
  -> Architecture Challenge
  -> Issue / Diff Review / Test / Debug
  -> 用户验收
  -> 能力账本与工程日志
```

## 项目定位

这个仓库负责维护 `replicate-learning` Skill 的 V2 方案、执行协议、模板、工具和验收规则。

Skill 适用于以下任务：

- 学习一个本地或开源项目；
- 深度拆解项目的业务、架构、源码和运行机制；
- 覆盖项目中的源码、测试、配置、脚本、SQL、部署和前端文件；
- 对关键机制进行预测、证据调查和实验验证；
- 设计替代实现、重构方案或跨领域迁移方案；
- 从真实项目中提取 Feature、Bug Fix、Refactor、Migration 等工程任务；
- 训练用户给 AI 提供上下文、审查 diff、运行测试和完成验收。

它不承诺模型对任意项目一次性生成正确结果。它通过证据等级、状态落盘、质量契约、工具自检和人工验收，降低遗漏、幻觉和伪完成风险。

## 核心产物

### 三本正式教材

#### 第一册：项目源码与工程实现

回答：

> 这个项目是什么、解决什么业务问题、每个文件和关键代码如何工作？

内容包括：

- 系统全景和业务闭环；
- 模块、进程、数据和依赖关系；
- 全文件覆盖矩阵；
- 关键类、方法、配置和脚本讲解；
- 调用链、数据流、状态变化和失败边界；
- 框架行为与底层等价实现。

#### 第二册：实验与机制验证

回答：

> 为什么它这样工作？改变或删除它之后会发生什么？

内容包括：

- Prediction Card；
- Evidence Card；
- Experiment Card；
- 日志、堆栈和数据变化；
- 预测正确、错误或部分正确的复盘；
- 未运行内容、失败原因和剩余风险。

#### 第三册：架构挑战与独立重构

回答：

> 如果不照抄原项目，我会怎样设计、替换和迁移这个系统？

内容包括：

- Architecture Challenge；
- 等价实现；
- Replacement；
- Modification；
- Reconstruction；
- Trade-off；
- 新领域 Transfer。

### 独立工程日志

工程日志不写入被学习项目的知识教材目录，而是独立保存：

```text
.replicate-learning-log/<项目名>/
  Issue/
  Context/
  Review/
  Debug/
  Delivery/
```

日志记录：

- Issue 原文和用户初始判断；
- AI 的调查结果；
- 上下文包；
- 代码 diff；
- 用户的审查意见；
- 测试与调试过程；
- 最终 Accept/Reject 状态；
- AI 失误样本；
- 能力账本证据。

## Skill 目录

```text
skills/replicate-learning/
├── SKILL.md                         # Skill 入口和执行路由
├── docs/
│   ├── V2试运行手册.md
│   ├── 安装与执行边界.md
│   └── 复刻式学习方法-通用.md
├── examples/                        # 正例和工程任务样例
├── references/                      # 执行协议、模板和方法参考
├── scripts/                         # 自检、脚手架、源码注入和质量工具
└── spec/                            # 质量契约和验收规范
```

入口文件是：

```text
skills/replicate-learning/SKILL.md
```

模型触发 Skill 后，先根据用户意图读取 `references/V2执行协议.md`，再按任务类型读取对应模板和工具说明。不会要求模型每次把所有文档一次性装入上下文。

## V2 执行流程

### 1. 启动项目考古

首先确定：

- 被学习项目根目录；
- 项目知识目录；
- 独立工程日志目录；
- README、AGENTS.md、构建文件和测试入口；
- 已有状态文件、总索引和覆盖矩阵。

首次运行至少建立：

```text
NOTES/00-系统全景地图.md
NOTES/项目文件覆盖矩阵.md
NOTES/概念词典.md
NOTES/阶段对照-完整性地图.md
NOTES/教学讲解/00-总索引.md
```

### 2. 按批次生成第一册

每个批次围绕一个业务或技术闭环组织，而不是简单按目录顺序堆文件。

每批需要：

- 记录文件范围；
- 标注源码证据；
- 解释调用链和数据流；
- 记录已验证、未验证和推断内容；
- 更新覆盖矩阵和状态。

### 3. 生成第二册实验记录

对关键机制按以下顺序执行：

```text
Prediction
  -> Evidence
  -> Experiment
  -> Correction
```

不能把模型推断直接写成事实。无法运行时必须记录阻塞命令、错误原文、排查范围和剩余风险。

### 4. 生成第三册架构挑战

用户或模型针对同一机制提出：

- 不依赖原框架的设计；
- 替换组件的设计；
- 删除某模块后的退化行为；
- 不同业务领域中的迁移方案；
- 原实现和新设计之间的取舍。

### 5. 执行工程 Issue 闭环

工程任务遵循八步协议：

```text
Understand
  -> Investigate
  -> Predict
  -> Plan
  -> Delegate
  -> Review
  -> Test
  -> Accept
```

用户不需要手写所有核心生产代码，但必须参与关键预测、架构判断、diff 审查和最终验收。

最终状态只能由用户确认：

- `Accept`
- `Accept with known risk`
- `Reject and revise`
- `Blocked with evidence`

AI 不得自行宣布任务已完成。

## 安装方式

这是一个标准 Agent Skill 目录。使用时，将以下目录复制到所使用 Agent 的 Skill 目录：

```text
skills/replicate-learning/
```

常见目录示例：

```text
~/.agents/skills/replicate-learning
~/.claude/skills/replicate-learning
~/.workbuddy/skills/replicate-learning
```

具体路径取决于使用的 Agent 平台。Skill 至少需要保留 `SKILL.md`，建议整个目录一起安装，以便模型读取 references、templates、scripts、examples 和 spec。

安装后可以使用自然语言触发，例如：

```text
学习这个项目：D:\develop\workspace\my-project
继续学习
讲解第 3 批
验证这个核心机制
为这个项目生成一个 Issue 并执行完整工程流程
验收当前学习结果
```

## 本地验证

进入 Skill 目录执行：

```powershell
cd skills/replicate-learning
python scripts/skill_selfcheck.py
python scripts/v2_selfcheck.py
```

当前预期结果：

```text
检查项 47，失败 0 -> PASS
V2 self-check: PASS
```

### 主要工具

```text
scripts/skill_selfcheck.py   Skill 文档、模板、工具和质量契约对账
scripts/v2_selfcheck.py      V2 入口和产物契约检查
scripts/new_batch.py         生成标准批次骨架
scripts/inject_source.py     从真实源码注入代码和行号
scripts/safe_edit.py         保护 Markdown 代码围栏的安全编辑
scripts/gate_lecture.py      检查批次教材质量
scripts/gate_all.py          批量运行教材闸门并比较基线
scripts/callsite.py          提取符号调用点
scripts/fix_lineno.py        修正源码行号标记
scripts/annotate_gaps.py     定位教材注释缺口
scripts/sync_gate_result.py  将闸门结果同步到教材
```

## 证据等级

教材和工程日志必须区分以下证据：

| 等级 | 含义 |
|---|---|
| `事实-源码` | 可以回链到真实文件、类、方法或行号 |
| `事实-实测` | 由命令、测试、日志、堆栈或实验得到 |
| `事实-历史` | 由 Git 提交、差异或 blame 得到 |
| `外部事实` | 来自官方文档、依赖源码或协议规范 |
| `推断` | 根据现象和代码推导，尚未直接验证 |

尤其是性能、并发、安全、故障和生产行为，不允许用模型记忆代替证据。

## 当前边界

当前版本已经完成：

- V2 Skill 入口和意图路由；
- 三本书和独立工程日志协议；
- Prediction/Evidence/Experiment 模板；
- Architecture Challenge 和 Issue 八步模板；
- 质量契约和自动化自检；
- 参考版源码保真、批次教材和安全编辑工具继承；
- Windows 子进程编码兼容修复。

当前尚未承诺：

- 自动评分用户所有回答；
- 自动生成复杂 Benchmark；
- 自动故障注入所有项目；
- 多 Agent 自动协作；
- 对任意业务项目一次性完成全部教材；
- AI 不经过人工审查就能保证代码正确。

首轮真实试运行应至少完成：

```text
四份基础地图
  + 第一册一个源码批次
  + 一组 Prediction / Evidence / Experiment
  + 一个 Architecture Challenge
  + 一个 Issue 八步闭环
  + 一次用户 Diff Review 和最终 Accept
```

## 相关文档

- [总方案](总方案.md)
- [实施计划](docs/实施计划.md)
- [安装与执行边界](skills/replicate-learning/docs/安装与执行边界.md)
- [V2 试运行手册](skills/replicate-learning/docs/V2试运行手册.md)
- [Skill 入口](skills/replicate-learning/SKILL.md)
- [V2 执行协议](skills/replicate-learning/references/V2执行协议.md)

## 开发约定

修改 Skill 时建议遵循：

1. 先修改规范或质量契约；
2. 同步更新 `SKILL.md`、references、templates 和 scripts；
3. 为新增行为补充正例和反例；
4. 执行两个自检脚本；
5. 再进行真实项目试运行；
6. 记录已知缺口，不把“已扫描”写成“已讲解”，不把“已讲解”写成“已验证”。

## 项目状态

当前状态：V2 Skill 首版骨架已完成，质量自检通过，进入参考案例与真实业务项目试运行阶段。

