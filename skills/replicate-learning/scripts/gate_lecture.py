#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gate_lecture.py —— 批次讲解「内容真实性 + 注释密度 + 行号一致性 + 用法与接入」闸门（SKILL §6.4 C 组）

判据版本：见下方 GATE_VERSION。**任何判据变更（新增/收紧/放宽检查项或门槛）都必须**：
  ① 递增 GATE_VERSION；② 在 SKILL §6.6 记一条变更（版本 / 改了什么 / 影响哪些批次 / 存量工单）；
  ③ 跑回归集确认"不该变的批次判定不变"。道理：判据一改，存量批次会集体变红或变绿（实测两次：
  加快照机制后 9 批 77 行由 FAIL 转为"源码演进"；加 ⑤ 后阶段8批次4 由全绿转红），没有版本号就查不出"这批是按哪版判的"。
改技能文档本身的 DoD（改完必须跑 `scripts/skill_selfcheck.py` 全绿 → 回归集判定不变 → 同步四处副本）见 SKILL §6.6。

用法：
    python gate_lecture.py <批次讲解.md> --src <源码根目录>
        [--snapshot <commit>]   # 不传则自动读批头「源码依据：commit <sha>」
        [--manifest <本批源码清单.json>]   # 显式指定 `batch_manifest.py prepare` 的产物
        [--json out.json] [--verbose]

`--manifest` 与"位置契约清单"是两样东西，别混（批次49 实录：混了会让盖章永远 ABORT）：
  · `--manifest`（本批源码清单）：`batch_manifest.py prepare` 产出的**源文件 sha256 清单**，
    `sync_gate_result.py --manifest` 校验的就是它 → 结构化结果里的 `source_manifest_sha256` 取它；
  · 位置契约清单（`<讲稿名>.blocks.json`，讲稿旁 / `_tools/` / `NOTES/_tools/`）：①p/②p/④p 的归属口径，
    只影响"位置级 vs 归属级"的档位，与 `--manifest` 无关。
不给 `--manifest` 时，`source_manifest_sha256` 退回位置契约清单的哈希（旧行为，兼容存量）。

五项检查（任一不过 = 退出码 1）：
  ① 正向保真度：讲解里每个 java 代码块（凭类名归属源文件）的每一行代码，
      必须能在「当前源码树」或「本批声明的源码快照」里逐字找到。
      - 只在当前树命中 → 正常；
      - 只在快照命中 → **源码演进**（本批之后该文件被重写）：不计 FAIL，单独打印漂移量；
      - 两处都没有 → **候选编造/改写**：计 FAIL（这是本检查真正要抓的东西）。
      - 批头未声明快照时，退回"只比当前树"，并在报告里提示"无法区分演进与编造"。
  ② 反向完整度：★类源文件的每一条有效行，必须出现在讲解里（**全批所有块并集**）。门槛 99.5%。
      —— 抓"摘录式贴码 / 整节缺失"。★ 记录在父标题（如 `### 6.5 Xxx★`）同样生效。
      2.13：★ 块的**类名归属**加了标题链兜底 + 同类去重（血证 H23）——原实现只认"块自身含类声明"，
      而 ⑥ 要求 ★ 类**按职责段拆讲**（段1/段2…），拆分后没有任何单块含类声明 → 本项静默跳过、
      打印"0 个★类"并 PASS（**真空通过**）。实测全库 60 份批次里 6 份命中，其中 4 份一个类都没查过。
  ③ 注释密度：按 §6.1.1「关键行」口径算
      (a) 无注释连段 <8 行  (b) 教学注释条数 ≥ 关键行数÷12  (c) ★类每个方法签名行或相邻行有注释
      —— 抓"只贴 `// :Lnn` 裸行号、没有一句讲解"。
  ④ 行号一致性（2026-09-15 新增）：`// :Lnn` 标了行号、且该行内容能在源文件里**唯一定位**时，
      nn 必须就是那一行。指错行号 = FAIL（比少注释更误导初学者）。
  ⑤ 用法与接入（2026-09-16 新增）：讲清"这份代码怎么被用、怎么被接上"，抓
      "每行都讲了、读者仍不知道怎么用"（§6.4 ⑥ 第 5 层要求）：
      (a) 每个 6.x 逐件小节必须有 **【怎么用】**（调用现场：谁在哪个类哪个方法哪一行调它、传什么形态拿回什么）；
      (b) 每个 6.x 逐件小节必须有 **【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）；
      (c) 件内代码块出现 `interface` / `abstract class` 的，必须有 **【怎么接】**（实现/继承要覆写什么、
          最小可编译实现、注册装配路径、扩展步骤、类型陷阱）；
      (d) 批级必须有 **⑦.5 扩展与接入路径**（含 ≥3 条编号步骤）。
      2.14：**件段不得越过一级节标题**——⑥ 之后的小节（⑧ 穿透卡 / ⑨ No-Framework / ⑩ 反例）
      里的手写 `interface` 骨架与【怎么接】标记不再被算进"最后一个 6.x 件"（血证 H24）。
      标题带【历史版本示例】的小节免检（旧版代码只做快照核验，不要求讲用法）。

免检小节：标题含 手写 / No-Framework / 不用框架 / 等价实现 / 反例 / 对照 的代码块不参与 ①②，
但会被统计并打印（防止借"反例"之名夹带未核实代码）。
用法片段：位于 `**【怎么用】/【怎么接】/【扩展步骤】/【上下游】` 标记之下的代码块属**教学合成片段**
（照抄式调用示例、实现骨架），不参与 ①②③④；**但带行号标注的块不豁免**——标了行号即声明"这是源码原文"，
必须逐字核验。行号标注**两种格式都算**：`// :Lnn`（现行）与 `// :N`（已作废但存量仍在用）。
历史版本块：小节标题含「历史版本 / 历史快照 / 已被阶段」的块，**必须**用快照核验——块内每行都要在
快照里找到（没声明快照 = 直接 FAIL），这样"标历史版本"就不能当免检后门用。
"""
import io
import os
import re
import sys
import json
import math
import tarfile
import subprocess
import collections

GATE_VERSION = "2.30"    # 2.30：⓪d 增补 E12/E13（用户第五轮要求 · ⑥ 的可复制性）：
                         #       E12 ⑥ **每件**的【怎么用】须含「可照抄的最小调用」——"怎么用"若只写
                         #           "某处会调用它"，读者仍然照抄不出一次真实调用。锚 = 件区间内命中
                         #           MINSNIP_RE（可照抄的最小调用｜最小可编译实现｜教学合成片段）。
                         #       E13 凡**有【怎么接】的件**，其中须含「最小可编译实现」——接入说明若只有
                         #           步骤没有可编译片段，读者仍需自己猜 API 形状。
                         #       校准：批次1-5 的调用片段散在【怎么用】文字/代码块里（MINSNIP 命中
                         #       2-6 处/批），ragent 批次1-10 同类；阶段3 批次31-38 整体归零。
                         #       门 = SNIP_FAIL_SINCE=2.30（与 2.29 结构基准门分门，不追溯 2.29 及以下）。
                         # 2.29：⓪f 批次3 结构基准门（五项：⑫.5 fenced / ⑦.1 fenced / ④ 五段式 / ② 段落≤8 / ⑥ 边界与副作用+上下游表格）
                         # 2.28：⓪e 增补 E11（用户第四轮要求 · ⑫ 提示词块化与多轮）：
                         #       ⑫ 里所有"发给 AI 的提示词"必须放进 ```text 代码块（观感 + 可复制），
                         #       且**第 5 条须分多轮**（≥2 块）——现实开发是多轮问答（轮1 勘察禁写码 →
                         #       轮2 只出骨架 → 轮3 实现+自检），每轮一块并标轮次目标/期望形态/偏差信号。
                         #       校准：批次1-5 的第 5 条为**纯文本八段 + 轮次序列表**（0 块）——本条是
                         #       "比批次1 更进一步"的新标准（用户明确要求"都放进代码块"），门 = 2.28。
                         # （前值）2.27：⓪e 增补三项（用户第三轮复核批次37 · ⑥【讲解】段与 ⑫ 第2/3/5 步的排版）：
                         #       E8 ⑥ 【讲解】段 ≤300 字（且禁止「其一，/其二，」内联枚举——要点应列表化）：
                         #          批次1-5 = 36-80 字；批次33-38 = 445-958 字（2-5 处超 300）、内联枚举 1-4 处；
                         #       E9 ⑫ 第 2 条（现状勘察）与第 3 条（方案比较）**各须含 ≥1 个代码块**
                         #          （"你发给 AI 的原文"提示词，整段可复制）：批次1-5/30/31/33 各有 1 个；
                         #          批次34-38 ⑫ 内围栏数全为 0（提示词块整体消失）；
                         #       E10  〤 第 5 条须八段（【任务】【依赖】【要新增的类】【核心约束】【注释要求】
                         #          【验收标准】【禁止】【输出格式】）**各自独立成行** + 表格 ≥2（投喂策略 / 骨架）：
                         #          批次1-5 = 8/8 行 + 16 表格行；批次34-38 = 0/8 + 0。
                         #       三项门 = STYLE2_FAIL_SINCE=2.27（与 E1-E7 的 2.26 分门，不追溯已声明 2.26 的批次）。
                         # （前值）2.26：⓪e 结构密度与排版检查（**第二轮 Goodhart 防线** · 2026-09-18 用户复核批次37）：
                         #       以批次1/2/3（高水位标尺）量化比对阶段3——⑦ 五小节被「编号链」偷换》
                         #       （批次33-38 只剩 ⑦.1+⑦.5）、⑩ 反例 ❌/✅ 代码对照块归零（31-38）、
                         #       ③ 教学片段「可照抄的最小调用」归零（31-38）、⑫ 缩水 55%（34-38 仅 114-117 行）、
                         #       ②④ 超长段密排（33-38 超 300 字 1-4 段，最长 743）、① ② 图裸围栏无着色
                         #       （33-38 的 ① ② 全是裸围栏）。**断层批：⑩/③→31、⑦→33、⑫→34**；
                         #       批次30 为反证（同阶段同注入管线，⑦/⑩/③ 全保持）→ 退化非必然，
                         #       是模板在这三处失守而闸门恰好只查 ⑦.5（所以它独活）。
                         #       ⓪e = E1 ⑦五小节 / E2 ⑫行数≥180 / E3 ②④单段≤300字 / E4 ①②⑦围栏必标语言 /
                         #       E5 ⑩❌对照块≥3 对（以上 FAIL 档，门=STYLE_FAIL_SINCE）+ E6 ③教学片段≥3 /
                         #       E7 ④深潜小标题≥2（报告档）。
                         # （前值）2.25：⓪d 形态质量检查（Goodhart 防线）——2026-09-18 批次20-38 逐节扫描实测：
                         #       闸门只机械判定被检查项，写作注意力被检查项吸走，**未检查的 §6.4 必含形态
                         #       在批次33-38 整体丢失**：② 流水线图 19 批全有→6 批全无、⑤ 穿透清单消失、
                         #       ⑥ "要解决的一个问题"开场归零、★类逐步回放归零、⑭ 完整答案退化为钩回指针、
                         #       ⑥ 逐行要点表 36/38 归零（⑤ 位置检查在锚缺失时空过）。⓪d 把这些形态全部
                         #       变成可判定项；版本门与 ⓪b 同款（声明判据 ≥2.25 → FAIL 档，存量只报告）。
                         # 2.24：gate 对 Python 等注释型语言生效（H27 家族收尾）——①④ 内容/行号实检、
                         #       ② ★文件级覆盖、prose_index 跨语言——py 的 ①④ 此前是
                         #       "0 个代码块 → PASS" 的真空通过（deer-flow 17 批实测全如此）；
                         #       ③ 密度对 py/sh 为**报告档**（关键行判定首版近似，语料校准后单独升档）；
                         #       Java 路径零改动（双隔离：java 走原 by_class/rev 与原函数，py 走全新索引/函数）；
                         #       （前值）2.23：两处"注入源码里的 markdown 行被当成讲义结构"的误判——（a）块内 H3 只在含中文时报警；
                         #       （b）件段边界只在**正文**里认 `## `（`check_usage` 此前用原始行，与 2.22 修 `_prose_lines` 的根因同族）；
                         #       （前值）2.22：注释标记**按语言取前缀**（`ANNO` / `L_ANNO` 认 `//` `#` `--`）
                         # 2.21：新增**记录类形态判据**（is_record / check_record_shape）——整理批、进行中记录、草稿这类产物
                         #       **既不该按 17 节判、也不能没人管**：不立判据时它落在
                         #       「教材标志 <3 → 普通文档」的灰区，静默逃过一切形态约束（H23/H25 同族）；
                         #       三项：R1 状态行（状态或日期）/ R2 未完成与下一步清单 >=2 条 / R3 不冒充成品；
                         #       档位：自声明判据版本 >= 2.21 才判 FAIL，否则报告档（不追溯存量，同 2.19 机制）
                         #       首屏 15 行内声明参照物/存档（形态状态 / 节选 / 历史版本 / 已存档）→ 结构判定走**报告档**；
                         #       含 >=5 行 java 块 → 教材（老口径）；否则**教材标志投票 >=3 项**即判教材
                         #       （带圈节标题 / 批头声明 / 行号标注 / 6.x 小节 / 7.5 或索引节）
                         # 2.19：给 2.17 引入的 ⓪b 三项（① 架构图 / ⑦.1 编号链 / ⑧ 省略段）加**适用档位**：
                         #       批次自己声明「判据版本 ≥ 2.18」的 → 三项按 FAIL 判（新批落笔即声明，一律从严）；
                         #       未声明或声明更早的（存量批，78 份里 72 份从没写过版本）→ 降为**报告档**，数字照打。
                         #       为什么：新判据不追溯旧产物——2.17 直接把 60 份里的 12 份由绿转红，而它们
                         #       从没声称按哪版判据写；这与 2.10/2.11 两次的处置原则（先测误报率、不追溯）冲突。
                         # 2.18：**报告项**（不计 FAIL）——教材自足与构造手法（血证 H26 同轮，用户要求 2/4）：
                         #       A 每个代码块前 4 行内应有白话开场句（"这段解决什么"——只进报告，供存量工单）；
                         #       B ⑥ 每件应点名构造方式（谁 new/注入/生命周期）与实现手法（模式/数据结构/算法 + 权衡）。
                         #       先进报告档实测命中率，存量清完再议升 FAIL（判据纪律 §四-2）
                         # 2.17：新增 ⓪b **每批必含内容**硬检查（§6.4 ①⑦⑧ 从"通常会有"升为"必含可机械判定"）：
                         #       ① 节必须有架构图（围栏块 ≥5 行连接符/箭头 且 ≥3 个标识符能在仓库中找到）；
                         #       ⑦.1 必须 ≥5 跳编号调用链且每跳带行号（:L 或 :NNN）；
                         #       ⑧ 必须出现 L0~L3 四个层级标签且含"省略了什么生产边界"或等价表述（血证 H26 同轮）
                         # 2.16：⑫ 增**回顾语 FAIL 档**（VIB_RETRO：以"已有该批成果"为前提的回顾表述
                         #       一律禁止，⑫ 必须以"能力尚不存在、从零构建"为起点，§6.2 写作视角重构 / 血证 H26）
                         #       + 报告档新增 2 维（既有资产带路径清单 ≥3 / 真实需求含企业级约束 ≥1）
                         # 2.15：⓪ 增**17 个一级节标题的规范形态硬检查**——带圈数字丢失/多余空格会让
                         #       `^## ⑫` 这类定位正则静默失效、整节检查被跳过却照样打印 PASS（血证 H25：
                         #       本技能自己的脚本就丢过 ⑨/⑫ 三处、存活数周无人发现）；找不到段 = FAIL 并打印实际标题原文
                         # 2.14：⑤ 的**件段不得越过一级节标题**（原实现让最后一个 6.x 件的段延伸到 EOF，
                         #       把 ⑧/⑨/⑩ 里的手写 interface 与【怎么接】算到它头上：10 件 iface 误判 / 6 件 wire 误判，血证 H24）
                         # 2.13：② ★ 类的类名归属加「★ 标题链兜底」+ 同类去重（原实现只认块内类声明，
                         #       ★ 类按职责段拆讲时 ② 静默跳过 → 真空通过，血证 H23）
                         # 2.12：③ 注释密度的 need 加 key_n 上限（原式对"关键行<5 的 ★ 块"不可满足，血证 H22）
                         # 2.5：免检护栏认两种行号格式（`// :Lnn` 与作废的 `// :N`），堵住"标了行号却能免检"的漏洞
                         # 2.6：⓪ 增围栏**配对**体检（原只查奇偶；配对错位会让整段正文被吞进代码块却仍 PASS）
                         # 2.7：⑤ 增**位置**判据（【怎么用】必须在「逐行要点表」之后、件内 `---` 之前，否则读者会把它读成下一节）
                         # 2.8：新增 ⑥ **散文符号真实性**（正文里的 文件:行 引用 / 件标题声明的 .java / 本仓类.方法；
                         #      反引号符号走白名单+待确认清单。血证 H16：① 只管代码块，正文提到不存在的东西它一个字都不查）
                         # 2.9：⓪ 的占位判据扩到**含中文的 `__占位__`**（原只认 TODO/FIXME/CONT-/<<<SRC:；
                         #      血证 H18：填空白骨架能一路全绿——"还没写"与"已写好"在闸门眼里没有区别）
                         # 2.10：⑯ 段是否写明当前判据版本 → **报告项**（不计 FAIL）。实测只有 6/78 份写明，
                         #      直接判 FAIL 会让"绿"清零；先靠 sync_gate_result.py 补存量，再升 FAIL（血证 H15）

# ── 归一化 ────────────────────────────────────────────────────────────────
ANNO = re.compile(r"(?://|#|--)\s*:L?(\d+(?:-\d+)?)[ \t]*(.*)$")
# ↑ 2.22：**注释标记按语言取前缀**，不再只认 `//`。
#   为什么必须改：本技能已被用到 Python / TypeScript / Shell / YAML 项目上，
#   而这些语言的注释前缀是 `#`（YAML/Shell/Python/TOML）或 `--`（SQL）。
#   只认 `//` 的后果不是"少检一点"，而是**检查整组失效却照样打印 PASS**：
#   实测（deer-flow 阶段1 批次2，2026-09-16）6 个注入块里 5 个是 YAML，
#   行尾写的是 `# :L54  ←教材：…`，于是 ③ 注释密度把 221 条真实教材注释**一条都没认出来**
#   （has_cjk_comment 走 anno_text 分支返回空），直接判 FAIL —— 即
#   **"写对了却不认"**，与 H23/H25（"没写却不查"）是同一个根因的两个方向。
#   安全性：`#` 后**必须跟 `:`**，所以 YAML 里 `# 2026` 这类普通注释不会被误认成行号标注。
CJK = re.compile(r"[\u4e00-\u9fff]")
TRAIL_CMT = re.compile(r"(\s+(//|#|--).*)$")
CMT_LINE = re.compile(r"^\s*(//|/\*|\*|#|--)")
PUNCT_ONLY = re.compile(r"^[{}()\[\];,<>\s]*$")
DOCTYPE_DECL = re.compile(r"^\s*(?:public|private|protected|static|final|\s)*[A-Za-z_][\w<>\[\],\.\s]*\s+\w+\s*;\s*$")
LICENSE_HINT = re.compile(r"(Licensed to the Apache|Apache License|WITHOUT WARRANTIES|limitations under the License)")
EXEMPT = re.compile(
    r"(手写|No-Framework|不用框架|等价实现|反例|反面对照|对照实现|穿透卡|穿透|示例|演示|伪代码"
    r"|卡[一二三四五六七八九十0-9]|L0-L4|L1-L4|例 \d|Tiny|样例节选)", re.I)
HIST = re.compile(r"(【历史版本|历史版本示例|历史快照|已被阶段\s*\d+)", re.I)
CJK_LANGS = {"java", "sql", "yaml", "yml", "xml", "properties", "lua", "st", "json"}
# ── 2.24：语言能力表与非 Java 实检工具 ───────────────────────────────────
# 设计：java 走原路径（by_class/rev 原样），非 Java 走本节新索引与新函数——两条路互不可见，
# Java 批次 stdout 逐字节不变（22 份语料 diff 为空验收）。
HASH_ANNO_LANGS = {"bash", "sh", "shell", "zsh", "python", "py", "yaml", "yml", "toml",
                   "conf", "ini", "dockerfile", "dotenv", "makefile", "mk", "make", "ruby", "nginx"}
DASH_ANNO_LANGS = {"sql", "haskell", "lua"}
ANNO_LANGS = HASH_ANNO_LANGS | DASH_ANNO_LANGS | {
    "java", "js", "jsx", "ts", "tsx", "mjs", "go", "rust", "rs", "c", "cpp", "cs", "kotlin", "swift", "php"}
DATA_LANGS = {"yaml", "yml", "xml", "json", "jsonc", "properties", "ini", "conf", "toml",
              "dotenv", "dockerfile", "text", "txt", "plaintext", "makefile", "mk", "make"}
NONKEY_PY = re.compile(r"^\s*(#|$|\)|\]|\}|\{|import\s|from\s|@\w|\.\.\.)")
NONKEY_SH = re.compile(r"^\s*(#|$|\)|\]|\}|\{|done$|fi$|esac$|then$|do$|else$|;;)")


def _anno_parts(line):
    """返回 (前缀字符, 行号文本, 注释文本) 或 (None, None, None)。"""
    m = ANNO.search(line)
    if not m:
        return None, None, None
    return line[m.start()], m.group(1), (m.group(2) or "").strip()


def strip_anno_lang(line, lang):
    """按语言剥离行号标注：前缀不匹配该语言 → 视为无标注（防字符串里的 # 被误剥）。

    返回 (剥标后的行, 行号 int 或 None, 教材注释文本或 None)。
    """
    pfx, no, note = _anno_parts(line)
    if pfx is None or no is None:
        return line, None, None
    if lang in HASH_ANNO_LANGS and pfx != "#":
        return line, None, None
    if lang in DASH_ANNO_LANGS and pfx != "-":
        return line, None, None
    if lang not in HASH_ANNO_LANGS and lang not in DASH_ANNO_LANGS and pfx != "/":
        return line, None, None
    m = ANNO.search(line)
    return line[:m.start()].rstrip(), int(no.split("-")[0]), note


def has_cjk_lang(line, lang):
    """该行是否带中文讲解（行号标注后的 ←教材： 文本，或该语言注释里的中文）。"""
    pfx, _, note = _anno_parts(line)
    if note and pfx is not None and CJK.search(note):
        return True
    code = strip_anno_lang(line, lang)[0]
    tok = "--" if lang in DASH_ANNO_LANGS else ("#" if lang in HASH_ANNO_LANGS else "//")
    head = code.split(tok)[0]
    tail = code[len(head):]
    return bool(tail) and bool(CJK.search(tail))


def mark_text_blocks_lang(bl, lang):
    """文本块（三引号/多行串）内部行标记——数据不是逻辑，不计入密度。"""
    if lang not in ("python", "py"):
        return mark_text_block_lines(bl)
    inside, state = [], False
    for ln in bl:
        code, _, _ = strip_anno_lang(ln, lang)
        cnt = code.count('"""') + code.count(chr(39) * 3)
        inside.append(state)
        if cnt % 2 == 1:
            state = not state
    return inside


def is_key_lang(code, lang):
    """非 Java 的关键行判定（首版近似——③ 对 py/sh 因此只做报告档）。"""
    s = code.strip()
    if not s:
        return False
    if lang in ("python", "py") and NONKEY_PY.match(s):
        return False
    if lang in ("bash", "sh", "shell", "zsh") and NONKEY_SH.match(s):
        return False
    if lang in ("ts", "tsx", "js", "jsx", "mjs") and s.startswith("//"):
        return False
    if s.startswith(("package ", "import ", "export ", "#include", "from ")):
        return False
    if PUNCT_ONLY.match(s):
        return False
    return True


