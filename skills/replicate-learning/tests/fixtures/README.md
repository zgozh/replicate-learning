# 回归夹具（方案 §3.1 第 2 条）

这两组夹具是"提速重构不许降质"的机械凭据。它们录的是**输入**（源码、注释计划、分片、清单）
与**当时闸门实跑的结论**，不是本次重算出来的漂亮数字。

| 夹具 | 来源 | 用来钉什么 |
|---|---|---|
| `batch48/` | ragent-official 真实批次48（Java，8 件 / 778 行） | 预检能否在注入**之前**报出「★ 签名缺口 3 个 + 密度连段 5 处」；槽位化后能否"补 9~10 条注释、重复构建两次、不改 `contains`" |
| `py_mini/` | 合成迷你模块（Python） | 多行字符串与反斜杠续行**不许**被加行尾注释；Python 侧的检查计数与 `REPORT/NOT_CHECKED` 档位 |

## batch48/

- `project/rag/src/main/java/.../blockaware/*.java`：批次48 的 8 份主讲源码（逐字节拷贝）。
- `b48_manifest.json`：批次48 的源文件清单。**键补回了 `rag/` 前缀**并把 `source_root` 改写为 `.`——
  原批次里清单以 `<ragent>/rag` 为根、注释计划以 `<ragent>` 为根（两种根并存），夹具统一到 ragent 根，
  以便 `--src tests/fixtures/batch48/project` 同时满足清单与计划里的相对路径。
- `b48_inject_plan_r1.json`：**首轮**注释计划（注入前那一版，113 条 anno）。
  它只在会话导出 `test.md` 的 write 调用里留了一份（原文件后来被修复版覆盖）。
- `b48_inject_plan_fixed.json`：修复后的计划（补了 ★ 签名与密度连段的注释）。
- `parts/`：批次48 的 5 份分片（`⑥` 在 `b48_part_6.md`），供"组装→注入→重复构建"用。
- `expectations.json`：首跑闸门的结论（★ 缺口方法名、5 处密度连段），抄自会话导出。
- `build_batch48_fixture.py`：从 `D:\ragent-official` 与 `test.md` 重建夹具的脚本（只读原始资料）；
  换机器没有该项目时**直接用已提交的夹具即可**，不必重建。`--check` 只校验不写盘。

## py_mini/

- `project/app/sample.py`：迷你模块，含模块 docstring、多行 SQL 字符串、反斜杠续行。
- `plan.json`：正常注释计划（用于"检查对象计数"）。
- `plan_bad_keys.json`：四种坏键（字符串内部行、续行、越界、非数字）——预检必须逐条报出**可执行的错误**，
  而不是打印警告后继续。

## 端到端脚本化试运行

`tests/e2e_scripted_run.py` 用这两组夹具 + 真实批次48 教材跑完整第二轮流水线
（清单 → 预检 → 脚手架 → 组装注入 → 门禁 → 盖章 → 发布 → Python 侧），
并用 `batch_trace` 记录**脚本化步骤**的分步耗时：

```bash
python skills/replicate-learning/tests/e2e_scripted_run.py            # 产物在 .replicate-learning-log/e2e-scripted/
python skills/replicate-learning/tests/e2e_scripted_run.py --work /tmp/e2e
```

没装 ragent-official 时自动跳过依赖真实教材的三步并打印说明（可用 `RAGENT_ROOT` 指定项目根）。
**它只测脚本侧**：模型写作耗时（investigate/write）在报表里单列为"未记录阶段"，脚本不臆造该数字。
参考实测值见根目录 `replicate-learning-第二轮提速重构-交付说明.md` §4。

## 已知缺口（诚实记录）

本机只有 ragent-official 一个项目的完整第一册（Java）。**没有可用的 Python 项目完整第一册批次**，
所以 Python 侧的回归是"合成迷你模块 + 本仓脚本自身的 Python 源码"，不是真实 Py 批次对照。
方案 §5 要求的"Python 跨模块批"对照数据要等有真实 Py 项目批次时再补；在此之前，
Python 侧的结论只按夹具范围内的事实陈述，不外推。
