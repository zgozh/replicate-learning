# Replicate-Learning（复刻式学习方法）

> **参考而非照抄**——骨架/配置从答案卷抄（工程惯例），机制/算法自己手写（那才是学到的东西）。
> 这是一个**方法论技能**：指导"照着一个成熟项目一步步学 + 复刻成自己的代码"的过程，把每条机制讲透、按档位控制讲解成本、逐项验收。

非强制规范，适配而非照抄。它是"参考弹药库 / 决策菜单"，不是"规范 / 枷锁"——每个项目用不用、用到哪一步，由你基于当时需求与约束定。

---

## How it works

开始学习/复刻一个成熟项目时，先定**《讲解分级表》**，把每一类**事先分级**（★机制满深度 / 中等半深 / 样板精简），然后按「抄样板、写机制」分治推进：每类按**六段**讲透（业务场景 → 架构概念先补 → 实现四问 → 代码逐行 → 调用链 → 用法），每批 ≤3 类、宁多轮不量产，讲完给验收问题（一问一答带答案），每批立即构建验证，最终归档 `NOTES/阶段N` + 勾完整性地图 + 更新进度表 + commit。

它只做五件事：①抄样板/写机制分治与排雷阅读法；②完整性地图与 ★必亲手写红线；③大型项目地图先行拆解（v1 冻结）；④选择性复刻（跨栈 mini）；⑤六段讲解+分级+教学讲解纪要。

## When to use

当用户正在「照着**一个成熟开源项目**逐阶段学 + 复刻成自己的代码」，需要对**每一类**做：先讲懂、再实现、diff、构建验证、归档勾地图。典型触发词：

- 「读 AGENTS.md 和教材第 N 章，继续阶段 N」
- 「进入 ★<类名>」「<类名> 我写完了」
- 「这一批讲完再写」「下一个机制我自己写」

## When NOT to use

| 场景 | 该去哪？ |
|---|---|
| 从零做一个新产品（非学习场景） | `new-project-bootstrap` |
| 纯分析一个参照项目的架构、提炼模式（不动手复刻） | `architecture-patterns` |
| 用户明说「只要出活 / 量产 / 别讲 / 直接写」 | `ai-native-dev-workflow`（派活） |
| 写 AGENTS.md / 验收清单 / commit 规范 / 跨会话续接 | `ai-native-dev-workflow` |
| 完成声明前的验证纪律（证据先于断言） | `verification-before-completion` |
| TDD / 执行计划 / 子代理开发 / 代码评审 / git worktree | 对应 superpowers 技能 |

**判断标准：如果目标不是「学懂并复刻一个成熟项目」，就不要让本技能介入。** 六段 / 分级表只服务于「逐类讲透 + 复刻」，套到普通开发任务会变成枷锁。

## What's inside

```
skills/replicate-learning/
├── SKILL.md                              入口：触发条件 / 分级规则 / 边界契约 / 反模式；thin，指到下面几个文件
├── docs/
│   └── 复刻式学习方法-通用.md             全量方法论（含文首目录；每类讲解标准、多套可复用模板的出处）
├── examples/
│   └── 黄金样例.md                       六段达标基准（★机制满深度示范 + 详细度判定表 + 产出自查）
└── references/                           渐进式披露：可复用空白模板
    ├── 讲解分级表模板.md
    ├── 业务闭环定位图模板.md
    ├── AGENTS.md-复刻增量模板.md
    ├── 教学讲解纪要模板.md
    └── 面试题卡模板.md
```

## Installation

这是一套**方法论技能**，可像任何 Agent Skill 一样放进你运行时的技能目录：

```
git clone <this-repo> ~/.agents/skills/replicate-learning-book
# 或把 skills/replicate-learning/ 整个目录拷进：
#   ~/.agents/skills/replicate-learning        (Claude Code / Codex / Gemini CLI 均识别 ~/.agents/skills/)
#   ~/.claude/skills/replicate-learning
```

装好后，对一个学习/复刻项目说「读 AGENTS.md 和教材第 N 章，继续阶段 N」即可触发。Skill 标准前端字段仅 `name` + `description`，符合 [Agent Skills 规范](https://agentskills.io/specification)。

## Boundaries & delegation

- **本技能只做五件事**（见上）；不重述其他技能职责（one home per fact）。
- 教学讲解允许写溯源；**交付代码的注释禁止来源字眼**——两类文本分开，别混。
- **强调单一定位**：若在非复刻场景调用，应**拒绝**而不是把六段/分级表强套上去（见 `When NOT to use`）。

## Philosophy

- **参考而非照抄**——答案卷是"参考"，不是"教材"；机制要读懂原理、能自己讲清、能独立实现，才算学会。
- **诚实边界**——注释/代码只写「做什么/为什么」，对外表述「个人结合 AI 辅助 + 自研增量」。
- **讲解成本可控**——档位事先定死、每批 ≤3 类；不量产、不压大纲句。
- **证据先于断言**——每批完成即构建验证并如实汇报；未跑不得宣称完成（对齐 `verification-before-completion`）。

## Contributing

对这个技能提改进，建议遵循 `writing-skills` 的技能版 TDD：先写一个"无技能时的翻车场景"（RED），再改技能文档（GREEN），最后收口反模式（REFACTOR）。提交前请跑 `docs/验证报告.md` 里的检验项。

## License

MIT License（见 `LICENSE`）。允许自由使用、修改、再分发；保留版权声明即可。许可更严苛（如 Apache-2.0 / CC BY-SA）可自行替换。