def _len_or0(x):
    return len(x) if x else 0


def _manifest_path_for(lec):
    """位置契约清单**路径**的三个查找位：讲稿旁 / NOTES/_tools/（deer-flow 约定）/ 讲稿目录。
    用 basename 匹配，避免中文文件名在跨目录拼接时的形态差异。"""
    base = os.path.basename(lec) + ".blocks.json"
    for d in (os.path.dirname(lec),
              os.path.join(os.path.dirname(lec), "_tools"),
              os.path.join(lec.split(os.sep + "NOTES" + os.sep)[0] if (os.sep + "NOTES" + os.sep) in lec else os.path.dirname(lec), "NOTES", "_tools")):
        p = os.path.join(d, base)
        if os.path.isfile(p):
            return p
    return None


def _manifest_for(lec):
    p = _manifest_path_for(lec)
    if not p:
        return None
    try:
        return json.load(io.open(p, encoding="utf-8"))
    except Exception:
        return None


def _py_index(root):
    """非 Java 源码索引：basename → 路径们 + 归一化行 → Counter(文件)（归属回退用）。"""
    by_base, rev = {}, collections.defaultdict(collections.Counter)
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            if fn.endswith((".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".sh", ".bash",
                            ".yaml", ".yml", ".toml")):
                p = os.path.join(dp, fn)
                by_base.setdefault(fn, []).append(p)
                try:
                    t = io.open(p, encoding="utf-8", errors="replace").read()
                except OSError:
                    continue
                for l in t.split("\n"):
                    n = norm_code(l)
                    if n and not CMT_LINE.match(n):
                        rev[n][p] += 1
    return by_base, rev


def _resolve_py_src(sect, chain, hint, by_base, rev_py, code_lines):
    """从标题/标题链/提示里的反引号文件名归属源文件；歧义时用内容计数器择优；失败 None。"""
    cands = []
    for src in [sect or ""] + list(chain or []) + [hint or ""]:
        cands += re.findall(r"`([^`\n]+\.(?:py|ts|tsx|js|jsx|mjs|sh|bash|yaml|yml|toml))`", src)
    for c in cands:
        hits = by_base.get(os.path.basename(c))
        if not hits:
            continue
        if len(hits) == 1:
            return hits[0]
        best, bestn = None, -1
        for h in hits:
            n = sum(1 for cl in code_lines if cl in src_code_set(h))
            if n > bestn:
                best, bestn = h, n
        return best
    if code_lines:
        cnt = collections.Counter()
        for cl in code_lines:
            cnt.update(rev_py.get(cl, {}))
        top = cnt.most_common(2)
        if top and (len(top) == 1 or top[0][1] > top[1][1]):
            return top[0][0]
    return None

SKIP_DIRS = {"target", "node_modules", ".git", ".tmp_audit", ".tmp_lecture", ".workbuddy"}
SPLIT_DECL = re.compile(r"\b(?:class|interface|enum|record)\s+([A-Z][A-Za-z0-9_]*)")
SNAP_DECL = re.compile(r"(?:源码依据|源码快照|snapshot)[^\n]{0,40}?([0-9a-f]{7,40})")
# 2.9 占位符（含中文的 `__xxx__`）：只扫围栏内。**要求占位里含汉字**，这样 Python 的 `__init__`
# 这类 dunder 与 `__main__` 不会误报（全库实测：78 份讲解 + 2 份样例 = 0 处，只有模板自身命中）
PLACEHOLDER = re.compile(r"__[^_\n]*[\u4e00-\u9fff][^_\n]*__")

# ── 快照状态（进程级） ────────────────────────────────────────────────────
SNAPSHOT = None          # commit sha
SNAP_TAR = None          # git archive 出来的 tar 字节
SNAP_UNION = None        # 快照里所有 .java 的归一化代码行集合
_snap_file_cache = {}


def strip_anno(line):
    """去掉行尾 `// :Lnn <说明>`，返回 (剩余代码, 标注后的说明文字)"""
    m = ANNO.search(line)
    if not m:
        return line, ""
    return ANNO.sub("", line), (m.group(2) or "").strip()


def norm_code(line):
    """代码归一化：去行号标注、去行尾注释、折叠空白（折行/对齐差异不算差异）"""
    code, _ = strip_anno(line)
    code = code.replace("\t", " ")
    code = re.sub(r"\s+", " ", code).strip()
    return code


def has_cjk_comment(line):
    """该行是否有中文注释：行号标注后带中文，或行内注释含中文"""
    _, anno_text = strip_anno(line)
    if anno_text and CJK.search(anno_text):
        return True
    code, _ = strip_anno(line)
    head = code.split("//")[0]
    tail = code[len(head):]
    if tail and CJK.search(tail):
        return True
    if CMT_LINE.match(code) and CJK.search(code):
        return True
    return False


def mark_text_block_lines(bl):
    """标出处于文本块（\"\"\" 或 SQL 多行串）内部的行 —— 它们是数据不是逻辑，不计入密度"""
    inside = []
    state = False
    for ln in bl:
        code, _ = strip_anno(ln)
        cnt = code.count('"""')
        if state:
            inside.append(True)
            if cnt % 2 == 1:
                state = False
        else:
            inside.append(False)
            if cnt % 2 == 1:
                state = True   # 进入文本块（修复：原实现两分支皆 False，豁免从未生效——批次26 实录）
            if cnt % 2 == 1:
                state = True
    return inside


def is_key_line(line, in_license, in_text_block=False):
    """§6.1.1「关键行」判定：非关键行不计入密度"""
    if in_text_block:
        return False
    code, _ = strip_anno(line)
    s = code.strip()
    if not s or in_license or LICENSE_HINT.search(s):
        return False
    if s.startswith(("package ", "import ", "export ")):
        return False
    if PUNCT_ONLY.match(s):
        return False
    if DOCTYPE_DECL.match(s):
        return False
    return True


# ── 讲解文件解析 ──────────────────────────────────────────────────────────
def heading_chain(lines, start):
    """从 start 往上取**真正的祖先标题链**（外层 → 最近）。
    只收"层级严格更高"的标题：同级标题（如上一个 `### 6.5 Xxx★`）不属于本块的祖先，
    否则 ★ 会串到别的节去（2026-09-15 修）。"""
    chain, min_lv = [], 7
    for i in range(start - 2, -1, -1):
        m = re.match(r"^(#{2,5}) (.*)$", lines[i])
        if m:
            lv = len(m.group(1))
            if lv < min_lv:
                chain.append(m.group(2).strip())
                min_lv = lv
        if lines[i].startswith("# "):
            break
    chain.reverse()
    return chain


def parse_blocks(path):
    """返回 (全部行, [(起始行号, 语言, 行列表, 所属小节标题, 所属一级节标题, 类名线索, 标题链, 用法标记)])"""
    lines = open(path, encoding="utf-8", errors="replace").read().split("\n")
    out, cur, lang, start = [], None, None, 0
    hint, hint_cur = {}, ""
    for i, l in enumerate(lines):
        if re.match(r"^#{2,5} ", l):
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", l)
                   if not re.fullmatch(r"L\d+", w)]
            if ids:
                hint_cur = " ".join(ids)
        hint[i + 1] = hint_cur
    # 用法/接入标记：块前最近的 `**【怎么用】**` 之类粗体标记；换标题即清空。
    # 命中标记的块视为**教学合成片段**（照抄式用法/实现骨架），免 ① 保真核验——
    # 但带 `// :Lnn` 行号标注的块例外（标了行号即声明"这是源码原文"，必须核验）。
    mk, mk_cur = {}, ""
    for i, l in enumerate(lines):
        if re.match(r"^#{2,5} ", l):
            mk_cur = ""
        elif re.match(r"^\*\*(【怎么用】|【怎么接】|【扩展步骤】|【上下游】)", l):
            mk_cur = l.strip()[:24]
        mk[i + 1] = mk_cur
    for i, l in enumerate(lines):
        m = re.match(r"^(\s*)(`{3,})\s*([A-Za-z0-9_+-]*)\s*$", l)
        if cur is None:
            if m:
                cur, lang, start = [], (m.group(3) or "").lower(), i + 2
        else:
            if re.match(r"^\s*`{3,}\s*$", l):
                s3 = sect_of(lines, start, (3, 4, 5))
                s2 = sect_of(lines, start, (2,))
                out.append((start, lang, cur, s3 if s3 != "?" else s2, s2,
                            hint.get(start, ""), heading_chain(lines, start), mk.get(start, "")))
                cur = None
            else:
                cur.append(l)
    return lines, out


def sect_of(lines, start, levels=(2, 3, 4, 5)):
    """回溯最近的小节标题"""
    for i in range(start - 2, -1, -1):
        if re.match(r"^#{2,5} ", lines[i]):
            lv = len(lines[i]) - len(lines[i].lstrip("#"))
            if lv in levels:
                return lines[i].strip()
    return "?"


def find_classes(text):
    return re.findall(r"\b(?:class|interface|enum|record|@interface)\s+([A-Z][A-Za-z0-9_]*)", text)


# ── 源码索引 ──────────────────────────────────────────────────────────────
def index_sources(root):
    """返回 (类名 -> 文件列表, 代码行 -> Counter(文件))；后者用于无类名片段块的归属回退"""
    by_class = collections.defaultdict(list)
    rev = collections.defaultdict(collections.Counter)
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            if fn.endswith(".java"):
                p = os.path.join(dp, fn)
                by_class[fn[:-5]].append(p)
                for l in open(p, encoding="utf-8", errors="replace").read().split("\n"):
                    n = norm_code(l)
                    if n and not CMT_LINE.match(n):
                        rev[n][p] += 1
    return by_class, rev


_NS_CACHE = {}


def _ns(path):
    if path not in _NS_CACHE:
        _NS_CACHE[path] = src_nospace(path)
    return _NS_CACHE[path]


def line_variants(n):
    """讲解行的等价形态：原样 / 去掉行尾注释（教材旧格式形如 `代码  // 中文说明`）"""
    yield n
    head = n.split("//")[0].strip()
    if head and head != n:
        yield head


def line_ok_in(path, n):
    """该行是否属于源文件：先逐行比（含"去掉行尾注释"的等价形态），再退化为"去空白子串"（容忍折行）"""
    sset = src_code_set(path)
    for v in line_variants(n):
        if v in sset:
            return True
        ns = re.sub(r"\s+", "", v)
        if len(ns) >= 8 and ns in _ns(path):
            return True
    return False


def attribute(code, classes, by_class, rev):
    """返回 (最佳源文件, 真·不命中行列表)；先按类名，再按内容回退"""
    pool_files = []
    for c in classes:
        pool_files += by_class.get(c, [])
    if not pool_files:
        votes = collections.Counter()
        for x in code:
            for f in rev.get(x, {}):
                votes[f] += 1
        if not votes:
            return None, None
        f, hit = votes.most_common(1)[0]
        if hit / len(code) < 0.85:
            return None, None
        pool_files = [f]
    best = None
    for p in set(pool_files):
        lost = [x for x in code if not line_ok_in(p, x)]
        if best is None or len(lost) < len(best[1]):
            best = (p, lost)
    return best


_SRC_CODE_SET_CACHE = {}


def src_code_set(path):
    if path in _SRC_CODE_SET_CACHE:
        return _SRC_CODE_SET_CACHE[path]
    s = set()
    for l in open(path, encoding="utf-8", errors="replace").read().split("\n"):
        n = norm_code(l)
        if n and not CMT_LINE.match(n):
            s.add(n)
    _SRC_CODE_SET_CACHE[path] = s
    return s


def src_nospace(path):
    """整文件的"去空白"文本：用于容忍跨行折行差异（讲解把长行拆两行不算编造）"""
    txt = open(path, encoding="utf-8", errors="replace").read()
    out = []
    for l in txt.split("\n"):
        c, _ = strip_anno(l)
        head = c.split("//")[0]
        out.append(head)
    return re.sub(r"\s+", "", "".join(out))


def src_lines(path):
    return open(path, encoding="utf-8", errors="replace").read().split("\n")


# ── 快照（本批声明的源码 commit） ─────────────────────────────────────────
def load_snapshot(sha):
    """把该 commit 的所有 .java 读成一个 tar 与"代码行并集"，用于区分「源码演进」与「编造」。
    2.24 健壮性加固（非判据变更）：`git archive` 的捕获流在个别环境会被截断（tarfile 报
    ReadError 'end of file header'，实测 deer-flow 55MB 快照 4/4 复现），而本函数原有
    「读取失败 → 退回只比当前树」的降级路径却没有兜 tarfile 异常 → 直接崩溃。
    修法 = ① 失败重试一次（读操作，幂等）② 仍失败则走既有降级（返回 False），绝不让闸门崩。
    判定层零变化：tar 完整时行为与旧版逐字节一致（Java 23 份语料回归见变更登记）。"""
    global SNAPSHOT, SNAP_TAR, SNAP_UNION
    data = b""
    for _attempt in range(2):                      # 截断多为环境级瞬时问题：重试一次
        data = subprocess.run(["git", "archive", "--format=tar", sha],
                              cwd=ROOT, capture_output=True).stdout
        if data:
            try:
                with tarfile.open(fileobj=io.BytesIO(data)) as tf:
                    tf.getmembers()                # 完整性探测：能列全成员才算拿到快照
                break
            except (tarfile.TarError, EOFError, OSError, ValueError):
                data = b""                         # 截断/损坏 → 当作没拿到，重试或降级
    if not data:
        SNAPSHOT, SNAP_TAR, SNAP_UNION = sha, None, None
        return False
    union = set()
    with tarfile.open(fileobj=io.BytesIO(data)) as tf:
        for m in tf.getmembers():
            if not m.isfile() or not m.name.endswith(".java"):
                continue
            for l in tf.extractfile(m).read().decode("utf-8", "replace").split("\n"):
                n = norm_code(l)
                if n and not CMT_LINE.match(n):
                    union.add(n)
    SNAPSHOT, SNAP_TAR, SNAP_UNION = sha, data, union
    return True


def resolve_snapshot(lines, explicit=None):
    """快照来源：命令行 --snapshot > 批头声明「源码依据：commit <sha>」"""
    if explicit:
        return explicit, "命令行"
    head = "\n".join(lines[:80])
    m = SNAP_DECL.search(head)
    return (m.group(1), "批头声明") if m else (None, None)


def snap_file_lines(rel):
    """快照里某个文件的代码行（按需从 tar 取，带缓存）"""
    if rel in _snap_file_cache:
        return _snap_file_cache[rel]
    got = None
    if SNAP_TAR:
        want = rel.replace("\\", "/")
        with tarfile.open(fileobj=io.BytesIO(SNAP_TAR)) as tf:
            for m in tf.getmembers():
                if m.isfile() and m.name == want:
                    got = tf.extractfile(m).read().decode("utf-8", "replace").split("\n")
                    break
    _snap_file_cache[rel] = got
    return got


# ── 检查 ①：正向保真度 ───────────────────────────────────────────────────
L_ANNO = re.compile(r"(?://|#|--)\s*:L?\d+")   # 两种格式都算"标了行号"：`// :Lnn`（现行）与 `// :N`（作废但存量 36 文件/7315 处在用）。
                                      # 2.5 修：此前只认带 L 的格式，旧格式标了行号却能混进免检（护栏漏洞，实测当时 0 个块命中）
                                      # 2.22 修：注释标记按语言取前缀（`//` / `#` / `--`），与 ANNO 同源。
                                      #   `is_exempt` 用它判"命中免检标记但块内带行号 = 声明自己是源码原文 → 不豁免"，
                                      #   只认 `//` 时，YAML/Shell 块里的 `# :Lnn` 会被当成"没标行号"而**错误豁免**。


def is_exempt(sect, h2, mk="", bl=None):
    """免检判定：小节名或所属一级节名命中免检词，或属于 ⑨ No-Framework 节下的 ### 9.x，
    或块位于 `**【怎么用】/【怎么接】/【扩展步骤】/【上下游】` 标记之下（教学合成片段）。
    例外：命中标记但块内带行号标注（`// :Lnn` 或作废的 `// :N`）= 声明自己是源码原文 → 不豁免，照常核验。"""
    if EXEMPT.search(sect or "") or EXEMPT.search(h2 or ""):
        return True
    if re.match(r"^#{3,5}\s*9\.", sect or ""):
        return True
    if mk and not any(L_ANNO.search(x) for x in (bl or [])):
        return True
    return False


def is_hist(sect, chain=None):
    """历史版本块：必须用快照核验（不能当免检后门）。
    判定只看"块自身标题或任一祖先标题"是否显式声明历史版本（如【历史版本示例】/ 已被阶段N 重写）。"""
    if HIST.search(sect or ""):
        return True
    return any(HIST.search(h) for h in (chain or []))


def check_fidelity(blocks, by_class, rev):
    rows = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java":
            continue
        text = "\n".join(bl)

        def _ids(t):
            return [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", t) if not re.fullmatch(r"L\d+", w)]

        classes = SPLIT_DECL.findall(text)
        if not classes:
            classes = _ids(sect) or _ids(hint)
        code = [norm_code(x) for x in bl]
        code = [c for c in code if c and not CMT_LINE.match(c)]
        if len(code) < 5:
            continue
        cand, lost = attribute(code, classes, by_class, rev)
        # 快照分类：只在快照里命中 = 源码演进；两处都不在 = 候选编造
        snap_lost = None
        if lost is not None and SNAP_UNION is not None:
            snap_lost = [c for c in lost if c not in SNAP_UNION]
        hist = is_hist(sect, chain)
        rows.append(dict(start=start, sect=sect, h2=h2, lang=lang, classes=classes,
                         n_code=len(code), exempt=is_exempt(sect, h2, mk, bl), hist=hist,
                         cand=os.path.relpath(cand, ROOT) if cand else None,
                         lost=len(lost) if lost is not None else None,
                         lost_samples=(lost[:4] if lost else []),
                         snap_lost=len(snap_lost) if snap_lost is not None else None,
                         snap_lost_samples=(snap_lost[:4] if snap_lost else []),
                         evolve=(len(lost) - len(snap_lost)) if (lost is not None and snap_lost is not None) else None))
    return rows


def block_star(sect, chain):
    """该块是否算 ★ 类：块自己标题带 ★，或任意父标题带 ★（2026-09-15 修：此前只看最近标题，
    ★ 标在 `### 6.5 Xxx★` 而块在 `#### 6.5.A` 下时，② 会静默空转）"""
    return "★" in (sect or "") or any("★" in h for h in (chain or []))


# ── 检查 ②：反向完整度（★类） ────────────────────────────────────────────
def star_class_fallback(sect, hint, chain, by_class):
    """★ 块的类名归属兜底（判据 2.13，血证 H23）：块自身没有类声明时，从 **★ 标题链**里取类名。

    **为什么必须有这条兜底**：⑥ 明确要求 ★ 类**按职责段拆讲**（段 1 / 段 2 …）。拆分之后
    **没有任何单块含类声明**，而原实现写的是 `if not classes: continue` —— 于是本项静默跳过、
    打印「0 个★类」并 PASS。**这是一次真空通过，不是核验过**：读者看到 PASS，会以为
    "★ 类的每一行都被讲解覆盖了"，实际上一行都没查。

    实测（2026-09-16，全库 60 份批次文件）：6 份命中该盲区（阶段9 四批 + 阶段10批次1 +
    阶段6批次1），其中 4 份属于"有 ★ 块但一个类都没查"。补上兜底后 17/50 份转 FAIL，
    逐份人工验伪：缺失行**都是真缺口**（`@Slf4j` / 类声明 / 依赖字段 / 私有方法确实没在讲解里出现过），
    **误报 0** —— 所以这是一次"把真空变成实检"，不是收紧门槛。

    取名优先级：块自身标题 → （倒序）祖先标题链里最近一个带 ★ 的标题 → 最近含类名的标题。
    只接受 `by_class` 里真实存在的类（避免把 `Comparator` 这类 JDK 类型当成本仓类）。
    **类名长度 ≥3 即可**（`[A-Z][A-Za-z0-9_]{2,}`）：别处 `_ids` 用的是 `{3,}`（≥4 字符），
    照抄会让 `Dao` / `Rrf` / `Foo` 这类短名解析不出来 → 又退回真空通过（自检当场抓到）。
    """
    ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{2,}", sect or "") if not re.fullmatch(r"L\d+", w)]
    for h in reversed(chain or []):
        if "★" in h:
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{2,}", h)
                   if not re.fullmatch(r"L\d+", w)] + ids
    if not ids:
        ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{2,}", hint or "") if not re.fullmatch(r"L\d+", w)]
    for c in ids:
        if by_class.get(c):
            return c
    return None


def check_reverse(blocks, lines, by_class):
    """★类 = 标题（自身或任一父标题）带 ★ 的 java 代码块，**按类去重**后逐类算覆盖。

    2.13 两处改动（血证 H23）：
      ① 类名归属加 `star_class_fallback()` 兜底——★ 类按职责段拆讲时不再静默跳过；
      ② 同一 ★ 类只出一条记录：覆盖是拿**全批所有块的并集**算的（`lect_all`），
         段1/段2… 各自算一遍会得到完全相同的数字，重复行只会把"3 个★类"报成"15 个"。
    """
    rows = []
    seen_cls = set()
    lect_all = set()
    for blk in blocks:
        for x in blk[2]:
            n = norm_code(x)
            if n:
                lect_all.add(n)
    lect_ns = [re.sub(r"\s+", "", v) for v in lect_all]
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java" or not block_star(sect, chain):
            continue
        if is_exempt(sect, h2, mk, bl):
            continue          # 样例节选 / 手写版 / 用法片段等免检块不参与 ★完整性（它们本就不是整文件）
        if is_hist(sect, chain):
            continue          # 历史版本块由 ① 按快照核验，不拿当前树做反向覆盖
        classes = find_classes("\n".join(bl))
        if not classes:
            # 2.13 兜底：段拆块不含类声明时，从 ★ 标题链取类名（否则本项真空通过）
            c = star_class_fallback(sect, hint, chain, by_class)
            classes = [c] if c else []
        if not classes:
            continue
        for c in classes[:1]:
            if c in seen_cls:
                continue
            cands = by_class.get(c)
            if not cands:
                continue
            seen_cls.add(c)
            p = cands[0]
            real, miss = 0, []
            for sl in src_lines(p):
                t = norm_code(sl)
                if not t or CMT_LINE.match(t) or t.startswith(("import ", "package ")) or PUNCT_ONLY.match(t):
                    continue
                real += 1
                if t in lect_all:
                    continue
                # 容忍等价形态：折行拼接 / 行尾带教材注释
                ts = re.sub(r"\s+", "", t)
                if len(ts) >= 8 and any(ts in v for v in lect_ns):
                    continue
                miss.append(t)
            cov = (real - len(miss)) / real if real else 1.0
            rows.append(dict(cls=c, src=os.path.relpath(p, ROOT), sect=sect,
                             real=real, miss=len(miss), cov=round(cov, 4),
                             samples=miss[:3]))
    return rows


# ── 检查 ③：注释密度 ─────────────────────────────────────────────────────
SIG = re.compile(r"^\s*(?:(?:public|protected|private|static|final|synchronized|abstract|default|native)\s+)+"
                 r"[\w<>\[\],\.\?]+\s+(\w+)\s*\([^;]*\)\s*(?:throws\s+[\w\s,\.]+)?\{\s*$")


def method_names_of(path):
    """源文件里的方法名（只认"带修饰符 + 返回类型 + 名 + 参数 + {"的行；故意宽松以少误报）"""
    out = []
    for l in src_lines(path):
        c, _ = strip_anno(l)
        m = SIG.match(c)
        if m:
            out.append(m.group(1))
    return list(dict.fromkeys(out))


def check_density(blocks, by_class=None, rev=None):
    rows = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang not in CJK_LANGS or len(bl) < 5:
            continue
        exempt = is_exempt(sect, h2, mk, bl)
        in_lic, seen_pkg = False, False
        keys = []
        tb = mark_text_block_lines(bl)
        for idx, ln in enumerate(bl):
            code, _ = strip_anno(ln)
            if code.strip().startswith(("package ", "import ")):
                seen_pkg = True
            if LICENSE_HINT.search(code):
                in_lic = True
            if in_lic and "*/" in code:
                in_lic = False
            if seen_pkg:
                in_lic = False
            if not is_key_line(ln, in_lic, tb[idx]):
                continue
            keys.append((ln, has_cjk_comment(ln)))
        key_n = len(keys)
        mx, cur, runs = 0, 0, 0
        for _, ok in keys:
            if ok:
                if cur >= 8:
                    runs += 1
                mx = max(mx, cur)
                cur = 0
            else:
                cur += 1
        if cur >= 8:
            runs += 1
        mx = max(mx, cur)
        cmts = sum(1 for _, ok in keys if ok)
        star = block_star(sect, chain)
        # 2.12（血证 H22）：`max(5, …)` 对 ★ 块无条件取 5，而注释只能落在**关键行**上——
        # 于是"关键行 < 5 的 ★ 块"要求 5 条注释却最多只能有 key_n 条，**数学上不可满足**。
        # 实测全库 245 个 ③ 不达标块里有 27 个（11%）属于这种；用 min(key_n, …) 封顶。
        need = min(key_n, max(5, math.ceil(key_n / 12))) if star else math.ceil(key_n / 12)
        rows.append(dict(start=start, sect=sect, exempt=exempt, key_lines=key_n,
                         comments=cmts, max_run=mx, bad_runs=runs,
                         need=need, star=star))
    return rows


def star_classes(blocks, by_class):
    """本批的 ★ 类清单（自身或父标题带 ★；类名来自块内声明或标题）"""
    out = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java" or not block_star(sect, chain) or is_exempt(sect, h2, mk, bl):
            continue
        names = find_classes("\n".join(bl))
        if not names:
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", sect) if not re.fullmatch(r"L\d+", w)] or \
                  [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", hint) if not re.fullmatch(r"L\d+", w)]
            names = ids
        for c in names[:1]:
            if c not in out and by_class.get(c):
                out.append(c)
    return out


def check_sig(blocks, by_class):
    """③c ★类方法签名覆盖（**按类、跨块**判定）：★类每个方法至少有一条注释落在签名行或相邻行。
    注意是"整类"口径——★类允许拆成多个职责段块，只要全篇合起来每个方法都被讲到即可。"""
    covered = []          # [(norm_line, 下一行是否带中文注释)]
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java":
            continue
        for j, ln in enumerate(bl):
            covered.append((norm_code(ln), has_cjk_comment(ln),
                            has_cjk_comment(bl[j + 1]) if j + 1 < len(bl) else False))
    rows = []
    for c in star_classes(blocks, by_class):
        p = by_class[c][0]
        miss = []
        for nm in method_names_of(p):
            hit = any((nm + "(") in n and (ok or nxt) for n, ok, nxt in covered)
            if not hit:
                miss.append(nm)
        if miss:
            rows.append(dict(cls=c, src=os.path.relpath(p, ROOT), missing=miss))
    return rows


# ── 检查 ④：行号一致性 ───────────────────────────────────────────────────
def check_lineno(blocks, by_class, rev):
    """`// :Lnn` 的行号是否指向该行内容真正所在的行。
    只在"该行内容能在源文件里唯一定位"时才判定（折行/压缩行、重复行、公共符号行跳过）。"""
    rows = []
    for start, lang, bl, sect, h2, hint, chain, mk in blocks:
        if lang != "java" or is_exempt(sect, h2, mk, bl):
            continue
        classes = SPLIT_DECL.findall("\n".join(bl))
        if not classes:
            ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", sect) if not re.fullmatch(r"L\d+", w)]
            if not ids:
                ids = [w for w in re.findall(r"[A-Z][A-Za-z0-9_]{3,}", hint) if not re.fullmatch(r"L\d+", w)]
            classes = ids
        code = [norm_code(x) for x in bl]
        code = [c for c in code if c and not CMT_LINE.match(c)]
        if len(code) < 5:
            continue
        cand, _ = attribute(code, classes, by_class, rev)
        if cand is None:
            continue
        base = None
        if is_hist(sect, chain) and SNAPSHOT:
            base = snap_file_lines(os.path.relpath(cand, ROOT))
        src = base if base is not None else src_lines(cand)
        idx = collections.defaultdict(list)
        for i, l in enumerate(src):
            n = norm_code(l)
            if n:
                idx[n].append(i + 1)
        bad = []
        checked = 0
        for x in bl:
            m = ANNO.search(x)
            if not m:
                continue
            n = norm_code(x)
            if len(n) < 8 or PUNCT_ONLY.match(n):
                continue
            where = idx.get(n, [])
            if len(where) != 1:
                continue                       # 无法唯一定位 → 不判定（折行/重复行）
            checked += 1
            want = int(m.group(1).split("-")[0])
            if want != where[0]:
                bad.append((want, where[0], n[:70]))
        rows.append(dict(start=start, sect=sect, src=os.path.relpath(cand, ROOT),
                         checked=checked, bad=len(bad), samples=bad[:3]))
    return rows


# ── 检查 ⓪：结构（A 组：节数 / 围栏 / 占位残留 / ⑫ 八条·八段·自指·薄条·回链） ──
FENCE_LINE = re.compile(r"^(\s*)(`{3,})\s*([A-Za-z0-9_+-]*)\s*$")

# 2.15（血证 H25）：17 个一级节标题的**规范形态**硬检查（§6.4：①~⑯ + 索引）。
# 为什么必须有这条：⑫/⑯ 等节的定位都靠 `^## ⑫\s` 这类带圈数字正则；而带圈数字（⑨⑩⑫⑮⑯ 等）
# 在某些落盘链路会**静默丢失**——标题变成 `##  Vibecoding 视角`（⑫ 丢了）或 `##  ⑫`（多了一个空格）后，
# 那一节的所有检查被整体跳过，节数却仍可能是 17（标题还在，只是首字符不对）→ PASS 照样打印。
# 「找不到段」必须是可见的 FAIL，并把**实际标题原文**打出来，否则下游一切新增检查都无法被验证。
SECTION_H2 = re.compile(r"^##(?!#)")
CIRCLED16 = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯"


def section_form_check(lines):
    """返回 (缺失的规范节标题, 形态变形的节标题[(期望首字符, 实际原文)], 实际一级标题列表)。

    规范形态（§6.4）：`## ① …` ~ `## ⑯ …` + `## 索引…`——`##` 后**恰好一个空格**，
    紧跟带圈数字（或「索引」），再跟空白或行尾。宽松形态（`^##\\s*①`）能命中而规范形态不能 = 变形。
    """
    heads = [l for l in lines if SECTION_H2.match(l)]
    missing, deformed = [], []
    for c in list(CIRCLED16) + ["索引"]:
        # 带圈数字要求"数字后必须跟空白/行尾"（防止 `## ①abc` 蒙混）；索引节允许直接带后缀（`## 索引节`/`## 索引与导航` 都是规范形态）
        canon = r"^## " + c + (r"(?=\s|$)" if len(c) == 1 else "")
        if any(re.match(canon, l) for l in heads):
            continue
        loose = [l for l in heads if re.match(r"^##\s*" + c, l)]
        if loose:
            deformed.append((c, loose[0].strip()))
        else:
            missing.append(c)
    return missing, deformed, heads


def fence_scan(lines):
    """围栏**配对**体检（2.6 新增）。口径与 parse_blocks 完全一致：
    块外任意围栏行都算"开始"（可带语言标签，也可不带）；块内只有**不带语言标签**的围栏行才闭合，
    带标签的行会被当成正文追加——这正是"前一个块没闭合"的症状。
    返回 ([问题三元组], 结束时是否仍在块内)。
    为什么需要它：⓪ 原来只查"围栏数量为偶数"，而**删除一对围栏中的一半、或把闭合栅栏与开始栅栏互换**，
    数量仍是偶数 → 一整段正文被吞进代码块却照样 PASS（真实事故见血证 H14）。
    只判 A（块内出现带标签围栏）/ D（结束时未闭合）/ H3（`### ` 级标题落在块内）三类——
    `## ` 级不判：合法 prompt 模板的正文里会出现 `## 1. xxx`（当前仅 1 个文件 7 处，属正常）。"""
    inside = False
    bad = []
    for i, l in enumerate(lines):
        m = FENCE_LINE.match(l)
        if m:
            if not inside:
                inside = True
            else:
                if m.group(3):
                    bad.append(("块内又出现带语言标签的围栏（前一个代码块未闭合）", i + 1, l.strip()[:36]))
                else:
                    inside = False
            continue
        # 2.23：只对**含中文**的 H3 报警——讲义节标题一律中文，而注入源码里出现的英文
        # `### xxx`（如 FastAPI description 的 markdown）是源码内容，不是被吞的正文。
        if inside and re.match(r"^### ", l) and CJK.search(l):
            bad.append(("标题落在代码块内（正文被吞）", i + 1, l.strip()[:36]))
    return bad, inside


def vib_depth(seg):
    """⑫ 内容深度（判据 2.11）——**⑫ 是整份教材里唯一能跨项目复用的那一节，也是唯一产生过
    "内容编造"级血证（H16）的那一节**；而 2.10 之前闸门对它只有"容器检查"（数条数/数标签/数行数），
    旧八条与现行八条同样全绿（实测：阶段7批次2 旧八条形态一路全绿）。

    本函数把 §6.2.1 的**可判定实质**测出来。分两档（先测误报率再收判据的落地）：
      FAIL 档（4 项，全库通过率 82%~91%，且都是 §6.2.1 的旧有明文）：
        A 八个条目标题必须命中 8 类语义（真实需求/现状勘察/方案比较/增量实现/提示词/产出后审查/验证反馈循环/最终沉淀）
        B 第 5 条必须含完整八段提示词骨架（≥6/8 个标签）
        C 第 5 条必须讲"设计要点"（为什么这么写）——只给一个提示词不算讲完
        D 第 6 条必须是 ≥6 项的审查清单
      报告档（其余维度只统计不判 FAIL，供存量工单与记分卡用）。
    """
    heads = list(re.finditer(r"^#{3,4}\s*\d+[\.、]\s*(.+)$", seg, re.M))
    titles = [h.group(1).strip() for h in heads]
    bodies = []
    for i, h in enumerate(heads):
        end = heads[i + 1].start() if i + 1 < len(heads) else len(seg)
        bodies.append(seg[h.end():end])
    hit, cls_of = [], []
    for t in titles:
        c = None
        for name, pat in VIB_CLASSES:
            if re.search(pat, t):
                c = name
                break
        cls_of.append(c)
        if c and c not in hit:
            hit.append(c)
    by = {}
    for c, b in zip(cls_of, bodies):
        if c and c not in by:
            by[c] = b
    r1 = by.get("真实需求", "")
    r2 = by.get("现状勘察", "")
    r3 = by.get("方案比较", "")
    r4 = by.get("增量实现", "")
    r5 = by.get("提示词", "")
    r6 = by.get("产出后审查", "")
    r7 = by.get("验证反馈循环", "")
    r8 = by.get("最终沉淀", "")
    tables = [m.group(0).strip().count("\n") + 1
              for m in re.finditer(r"(?:^\|.*\|\s*$\n?)+", seg, re.M)]
    labels = len(vib_prompt_segments(r5))
    r6_tbl = [m.group(0).strip().count("\n") + 1
              for m in re.finditer(r"(?:^\|.*\|\s*$\n?)+", r6, re.M)]
    # 审查清单可以是表、编号列表、或 `- [ ]` 勾选项——三种都算（实测误报来源：
    # 早期批次用 `- [ ] …？` 勾选式清单，只数表格会把 9 项清单判成 0 项）
    r6_list = (len(re.findall(r"^\s*\d+[\.、)]\s", r6, re.M))
               + len(re.findall(r"^\s*[-*]\s", r6, re.M)))
    audit_items = max(r6_tbl + [r6_list] or [0])
    return dict(
        titles=titles, hit=hit,
        miss_class=[n for n, _ in VIB_CLASSES if n not in hit],
        labels=labels,
        design=bool(re.search(
            r"设计要点|设计说明|八段结构对照|为什么这么写|为什么这样写|为什么给|"
            r"为什么第\s*\d|为何这么写", r5)),
        audit_items=audit_items,
        # 报告档
        r2_prompt="```" in r2,
        r2_items=len(re.findall(r"^\s*\d+[\.、)]\s", r2, re.M)),
        r2_pitfall=len(re.findall(r"不先看|没先看|不看|不确认|不查|不想清楚|不核对|不先确认|不验|翻车|后果是", r2)),
        r3_table=any(m.group(0).strip().count("\n") + 1 >= 3
                     for m in re.finditer(r"(?:^\|.*\|\s*$\n?)+", r3, re.M)),
        r3_reject=bool(re.search(r"为什么不是|不选|落选|否决|不用它|为什么不选", r3)),
        r4_steps=max([m.group(0).strip().count("\n") + 1
                      for m in re.finditer(r"(?:^\|.*\|\s*$\n?)+", r4, re.M)] or [0]),
        r4_bound=bool(re.search(r"不(应)?触碰|不动 |不要动|不改 |禁止改|不引入", r4)),
        r5_rounds=len(re.findall(r"第\s*\d\s*轮|轮\s*\d|turn\s*\d+", r5, re.I)),
        r6_method=bool(re.search(r"怎么查|检查方法|如何查|核对|通过判据|验证方法|依据|落点|grep", r6)),
        r7_rounds=min(len(re.findall(r"现象", r7)), len(re.findall(r"定位|根因", r7)),
                      len(re.findall(r"教训|沉淀", r7))),
        r8_rules=len(re.findall(r"^\s*\d+[\.、)]\s", r8, re.M)),
        # 2.16 报告档新增（§6.2.1 条 1/条 2 的"从零构建"要件）：
        # 既有资产清单——条 1/条 2 里带路径（含行号）的可复用资产条数；
        assets=len(re.findall(r"[\w./\\\-]+\.(?:java|xml|ya?ml|sql|json|properties|md)(?::L?\d+)?",
                              r1 + "\n" + r2 + "\n" + r4)),
        # 企业级约束——条 1 真实需求里的生产环境约束词（降级/限流/幂等/审计/灰度…）。
        enterprise=len(re.findall(r"降级|限流|幂等|审计|灰度|合规|一致性|性能|成本|可观测|超时|重试|回滚|事务", r1)),
    )


# ── 2.20：教材类文件判定（封堵"没有 java 代码块就跳过结构判定"的真空通过） ──
# 血证 H23/H25 同族：判据只在"能识别出对象"时才生效，于是**改变对象的语言或形态就能绕过它**。
# 实测（2026-09-17）：examples/黄金样例-python.md 因无 java 块被当"非教材批"整体跳过结构判定并打印 PASS。
LECTURE_REF_MARKS = ("形态状态", "节选", "已存档")


def _flag_circled_heads(lines):
    return len([l for l in lines if re.match(r"^## [" + CIRCLED16 + r"](?=\s|$)", l)]) >= 3


def _flag_batch_head(lines):
    head = "\n".join(lines[:12])
    return any(k in head for k in ("本批一句话", "本批核心类", "源码依据", "验收结果"))


def _flag_anno(lines):
    return sum(1 for l in lines if L_ANNO.search(l)) >= 5


def _flag_items(lines):
    return any(re.match(r"^#{3,6}\s*6\.\d", l) for l in lines)


def _flag_ext_or_index(lines):
    return (any(re.match(r"^#{3,6}\s*(?:%s\.5|7\.5)" % CIRCLED16[6], l) for l in lines)
            or any(re.match(r"^## 索引", l) for l in lines))


LECTURE_FLAGS = (
    ("带圈一级节标题>=3", _flag_circled_heads),
    ("批头声明（本批一句话/核心类/源码依据/验收结果）", _flag_batch_head),
    ("行号标注 // :Lnn >=5", _flag_anno),
    ("6.x 逐件小节>=1", _flag_items),
    ("7.5 扩展小节或索引节", _flag_ext_or_index),
)


def is_lecture(lines, blocks):
    """2.20：这份 .md 是否**教材类文件**（应判 17 节形态）→ (bool, 依据原文)。

    口径（可机械判定；误报率实测见 SKILL §6.6 的 2.20 行）：
      1. 首屏 15 行内声明了参照物/存档标记（形态状态 / 节选 / 历史版本 / 已存档）→ **报告档**：
         参照物只讲"深度与形态"，拿它当批次判会把语料变成噪音（血证 H10 同族）；
      2. 含 >=5 行 java 代码块 → 教材（沿用 2.19 及以前的老口径）；
      3. 否则按**教材标志**投票：命中 >=3 项即判教材（带圈节标题 / 批头声明 / 行号标注 / 6.x 小节 / 7.5 或索引节）。
         用途：**封堵"换成非 java 语言、或删掉代码块就跳过结构判定"的真空通过**（血证 H23/H25 同族漏洞）。
    """
    # 只在「声明位」识别参照物：前 8 行里以 `>` 或 `# ` 开头的行。防呆：批头模板第 6 行写着
    # 「见 ⑥ 的【历史版本示例】」——按整段扫会把**所有新批次**误判成参照物（本次实测踩到）。
    for _l in lines[:8]:
        if not (_l.startswith(">") or _l.startswith("# ")):
            continue
        for m in LECTURE_REF_MARKS:
            if m in _l:
                return False, "参照物/存档（声明位「%s」）→ 结构判定按报告档走" % m
    if any(b[1] == "java" and len(b[2]) >= 5 for b in blocks):
        return True, "含 >=5 行 java 代码块（老口径）"
    hits = [name for name, fn in LECTURE_FLAGS if fn(lines)]
    if len(hits) >= 3:
        return True, "教材标志命中 %d 项：%s" % (len(hits), "、".join(hits))
    return False, "教材标志命中 %d 项（<3），按普通文档处理" % len(hits)



# ── 2.21：记录类形态（整理批 / 进行中记录 / 草稿） ──
# 为什么单立一类：这类产物**既不该按 17 节判**（它不是教材），也不能没人管——
# 不立判据时它落在"教材标志 <3 → 普通文档"的灰区里，静默逃过一切形态约束（与 H23/H25 同族）。
# 三项要求只约束"记录该自证的东西"：状态与日期（这份东西还有效吗）、未完成项（还剩什么没做）、
# 不冒充成品（带成品批迹就必须标未完成/草稿）。
# 档位沿用 2.19 机制：文件自己声明「判据版本 >= 2.21」才判 FAIL，否则报告档（不追溯存量）。
RECORD_FAIL_SINCE = "2.21"
RECORD_NAME_MARKS = ("整理批", "进行中", "草稿", "WIP", "记录", "续传", "日志")
RECORD_DECL_MARKS = ("记录类", "形态状态：记录")
R3_MARKS = ("未完成", "草稿", "进行中")
_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")


# ── 判据版本的**唯一识别口径**（2.30 修复 · 血证 H27 家族） ─────────────────────
# `⑯` 的规范版本字段是 `**判据版本：v2.30**`；盖章表头写的是 `判据 v2.30`——**同一件事的两种形态**。
# 曾经 `style_scope()` 自带一个只认后者的正则，于是**同一份正文首跑判"报告档"、盖章后升 FAIL 档**：
# 批次49 实录（G-BATCH3 ⓪f 盖章前 REPORT、盖章后 FAIL）导致"盖章前 PASS、盖章后失败"的反复排查。
# "判据只在它能识别的形态上生效 = 最大的绕过口"（H27）——所以版本门只留**这一个来源**：
# `⑯` 段里的版本字段；字段写不出来时才退回宽松 `vX.Y`。core/form/snip/style 四个门全部走它。
VER_FIELD_RE = re.compile(r"判据\s*(?:版\s*本)?\s*[:：]?\s*v?(\d+\.\d+)")
VER_LOOSE_RE = re.compile(r"\bv(\d+\.\d+)\b")


def find_versions(txt):
    """按「规范版本字段优先、宽松 vX.Y 兜底」取版本号列表（可能为空）。"""
    return VER_FIELD_RE.findall(txt) or VER_LOOSE_RE.findall(txt)


def declared_version(lines):
    """全文里最后出现的判据版本（记录类文件没有 16 节，ver_marker 用不了）。"""
    vs = find_versions("\n".join(lines))
    return vs[-1] if vs else None


def declared_at_least(lines, ver):
    v = declared_version(lines)
    if not v:
        return False
    try:
        return float(v) >= float(ver)
    except ValueError:
        return False


def is_record(lines, name=""):
    """是否**记录类文件** → (bool, 依据)。"""
    for m in RECORD_NAME_MARKS:
        if m in (name or ""):
            return True, "文件名含「%s」" % m
    for l in lines[:8]:
        if not (l.startswith(">") or l.startswith("# ")):
            continue
        for m in RECORD_DECL_MARKS:
            if m in l:
                return True, "声明位含「%s」" % m
    return False, "非记录类"


def check_record_shape(lines):
    """记录类三项检查 → 违规说明列表（空 = 通过）。"""
    bad = []
    head = "\n".join(lines[:8])
    if not (re.search(r"状态\s*[:：]", head) or _DATE_RE.search(head)):
        bad.append("R1 缺状态行：首屏 8 行内要写「状态：进行中/已完成/阻塞」或日期 YYYY-MM-DD"
                   "（没有状态与日期，读者无法判断这份记录是否还有效）")
    txt = "\n".join(lines)
    has_kw = any(k in txt for k in ("未完成", "下一步", "待办", "TODO"))
    items = len(re.findall(r"^\s*(?:\d+[.、)]|[-*]\s*\[[ xX]\])\s*\S", txt, re.M))
    if not has_kw or items < 2:
        bad.append("R2 缺「未完成/下一步」清单：需出现关键词且清单 >=2 条（实测关键词 %s、清单 %d 条）"
                   "（记录类的价值就在「还剩什么没做」）" % ("有" if has_kw else "无", items))
    if _flag_circled_heads(lines) and _flag_items(lines):
        if not any(k in head for k in R3_MARKS):
            bad.append("R3 疑似冒充成品：文件同时具备成品批迹（带圈一级节标题 >=3 且含 6.x 逐件小节），"
                       "但状态行没写「未完成/草稿/进行中」——半成品不许按记录类混过去")
    return bad

def _prose_lines(lines):
    """剔除代码围栏内部的那些行（2.22）。

    为什么需要它：`^## ` 节数计数与节标题形态检查原本扫**全文**，而**逐字注入的源码里
    完全可能有 markdown 风格的注释行**。实测（deer-flow 阶段1 批次1，2026-09-16）：
    `Makefile:64` 是分节注释 `## Setup & Diagnosis`，注入后它逐字以 `## ` 开头 →
    节数从 17 变 **18** → ⓪ `[FAIL] 节数 18 ≠ 17`；更隐蔽的是它把 ⑥6.1 的**件段"切断"**了
    （件段边界判据见 2.14：件段不得越过一级节标题），连带使 ⑤ 误报
    「缺【怎么用】/【缺【上下游】」——一个源码注释引发三处误判。

    源码是**逐字注入**的（保真是硬要求），改不了；能改的是"**哪里算正文**"这个判定。
    """
    out, inside = [], False
    for l in lines:
        if re.match(r"^\s*`{3,}", l):
            inside = not inside
            continue
        if not inside:
            out.append(l)
    return out


def check_structure(lines, is_lec):
    """is_lec=True 才判教材批的结构（总览/索引/记录/参照物类文件跳过）"""
    txt = "\n".join(lines)
    prose = _prose_lines(lines)                     # 2.22：节数只在正文里数（围栏内是源码，不是节）
    sec = len([l for l in prose if re.match(r"^## ", l)])
    fences = len([l for l in lines if re.match(r"^\s*`{3,}", l)])
    fence_bad, fence_open = fence_scan(lines)
    # 占位符只在**代码块内**统计（正文里"残留检查：TODO 0"这类描述句不该误报）
    # 2.9 起也认**含中文的 `__占位__`**（填空白骨架/草稿不得冒充达标批，血证 H18）
    inblock, residual = False, 0
    for l in lines:
        if re.match(r"^\s*`{3,}", l):
            inblock = not inblock
            continue
        if inblock and (re.search(r"<<<SRC:|CON" + r"T-|TO" + r"DO|FIX" + r"ME", l) or PLACEHOLDER.search(l)):
            residual += 1
    m = re.search(r"^## ⑫\s", txt, re.M)
    m2 = re.search(r"^## ⑬\s", txt, re.M)
    eight = prompt = selfref = back = 0
    thin = []
    retro = []
    if m:
        seg = txt[m.end(): m2.start() if m2 else len(txt)]
        eight = len(re.findall(r"^#{3,4}\s*\d+[\.、]\s*", seg, re.M))
        bodies = re.split(r"^#{3,4}\s*\d+[\.、]", seg, flags=re.M)[1:]
        for i, b in enumerate(bodies):
            if len([x for x in b.split("\n") if x.strip()]) <= 2:
                thin.append(i + 1)
        prompt = len(re.findall(r"^【[^】]+】", seg, re.M))
        selfref = len(re.findall(r"本批|本阶段|教材第|答案卷|阶段[0-9]|批次[0-9]", seg))
        back = len(re.findall(r"^- 「", seg, re.M))
        # 2.16：回顾语 FAIL 档（§6.2 从零构建视角；词表出处见 VIB_RETRO 注释）
        retro = [(w, seg.count(w)) for w in VIB_RETRO if w in seg]
    # 2.15：节标题规范形态（仅教材批判定；总览/索引类文件无 17 节结构，跳过）
    sec_missing, sec_deformed, sec_heads = ([], [], [])
    if is_lec:
        sec_missing, sec_deformed, sec_heads = section_form_check(prose)
    return dict(sections=sec, fences=fences, residual=residual, eight=eight, prompt=prompt,
                selfref=selfref, back=back, thin=thin, is_batch=is_lec, retro=retro,
                fence_bad=fence_bad, fence_open=fence_open,
                sec_missing=sec_missing, sec_deformed=sec_deformed, sec_heads=sec_heads,
                vib=vib_depth(seg) if m else None)


# ── 检查 ⓪b：每批必含内容（2.17：① 架构图 / ⑦.1 编号调用链 / ⑧ L0-L3 穿透卡） ──
# 血证 H26 同轮（用户要求 6）：这四样从"通常会有"升为"每批必含且可机械检查"。
# 口径全部经过全库实测校准（60 份批次），误报率≈0 才进 FAIL 档：
DIAGRAM_ARROW = re.compile(r"(──|─{2,}|-->|->|=>|→|←|↑|↓|▼|▲|│|├|└|┌|┐|┘|┤)")
DIAGRAM_TOKEN = re.compile(r"\b[A-Z][A-Za-z0-9_]{2,}\b")
# 通用词任何仓库都"找得到"，不算"图中的真实组件"（防呆：没有这层，画三个空盒子写 Service/Mapper 也算过）
DIAGRAM_STOP = {
    "Service", "Controller", "Mapper", "Entity", "Config", "Configuration", "Impl", "DTO", "VO",
    "ServiceImpl", "Manager", "Handler", "Utils", "Util", "Exception", "Request", "Response",
    "Repository", "Component", "Bean", "Autowired", "Override", "String", "Integer", "Long",
    "List", "Map", "Set", "Object", "NULL", "JDK", "API", "HTTP", "HTTPS", "JSON", "URL", "URI",
    "SQL", "OK", "FAIL", "PASS", "TODO",
}
H71_HEAD = re.compile(r"^#{3,5}\s*(?:⑦\.1|7\.1)", re.M)
H72_HEAD = re.compile(r"^#{3,5}\s*(?:⑦\.2|7\.2)", re.M)
HOP_LINE = re.compile(r"^\s*\d+(?:\s+[→\-\S]|[\.、]\s*\S)")   # 编号跳：`1  → …` 或 `1. …`
HOP_LINENO = re.compile(r":L?\d+")                            # 行号：`Some.java:41` 或 `:L41` 都认
OMIT_EQ = re.compile(r"省略了什么|显式省略|省略清单|省略了|砍掉了|不覆盖|未覆盖的|没有实现|未实现|不含")


def _search_any(pat, txt):
    """head_pat/end_pats 既可以是字符串（按 re.M 处理）也可以是已编译正则。"""
    return pat.search(txt) if hasattr(pat, "search") else re.search(pat, txt, re.M)


def _txt_seg(txt, head_pat, *end_pats):
    """截取 `head_pat` 标题之后到第一个 `end_pats` 命中（或下一一级节、或 EOF）的正文。"""
    m = _search_any(head_pat, txt)
    if not m:
        return None
    stops = []
    for ep in end_pats:
        m2 = _search_any(ep, txt[m.end():])
        if m2:
            stops.append(m.end() + m2.start())
    m3 = re.search(r"^## ", txt[m.end():], re.M)
    if m3:
        stops.append(m.end() + m3.start())
    return txt[m.end(): min(stops) if stops else len(txt)]


def _fenced_blocks(seg):
    """段内全部围栏块（任意语言；空语言=text 图也算）"""
    out, cur = [], None
    for l in seg.split("\n"):
        if FENCE_LINE.match(l):
            if cur is None:
                cur = []
            else:
                out.append("\n".join(cur))
                cur = None
            continue
        if cur is not None:
            cur.append(l)
    return out


def check_core_sections(lines, by_class, root):
    """2.17：① 架构图 / ⑦.1 编号调用链 / ⑧ L0-L3 穿透卡 的每批必含检查。

    返回 dict(sec1=, chain=, drill=)，值=None 表示通过，否则为 FAIL 原因原文（可直接打印）。
    """
    txt = "\n".join(lines)
    out = dict(sec1=None, chain=None, drill=None)

    # (a) ① 节：必须有图（围栏块 ≥5 行含连接符/箭头），且图里 ≥3 个标识符能在仓库中找到
    s1 = _txt_seg(txt, r"^## ①\s", r"^## ②\s")
    if s1 is None:
        out["sec1"] = "① 节缺失（找不到 `## ①` 标题——① 必须给盒状/分层全景图，见 §6.4 ①）"
    else:
        blocks = _fenced_blocks(s1)
        dia = [b for b in blocks if sum(1 for l in b.split("\n") if DIAGRAM_ARROW.search(l)) >= 2]
        best = max((sum(1 for l in b.split("\n") if DIAGRAM_ARROW.search(l)) for b in blocks), default=0)
        if best < 5:
            out["sec1"] = ("① 节无架构图：围栏块内含连接符/箭头最多的块也只有 %d 行（<5）"
                           "——必含一张盒状/分层图（``` 围栏 + ≥5 行连接线/箭头）" % best)
        else:
            idx = prose_index(root)
            moddirs = {d for d in os.listdir(root)
                       if os.path.isdir(os.path.join(root, d)) and not d.startswith(".")}
            ids = set()
            for b in dia:
                for w in DIAGRAM_TOKEN.findall(b):
                    if w in DIAGRAM_STOP:
                        continue
                    if w in by_class or re.search(r"\b" + re.escape(w) + r"\b", idx["src"]):
                        ids.add(w)
                for w in re.findall(r"\b[a-z][a-z0-9_-]{2,}\b", b):
                    if w in moddirs:
                        ids.add(w)
            if len(ids) < 3:
                out["sec1"] = ("① 架构图里的真实组件标识符只有 %d 个（<3）：%s"
                               "——图中组件名必须是真实存在的类/模块/中间件名（读者按图索骥要能找到）"
                               % (len(ids), "、".join(sorted(ids)[:5]) or "（一个都没有）"))

    # (b) ⑦.1：≥5 跳编号调用链且每跳带行号（小节标题 `⑦.1`/`7.1` 两种形态都认——存量两种都在用）
    s71 = _txt_seg(txt, H71_HEAD, H72_HEAD)
    if s71 is None:
        out["chain"] = "⑦.1 小节缺失（⑦ 必含五小节之一：编号调用链，每跳带真实类名 + 行号）"
    else:
        hops = [l for l in s71.split("\n") if HOP_LINE.match(l)]
        hops_ln = [l for l in hops if HOP_LINENO.search(l)]
        if len(hops) < 5 or len(hops_ln) < 5:
            out["chain"] = ("⑦.1 编号调用链不达标：编号跳 %d 条 / 其中带行号 %d 条（各需 ≥5）"
                            "——散文式箭头链不算，改写成 `1  → 类.方法()  :Lnn` 的编号跳链"
                            % (len(hops), len(hops_ln)))

    # (c) ⑧：必须出现 L0~L3 四个层级标签，且含"省略了什么生产边界"或等价表述
    s8 = _txt_seg(txt, r"^## ⑧\s", r"^## ⑨\s")
    if s8 is None:
        out["drill"] = "⑧ 节缺失（找不到 `## ⑧` 标题——⑧ 必须给 L0-L3 穿透卡，见 §6.4 ⑧）"
    else:
        lv_miss = [k for k in range(4) if not re.search(r"L%d(?!\d)" % k, s8)]
        if lv_miss:
            out["drill"] = ("⑧ 穿透卡缺层级标签：%s（每张卡必须 L0 证据层→L1 调用链层→L2 手写等价层→"
                            "L3 取舍层 逐级写明）" % "、".join("L%d" % k for k in lv_miss))
        elif not OMIT_EQ.search(s8):
            out["drill"] = ("⑧ 穿透卡缺「省略了什么生产边界」段（L2 手写等价后必带："
                            "分布式锁/持久化/超时治理…哪些被教学版省略——没有这个清单，读者会把玩具实现当生产实现）")
    return out


FORM_FAIL_SINCE = "2.25"      # ⓪d 形态质量 FAIL 档的适用起点（与 ⓪b 的 CORE_FAIL_SINCE 同一套版本门）


def form_scope(lines):
    """2.25：⓪d（② 流水线图 / ⑤ 双清单 / ⑥ 问题开场+要点表+★回放 / ⑭ 完整答案）的适用档位。

    与 core_scope 同口径：批次在 ⑯ 段声明「判据版本 vX.Y」且 X.Y ≥ 2.25 → FAIL 档；
    未声明或更早 → 报告档（存量 33-38 在回修完成前不被追溯，回修后由 sync_gate_result
    写入当前版本即自动从严）。新批由 new_batch.py 落笔即写当前版本 → 一律从严。
    """
    has_v, which, _ = ver_marker(lines)
    if has_v and which:
        try:
            return float(which) >= float(FORM_FAIL_SINCE), which
        except ValueError:
            return False, which
    return False, which


SNIP_FAIL_SINCE = "2.30"      # 2.30：⑥ 可复制性（每件【怎么用】的最小调用 /【怎么接】的最小可编译实现）FAIL 档起点


def snip_scope(lines):
    """2.30：E12/E13 的适用档位（与 form_scope 同款版本门）。

    批次在 ⑯ 声明「判据版本 vX.Y」且 X.Y ≥ 2.30 → FAIL 档；未声明或更早 → 报告档
    （回修后由 sync_gate_result 写入当前版本即自动从严）。
    """
    has_v, which, _ = ver_marker(lines)
    if has_v and which:
        try:
            return float(which) >= float(SNIP_FAIL_SINCE), which
        except ValueError:
            return False, which
    return False, which


def check_form(lines):
    """2.25：⓪d 形态质量检查（§6.4 ②⑤⑥⑭ 必含形态的机械判定，Goodhart 防线）。

    返回 dict(fails=[FAIL 原文…], stats=dict(sec2=, sec5_pen=, sec5_skel=, pieces=,
    no_intro=, no_tbl=, stars=, no_replay=, q=, ans=))。
    判据均从存量高质量批（ragent 批次21/32）正向提取，校准目标：批次20-32 基本全绿
    （29/31 的 ⑤、20 的★回放为已知的模板过渡期真实缺口）、33-38 全红。
    """
    txt = "\n".join(lines)
    fails = []
    stats = dict(sec2=0, sec5_pen=False, sec5_skel=False,
                 pieces=0, no_intro=0, no_tbl=0, stars=0, no_replay=0, q=0, ans=0)

    # (a) ②：纵向 ASCII 流水线图（§6.4 ②：场景开场 + 流水线图每站标批次 + 分支流预告）
    s2 = _txt_seg(txt, r"^## ②\s", r"^## ③\s")
    if s2 is None:
        fails.append("② 节缺失（§6.4 ②：业务场景与端到端闭环——场景开场 + 流水线图 + 分支流预告）")
    else:
        stats["sec2"] = max((sum(1 for l in b.split("\n") if DIAGRAM_ARROW.search(l))
                             for b in _fenced_blocks(s2)), default=0)
        if stats["sec2"] < 3:
            fails.append("② 无业务闭环流水线图（围栏内箭头/连接线最多 %d 行，<3）——§6.4 ② 必含"
                         "「场景开场 + 纵向 ASCII 流水线图（每站标注来源批次）+ 分支流预告」"
                         "（批次33-38 实录：该形态整体丢失，只剩密排长段）" % stats["sec2"])

    # (b) ⑤：双清单（穿透清单表 + 讲解骨架清单表）
    s5 = _txt_seg(txt, r"^## ⑤\s", r"^## ⑥\s")
    if s5 is None:
        fails.append("⑤ 节缺失（§6.4 ⑤：批前两个内部清单）")
    else:
        rows5 = [l for l in s5.split("\n") if l.strip().startswith("|")]
        stats["sec5_pen"] = any(("穿透" in l and "证据" in l) for l in rows5)
        stats["sec5_skel"] = any("业务镜头" in l for l in rows5)
        if not stats["sec5_pen"]:
            fails.append("⑤ 缺「外部调用穿透清单」表（表头须含 穿透/证据 两列）——它决定本批哪些点"
                         "穿透讲、哪些回链已讲批次，缺失 = 回链纪律失守（批次33-38 实录：整表消失）")
        if not stats["sec5_skel"]:
            fails.append("⑤ 缺「讲解骨架清单」表（表头须含 业务镜头 列的九列矩阵）——§5：填完骨架才准写正文")

    # (c) ⑥：每件「要解决的一个问题」开场 + 「逐行要点表」锚 + ★类「逐步回放」（件切分与 check_usage 同款）
    idx = [i for i, l in enumerate(lines) if ITEM_RE.match(l)]
    mask = _prose_mask(lines)
    miss_intro, miss_tbl, miss_replay = [], [], []
    miss_snip, miss_howto = [], []          # 2.30：E12 / E13
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        stops = [j for j in range(i + 1, end) if mask[j] and lines[j].startswith("## ")]
        if stops:
            end = stops[0]
        m = ITEM_RE.match(lines[i])
        if re.search(r"历史版本|已被阶段", m.group(3)):
            continue                                   # 历史版本小节免检（与 ⑤ 用法同口径）
        stats["pieces"] += 1
        seg = lines[i:end]
        body = "\n".join(seg)
        at = m.group(2)
        if "要解决的一个问题" not in body:
            miss_intro.append(at)
        if not any(TBL_ANCHOR.search(l) for l in seg):
            miss_tbl.append(at)
        if "★" in m.group(3):
            stats["stars"] += 1
            if "逐步回放" not in body:
                miss_replay.append(at)
        # 2.30（E12）：每件【怎么用】**段内**须有「可照抄的最小调用」
        #   （段界 = 【怎么用】→ 下一个【上下游】/【怎么接】/【讲解】/下一件；不能拿【怎么接】
        #    里的"最小可编译实现"充数——那正是本条要区分的两件事）
        #   标记形态**两种都认**（2.30 内修正）：`**【怎么用】**` 与存量批的 `【怎么用】`；
        #   段界要求【上下游】/【怎么接】/【讲解】**前面有空行**才算新段 —— 存量批常把它们
        #   紧接着写在【怎么用】的下一行（同段内联），那不是段界，否则【怎么用】段会被误截成半句。
        m_use = re.search(r"^(?:\*\*)?【怎么用】(?:\*\*)?", body, re.M)
        use_seg = ""
        if m_use:
            tail = body[m_use.end():]
            m_end = re.search(r"\n[ \t]*\n[ \t]*(?:\*\*)?【(?:上下游|怎么接|讲解)】(?:\*\*)?"
                              r"|^#{3,6}\s*6\.\d", tail, re.M)
            use_seg = tail[: m_end.start()] if m_end else tail
        if not MINSNIP_RE.search(use_seg):
            miss_snip.append(at)
        # 2.30（E13）：有【怎么接】的件，其中须有「最小可编译实现」
        if "【怎么接】" in body and "最小可编译实现" not in body:
            miss_howto.append(at)
    stats["no_intro"], stats["no_tbl"], stats["no_replay"] = len(miss_intro), len(miss_tbl), len(miss_replay)
    stats["miss_snip"] = miss_snip
    stats["miss_howto"] = miss_howto
    stats["no_snip"] = len(miss_snip)
    if miss_intro:
        fails.append("⑥ %d/%d 件缺「本文件要解决的一个问题」开场（%s）——§6.4 ⑥ 第 1 层：先给问题与"
                     "输入/输出再进代码（批次33-38 实录：全部归零，问题被压进【讲解】第一句）"
                     % (len(miss_intro), stats["pieces"], "、".join(miss_intro[:6])))
    if miss_tbl:
        fails.append("⑥ %d/%d 件缺「逐行要点表」（%s）——§6.1.1 三项密度标准第 2 条：要点表讲控制流/"
                     "数据变化/异常路径，不是重复块内注释（批次36/38 实录：锚整段消失且旧 ⑤ 位置检查空过）"
                     % (len(miss_tbl), stats["pieces"], "、".join(miss_tbl[:6])))
    if miss_replay:
            fails.append("⑥ %d/%d 个★件缺「逐步回放」（%s）——§6.1.1 第 3 条：真实输入 → 每行发生什么 → "
                         "真实输出，含一条失败路径（读者看不到「代码跑起来是什么样」）"
                     % (len(miss_replay), stats["stars"], "、".join(miss_replay[:6])))

    # (d) ⑭：完整答案（A：/答：独立成段）且 ≥10 题
    s14 = _txt_seg(txt, r"^## ⑭\s", r"^## ⑮\s")
    if s14 is None:
        fails.append("⑭ 节缺失（§6.4 ⑭：复习问答）")
    else:
        stats["q"] = len(re.findall(r"\*\*Q\d+|^\s*\d+[\.、]\s*\*\*", s14, re.M))
        stats["ans"] = len(re.findall(r"^\s*(?:\*\*答\*\*|答：|A：|A:)", s14, re.M))
        if stats["q"] < 10:
            fails.append("⑭ 问答仅 %d 题（<10）——§6.4 ⑭：按本批决策点定 10~15 题，覆盖设计动机/"
                         "反面假设/跨批关系/故障推演" % stats["q"])
        if stats["ans"] < stats["q"]:
            fails.append("⑭ 问答退化：完整答案 %d/%d 题——答案须独立成段（A：/答：先行自答），"
                         "只留【钩回】指针 = 读者看不到推理过程（批次34-38 实录：答案实体消失）"
                         % (stats["ans"], stats["q"]))
    return dict(fails=fails, stats=stats)


# ── 检查 ⓪e：结构密度与排版（2.26 · **FAIL 档（声明判据 ≥2.26）**） ──────────
# 判据全部从批次1/2/3（用户钦定高水位）正向提取；校准目标：批次1-19/30 全绿，31/33/34 起按断层红。
STYLE_FAIL_SINCE = "2.26"     # ⓪e E1-E7 的 FAIL 档适用起点（版本门与 ⓪b/⓪d 同款；存量不追溯）
STYLE2_FAIL_SINCE = "2.27"    # ⓪e E8-E10（⑥【讲解】排版 / ⑫ 第2·3条提示词块 / 第5条八段分行）的门
STYLE3_FAIL_SINCE = "2.28"    # ⓪e E11（⑫ 第5条提示词块化与多轮）的门
STYLE4_FAIL_SINCE = "2.29"    # ⓪f 批次3 结构基准门（五项结构硬规则，SKILL §6.1.3 第 9~13 条）的门
S7_KEYS = ("调用链", "数据流", "状态变化", "不变式")      # ⑦ 五小节的关键词（⑦.1-⑦.4）
MINSNIP_RE = re.compile(r"可照抄的最小调用|最小可编译实现|教学合成片段")


def style_scope(lines):
    """返回 (strict_e17, strict_e810, strict_e11, ver)：2.26→E1-E7；2.27→E8-E10；2.28→E11。

    **版本来源与 core/form/snip 三门完全同一个**（`ver_marker` = `⑯` 段的规范版本字段）。
    2.30 修复（批次49 实录）：本函数原先自带一个只认「判据 vX.Y」的正则，识别不了规范字段
    「**判据版本：v2.30**」——
      · 首跑：⑯ 只有规范字段 → 认不出 → ⓪e/⓪f 落"报告档"，结构缺口只报不判红（退出码 0）；
      · 盖章：`sync_gate_result` 写进表头「判据 v2.30」→ 同一份正文被认出来 → 同一批缺口升 FAIL 档。
    结果就是"盖章前 PASS、盖章后失败"，而正文一个字没改。**版本门必须只有一个来源**：
    现在首跑与盖章后口径一致，首跑就报全量错误。
    """
    has_v, which, _ = ver_marker(lines)
    if has_v and which:
        try:
            f = float(which)
            return (f >= float(STYLE_FAIL_SINCE), f >= float(STYLE2_FAIL_SINCE),
                    f >= float(STYLE3_FAIL_SINCE), which)
        except ValueError:
            return False, False, False, which
    return False, False, False, which


def _seg_paras(seg):
    """剥围栏/表格/列表/标题/引用后按空行切段，返回段落字符长度列表（>20 字才计）。"""
    b = re.sub(r"```.*?```", "", seg or "", flags=re.S)
    out, cur = [], []
    for l in b.split("\n"):
        s = l.strip()
        if (not s) or s.startswith("|") or s.startswith("- ") or s.startswith("* ") \
           or s.startswith("#") or s.startswith(">") or re.match(r"^\d+[.、)]\s", s):
            if cur:
                out.append("".join(cur))
                cur = []
            continue
        cur.append(s)
    if cur:
        out.append("".join(cur))
    return [len(p) for p in out if len(p) > 20]


def _bare_fences(seg):
    """状态机统计"开围栏无语言标注"的处数（闭合围栏不计）。"""
    n, inside = 0, False
    for l in (seg or "").split("\n"):
        m = re.match(r"^```(\S*)", l)
        if not m:
            continue
        if not inside:
            inside = True
            if not m.group(1):
                n += 1
        else:
            inside = False
    return n


def check_structure_density(txt):
    """⓪e：返回 dict(fails=[], report=[], stats=dict(...))。

    E1 ⑦ 五小节齐全（调用链/数据流/状态变化/不变式）——批次33-38 被「编号链」偷换只剩 ⑦.1+⑦.5
    E2 ⑫ 行数 ≥180——34-38 仅 114-117（缩水 55%）
    E3 ②④ 单段 ≤300 字——33-38 超 300 字 1-4 段（密排"一大段堆在一起"）
    E4 ①/②/⑦ 内开围栏必须标语言（text/java/…）——33-38 的 ① ② 全裸围栏（渲染无着色）
    E5 ⑩ 反例 ❌ 代码对照块 ≥3 对——31-38 全 0（退化成纯文字清单）
    E6 ③ 教学片段 ≥3 处（全文"可照抄的最小调用"）——报告档
    E7 ④ 深潜小标题 ≥2 个（h4）——报告档
    """
    fails, report = [], []
    st = dict(s7miss="", s12=0, lp2=0, lp4=0, maxpara=0, bare=0, bad10=0, pair10=0,
              snip=0, s4h4=0, jj_max=0, jj_enum=0, p23="0/0", p5="0/8·0", p5f=0)
    s2 = _txt_seg(txt, r"^## ②\s", r"^## ③\s")
    s4 = _txt_seg(txt, r"^## ④\s", r"^## ⑤\s")
    s7 = _txt_seg(txt, r"^## ⑦\s", r"^## ⑧\s")
    s10 = _txt_seg(txt, r"^## ⑩\s", r"^## ⑪\s")
    s12 = _txt_seg(txt, r"^## ⑫\s", r"^## ⑬\s")

    # E1 ⑦ 五小节
    if s7 is None:
        fails.append("⑦ 节缺失（§6.4 ⑦：调用链、数据流、状态变化与边界）")
    else:
        subs = " ".join(re.findall(r"^#{3,4}\s*(.{0,60})", s7, re.M))
        miss = [k for k in S7_KEYS if k not in subs]
        st["s7miss"] = "、".join(miss)
        if miss:
            fails.append("⑦ 五小节不齐：缺 %s（小节标题须含该四关键词；批次33-38 实录：标题被改成"
                         "「编号链」且 ⑦.2/⑦.3/⑦.4 整体消失——⑦.5 独活是因为闸门恰好只查它）" % st["s7miss"])
        # E4 ⑦ 内的图示围栏必须标语言
        nb7 = _bare_fences(s7)
        st["bare"] += nb7
        if nb7:
            fails.append("⑦ 有 %d 处裸围栏（图示须标 ```text——裸围栏渲染无底色，读者看到的是白板）" % nb7)

    # E2 ⑫ 厚度
    if s12 is not None:
        st["s12"] = len(s12.split("\n"))
        if st["s12"] < 180:
            fails.append("⑫ 仅 %d 行（<180）——批次34-38 实录：八条标题在、内容薄（每条 6-23 行 vs 标尺"
                         " 19-51 行），Vibecoding 视角退化成提纲" % st["s12"])

    # E3 ②④ 段落长度
    for tag, seg in (("②", s2), ("④", s4)):
        lens = _seg_paras(seg)
        bad = [x for x in lens if x > 300]
        if lens:
            st["maxpara"] = max(st["maxpara"], max(lens))
        if bad:
            if tag == "②":
                st["lp2"] = len(bad)
            else:
                st["lp4"] = len(bad)
            fails.append("%s 有 %d 段超 300 字（最长 %d）——§6.1.3 排版硬标准：单段 ≤300 字，超了断段；"
                         "批次1/2/3 实测 0 段超标（最长 239）" % (tag, len(bad), max(lens)))

    # E4 ①/② 围栏语言
    for tag, seg in (("①", _txt_seg(txt, r"^## ①\s", r"^## ②\s")), ("②", s2)):
        nb = _bare_fences(seg)
        st["bare"] += nb
        if nb:
            fails.append("%s 有 %d 处裸围栏（图示须标 ```text——渲染无底色即用户可见的「代码块没颜色」）" % (tag, nb))

    # E5 ⑩ 反例对照块
    if s10 is None:
        fails.append("⑩ 节缺失（§6.4 ⑩：失败反例 ❌ 错法 + ✅ 修法）")
    else:
        st["bad10"] = s10.count("❌")
        st["pair10"] = len(re.findall(r"^```", s10, re.M)) // 2
        if st["bad10"] < 3 or st["pair10"] < 3:
            fails.append("⑩ 反例对照块不足（❌=%d / 代码块=%d，须各 ≥3）——批次31-38 实录：❌/✅ 代码对照块"
                         "整体归零、退化成纯文字清单（批次1/2/3=12-14 块、批次30=12 块）"
                         % (st["bad10"], st["pair10"]))

    # ══ E8/E9/E10（2.27 新增 · 门 STYLE2_FAIL_SINCE）══
    s6_ = _txt_seg(txt, r"^## ⑥\s", r"^## ⑦\s")
    # E8 ⑥【讲解】段排版
    if s6_:
        jj = [l.strip() for l in s6_.split("\n") if "【讲解】" in l]
        if jj:
            st["jj_max"] = max(len(x) for x in jj)
        st["jj_enum"] = len(re.findall(r"其一[，,：:]", s6_))
        if st["jj_max"] > 300:
            fails.append("⑥【讲解】段最长 %d 字（>300）——要点挤成一坨（批次33-38 实录 445-958 字；"
                         "标尺批次1-5 = 36-80 字）：其一/其二/其三应**列表化**、每点独立成段"
                         % st["jj_max"])
    # E9 ⑫ 第2·3条提示词块
    if s12 is not None:
        idx12 = [m.start() for m in re.finditer(r"^#{3,4}\s*(\d)\.\s", s12, re.M)]
        def _sub12(k):
            if k - 1 >= len(idx12):
                return ""
            st_ = idx12[k-1]
            en_ = idx12[k] if k < len(idx12) else len(s12)
            return s12[st_:en_]
        n2 = len(re.findall(r"^```", _sub12(2), re.M)) // 2
        n3 = len(re.findall(r"^```", _sub12(3), re.M)) // 2
        st["p23"] = "%d/%d" % (n2, n3)
        if n2 < 1 or n3 < 1:
            fails.append("⑫ 第 2 条现状勘察 / 第 3 条方案比较缺「你发给 AI 的原文」提示词块"
                         "（现各 %d/%d 个；批次1-5 各 1 个）——这两步是**用提示词模拟真实开发动作**的环节，"
                         "没有可复制的原文，读者只能看结论、学不到怎么问" % (n2, n3))
    # E10 ⑫ 第5条八段分行 + 表格
    if s12 is not None and len(idx12) >= 5:
        s5_ = _sub12(5)
        SEGS = ("任务", "依赖", "要新增的类", "核心约束", "注释要求", "验收标准", "禁止", "输出格式")
        seg_hit = sum(1 for nm in SEGS
                      if re.search(r"(?:^【%s】|^%s[：:])" % (re.escape(nm), re.escape(nm)), s5_, re.M))
        tbl5 = len(re.findall(r"^\|\s*[^|\n]+\|", s5_, re.M))
        st["p5"] = "%d/8·%d" % (seg_hit, tbl5)
        if seg_hit < 8 or tbl5 < 8:
            fails.append("⑫ 第 5 条「可直接使用的提示词」排版不达标（八段独立成行 %d/8、表格行 %d）"
                         "——八段（任务/依赖/要新增的类/核心约束/注释要求/验收标准/禁止/输出格式）"
                         "必须**各自独立成行**（段名写 `【任务】` 或 `任务：` 都认），并配「投喂策略」与"
                         "「可复用骨架」两张表（批次1 的 8/8 + 16 行是标尺；批次34-38 实录 0/8——"
                         "八段挤在一个【任务书】段里，读者无法按段复用）"
                         % (seg_hit, tbl5))

    # E11 ⑫ 第5条提示词块化与多轮（2.28）
    if s12 is not None and len(idx12) >= 5:
        s5f = _sub12(5)
        n5f = len(re.findall(r"^```", s5f, re.M)) // 2
        st["p5f"] = n5f
        if n5f < 2:
            fails.append("⑫ 第 5 条提示词未块化 / 未分轮（代码块 %d，须 ≥2）——提示词一律放进 ```text 代码块"
                         "（可复制、观感好），且**按多轮记录**（现实开发是多轮问答：轮1 只勘察禁写码 → "
                         "轮2 只出骨架 → 轮3 实现+自检），每轮一块、标轮次目标 / 期望形态 / 偏差信号" % n5f)

    # E6 ③ 教学片段（报告档）
    st["snip"] = len(MINSNIP_RE.findall(txt))
    if st["snip"] < 3:
        report.append("③ 教学片段「可照抄的最小调用」仅 %d 处（<3）——批次31-38 实录：教学片段整体消失"
                      "（批次1/2/3=9-14 处、批次30=17 处）" % st["snip"])

    # E7 ④ 深潜小标题（报告档）
    if s4 is not None:
        st["s4h4"] = len(re.findall(r"^####\s", s4, re.M))
        if st["s4h4"] < 2:
            report.append("④ 深潜无小节标题（h4=%d，须 ≥2）——批次1/2/3 为 4.1/4.2 带标题深潜；"
                          "批次20-38 实录：深潜压成密排长段（33-38 有 3 段超 300 字）" % st["s4h4"])
    return dict(fails=fails, report=report, stats=st)


# ── 检查 ⓪c：教材自足与构造手法（2.18 · **报告档，不计 FAIL**） ──
# 用户要求 2/4（血证 H26 同轮）：教材必须自足——每段代码/命令前有一句话"这段解决什么"；
# ⑥ 每件要回答"它是怎么被构造出来的、用了什么手法"。先实测命中率再定是否升 FAIL。
INTRO_CJK = re.compile(r"[一-鿿]")          # 行内含中文字符
CONSTRUCT_RE = re.compile(
    r"new\s|注入|构造|@Autowired|@Bean|装配|注册|生命周期|单例|工厂|实例化|创建时机|何时创建|谁来创建")
TECHNIQUE_RE = re.compile(r"模式|数据结构|算法|权衡|取舍|套路|手法|为什么这样设计|设计选择")


def check_batch3_structure(txt):
    """⓪f：批次3 结构基准五项（2.29 新增）。返回 dict(fails=[], report=[], stats=dict(...))。

    判据 = SKILL §6.1.3 第 9~13 条（用户钦定 ragent 阶段1批次3 为结构基准；血证 = b38 五处结构差）。
    """
    fails, report, st = [], [], dict(f_taskbook=None, f71=None, f4="", five=0, p2=99,
                                     fzl=0, up_tab=0, items=0)
    lines = txt.split("\n")

    def sec(a, b):
        m = re.search(a, txt, re.M)
        if not m:
            return None
        m2 = re.search(b, txt[m.end():], re.M)
        return txt[m.end(): m.end() + (m2.start() if m2 else len(txt) - m.end())]

    # F1 ⑫.5 八段任务书 fenced（首个【任务】/任务：行须已在围栏内）
    s5 = sec(r"^#{3,4} 5\. 可直接使用的提示词", r"^#{3,4} 6\. ")
    if s5:
        idx = None
        depth = 0
        for i, l in enumerate(s5.split("\n")):
            fm = re.match(r"^```(\S*)", l)
            if fm:
                depth = depth + 1 if not depth else 0
            if re.match(r"^(【任务】|任务：)", l) and idx is None:
                idx = i
                st["f_taskbook"] = (depth == 1)
        if st["f_taskbook"] is False:
            fails.append("⑫ 第 5 条八段任务书未 fenced ` ```text `（段名在行首 ≠ 各自成段——b38 事故：无空行渲染成巨块）；"
                         "等价形态 = 多轮递进块（提示词全 fenced + 八段骨架表）")
    else:
        fails.append("⑫ 第 5 条小节缺失（可直接使用的提示词）")

    # F2 ⑦.1 fenced
    s71 = sec(r"^#### ⑦\.1 调用链", r"^#### ⑦\.2")
    if s71 is None:
        fails.append("⑦.1 调用链小节缺失")
    else:
        st["f71"] = ("```text" in s71) and not re.search(r"^\d+\.\s*→", s71, re.M)
        if not st["f71"]:
            fails.append("⑦.1 调用链未 fenced ` ```text `（b38 事故：markdown 编号列表渲染无底色、行宽参差）；"
                         "链尾应有「怎么读懂这条链」段")

    # F3 ④ 标题 + 五段式标注
    s4 = sec(r"^## ④ ", r"^## ⑤ ")
    if s4 is None:
        fails.append("④ 节缺失")
    else:
        h4 = re.search(r"^## ④ (.+)$", s4, re.M)
        if h4 and "新概念白话解释" not in h4.group(1):
            fails.append("④ 标题应为「新概念白话解释」（现：%s）——概念表 + 五段式深潜，不是密排长段" % h4.group(1).strip())
        st["five"] = sum(1 for k in ("**是什么**", "**解决什么问题**", "**不用它会怎样**", "**代价**")
                         if k in s4)
        n4 = len(re.findall(r"^####\s*4\.\d", s4, re.M))
        if st["five"] < 4 or n4 < 2:
            fails.append("④ 深潜五段式标注不足（是什么/解决什么问题/不用它会怎样/代价 命中 %d/4，#### 4.x = %d 个）"
                         "——五段：是什么 / 解决什么问题 / 不用它会怎样 / 本批的具体用法 / 代价" % (st["five"], n4))

    # F4 ② 段落数 ≤8 + 分支流预告
    s2 = sec(r"^## ② ", r"^## ③ ")
    if s2 is None:
        fails.append("② 节缺失")
    else:
        plain = [p for p in re.split(r"\n\s*\n", s2)
                 if len(p.strip()) > 20 and not p.strip().startswith(("|", "```", "-", "#"))]
        st["p2"] = len(plain)
        if len(plain) > 8:
            fails.append("② 散文段落 %d > 8（b38 事故：23 段——闭环 A/B/C/D 细节的归宿是 ⑦.2/⑦.3/⑦.4 与 ⑩，不留在 ②）；"
                         "形态 = 场景开场 / 完整闭环（单主线图）/ 分支流预告 三块" % len(plain))
        if not re.search(r"分支流预告", s2):
            fails.append("② 缺「分支流预告」（标签 + 逐支 bullet 带行号）")

    # F5 ⑥ 每件 边界与副作用 + 上下游表格
    s6 = sec(r"^## ⑥ ", r"^## ⑦ ")
    if s6:
        heads = [(mm.start(), mm.group(0)) for mm in re.finditer(r"^#{3,4} 6\.\d[\s\S]", s6, re.M)]
        for k, (pos, h) in enumerate(heads):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(s6)
            body = s6[pos:end]
            if "```java" not in body and "```\n" not in body:
                continue
            st["items"] += 1
            if "边界与副作用" not in body:
                fails.append("6.x 缺「边界与副作用」三 bullet（边界/副作用/风险点）：%s" % h.strip()[:46])
            if "【上下游】" in body and "| 方向 |" not in body:
                fails.append("⑥【上下游】散段 → 应为两行表格（方向/谁/给拿什么形态/失败时看到什么）：%s"
                             % h.strip()[:46])
    return dict(fails=fails, report=report, stats=st)


def check_pedagogy(lines, blocks):
    """返回 dict(blocks_total=, blocks_no_intro=, items_total=, items_no_construct=, items_no_technique=)。

    A 白话开场：围栏块上方 4 行内（跳过空行）应有一行"像样的中文开场"——含中文、不是表格行、
      不是另一道围栏。表格行紧挨代码块的情况（如 ⑦.5 表后的步骤块）不算缺——表格本身就是说明。
    B 构造方式与手法：按 ⑥ 的 6.x 件切分（与 check_usage 同样的越节保护），逐件统计是否点名
      构造方式（new/注入/装配/生命周期…）与实现手法（模式/数据结构/算法/权衡…）。
    """
    blocks_total = blocks_no_intro = 0
    for b in blocks:
        st0 = b[0]                   # 首个代码行的 1 基行号 → 开围栏行的 0 基下标 = st0-2
        blocks_total += 1
        ok = False
        j = st0 - 3                  # 从开围栏的上一行（0 基）往上找
        seen = 0
        while j >= 0 and seen < 4:
            l = lines[j].strip()
            if not l:
                j -= 1
                continue
            seen += 1
            if l.startswith("|"):      # 表格行：表格本身就是这段的说明，不算缺开场
                ok = True
                break
            if INTRO_CJK.search(l):    # 含中文的一行（标题/要点/开场句都算——只查"有没有"，不查"好不好"）
                ok = True
            break
        if not ok:
            blocks_no_intro += 1

    idx = [i for i, l in enumerate(lines) if ITEM_RE.match(l)]
    items_total = items_no_construct = items_no_technique = 0
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        # 2.23：只在**正文行**上认一级节标题（围栏内的 `## ` 是源码，不是节边界）
        stops = [j for j in range(i + 1, end) if lines[j].startswith("## ")]
        if stops:
            end = stops[0]
        body = "\n".join(lines[i:end])
        items_total += 1
        if not CONSTRUCT_RE.search(body):
            items_no_construct += 1
        if not TECHNIQUE_RE.search(body):
            items_no_technique += 1
    return dict(blocks_total=blocks_total, blocks_no_intro=blocks_no_intro,
                items_total=items_total,
                items_no_construct=items_no_construct, items_no_technique=items_no_technique)


# ── 检查 ⑥：散文符号真实性（⓪~⑤ 之外最容易漏的一类错误：正文里提到的东西根本不存在） ──
# 血证 H16：批次1 的 ⑫ 整段描述了从未实现过的类/方法（ListItemBlock / MarkdownVisitor /
# ParseProfile.of …），六组全绿——因为 ① 只管代码块，正文一个字都不查。
# 判据取舍依据实测：**只留误报率≈0 的三条**——
#   R1  `Xxx.java:NN` 引用 → 文件必须存在且行号在范围内        （全库实测 0 处误报）
#   R4  件标题里声明的 `Xxx.java` 必须存在                     （78 文件 / 185 件标题实测 0 处）
#   R2''`本仓类.method(` → 方法名必须在本仓任意源码里出现过      （实测 2 处，1 真错 1 同名碰撞）
# R3（反引号里的 CamelCase 符号是否存在）**实测 371 处里 ~95% 是合法提及**——
#   第三方库类型（RedisTemplate/AsyncContext/各 *Exception）、教学示例类（Tiny*/Mini*/Immutable*）、
#   以及"本仓尚未实现"的规划名（MilvusVectorStoreService 等）。因此 **降级为报告清单，不判 FAIL**；
#   白名单见 spec/散文符号白名单.txt，稳定后再考虑升级。
PROSE_CALL = re.compile(r"`([A-Z][A-Za-z0-9_]*)\.([a-zA-Z][A-Za-z0-9_]*)\(")
PROSE_FILE = re.compile(r"`?([A-Za-z0-9_]+\.java)[:：](\d+)(?:-(\d+))?`?")
PROSE_TITLE = re.compile(r"^#{3,6}\s*6\.\d[\d\.]*\s*.*?`([A-Za-z0-9_]+\.java)`")
PROSE_CAMEL = re.compile(r"`([A-Z][a-z][A-Za-z0-9_]{1,})`")
_PROSE = {}


def prose_index(root):
    """惰性构建：文件名→路径 / import 过的外部类型 / 全部源码文本（判"方法名是否出现过"）"""
    if _PROSE:
        return _PROSE
    files, imported, srcs = {}, set(), []
    for dp, dn, fns in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in fns:
            if not fn.endswith((".java", ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".go", ".rs", ".sh", ".bash")):
                continue
            p = os.path.join(dp, fn)
            files.setdefault(fn, p)
            # 2.24 健壮性加固（非判据变更）：个别环境会瞬时吞文件（OSError Errno 2/9，
            # deer-flow 实测批次22 闸门 3 跑 2 崩在 open()）。与 load_snapshot 同款修法：
            # 失败重试一次（读操作幂等）；两次仍失败则保留路径登记（R1/R4 仍可见），
            # 只跳过正文并显式警告——缩小 src 只可能让 ⑥ 更严（假 FAIL 可复跑），
            # 不存在"识别不到就放过"的真空通过，也绝不让闸门崩。
            t = None
            for _attempt in range(2):
                try:
                    t = open(p, encoding="utf-8", errors="replace").read()
                    break
                except OSError as _e:
                    if _attempt == 0:
                        print("  ⚠️ prose_index 读取失败，重试：%s（%s）" % (p, _e), file=sys.stderr)
                    else:
                        print("  ⚠️ prose_index 两次读取失败，跳过该文件正文（路径仍登记）：%s（%s）" % (p, _e), file=sys.stderr)
            if t is None:
                continue
            srcs.append(t)
            if fn.endswith(".java"):
                for m in re.finditer(r"^import\s+(?:static\s+)?([\w.]+);", t, re.M):
                    imported.add(m.group(1).split(".")[-1])
            elif fn.endswith(".py"):
                for m in re.finditer(r"^\s*(?:import|from)\s+([\w.]+)", t, re.M):
                    imported.add(m.group(1).split(".")[-1])
            elif fn.endswith((".ts", ".tsx", ".js", ".jsx", ".mjs")):
                for m in re.finditer(r"(?:import\s+[^'\"]*from\s*|import\s+)['\"]([^'\"]+)['\"]", t):
                    imported.add(m.group(1).split("/")[-1])
    _PROSE.update(files=files, imported=imported, src="\n".join(srcs))
    return _PROSE


def load_prose_whitelist():
    """spec/散文符号白名单.txt：一行一条；`#` 开头为注释；支持 `前缀*` 通配"""
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "spec", "散文符号白名单.txt")
    rules, exact = [], set()
    if os.path.exists(p):
        for l in open(p, encoding="utf-8"):
            l = l.strip()
            if not l or l.startswith("#"):
                continue
            if l.endswith("*"):
                rules.append(l[:-1])
            else:
                exact.add(l)
    return rules, exact


def check_prose(lines, by_class, root):
    """⑥ 散文符号真实性（只扫代码围栏之外的行）

    返回里除违规清单外还带**核验对象计数**（`n1/n2/n4/n3`，方案 §3.4 要求"适用性/对象数"可判）：
    r1/r2/r4 只装违规，看它们数不出"到底核对了多少个引用"——也就无法区分"全对"与"一个都没查"。
    """
    idx = prose_index(root)
    wl_prefix, wl_exact = load_prose_whitelist()
    r1, r2, r4, r3 = [], [], [], []
    n1 = n2 = n3 = n4 = 0
    inside = False
    for i, l in enumerate(lines):
        if FENCE_LINE.match(l):
            inside = not inside
            continue
        if inside:
            continue
        n = i + 1
        m = PROSE_TITLE.match(l)
        if m:
            n4 += 1
            if m.group(1) not in idx["files"]:
                r4.append((n, "件标题声明的 %s 不存在" % m.group(1)))
        for mm in PROSE_FILE.finditer(l):
            n1 += 1
            f, a, b = mm.group(1), int(mm.group(2)), mm.group(3)
            if f not in idx["files"]:
                r1.append((n, "无此文件 %s" % f))
                continue
            tot = len(open(idx["files"][f], encoding="utf-8", errors="replace").read().split("\n"))
            if a > tot or (b and int(b) > tot):
                r1.append((n, "%s:%s 越界（该文件共 %d 行）" % (f, mm.group(2) + ("-" + b if b else ""), tot)))
        for mm in PROSE_CALL.finditer(l):
            cls, meth = mm.group(1), mm.group(2)
            if cls not in by_class:
                continue
            n2 += 1
            if not re.search(r"\b" + meth + r"\b", idx["src"]):
                if (cls + "." + meth) in wl_exact:
                    continue
                r2.append((n, "%s.%s() —— 全仓源码里没有 %s 这个方法" % (cls, meth, meth)))
        for mm in PROSE_CAMEL.finditer(l):
            s = mm.group(1)
            n3 += 1
            if s in by_class or s in idx["imported"] or s in wl_exact:
                continue
            if any(s.startswith(x) for x in wl_prefix):
                continue
            if re.search(r"\b" + s + r"\b", idx["src"]):
                continue
            r3.append((n, s))
    return dict(r1=r1, r2=r2, r4=r4, r3=r3, n1=n1, n2=n2, n3=n3, n4=n4)


# ── 检查 ⑤：用法与接入（⑥ 每件的调用现场 / 上下游 / 实现注册 + 批级 ⑦.5 扩展路径） ──
ITEM_RE = re.compile(r"^(#{3,6})\s*(6\.\d[\d\.]*)\s*(.*)$")
TBL_ANCHOR = re.compile(r"逐行要点表|^\|\s*行\s*\|")   # 2.7：⑤ 的定位锚——「怎么用」必须排在它之后
USE_MARKS = ("【怎么用】", "【调用现场】")
WIRE_MARKS = ("【怎么接】", "【实现与注册】")
IO_MARKS = ("【上下游】", "【上下游契约】")

# ⑫ 的八类语义（判据 2.11 / §6.2.1）+ 八段提示词的八个标签。
# 只匹配"语义"，不匹配"标题措辞"——同一件事写成"现状勘察"或"代码勘察"都算，
# 但写成"依赖（上游接口与既有代码）"不算（那是"谁给我什么"，不是"我该先读什么、不读会怎样"）。
VIB_CLASSES = (
    ("真实需求", r"真实需求|需求澄清|真实开发任务"),
    ("现状勘察", r"现状勘察|代码勘察|勘察"),
    ("方案比较", r"方案比较|选型"),
    ("增量实现", r"增量实现|拆分"),
    ("提示词", r"提示词|提示模板"),
    ("产出后审查", r"审查"),
    ("验证反馈循环", r"反馈循环|迭代过程|反馈"),
    ("最终沉淀", r"沉淀|可迁移|教训|踩过的坑"),
)
VIB_LABELS = ("【任务】", "【依赖】", "【要新增的类】", "【核心约束】",
              "【注释要求】", "【验收标准】", "【禁止】", "【输出格式】")
# 八段的"段名"识别：同一段写成 `【任务】` 或 `任务：` 都算——**只认一种写法就是把"形式"当"实质"**，
# 会把成型的中式标签提示词（`任务：/背景：/约束：/验收标准：/输出格式：`）误判成"没有骨架"。
VIB_SEG = (("任务", r"任务|目标"),
           ("依赖", r"依赖|背景|已有|上游"),
           ("要新增的类", r"要新增的类|新增类|要新增|文件清单|产出物"),
           ("核心约束", r"核心约束|约束|红线|必须遵守"),
           ("注释要求", r"注释要求|注释|代码注释"),
           ("验收标准", r"验收标准|验收|测试要求|测试约束"),
           ("禁止", r"禁止|反例|不要"),
           ("输出格式", r"输出格式|输出|交付格式"))

# 2.16（血证 H26 / §6.2 从零构建视角）：⑫ 的「回顾语」黑名单——
# 以"已有该批成果"为前提的回顾表述一律 FAIL（自指禁令管"指称"，这条管"时态"）。
# 词表按全库实测给全（60 份批次的 ⑫ 段逐一过目上下文）：
#   回顾性重构 33 处 / 26 文件、回顾性重建 7 处——全部是旧框架的声明/标注形态，
#   否定语境（"不是回顾性重构"这类反用）实测 0 处 → 误报 0；
#   其余 12 词实测 0 命中（提示词原列词 + 同族变体），列入防回潮。
# 注意排除项：「逆向重建」是 §6.2.3 规定的合规声明用词，不在此列；
# 「当时的」出现在合规声明"不是当时的真实对话"里，也不在列。
VIB_RETRO = ("回顾性重构", "回顾性重建",
             "本批已实现", "本批已经实现", "本批的代码", "本批代码", "本批实现",
             "回看这一批", "当时我们", "已经写完", "回述", "事后重建", "复刻出", "那一批")


def vib_prompt_segments(r5):
    """第 5 条里识别出的提示词段名集合（两种写法都认）。"""
    hits = set()
    for name, pat in VIB_SEG:
        if re.search(r"【\s*(?:%s)\s*】" % pat, r5):
            hits.add(name)
    for m in re.finditer(r"^\s*([^\n【】:：]{1,12}?)\s*[:：]", r5, re.M):
        lab = m.group(1)
        for name, pat in VIB_SEG:
            if re.fullmatch(pat, lab):
                hits.add(name)
    return hits
IFACE_RE = re.compile(r"^\s*(?:public\s+|abstract\s+|sealed\s+|static\s+)*(?:interface|abstract\s+class)\s+\w+")
EXT_HEAD_RE = re.compile(r"^#{3,6}\s*(?:⑦\.5|.*(?:扩展与接入|接入与扩展|扩展路径))")


def ver_marker(lines):
    """2.10（**报告项，不计 FAIL**）：⑯ 段有没有写明判据版本 → 返回 (是否标过任何版本, 标的版本, 是否当前版)。

    两问分开的用意：**"从没标过"才是真缺陷**（⑯ 里的数字没人知道按哪版跑的，血证 H15 就是复述旧结论）；
    "标了但不是当前版"只是**提示复核**——判据每升一版就让所有旧标注变成"不达标"是跑步机，不是质量。
    实测：78 份里 6 份写过版本；升到 2.10 后那 6 份也变"非当前版"——正说明两问必须分开。"""
    txt = "\n".join(lines)
    m = re.search(r"^## ⑯", txt, re.M)
    if not m:
        return False, None, False
    seg = txt[m.start():]
    vs = find_versions(seg)
    return bool(vs), (vs[-1] if vs else None), GATE_VERSION in seg


CORE_FAIL_SINCE = "2.18"     # ⓪b 三项 FAIL 档的**适用起点**：只有自我声明判据版本 ≥ 本值的批次才从严


def core_scope(lines):
    """2.19：⓪b（① 架构图 / ⑦.1 编号链 / ⑧ 省略段）的**适用档位** → (是否判 FAIL, 声明的版本或 None)。

    为什么必须加这个开关（血证 H26 同轮，用户 2026-09-17 指令"按建议改一下那个 FAIL 档"）：
      2.17 把这三项从"通常会有"直接升为 FAIL，而全库 78 份里只有 6 份写过判据版本——
      拿一条**新判据去追溯旧产物**，结果是 60 份里的 12 份由绿转红、"绿"被清零；
      这与 2.10（⑯ 版本标注）与 2.11（ 深度）两次的处置原则冲突：
      那两次都是**先做报告档、实测误报率、清完存量再议升级**，而不是让旧产物为新风向买单。

    口径（可机械判定、不靠人记）：
      - 批次在 ⑯ 段声明了「判据版本 vX.Y」且 X.Y ≥ 2.18 → 三项按 FAIL 判；
      - 未声明版本、或声明更早 → 三项降**报告档**（[报告] 前缀 + 数字照打，进 gate_all 记分卡）；
      - 新批由 `new_batch.py` 落笔即写入当前判据版本 → **新批一律从严**，没有"忘记声明就放松"的后门。
    """
    has_v, which, _ = ver_marker(lines)
    if has_v and which:
        try:
            return float(which) >= float(CORE_FAIL_SINCE), which
        except ValueError:
            return False, which
    return False, which


def _prose_mask(lines):
    """与 `_prose_lines` 同一套围栏跟踪，但返回**与 lines 对齐的布尔掩码**（2.23）。

    为什么需要：`check_usage` 此前用 `lines[j].startswith("## ")` 找件段边界，
    于是**围栏内的源码行**（如 FastAPI description 里的 `## DeerFlow API Gateway`）
    也会被当成一级节标题，把件段提前切断 → 误报「缺【怎么用】/【缺【上下游】」。
    `_prose_lines`（2.22）已记录过同族根因，这里把同一口径用到件段边界上。
    """
    mask, inside = [], False
    for l in lines:
        if re.match(r"^\s*`{3,}", l):
            mask.append(False)
            inside = not inside
            continue
        mask.append(not inside)
    return mask


def check_usage(lines):
    """⑤ 用法与接入：切出每个 6.x 件，检查【怎么用】/【上下游】/（抽象件）【怎么接】与批级扩展小节。"""
    idx = [i for i, l in enumerate(lines) if ITEM_RE.match(l)]
    prose_mask = _prose_mask(lines)
    items = []
    for k, i in enumerate(idx):
        end = idx[k + 1] if k + 1 < len(idx) else len(lines)
        # 2.14（血证 H24）：件段**不得越过一级节标题**。原实现里"最后一个 6.x 件"的段一直延伸到
        # 文件末尾——于是 ⑧ 穿透卡 / ⑨ No-Framework / ⑩ 反例里的手写 `interface Xxx {` 骨架与
        # 【怎么接】标记都被算到那个件头上。实测全库：**10 件 iface 误判为真**（该件凭空要多写
        # 【怎么接】）、**6 件 wire 误判为真**（后文有【怎么接】就算它写了）。件段到自己所属一级节
        # 结束为止，这才是"件内"的字面意思。
        # 2.23：只在**正文行**上认一级节标题（围栏内的 `## ` 是源码，不是节边界）
        stops = [j for j in range(i + 1, end) if prose_mask[j] and lines[j].startswith("## ")]
        if stops:
            end = stops[0]
        m = ITEM_RE.match(lines[i])
        seg = lines[i:end]
        body = "\n".join(seg)
        # 2.7 新增：⑤ 在件内的**位置**（顺序错了，读者会把"怎么用"当成下一节的内容）
        u = next((j for j, x in enumerate(seg) if any(mk in x for mk in USE_MARKS)), None)
        pos_bad = []
        if u is not None:
            t = next((j for j, x in enumerate(seg) if TBL_ANCHOR.search(x)), None)
            if t is not None and u < t:
                pos_bad.append("【怎么用】出现在「逐行要点表」之前（:L%d）" % (i + 1 + u))
            r = next((j for j, x in enumerate(seg) if x.strip() == "---"), None)
            if r is not None and u > r:
                pos_bad.append("件内 `---` 出现在【怎么用】之前（:L%d）" % (i + 1 + r))
        items.append(dict(
            no=m.group(2), title=m.group(3).strip()[:52], at=i + 1,
            hist=bool(re.search(r"历史版本|历史快照|已被阶段", m.group(3))),
            iface=any(IFACE_RE.match(l) for l in seg),
            use=any(x in body for x in USE_MARKS),
            wire=any(x in body for x in WIRE_MARKS),
            io=any(x in body for x in IO_MARKS),
            pos_bad=pos_bad))
    ext = [i for i, l in enumerate(lines) if EXT_HEAD_RE.match(l)]
    steps = 0
    if ext:
        seg = "\n".join(lines[ext[0]: ext[0] + 160])
        steps = len(re.findall(r"^\s*\d+[\.、)]\s*\S", seg, re.M))
    return items, dict(at=(ext[0] + 1 if ext else 0), steps=steps)


# ── 主流程 ───────────────────────────────────────────────────────────────
def main():
    global ROOT
    try:                                    # 见 lecture_checks.configure_stdio 的说明：
        import lecture_checks as _LC        # stdout 被重定向时按 GBK 编码会让本脚本崩在打印上
        _LC.configure_stdio()
    except Exception:
        pass
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    lec = os.path.abspath(sys.argv[1])   # 2.24：绝对化——_manifest_for 的 NOTES/_tools 回退依赖绝对形态
    root = "."
    verbose = "--verbose" in sys.argv
    explicit_snap = None
    if "--src" in sys.argv:
        root = sys.argv[sys.argv.index("--src") + 1]
    if "--snapshot" in sys.argv:
        explicit_snap = sys.argv[sys.argv.index("--snapshot") + 1]
    jout = None
    if "--json" in sys.argv:
        jout = sys.argv[sys.argv.index("--json") + 1]
    # `--manifest`：**显式指定本批源码清单**（`batch_manifest.py prepare` 的产物）。
    # 2.30 修复（批次49 实录）：result 的 `source_manifest_sha256` 此前只从「位置契约清单」
    # （`<讲稿名>.blocks.json` 的三个查找位）取——本批没有那个文件 → None，而 `sync_gate_result.py`
    # 的校验拿 `--manifest`（**批次源码清单**）去比 → 永远不等 → ABORT。两个清单不是同一个东西，
    # 名字却一样；现在把话说明白：显式给了 `--manifest` 就用它，并把它与位置契约清单分别记进结果。
    manifest_arg = None
    if "--manifest" in sys.argv:
        manifest_arg = os.path.abspath(sys.argv[sys.argv.index("--manifest") + 1])
        if not os.path.isfile(manifest_arg):
            print("找不到源码清单（--manifest）：", manifest_arg)
            return 2
    ROOT = os.path.abspath(root)

    if not os.path.isfile(lec):
        print("找不到讲解文件：", lec)
        return 2
    lines, blocks = parse_blocks(lec)
    by_class, rev_index = index_sources(ROOT)

    sha, how = resolve_snapshot(lines, explicit_snap)
    snap_ok = load_snapshot(sha) if sha else False

    print("=" * 96)
    print("批次讲解闸门（§6.4 C 组）v%s:" % GATE_VERSION, os.path.basename(lec))
    print("源码根目录:", ROOT)
    _hdr_loc = _manifest_path_for(lec)
    _hdr_mp = manifest_arg or _hdr_loc
    if not _hdr_mp:
        _hdr_txt = ("**无**（位置契约清单 `<讲稿名>.blocks.json` 不在三个查找位；"
                    "①p/②p/④p 走归属级报告档）")
    else:
        _hdr_txt = "%s（%s）" % (_hdr_mp, "`--manifest` 显式指定" if manifest_arg else "位置契约清单")
    print("源码清单: %s" % _hdr_txt)
    if sha:
        print("源码快照: %s（%s）%s" % (sha, how, "" if snap_ok else "  ⚠️ 读取失败，退回只比当前树"))
    else:
        print("源码快照: 未声明（批头应写「源码依据：commit <sha>」）→ 无法区分「源码演进」与「编造」")
    print("=" * 96)

    # ⓪ 结构（A 组）
    is_rec, rec_why = is_record(lines, os.path.basename(lec))
    if is_rec:
        is_lec, lec_why = False, "记录类文件（%s）→ 按记录类形态判，不判 17 节" % rec_why
    else:
        is_lec, lec_why = is_lecture(lines, blocks)
    st = check_structure(lines, is_lec)
    print("\n⓪ 结构（A 组 · §6.4 三十六节规范 + ⑫ 形态）")
    print("   教材判定：%s —— %s" % ("是" if is_lec else "否", lec_why))
    s_reasons = []
    if not st["is_batch"]:
        print("   （非教材文件：跳过结构判定；口径见 2.20 的教材标志投票 + 参照物豁免）")
        if is_rec:
            # 2.21：记录类形态（版本门控：声明 >= 2.21 才判 FAIL）
            _strict = declared_at_least(lines, RECORD_FAIL_SINCE)
            _rec_bad = check_record_shape(lines)
            print("   记录类形态（v%s · %s）" % (GATE_VERSION,
                  ("FAIL 档（本文件声明判据版本 >= %s）" % RECORD_FAIL_SINCE) if _strict
                  else ("报告档（未声明判据版本 >= %s，不追溯存量）" % RECORD_FAIL_SINCE)))
            for _r in _rec_bad:
                print(("   [FAIL] " if _strict else "   [报告] ") + _r)
            if not _rec_bad:
                print("   R1 状态行 / R2 未完成或下一步清单 / R3 不冒充成品 → 齐")
            if _strict:
                s_reasons.extend(_rec_bad)
    else:
        if st["sections"] != 17:
            s_reasons.append(f"节数 {st['sections']} ≠ 17（①~⑯ + 索引，§6.4 定义）")
        if st["fences"] % 2:
            s_reasons.append(f"代码围栏 {st['fences']} 个 = 奇数（markdown 语法：有未闭合的块）")
        if st["residual"]:
            s_reasons.append(f"占位符残留 {st['residual']} 处")
        if st["eight"] != 8:
            s_reasons.append(f"⑫ 八条 = {st['eight']} ≠ 8（§6.2.1 定义）")
        if st["prompt"] != 8:
            # 2.11 起不再判 FAIL：这条只数 `^【…】` 行总数，**把形式当实质**——
            # 实测两类误报：① 合法写两份八段提示词的节（阶段10批次2 = 16）被误杀；
            # ② 用中式标签（`任务：/约束：/验收标准：`）写成的成型提示词（阶段13批次2 = 0）被误杀。
            # 改由下面 2.11 的"提示词段"判据（两种写法都认、且只看"有没有骨架"）承担。
            pass
        if st["selfref"]:
            s_reasons.append(f"⑫ 教材自指 {st['selfref']} 处（§6.2 写作视角铁律：必须 0）")
        if st["back"] == 0:
            s_reasons.append("⑫ 无「提问→引出」回链（§6.4 ⑫ 要求 ≥1，常见 4~6）")
        if st["thin"]:
            s_reasons.append(f"⑫ 八条中 {len(st['thin'])} 条内容过薄（≤2 行 = 一句话带过）：第 {st['thin']} 条")
        # 2.16：⑫ 回顾语（血证 H26 / §6.2 从零构建视角）
        if st["retro"]:
            s_reasons.append(
                "⑫ 含「回顾语」：%s——这些都是以「已有该批成果」为前提的回顾表述，违反 §6.2 从零构建视角"
                "（本批功能必须「尚不存在」，叙事从真实需求起步）；请改写为从零构建的开发叙事"
                % "、".join("`%s`×%d" % (w, n) for w, n in st["retro"]))
        v = st.get("vib")
        if v:
            if v["miss_class"]:
                s_reasons.append("⑫ 条目未覆盖这些语义类：%s（§6.2.1 八条：%s）"
                                 % ("、".join(v["miss_class"]),
                                    "、".join(n for n, _ in VIB_CLASSES)))
            if v["labels"] == 0:
                s_reasons.append("⑫ 第 5 条找不到任何提示词段（任务/依赖/约束/验收标准/禁止/输出格式…）"
                                 "——§6.2.1：第 5 条必须给出**可直接使用的完整提示词骨架**，"
                                 "不能只描述『要做什么』")
            if not v["design"]:
                s_reasons.append("⑫ 第 5 条缺「设计要点」（只给一个提示词不算讲完——"
                                 "必须解释这份提示词为什么这么写，读者才学得会而不是只会抄）")
            if v["audit_items"] < 6:
                s_reasons.append("⑫ 第 6 条审查清单只有 %d 项（§6.2.1：≥6 项，"
                                 "且每项要有『怎么查』）" % v["audit_items"])
        for kind, ln, t in st["fence_bad"][:6]:
            s_reasons.append(f"围栏配对：{kind}（:L{ln}  {t}）")
        if len(st["fence_bad"]) > 6:
            s_reasons.append(f"围栏配对：另有 {len(st['fence_bad']) - 6} 处")
        if st["fence_open"]:
            s_reasons.append("围栏未闭合：文件结束时仍处于代码块内（后面的正文全被吞进代码块）")
        # 2.15：节标题规范形态（血证 H25）——找不到段必须是可见的 FAIL
        if st["sec_missing"]:
            s_reasons.append(
                "一级节标题缺失 %d 个：%s——带圈数字丢失或整节不存在；定位正则（如 `^## ⑫`）静默失效，"
                "对应节的全部检查被跳过却照样 PASS"
                % (len(st["sec_missing"]), "、".join("`## %s …`" % c for c in st["sec_missing"])))
        for c, actual in st["sec_deformed"]:
            s_reasons.append(
                "一级节标题形态不规范：期望以 `## %s ` 开头，实际原文 `%s`"
                "（多余/缺失空格会让定位正则静默失效）" % (c, actual[:40]))
        if not s_reasons:
            print(f"   节数={st['sections']} 围栏={st['fences']}(偶/配对OK) 占位={st['residual']} "
                  f"⑫八条={st['eight']} 八段={st['prompt']} 自指={st['selfref']} 回链={st['back']} "
                  f"薄条={len(st['thin'])}")
    v = st.get("vib")
    if v:
        print("   ⑫ 深度（2.11 · FAIL 档）：语义类 %d/8 ｜ 提示词段 %d/8 ｜ 设计要点 %s ｜ 审查清单 %d 项"
              % (len(v["hit"]), v["labels"], "有" if v["design"] else "无", v["audit_items"]))
        if v["labels"] and v["labels"] < 6:
            print("        ↳ 提示词段只成型 %d/8（八段齐全仍是 §6.2.1 要求；本项暂列报告档，"
                  "存量清到 ≤5 份后再升 FAIL）" % v["labels"])
        miss_rep = []
        if not v["r2_prompt"] and v["r2_items"] < 5:
            miss_rep.append("现状勘察既无勘察 prompt 块、编号项也只有 %d<5" % v["r2_items"])
        if v["r2_pitfall"] < 3:
            miss_rep.append("『不先看会怎样』翻车场景 %d<3" % v["r2_pitfall"])
        if not v["r3_table"]:
            miss_rep.append("方案比较无对比表")
        if not v["r3_reject"]:
            miss_rep.append("方案比较无『为什么不是其他方案』")
        if v["r4_steps"] < 6:
            miss_rep.append("增量实现步表 %d<6 行" % v["r4_steps"])
        if not v["r4_bound"]:
            miss_rep.append("缺『不应触碰的边界』")
        if v["r5_rounds"] < 3:
            miss_rep.append("提示词不是多轮序列（轮次标记 %d<3）" % v["r5_rounds"])
        if not v["r6_method"]:
            miss_rep.append("审查项缺『怎么查』")
        if v["r7_rounds"] < 1:
            miss_rep.append("验证反馈循环无完整四段（现象/定位/修正/教训）")
        elif v["r7_rounds"] < 3:
            miss_rep.append("四段迭代只有 %d<3 轮" % v["r7_rounds"])
        if v["r8_rules"] < 5:
            miss_rep.append("最终沉淀 %d<5 条" % v["r8_rules"])
        # 2.16 报告档新增（不计 FAIL）：既有资产清单 ≥3 条带路径 / 真实需求含 ≥1 条企业级约束
        if v["assets"] < 3:
            miss_rep.append("既有资产清单带路径条目 %d<3" % v["assets"])
        if v["enterprise"] < 1:
            miss_rep.append("真实需求无企业级约束词（降级/限流/幂等/审计/一致性…）")
        print("   ⑫ 深度报告档（**不计 FAIL**，供存量工单与记分卡）：%s"
              % ("；".join(miss_rep) if miss_rep else "全部达标"))
    for r in s_reasons:
        print("   [FAIL] " + r)
    if st["sec_missing"] or st["sec_deformed"]:
        print("   实际命中的一级节标题原文（逐条比对带圈数字是否丢失/空格是否变形）：")
        for h in st["sec_heads"][:20]:
            print("     " + h.strip()[:70])
        if len(st["sec_heads"]) > 20:
            print("     …（另有 %d 个）" % (len(st["sec_heads"]) - 20))
    print(f"   → {'PASS' if not s_reasons else 'FAIL'}")

    # ⓪b 每批必含内容（2.17 · §6.4 ①⑦⑧ 从"通常会有"升为"必含可机械判定"）
    core = dict(sec1=None, chain=None, drill=None)
    core_strict, core_ver = core_scope(lines)
    form = dict(fails=[], stats=None)
    form_strict, form_ver = False, None
    if st["is_batch"]:
        core = check_core_sections(lines, by_class, ROOT)
        core_bad = [v for v in core.values() if v]
        mode = ("FAIL 档（本批声明判据版本 v%s ≥ %s）" % (core_ver, CORE_FAIL_SINCE)) if core_strict \
            else ("报告档（本批未声明判据版本 ≥ %s，不追溯旧产物）" % CORE_FAIL_SINCE)
        print("\n⓪b 每批必含内容（v%s · §6.4 ①⑦⑧ · %s）" % (GATE_VERSION, mode))
        for r in core_bad:
            print(("   [FAIL] " if core_strict else "   [报告] ") + r)
        if not core_bad:
            print("   ① 架构图（≥5 连接线 + ≥3 真实标识符）｜⑦.1 编号链（≥5 跳带行号）｜⑧ L0-L3 + 省略段 → 齐")
        if not core_strict:
            print("   ↳ 本批升 FAIL 档的条件：在 ⑯ 段写明「判据版本：v%s」（新批由 new_batch.py 自动落笔）；"
                  "一键补齐：`python scripts/sync_gate_result.py <本文件> --src <仓库根> --apply`" % GATE_VERSION)
        # ⓪c 教材自足与构造手法（2.18 · 报告档，不计 FAIL——先实测命中率，存量清完再议升级）
        ped = check_pedagogy(lines, blocks)
        print("\n⓪c 教材自足与构造手法（2.18 · 报告档，不计 FAIL）")
        print("   代码块白话开场：缺开场 %d/%d 块（每段代码/命令前一句话「这段解决什么」）"
              % (ped["blocks_no_intro"], ped["blocks_total"]))
        if ped["items_total"]:
            print("   ⑥ 件：缺构造方式（谁 new/注入/生命周期）%d/%d 件 ｜ 缺实现手法（模式/数据结构/算法+权衡）%d/%d 件"
                  % (ped["items_no_construct"], ped["items_total"],
                     ped["items_no_technique"], ped["items_total"]))

        # ⓪d 形态质量（2.25 · §6.4 ②⑤⑥⑭ 必含形态——Goodhart 防线，版本门与 ⓪b 同款）
        form = check_form(lines)
        form_strict, form_ver = form_scope(lines)
        fs = form["stats"]
        mode = ("FAIL 档（本批声明判据版本 v%s ≥ %s）" % (form_ver, FORM_FAIL_SINCE)) if form_strict \
            else ("报告档（本批未声明判据版本 ≥ %s，不追溯旧产物；回修后由 sync_gate_result 写入当前版本即从严）" % FORM_FAIL_SINCE)
        print("\n⓪d 形态质量（v%s · §6.4 ②⑤⑥⑭ · %s）" % (GATE_VERSION, mode))
        if fs:
            print("   ②流水线图箭头行=%s ｜ ⑤穿透表=%s 骨架表=%s ｜ ⑥件=%s 问题开场缺=%s 要点表缺=%s ★件=%s 回放缺=%s"
                  " ｜ ⑥最小调用缺=%s ｜ ⑭问答 %s题/完整答 %s"
                  % (fs["sec2"], "有" if fs["sec5_pen"] else "无", "有" if fs["sec5_skel"] else "无",
                     fs["pieces"], fs["no_intro"], fs["no_tbl"], fs["stars"], fs["no_replay"],
                     fs["no_snip"], fs["q"], fs["ans"]))
        else:
            print("   ②⑤⑥⑭ 形态统计 → 齐（② 图 ｜ ⑤ 双清单 ｜ ⑥ 问题开场+要点表+★回放 ｜ ⑭ 完整答案）")
        for r in form["fails"]:
            print(("   [FAIL] " if form_strict else "   [报告] ") + r)
        # 2.30（E12/E13 · ⑥ 可复制性）：每件【怎么用】的最小调用 /【怎么接】的最小可编译实现
        snip_strict, snip_ver = snip_scope(lines)
        snip_bad_n = 0
        for _lst, _tmpl in ((fs["miss_snip"],
                             "⑥ %d/%d 件【怎么用】缺「可照抄的最小调用」（%s）——§6.4 ⑥ 第 6 层："
                             "\"怎么用\"只写\"某处会调用它\"，读者照抄不出一次真实调用；"
                             "须给可直接复制的片段（代码块，标\"教学合成片段\"）"),
                            (fs["miss_howto"],
                             "⑥ %d/%d 件的【怎么接】缺「最小可编译实现」（%s）——接入说明若只有步骤"
                             "没有可编译片段，读者仍需自己猜 API 形状")):
            if _lst:
                print(("   [FAIL] " if snip_strict else "   [报告] ")
                      + _tmpl % (len(_lst), fs["pieces"], "、".join(_lst[:6])))
                if snip_strict:
                    snip_bad_n += len(_lst)
        if not form["fails"] and not snip_bad_n:
            print("   → PASS")
        if not form_strict or not snip_strict:
            _gates = []
            if not form_strict:
                _gates.append("%s（⓪d 形态）" % FORM_FAIL_SINCE)
            if not snip_strict:
                _gates.append("%s（⑥ 可复制性）" % SNIP_FAIL_SINCE)
            print("   ↳ 升 FAIL 档条件：⑯ 写明「判据版本：v%s」（新批由 new_batch.py 自动落笔）；"
                  "一键补齐：`python scripts/sync_gate_result.py <本文件> --src <仓库根> --apply`"
                  % "、v".join(_gates))

    # ⓪e 结构密度与排版（2.26 · §6.4 ⑦⑫⑩③ 结构 + ②④ 排版 + 围栏标注 · FAIL 档）
    sden = check_structure_density("\n".join(lines))
    sd = sden["stats"]
    style_strict, style2_strict, style3_strict, style_ver = style_scope(lines)
    mode = ("FAIL 档（本批声明判据版本 v%s ≥ %s）" % (style_ver, STYLE_FAIL_SINCE)) if style_strict \
        else ("报告档（本批未声明判据版本 ≥ %s，不追溯旧产物；回修后由 sync_gate_result 写入当前版本即从严）" % STYLE_FAIL_SINCE)
    print("\n⓪e 结构密度与排版（v%s · §6.4 ⑦⑫⑩③/②④ · %s）" % (GATE_VERSION, mode))
    print("   ⑦缺小节=%s ｜ ⑫行数=%s ｜ ②④超长段=%s/%s（最长 %s）｜ ①②⑦裸围栏=%s ｜ ⑩❌=%s 块=%s"
          " ｜ ③教学片段=%s（报告）｜ ④深潜h4=%s（报告）"
          % (sd["s7miss"] or "无", sd["s12"], sd["lp2"], sd["lp4"], sd["maxpara"],
             sd["bare"], sd["bad10"], sd["pair10"], sd["snip"], sd["s4h4"]))
    print("   ⑥【讲解】最长段=%s 字（内联枚举 %s）｜ ⑫第2·3条提示词块=%s ｜ ⑫第5条八段=%s ｜ ⑫第5条提示词块数=%s"
          % (sd["jj_max"], sd["jj_enum"], sd["p23"], sd["p5"], sd["p5f"]))
    for r in sden["fails"]:
        if r.startswith("⑫ 第 5 条提示词未块化"):
            _st = style3_strict
        elif r.startswith(("⑥【讲解】", "⑫ 第 2 条", "⑫ 第 5 条")):
            _st = style2_strict
        else:
            _st = style_strict
        print(("   [FAIL] " if _st else "   [报告] ") + r)
    for r in sden["report"]:
        print("   [报告] " + r)
    if not sden["fails"]:
        print("   → PASS")
    if not style_strict:
        print("   ↳ 升 FAIL 档条件：⑯ 写明「判据版本：v%s」；一键补齐："
              "`python scripts/sync_gate_result.py <本文件> --src <仓库根> --apply`" % GATE_VERSION)

    # ⓪f 批次3 结构基准门（2.29 · §6.1.3 第 9~13 条 · FAIL 档由 STYLE4 版本门决定）
    s3s = check_batch3_structure("\n".join(lines))
    st3 = s3s["stats"]
    style4_strict = style_ver is not None and float(style_ver) >= float(STYLE4_FAIL_SINCE)
    mode4 = ("FAIL 档（本批声明判据版本 v%s ≥ %s）" % (style_ver, STYLE4_FAIL_SINCE)) if style4_strict \
        else ("报告档（本批未声明判据版本 ≥ %s，不追溯旧产物；回修后由 sync_gate_result 写入当前版本即从严）" % STYLE4_FAIL_SINCE)
    print("\n⓪f 批次3 结构基准门（v%s · §6.1.3 第 9~13 条 · %s）" % (GATE_VERSION, mode4))
    print("   ⑫.5 任务书fenced=%s ｜ ⑦.1 fenced=%s ｜ ④五段标注=%s/4 ｜ ②段落=%s（≤8） ｜ ⑥件=%s（逐件查边界与副作用/上下游表格）"
          % (st3["f_taskbook"], st3["f71"], st3["five"], st3["p2"], st3["items"]))
    for r in s3s["fails"]:
        print(("   [FAIL] " if style4_strict else "   [报告] ") + r)
    for r in s3s["report"]:
        print("   [报告] " + r)
    if not s3s["fails"]:
        print("   → PASS")
    if not style4_strict:
        print("   ↳ 升 FAIL 档条件：⑯ 写明「判据版本：v%s」；一键补齐："
              "`python scripts/sync_gate_result.py <本文件> --src <仓库根> --apply`" % GATE_VERSION)
    if style4_strict and s3s["fails"]:
        fails_0f = list(s3s["fails"])
    else:
        fails_0f = []

    # ① 正向
    fid = check_fidelity(blocks, by_class, rev_index)
    chk = [r for r in fid if not r["exempt"]]
    tot = sum(r["n_code"] for r in chk)
    # FAIL 基准：有快照时看"两处都没有"的行；无快照时退回"当前树不命中"
    def fail_lines(r):
        if r["lost"] is None:
            return r["n_code"]
        if is_hist(r["sect"], None) and r["snap_lost"] is not None:
            return r["snap_lost"]
        return r["snap_lost"] if r["snap_lost"] is not None else r["lost"]

    lost = sum(fail_lines(r) for r in chk)
    drift = sum((r["lost"] or 0) - (r["snap_lost"] or 0) for r in chk
                if r["lost"] is not None and r["snap_lost"] is not None)
    unattr = [r for r in chk if r["lost"] is None]
    print(f"\n① 正向保真度：{len(chk)} 个代码块 / {tot} 行代码 → 候选不符 {lost} 行 "
          f"= 保真度 {100.0*(tot-lost)/tot if tot else 100:.1f}%  "
          f"{'PASS' if lost == 0 and not unattr else 'FAIL'}")
    if drift:
        print(f"   （其中 {drift} 行属【源码演进】：只在本批快照里命中，当前树已重写——不计 FAIL，但需在小节标题标【历史版本示例】）")
    for r in chk:
        if r["lost"] is None:
            print(f"   ! 无法归属源文件  {os.path.basename(lec)}:{r['start']}  {r['sect']}")
        elif fail_lines(r):
            print(f"   ! 候选不符 {fail_lines(r)}/{r['n_code']} 行  :{r['start']}  {r['sect']}"
                  + ("  【历史版本块，按快照核验】" if r["hist"] else ""))
            print(f"     归属 = {r['cand']}")
            why = "源码与快照里都没有" if r["snap_lost"] is not None else "源码里没有（未声明快照，无法判断是演进还是编造）"
            for s in (r["snap_lost_samples"] or r["lost_samples"]):
                print(f"       {why}: {s[:88]}")
    ex = [r for r in fid if r["exempt"]]
    if ex:
        print(f"   （免检小节 {len(ex)} 个代码块 / {sum(r['n_code'] for r in ex)} 行："
              f"{', '.join(sorted({r['sect'] for r in ex}))[:110]}）")

    # ② 反向
    rev_rows = check_reverse(blocks, lines, by_class)
    print(f"\n② 反向完整度（★类）：{len(rev_rows)} 个★类（★ 标在父标题同样计入）")
    bad_rev = [r for r in rev_rows if r["cov"] < 0.995]
    for r in rev_rows:
        tag = "OK " if r["cov"] >= 0.995 else "FAIL"
        print(f"   [{tag}] {r['cls']:<34} 有效行={r['real']:<4} 缺失={r['miss']:<4} 覆盖={r['cov']*100:.1f}%")
        for s in r["samples"]:
            print(f"          缺失: {s[:82]}")
    print(f"   → {'PASS' if not bad_rev else 'FAIL'}")

    # ③ 密度
    den = check_density(blocks, by_class, rev_index)
    sig = check_sig(blocks, by_class)
    print(f"\n③ 注释密度（§6.1.1）：{len(den)} 个代码块")
    bad_den = []
    for r in den:
        reasons = []
        if r["max_run"] >= 8:
            reasons.append(f"无注释连段 {r['max_run']} 行")
        if r["comments"] < r["need"]:
            reasons.append(f"注释 {r['comments']} < 需 {r['need']}")
        if reasons and not r["exempt"]:
            bad_den.append((r, reasons))
    for r in sig:
        print(f"   [FAIL] ★类方法签名无注释：{r['cls']}（{r['src']}）→ "
              f"{len(r['missing'])} 个：{', '.join(r['missing'][:8])}")
    for r, reasons in sorted(bad_den, key=lambda x: -x[0]["max_run"])[:25]:
        print(f"   [FAIL] :{r['start']:<6} 关键行={r['key_lines']:<4} 注释={r['comments']:<4} "
              f"最长无注释={r['max_run']:<4} {r['sect'][:44]}")
        print(f"          → {'; '.join(reasons)}")
    if len(bad_den) > 25:
        print(f"   ...另有 {len(bad_den)-25} 个不达标块")
    print(f"   → {'PASS' if not (bad_den or sig) else 'FAIL'}")

    # ④ 行号一致性
    ln_all = check_lineno(blocks, by_class, rev_index)
    ln_rows = [r for r in ln_all if r["bad"]]
    print(f"\n④ 行号一致性（`// :Lnn` ↔ 真实行号）：可判定 {sum(r['checked'] for r in ln_all)} 处"
          f" → 漂移 {sum(r['bad'] for r in ln_all)} 处")
    for r in sorted(ln_rows, key=lambda x: -x["bad"])[:15]:
        print(f"   [FAIL] :{r['start']:<6} 漂移 {r['bad']:>3}/{r['checked']:<3}  {r['sect'][:44]}")
        for want, real_no, s in r["samples"]:
            print(f"          标 :L{want} → 实际第 {real_no} 行: {s}")
    if len(ln_rows) > 15:
        print(f"   ...另有 {len(ln_rows)-15} 个块存在行号漂移")
    print(f"   → {'PASS' if not ln_rows else 'FAIL'}")

    # ⑤ 用法与接入
    u_items, u_ext = check_usage(lines)
    u_live = [r for r in u_items if not r["hist"]]
    bad_use = [r for r in u_live if not r["use"]]
    bad_io = [r for r in u_live if not r["io"]]
    iface = [r for r in u_live if r["iface"]]
    bad_wire = [r for r in iface if not r["wire"]]
    bad_pos = [r for r in u_live if r["pos_bad"]]
    bad_ext = (not u_ext["at"]) or u_ext["steps"] < 3
    print(f"\n⑤ 用法与接入（⑥ 每件：调用现场 + 上下游；抽象件：实现与注册；批级 ⑦.5 扩展路径）")
    if not st["is_batch"]:
        print("   （非教材批：跳过用法与接入判定）")
        bad_use = bad_io = bad_wire = bad_pos = []
        bad_ext = False
    else:
        print(f"   逐件={len(u_live)}（另历史版本小节 {len(u_items)-len(u_live)} 个免检）"
              f" 【怎么用】={len(u_live)-len(bad_use)}/{len(u_live)}"
              f" 【上下游】={len(u_live)-len(bad_io)}/{len(u_live)}"
              f" 抽象件={len(iface)} 【怎么接】={len(iface)-len(bad_wire)}/{len(iface)}"
              f" 位置OK={len(u_live)-len(bad_use)-len(bad_pos)}/{len(u_live)-len(bad_use)}"
              f" ⑦.5扩展小节={'有' if u_ext['at'] else '无'}(步骤{u_ext['steps']})")
        for tag, rows in (("缺【怎么用】", bad_use), ("缺【上下游】", bad_io), ("缺【怎么接】", bad_wire)):
            for r in rows[:12]:
                print(f"   [FAIL] {tag}：{r['no']} {r['title']}  （:L{r['at']}）")
            if len(rows) > 12:
                print(f"          ...另有 {len(rows)-12} 个")
        for r in bad_pos[:12]:
            print(f"   [FAIL] ⑤ 位置：{r['no']} {r['title']} → {'；'.join(r['pos_bad'])}")
        if bad_ext:
            why = "缺 ⑦.5 扩展与接入路径小节" if not u_ext["at"] else f"⑦.5 只有 {u_ext['steps']} 条编号步骤（<3）"
            print(f"   [FAIL] {why}（:L{u_ext['at']}）")
    print(f"   → {'PASS' if not (bad_use or bad_io or bad_wire or bad_pos or bad_ext) else 'FAIL'}")

    # ⑥ 散文符号真实性（血证 H16：① 只管代码块，正文提到不存在的类/方法它一个字都不查）
    prose = check_prose(lines, by_class, ROOT)
    p_bad = prose["r1"] + prose["r4"] + prose["r2"]
    print(f"\n⑥ 散文符号真实性（正文里的 文件:行 引用 / 件标题声明的文件 / 本仓类.方法）")
    print(f"   文件:行 引用不成立={len(prose['r1'])} ｜ 件标题文件不存在={len(prose['r4'])}"
          f" ｜ 本仓类.方法 全仓无此方法={len(prose['r2'])} ｜ 反引号符号待确认={len(prose['r3'])}（不计 FAIL）")
    for tag, rows in (("文件:行 引用不成立", prose["r1"]), ("件标题声明的文件不存在", prose["r4"]),
                      ("本仓类.方法 全仓无此方法", prose["r2"])):
        for n, s in rows[:12]:
            print(f"   [FAIL] {tag}：:L{n}  {s}")
        if len(rows) > 12:
            print(f"          ...另有 {len(rows)-12} 处")
    if prose["r3"]:
        seen = []
        for n, s in prose["r3"]:
            if s not in seen:
                seen.append(s)
        print(f"   （待人工确认 {len(prose['r3'])} 处 / {len(seen)} 种符号；多为第三方库类型、教学示例类"
              f"（Tiny*/Mini*/Immutable*）与「本仓尚未实现」的规划名——确认后可加进 spec/散文符号白名单.txt）")
        print(f"    例：{', '.join(seen[:12])}")
    print(f"   → {'PASS' if not p_bad else 'FAIL'}")

    core_bad_n = sum(1 for v in core.values() if v) if (st["is_batch"] and core_strict) else 0
    form_bad_n = len(form["fails"]) if (st["is_batch"] and form_strict) else 0
    if not st["is_batch"]:
        snip_bad_n = 0          # 2.30：非教材文件不判 ⑥ 可复制性（该值只在教材分支里被赋）
    style_bad_n = 0
    if st["is_batch"]:
        for r in sden["fails"]:
            if r.startswith("⑫ 第 5 条提示词未块化"):
                if style3_strict:
                    style_bad_n += 1
            elif r.startswith(("⑥【讲解】", "⑫ 第 2 条", "⑫ 第 5 条")):
                if style2_strict:
                    style_bad_n += 1
            elif style_strict:
                style_bad_n += 1

    # ── 2.24：非 Java 语言实检。档位分界 = 有没有位置契约（manifest）：
    #   manifest 块 → ①位置保真/④行号/②★文件覆盖 全 FAIL 档（位置级，客观可判）；
    #   无 manifest（归属级近似：标题反引号 + 内容匹配）→ 全部报告档（多源拼块/同名歧义下
    #   归属会选错——ragent 批次1 的多 profile yaml 拼块实测误报，故只可见不判红）。
    py_bad = 0
    _man = _manifest_for(lec)
    _man_blocks = {}
    if _man:
        for _b in _man.get("blocks", []):
            _i = _b.get("lecture_block_index")
            if _i is not None:
                _man_blocks[_i] = _b
    _pyord = [(i, b) for i, b in enumerate(blocks) if b[1] in ANNO_LANGS and b[1] != "java"]
    if _pyord or _man_blocks:
        _pybase, _pyrev = _py_index(ROOT)
        _s_pos = _s_lnchk = _s_pbad = _s_lnbad = 0          # 强（manifest）
        _r_pbad = _r_lnbad = _r_unattr = 0                  # 弱（归属，报告档）
        _cov = collections.defaultdict(set)
        _lect_norm_all = set()
        for _i, _b in _pyord:
            for _x in _b[2]:
                _c, _, _ = strip_anno_lang(_x, _b[1])
                _n = norm_code(_c)
                if _n and not CMT_LINE.match(_n):
                    _lect_norm_all.add(_n)
        _lect_ns = [re.sub(r"\s+", "", v) for v in _lect_norm_all]
        for _i, (_start, _lang, _bl, _sect, _h2, _hint, _chain, _mk) in _pyord:
            if is_exempt(_sect, _h2, _mk, _bl):
                continue
            _code = []
            for _x in _bl:
                _c, _, _ = strip_anno_lang(_x, _lang)
                _n = norm_code(_c)
                if _n and not CMT_LINE.match(_n):
                    _code.append(_n)
            if len(_code) < 5:
                continue
            _spec = _man_blocks.get(_i)
            _src_rel = _spec["src"] if _spec else None
            if not _src_rel:
                _hit = _resolve_py_src(_sect, _chain, _hint, _pybase, _pyrev, _code)
                _src_rel = os.path.relpath(_hit, ROOT) if _hit else None
            if not _src_rel:
                _r_unattr += 1
                continue
            _sp = os.path.join(ROOT, _src_rel)
            _sl = src_lines(_sp)
            _lnidx = collections.defaultdict(list)
            for _i3, _l3 in enumerate(_sl, 1):
                _n3 = norm_code(_l3)
                if _n3:
                    _lnidx[_n3].append(_i3)
            for _off, _x in enumerate(_bl):
                _c, _no, _note = strip_anno_lang(_x, _lang)
                _n = norm_code(_c)
                if not _n:
                    continue
                if _spec:
                    _want = int(_spec.get("start", 1)) + _off
                    _s_pos += 1
                    if _want > len(_sl) or _n != norm_code(_sl[_want - 1]):
                        _s_pbad += 1
                        if _s_pbad <= 3:
                            print(f"   [FAIL] ①p 位置不符 {_src_rel}:{_want}")
                            print(f"          讲解 {_n[:70]!r}")
                            print(f"          源码 {norm_code(_sl[_want - 1])[:70]!r}" if _want <= len(_sl) else "          <越界>")
                    _cov[_src_rel].add(_want)
                else:
                    if not (CMT_LINE.match(_n) and _no is None) and not line_ok_in(_sp, _n):
                        _r_pbad += 1
                        if _r_pbad <= 3:
                            print(f"   [报告] ①p（归属级）内容不符 {_src_rel}  {_n[:60]!r}")
                if _no is not None:
                    _s_lnchk += 1
                    if _spec:
                        _bad = (not (1 <= _no <= len(_sl))) or norm_code(_sl[_no - 1]) != _n
                    else:
                        _where = _lnidx.get(_n, [])
                        _bad = False if len(_where) != 1 else (_where[0] != _no)
                    if _bad:
                        if _spec:
                            _s_lnbad += 1
                        else:
                            _r_lnbad += 1
                        if _s_lnbad + _r_lnbad <= 6:
                            print(f"   [{'FAIL' if _spec else '报告'}] ④p 行号漂移 {_src_rel}:L{_no}  {_c[:60]!r}")
        # ② ★文件覆盖：manifest star_files = FAIL 档（位置级）；归属级整文件块 = 报告档
        _rev2s = []          # (rel, hit, eff, ratio, strong)
        for _rel in list(dict.fromkeys(list(((_man or {}).get("star_files") or [])))):
            _sl = src_lines(os.path.join(ROOT, _rel))
            _eff = {i for i, _l in enumerate(_sl, 1) if _l.strip() and not _l.strip().startswith("#!")}
            _hitn = len(_eff & _cov.get(_rel, set()))
            _rev2s.append((_rel, _hitn, len(_eff), _hitn / len(_eff) if _eff else 1.0, True))
        for _i, (_start, _lang, _bl, _sect, _h2, _hint, _chain, _mk) in _pyord:
            if _lang in DATA_LANGS or not block_star(_sect, _chain) or is_exempt(_sect, _h2, _mk, _bl):
                continue
            if _i in _man_blocks:
                continue
            _code = [norm_code(strip_anno_lang(_x, _lang)[0]) for _x in _bl]
            _code = [x for x in _code if x and not CMT_LINE.match(x)]
            if len(_code) < 5:
                continue
            _hit = _resolve_py_src(_sect, _chain, _hint, _pybase, _pyrev, _code)
            if not _hit:
                continue
            _rel = os.path.relpath(_hit, ROOT)
            _sl = src_lines(_hit)
            if len(_code) < 0.95 * len([x for x in _sl if x.strip()]):
                continue
            _real = _hitn = 0
            for _l in _sl:
                _t = norm_code(_l)
                if not _t or CMT_LINE.match(_t) or _t.startswith(("import ", "package ", "from ")) or PUNCT_ONLY.match(_t):
                    continue
                _real += 1
                if _t in _lect_norm_all:
                    _hitn += 1
                    continue
                _ts = re.sub(r"\s+", "", _t)
                if len(_ts) >= 8 and any(_ts in v for v in _lect_ns):
                    _hitn += 1
            _rev2s.append((_rel, _hitn, _real, _hitn / _real if _real else 1.0, False))
        _p2s = [r for r in _rev2s if r[4] and r[3] < 0.995]
        _p2r = [r for r in _rev2s if not r[4] and r[3] < 0.995]
        _den_py = []
        for _i, (_start, _lang, _bl, _sect, _h2, _hint, _chain, _mk) in _pyord:
            if _lang in DATA_LANGS or len(_bl) < 5:
                continue
            _tb = mark_text_blocks_lang(_bl, _lang)
            _keys = []
            for _j, _x in enumerate(_bl):
                _c, _, _ = strip_anno_lang(_x, _lang)
                if not is_key_lang(_c, _lang) or (_j < len(_tb) and _tb[_j]):
                    continue
                _keys.append(has_cjk_lang(_x, _lang))
            _kn = len(_keys)
            if not _kn:
                continue
            _mx = _cur = 0
            for _o in _keys:
                if _o:
                    _mx = max(_mx, _cur)
                    _cur = 0
                else:
                    _cur += 1
            _mx = max(_mx, _cur)
            _den_py.append((_start, _sect, _kn, sum(1 for o in _keys if o), _mx))
        print(f"\n[2.24] 非 Java 语言实检：{len(_pyord)} 个块 ｜ manifest：{'有（位置级 FAIL 档）' if _man else '无（归属级报告档）'}")
        _stag = "manifest 位置级" if _man else "归属级"
        print(f"   ①p 内容/位置保真：{_s_pos} 处核对（{_stag}）→ 不符 {_s_pbad} 处  {'PASS' if _s_pbad == 0 else 'FAIL'}"
              f" ｜ 归属级不符 {_r_pbad} 处（报告）｜ 归属不明 {_r_unattr} 块")
        for _rel, _hitn, _ne, _ra, _st in _rev2s:
            print(f"   [{'OK ' if _ra >= 0.995 else 'FAIL'}] ②p {_rel:<46} {_hitn:>4}/{_ne:<4} = {_ra*100:.1f}%"
                  f"{'（manifest）' if _st else '（归属级，报告）'}")
        print(f"   ②p ★文件覆盖：{len(_rev2s)} 个 → {'PASS' if not _p2s else 'FAIL'}（归属级不足 {_len_or0(_p2r)} 个，报告）")
        for _s, _sect, _kn, _cm, _mx in sorted(_den_py, key=lambda x: -x[4])[:6]:
            print(f"   [报告] ③p :{_s:<6} 关键行={_kn:<4} 注释={_cm:<4} 最长无注释={_mx:<3} {_sect[:38]}（报告档，不计 FAIL）")
        print(f"   ④p 行号一致性：可判定 {_s_lnchk} 处 → 漂移 {_s_lnbad} 处（{_stag}）  {'PASS' if _s_lnbad == 0 else 'FAIL'}"
              f" ｜ 归属级漂移 {_r_lnbad} 处（报告）")
        py_bad = _s_pbad + _s_lnbad + len(_p2s)

    ok = (not s_reasons and lost == 0 and not unattr and not bad_rev and not bad_den and not sig and not ln_rows
          and not bad_use and not bad_io and not bad_wire and not bad_pos and not bad_ext and not p_bad
          and not core_bad_n and not py_bad and not form_bad_n and not style_bad_n and not fails_0f
          and not snip_bad_n)

    print("\n⓪~⑤ 之外的残留引用自查（闸门盲区，SKILL §6.4「⑥ 节之外的残留引用检查」必做清单，需人工过）：")
    print("   ②多步示意（是否漏步/顺序反）｜⑦调用链表（方法名·字段名·两跳顺序）｜⑦边界条件表（行为是否与真实分支一致）")
    print("   ⑧穿透卡 L3·L4（异常类型是否与真实 throw/测试断言一致）｜⑩反例的 ✅ 代码（API 是否真实存在）")
    print("   ⑪测试表（方法名·构造实参·assertThrows 异常类 —— 逐条打开真实测试文件核对）｜⑯自检表（是否复述旧结论）")
    # 2.10（报告项，不计 FAIL）：⑯ 段有没有写明判据版本 —— 从没标过 = 数字不知道按哪版跑的（血证 H15）
    has_v, which, is_cur = ver_marker(lines)
    if not has_v:
        note = f"**从没写明判据版本**（⑯ 的数字不知道按哪版跑的）"
    elif not is_cur:
        note = f"标的是 v{which}（当前 v{GATE_VERSION} → 建议复核一遍数字）"
    else:
        note = f"已写明 v{GATE_VERSION} ✅"
    print(f"   ⑯ 判据版本标注（**报告项，不计 FAIL**）：{note}"
          f"　→ 一键补齐：`python scripts/sync_gate_result.py <本文件> --src <仓库根> --apply`")
    print("\n" + "=" * 96)
    print("总判定:", "PASS ✅" if ok else "FAIL ❌（C 组任一不过 = 当场修）")
    print("=" * 96)

    if jout:
        import lecture_checks as LC      # 结果 schema 与规则 ID 的单一来源（方案 §3.4）
        checks = []

        def _find(messages, where=None, line=None, part=None, severity=LC.FAIL):
            return [LC.make_finding(m, where=where, line=line, part_id=part, severity=severity)
                    for m in messages]

        # ── 结构（⓪） ──
        if not st["is_batch"]:
            checks.append(LC.make_check("G-STRUCT", LC.NOT_CHECKED, checked=0,
                                        note="非教材文件：跳过 17 节结构判定（口径见教材标志投票 + 参照物豁免）"))
        else:
            checks.append(LC.make_check(
                "G-STRUCT", LC.FAIL if s_reasons else LC.PASS,
                checked=st["sections"], findings=_find(s_reasons),
                note="节数=%d（应 17）｜围栏=%d｜占位=%d｜⑫八条=%d｜自指=%d｜回链=%d｜薄条=%d"
                     % (st["sections"], st["fences"], st["residual"], st["eight"], st["selfref"],
                        st["back"], len(st["thin"]))))

        # ── ⓪b/⓪c/⓪d/⓪e/⓪f ──
        if st["is_batch"]:
            core_msgs = [v for v in core.values() if v]
            checks.append(LC.make_check("G-CORE", (LC.FAIL if core_strict else LC.REPORT) if core_msgs else LC.PASS,
                                        checked=3,
                                        findings=_find(core_msgs, severity=LC.FAIL if core_strict else LC.REPORT),
                                        note="FAIL 档（声明 v%s ≥ %s）" % (core_ver, CORE_FAIL_SINCE) if core_strict
                                             else "报告档（未声明判据版本 ≥ %s，不追溯存量）" % CORE_FAIL_SINCE))
            _pieces = int((form["stats"] or {}).get("pieces") or 0)
            if _pieces:
                checks.append(LC.make_check(
                    "G-FORM", LC.FAIL if (form["fails"] and form_strict) else
                    (LC.REPORT if form["fails"] else LC.PASS),
                    checked=_pieces,
                    findings=_find(form["fails"], severity=LC.FAIL if form_strict else LC.REPORT),
                    note="②⑤⑥⑭ 必含形态（2.25 起 FAIL 档）"))
            else:
                checks.append(LC.make_check("G-FORM", LC.NOT_CHECKED, checked=0,
                                            note="本批没有 6.x 逐件小节 → 形态判据不适用"))
            snip_msgs = []
            if (form["stats"] or {}).get("miss_snip"):
                snip_msgs.append("⑥ %d/%d 件【怎么用】缺「可照抄的最小调用」：%s"
                                 % (len(form["stats"]["miss_snip"]), form["stats"]["pieces"],
                                    "、".join(form["stats"]["miss_snip"][:6])))
            if (form["stats"] or {}).get("miss_howto"):
                snip_msgs.append("⑥ %d/%d 件的【怎么接】缺「最小可编译实现」：%s"
                                 % (len(form["stats"]["miss_howto"]), form["stats"]["pieces"],
                                    "、".join(form["stats"]["miss_howto"][:6])))
            checks.append(LC.make_check("G-SNIP", (LC.FAIL if snip_strict else LC.REPORT) if snip_msgs else LC.PASS,
                                        checked=_pieces or 1,
                                        findings=_find(snip_msgs, severity=LC.FAIL if snip_strict else LC.REPORT),
                                        note="⑥ 可复制性（E12/E13，2.30 起 FAIL 档）")
                          if _pieces else
                          LC.make_check("G-SNIP", LC.NOT_CHECKED, checked=0,
                                        note="本批没有 6.x 逐件小节 → 可复制性判据不适用"))
        style_msgs, style_checked = [], int((sden["stats"] or {}).get("s7miss") is not None) + 1
        for r in sden["fails"]:
            if r.startswith("⑫ 第 5 条提示词未块化"):
                sev = LC.FAIL if style3_strict else LC.REPORT
            elif r.startswith(("⑥【讲解】", "⑫ 第 2 条", "⑫ 第 5 条")):
                sev = LC.FAIL if style2_strict else LC.REPORT
            else:
                sev = LC.FAIL if style_strict else LC.REPORT
            style_msgs.append((r, sev))
        checks.append(LC.make_check(
            "G-STYLE", (LC.FAIL if any(s == LC.FAIL for _m, s in style_msgs) else LC.REPORT)
            if style_msgs else LC.PASS,
            checked=style_checked,
            findings=[LC.make_finding(m, severity=s) for m, s in style_msgs] +
                     [LC.make_finding(m, severity=LC.REPORT) for m in sden["report"]],
            note="⓪e 结构密度与排版（2.26/2.27/2.28 版本门）"))
        if st["is_batch"]:
            b3_msgs = [(r, LC.FAIL) for r in s3s["fails"]] + [(r, LC.REPORT) for r in s3s["report"]]
            _b3n = int(st3.get("items") or 0)
            if _b3n or b3_msgs:
                checks.append(LC.make_check(
                    "G-BATCH3", LC.FAIL if (s3s["fails"] and style4_strict) else
                    (LC.REPORT if s3s["fails"] else LC.PASS),
                    checked=_b3n or 1,
                    findings=[LC.make_finding(m, severity=s) for m, s in b3_msgs],
                    note="⓪f 批次3 结构基准门（2.29 版本门）"))
            else:
                checks.append(LC.make_check("G-BATCH3", LC.NOT_CHECKED, checked=0,
                                            note="本批没有 6.x 逐件小节 → 结构基准门不适用"))

        # ── ①②③③c④⑤⑥ ──
        fid_findings = []
        for r in chk:
            if r["lost"] is None:
                fid_findings.append(LC.make_finding(
                    "无法归属源文件（%s）" % r["sect"][:60], where=os.path.basename(lec), line=r["start"]))
            elif fail_lines(r):
                fid_findings.append(LC.make_finding(
                    "候选不符 %d/%d 行（%s）%s" % (fail_lines(r), r["n_code"],
                                              r["cand"] or "未归属",
                                              "【历史版本块，按快照核验】" if r["hist"] else ""),
                    where=r["cand"] or os.path.basename(lec), line=r["start"], part_id=r["sect"][:40]))
        checks.append(LC.make_check("G-FIDELITY", LC.FAIL if (lost or unattr) else LC.PASS,
                                    checked=len(chk), findings=fid_findings,
                                    note="代码行 %d，候选不符 %d 行（%s）"
                                         % (tot, lost, "有快照" if sha else "未声明快照，无法区分演进与编造"))
                      if chk else
                      LC.make_check("G-FIDELITY", LC.NOT_CHECKED, checked=0,
                                    note="本批没有可核验的 java 代码块 → 正向保真**未检查**（0 对象不是 PASS）"))
        rev_findings = [LC.make_finding("★类 %s 覆盖 %.1f%%（判据 ≥99.5%%）缺 %d 行：%s"
                                        % (r["cls"], r["cov"] * 100, r["miss"],
                                           "；".join(s[:60] for s in r["samples"][:3])),
                                        where=r.get("src"), part_id=r["sect"][:40])
                        for r in bad_rev]
        checks.append(LC.make_check("G-REVERSE", LC.FAIL if bad_rev else LC.PASS,
                                    checked=len(rev_rows), findings=rev_findings,
                                    note="★ 类 %d 个（★ 标在父标题同样计入）" % len(rev_rows))
                      if rev_rows else
                      LC.make_check("G-REVERSE", LC.NOT_CHECKED, checked=0,
                                    note="本批没有可归属的 ★ 类块 → 反向覆盖**未检查**（0 对象不是 PASS）"))
        den_findings = []
        for r, reasons in bad_den:
            den_findings.append(LC.make_finding(
                "关键行=%d 注释=%d 最长无注释=%d → %s" % (r["key_lines"], r["comments"], r["max_run"],
                                                       "；".join(reasons)),
                where=os.path.basename(lec), line=r["start"], part_id=r["sect"][:40]))
        checks.append(LC.make_check("G-DENSITY", LC.FAIL if bad_den else LC.PASS,
                                    checked=len(den), findings=den_findings,
                                    note="密度：连段<8 且注释 ≥ 关键行÷12")
                      if den else
                      LC.make_check("G-DENSITY", LC.NOT_CHECKED, checked=0,
                                    note="没有可判密度的代码块（CJK 语言且 ≥5 行）→ **未检查**"))
        checks.append(LC.make_check("G-SIG", LC.FAIL if sig else LC.PASS,
                                    checked=len(star_classes(blocks, by_class)),
                                    findings=[LC.make_finding("★类方法签名无注释：%s → %s" % (r["cls"], "、".join(r["missing"][:8])),
                                                              where=r["src"]) for r in sig]
                                    if star_classes(blocks, by_class) else [],
                                    note="★类方法签名覆盖（按整类判定）")
                      if star_classes(blocks, by_class) else
                      LC.make_check("G-SIG", LC.NOT_CHECKED, checked=0, note="本批没有 ★ 类 → 未检查"))
        ln_checked = sum(r["checked"] for r in ln_all)
        checks.append(LC.make_check("G-LINENO", LC.FAIL if ln_rows else LC.PASS, checked=ln_checked,
                                    findings=[LC.make_finding("标 :L%d → 实际第 %d 行：%s" % (w, real, s[:60]),
                                                              where=os.path.basename(lec), line=r["start"], part_id=r["sect"][:40])
                                              for r in ln_rows for w, real, s in r["samples"][:3]],
                                    note="可判定标注 %d 处" % ln_checked)
                      if ln_checked else
                      LC.make_check("G-LINENO", LC.NOT_CHECKED, checked=0,
                                    note="没有任何可判定的行号标注（内容无法唯一定位）→ 未检查"))
        if not st["is_batch"]:
            checks.append(LC.make_check("G-USAGE", LC.NOT_CHECKED, checked=0,
                                        note="非教材批：跳过 用法与接入 判定"))
        else:
            use_findings = []
            for tag, rows in (("缺【怎么用】", bad_use), ("缺【上下游】", bad_io), ("缺【怎么接】", bad_wire)):
                for r in rows:
                    use_findings.append(LC.make_finding("%s：%s" % (tag, r["title"]),
                                                       where=os.path.basename(lec), line=r["at"],
                                                       part_id="%s %s" % (r["no"], r["title"][:24])))
            for r in bad_pos:
                use_findings.append(LC.make_finding("⑤ 位置错误：%s" % "；".join(r["pos_bad"]),
                                                   where=os.path.basename(lec), line=r["at"],
                                                   part_id="%s %s" % (r["no"], r["title"][:24])))
            if bad_ext:
                use_findings.append(LC.make_finding(
                    "缺 ⑦.5 扩展与接入路径小节" if not u_ext["at"] else
                    "⑦.5 只有 %d 条编号步骤（<3）" % u_ext["steps"],
                    where=os.path.basename(lec), line=u_ext["at"] or None))
            checks.append(LC.make_check(
                "G-USAGE", LC.FAIL if (bad_use or bad_io or bad_wire or bad_pos or bad_ext) else LC.PASS,
                checked=len(u_live), findings=use_findings,
                note="逐件 %d（历史版本小节 %d 个免检）｜抽象件 %d" % (len(u_live), len(u_items) - len(u_live), len(iface)))
                          if u_live else
                          LC.make_check("G-USAGE", LC.NOT_CHECKED, checked=0,
                                        note="本批没有 6.x 逐件小节 → 用法与接入**未检查**"))
        prose_checked = prose.get("n1", 0) + prose.get("n2", 0) + prose.get("n3", 0) + prose.get("n4", 0)
        prose_findings = [LC.make_finding("%s：%s" % (tag, s), where=os.path.basename(lec), line=n,
                                          severity=LC.FAIL)
                          for tag, rows in (("文件:行 引用不成立", prose["r1"]),
                                            ("件标题声明的文件不存在", prose["r4"]),
                                            ("本仓类.方法 全仓无此方法", prose["r2"]))
                          for n, s in rows]
        prose_findings += [LC.make_finding("反引号符号待人工确认：%s" % s, where=os.path.basename(lec),
                                           line=n, severity=LC.REPORT) for n, s in prose["r3"]]
        if prose_checked:
            checks.append(LC.make_check("G-PROSE", LC.FAIL if p_bad else LC.PASS, checked=prose_checked,
                                        findings=prose_findings,
                                        note="核验引用 %d 处（文件:行 %d / 本仓类.方法 %d / 反引号符号 %d）；"
                                             "不成立 %d 处；待人工确认 %d 处（不计 FAIL）"
                                             % (prose_checked, prose["n1"], prose["n2"], prose["n3"],
                                                len(p_bad), len(prose["r3"]))))
        else:
            checks.append(LC.make_check("G-PROSE", LC.NOT_CHECKED, checked=0,
                                        note="正文里没有可核验的 文件:行 / 件标题 .java / 本仓类.方法 引用 → 未检查"))

        # ── 快照与语言能力（可见，不与退出码打架） ──
        if sha and not snap_ok:
            print("   ⚠ 快照 %s 读取失败 → ① 只能退回当前树比对（**证据不完整**，不是完整通过）" % sha)
            checks.append(LC.make_check("G-SNAPSHOT", LC.REPORT, checked=0,
                                        note="批头声明了快照 %s 但读取失败：① 无法区分「源码演进」与「编造」。"
                                             "本项保持报告档（升 FAIL 属判据变更，需另起版本 + 回归）" % sha))
        elif sha:
            checks.append(LC.make_check("G-SNAPSHOT", LC.PASS, checked=1,
                                        note="快照 %s 读取成功（%s）" % (sha, how)))
        else:
            checks.append(LC.make_check("G-SNAPSHOT", LC.NOT_CHECKED, checked=0,
                                        note="批头未声明「源码依据：commit <sha>」→ 无法区分演进与编造"))

        if _pyord or _man_blocks:
            if _man:
                # 2.30 hotfix：manifest 在但块上无可核对对象（_s_pos+_s_lnchk==0）时，
                # PASS(checked=0) 会被 make_check 拒绝（"0 对象 PASS 是真空通过"）→ 降级 NOT_CHECKED
                _gpy_n = _s_pos + _s_lnchk
                checks.append(LC.make_check("G-PY",
                                            (LC.FAIL if py_bad else LC.PASS) if _gpy_n else LC.NOT_CHECKED,
                                            checked=_gpy_n,
                                            findings=[LC.make_finding("非 Java 位置/行号不符", where=os.path.basename(lec),
                                                                      severity=LC.FAIL)] * (1 if py_bad else 0),
                                            note=("manifest 位置级：①p 核对 %d 处不符 %d ｜ ②p ★文件 %d 个不足 %d ｜ "
                                                  "④p 可判定 %d 处漂移 %d"
                                                  % (_s_pos, _s_pbad, len(_rev2s), len(_p2s), _s_lnchk, _s_lnbad))
                                            if _gpy_n else
                                            "manifest 在但正文无非 Java 可核对对象（①p/④p 均 0 处）→ 未检查"))
            else:
                checks.append(LC.make_check("G-PY", LC.REPORT, checked=_r_pbad + _r_lnbad + len(_rev2s),
                                            note="无 manifest → 归属级近似，只可见不判红（①p 不符 %d 处 / "
                                                 "④p 漂移 %d 处 / ★文件 %d 个）" % (_r_pbad, _r_lnbad, len(_rev2s))))
        else:
            checks.append(LC.make_check("G-PY", LC.NOT_CHECKED, checked=0,
                                        note="本批没有非 Java 可注块 → 未检查（0 对象不是 PASS）"))
        if is_rec and not st["is_batch"]:
            _strict = declared_at_least(lines, RECORD_FAIL_SINCE)
            checks.append(LC.make_check("G-RECORD", (LC.FAIL if _strict else LC.REPORT) if _rec_bad else LC.PASS,
                                        checked=1,
                                        findings=_find(_rec_bad, severity=LC.FAIL if _strict else LC.REPORT),
                                        note="记录类形态（R1 状态行 / R2 未完成清单 / R3 不冒充成品）"))
        checks.append(LC.make_check("G-LECTURE", LC.REPORT, checked=1,
                                    note="教材判定：%s —— %s" % ("是" if is_lec else "否", lec_why)))

        _loc_mp = _hdr_loc                            # 位置契约清单（①p/②p/④p 的归属口径）
        _mp = manifest_arg or _loc_mp                 # 显式 --manifest 优先（它就是 sync_gate_result 要核对的那份）
        result = LC.make_result("gate_lecture.py", checks,
                                contract_version=GATE_VERSION,
                                lecture_sha256=LC.sha256_file(lec),
                                source_manifest_sha256=(LC.sha256_file(_mp) if _mp else None),
                                source_root=ROOT,
                                extra=dict(fidelity=fid, reverse=rev_rows, density=den, lineno=ln_rows,
                                           usage=dict(items=u_items, ext=u_ext),
                                           form=dict(fails=form["fails"], stats=form["stats"]),
                                           struct=dict(fails=sden["fails"], report=sden["report"],
                                                       stats=sden["stats"]),
                                           snapshot=sha, ver_marked=(ver_marker(lines)[2]),
                                           manifest_source=("cli" if manifest_arg else
                                                            ("location-contract" if _loc_mp else None)),
                                           location_contract_manifest=(_loc_mp or None),
                                           pass_=ok, verdict=("PASS" if ok else "FAIL")))
        # `verdict` 与退出码同源（`pass_`），`pass` 由阻塞项得出——两者不一致时以退出码为准并在 note 里点明
        if result["pass"] != ok:
            result["checks"].append(LC.make_check(
                "G-VERDICT", LC.REPORT, checked=1,
                note="结构化 pass=%s 与进程退出码判定=%s 不一致——以退出码为准（退出码是既有契约），"
                     "差异项请单独排查" % (result["pass"], ok)))
        json.dump(result, open(jout, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("明细已写:", jout)
        print("   结构化结果：%d 条检查（%s）｜lecture sha256=%s"
              % (len(result["checks"]),
                 "/".join(LC.STATUSES[i] + "=" + str(sum(1 for c in result["checks"] if c["status"] == LC.STATUSES[i]))
                          for i in range(len(LC.STATUSES))),
                 (result["lecture_sha256"] or "")[:12]))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
