## ⑥ 逐件讲解（完整代码 + 逐行说明）

**阅读顺序 = 依赖顺序（自底向上）**：先 6.1 路径累积（被调度器与标题切分器共用），再 6.2~6.5 四个"常规结构"切分器（标题/段落/代码/列表），后 6.6~6.8 三个"双形态"重头件（图片/HTML 表格/结构化表格★——立碑兑现与 KV 渲染压轴）。

---

#### 6.1 `HeadingHandler` —— 路径弹栈：标题把祖先链交给正文

**本文件要解决的一个问题**：调度器遍历到标题时，章节路径要从"上一节的路径"变成"含这个标题的新路径"——新标题该挂在哪一级下、哪些旧祖先要弹出，需要一个只做这件事的裁判。这个类把弹栈规则收敛到 `update` 一个方法。输入：当前 Outline + 标题块；输出：新 Outline（不可变）；失败面：无（null 全归一）。

**白话开场**：这段代码回答"不可变的路径状态怎么维护：为什么 levels 和 path 要一起存、弹栈的判据是什么、并发安全从哪来"。

**构造方式与手法**：`@Component` 无状态单例（:L31-32）——路径由调用方（调度器）持有并逐块传入，本类不存任何字段；手法 = **不可变值对象的函数式更新**（update 返回新 Outline :L69，绝不原地改）；权衡点：Outline 把 levels 与 path 绑成一对同长列表——拆开存则两处维护必漂移。

```java
// __INJECT_01__
```

**逐行要点表**（讲控制流、数据变化、状态变化、异常路径、副作用、"不这样会怎样"）：

| 行 | 讲解 |
|---|---|
| :L39-40 | Outline record 两字段同长：path（给用户看的章节名）+ levels（每级的原始 heading 级别） |
| :L37 | levels 必须一起留着（javadoc 自答）：只看路径深度无法判断新标题该挂哪一级下——不以 H1 开头的文档会把同级章节层层嵌套 |
| :L41 | `EMPTY` 哨兵：路径累积从空起（调度器 :L74 的起点） |
| :L43-46 | 紧凑构造器防御拷贝：与批次47 ChunkContext 同款纪律 |
| :L53 | current null 归 EMPTY：防御调用方首块前未初始化 |
| :L57 | 级别钳到 ≥1：解析器可能给 0 或负——Math.max 一行兜住 |
| :L59-63 | **弹栈核心**：从尾向前找第一个级别更小的标题（`>= level` 的全弹出）——真正的父级是最近一个级别更小的标题（:L59 注释自答） |
| :L65-66 | subList(0, keep) 重建：不可变对象的"修改"是造新的，绝不原地改 |
| :L67 | null 文本落空串：标题文本缺失不炸路径 |
| :L69 | 返回新 Outline：入参与返回值都不可变（:L50 契约） |

**边界与副作用**：

- 边界：update 是纯函数——同输入恒同输出，H2 后跟 H2 与 H2 后跟 H3 的弹栈行为可用两行例子推演（H1/H2 后遇 H2 → 弹 H2 留 H1；H1/H2/H3 后遇 H2 → 弹 H3 与 H2 留 H1）。
- 副作用：零——无状态单例，并发摄取共用同一实例（:L29 注释），线程安全靠"不写字段"。
- 风险点：level 语义依赖解析器给的原始值（MinerU 按字号猜的级别）——批次47 ChunkDraft :L53-55 已声明"只记有无不记级别"用于分节，本类的级别只用于**路径挂载**，两处语义不同不冲突。

**【怎么用】**（调用现场）

- 调用现场一（调度器）：批次47 Dispatcher :L74 起 `Outline.EMPTY`、:L78 `outline = headingHandler.update(outline, heading)`——返回值**必须接住**（不可变对象的更新姿势）。
- 调用现场二（测试）：手装 Dispatcher 时 `new HeadingHandler()`（ChunkingFixtureTest :L129-130）——无依赖直接 new。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```java
HeadingHandler handler = new HeadingHandler();
Outline o = handler.update(HeadingHandler.Outline.EMPTY, new HeadingBlock(null, 1, "第三章"));
o = handler.update(o, new HeadingBlock(null, 2, "3.2 计费"));
o.path(); // ["第三章", "3.2 计费"]——含自己（调度器先 update 再分发的原因）
```

**【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游 | Dispatcher.dispatch 主循环（仅 HeadingBlock 触发） | 当前 Outline + 标题块 | 无失败面——null 全归一 |
| 下游 | ChunkContext.of（批次47 :L80，路径随上下文进每个 chunker） | 不可变 Outline | 无——快照语义由防御拷贝保证 |

---

#### 6.2 `HeadingChunker` —— 标题回正文：井号取原始级别

**本文件要解决的一个问题**：标题块若不产出任何草稿，成品块的 content 就是**被剥掉全部结构的裸正文**——回填 LLM 上下文时看不出出自哪一节。标题必须按原文位置回到正文里，且带分节标记让打包阶段起一节。输入：HeadingBlock + 上下文；输出：单草稿（ofHeading 标记）；失败面：空文本标题无产出。

**白话开场**：这段代码回答"最小的 chunker 长什么样：一个守卫、一次钳位、一个三参工厂——以及 content 与向量文本为什么要差一个井号"。

**构造方式与手法**：`@Component` 无状态实现 `BlockChunker<HeadingBlock>`（:L35）——泛型上界让 chunk 参数就是精确类型（批次47 6.6 契约兑现）；手法 = **渲染差异最小化**——content 与 embeddingBody 只差 `"#".repeat(level) + " "` 前缀；权衡点：级别钳位 [1,6]（:L55）而不是信任解析器——markdown 井号上限 6，越界渲染出坏结构。

```java
// __INJECT_02__
```

**逐行要点表**（讲控制流、数据变化、状态变化、异常路径、副作用、"不这样会怎样"）：

| 行 | 讲解 |
|---|---|
| :L37 | `MAX_LEVEL=6`：markdown 井号上限——钳位常量收在类头 |
| :L40-42 | `blockType()` 注册键：HeadingBlock.class——调度器建表（批次47 :L53-55）的 key |
| :L46 | 空守卫：无文本标题 List.of()——无产出合法（接口契约） |
| :L49 | strip：标题两侧空白不入块 |
| :L50-53 | 元数据组装：outlinePath 来自 ctx——**调度器已先 update**（批次47 :L77-79），标题拿到含自己在内的路径；provenance 随块走 |
| :L55 | 级别钳位 [1,6]：解析器给的级别可能越界——井号数取**原始级别**，不按路径深度重算（:L32 javadoc 自答：路径深度是切片的产物，不是文档的事实） |
| :L56-57 | **双形态差异点**：content 带 `## ` 前缀（原文形态），embeddingBody 只给纯文本——markdown 标记对嵌入模型是零信息 token（:L56 注释自答）；ofHeading 标记=打包阶段起一节 |

**边界与副作用**：

- 边界：null 块/空文本两个守卫后只剩正常路径——产出恒单草稿，永不 pieces。
- 副作用：零——纯函数。
- 风险点：标题级别错（解析器按字号猜）只影响井号数不影响分节（批次47 :L53-55"位置客观"决策的消费端）——检索质量不受"该是 H3 却标了 H2"伤害。

**【怎么用】**（调用现场）

- 调用现场一（注册表）：`@Component` 被 Spring 集合注入收进调度器（批次47 :L48-50）——本类无手工注册。
- 调用现场二（打包侧）：ChunkPacker（批次49）按 heading 标记分节——本类 :L57 的 ofHeading 是那条流水线的第一环。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```java
HeadingChunker c = new HeadingChunker();
ChunkContext ctx = ChunkContext.of(List.of("第三章"), ChunkBudget.defaults());
List<ChunkDraft> out = c.chunk(new HeadingBlock(null, 2, "3.2 计费"), ctx);
out.get(0).content();        // "## 3.2 计费"
out.get(0).embeddingBody();  // "3.2 计费"——不带井号
out.get(0).heading();        // true——打包分节标记
```

**【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游 | Dispatcher.chunkOne（查表命中） | 精确类型 HeadingBlock + 上下文 | 无失败面（守卫内化） |
| 下游 | ChunkPacker（批次49，heading 标记分节） | 单草稿 | 无 |

---

#### 6.3 `ParagraphChunker` —— 双段量法：切不动说明整段撑得住

**本文件要解决的一个问题**：段落是散文的主体，绝大多数段落撑得住预算——切分逻辑必须让"绝大多数"走零成本路径。这个实现用两次尝试表达"尽量少切"：先按容忍上限量一次（量出单片=整段保留），量出多片才退回块大小重切。输入：ParagraphBlock + 上下文；输出：一或多片（多片带 pieces 标记）；失败面：null 段落空产出。

**白话开场**：这段代码回答"委托式切分怎么写：为什么本类不自行按下标截断、双段量法的先后顺序为什么不能反、pieces 标记在哪落"。

**构造方式与手法**：`@Component` 无状态实现（:L36）；手法 = **委托 + 度量分离**——边界回溯（换行/中文句末/英文句末）与文本归一化全在 TextSplitter（批次49），本类只决定"用哪个上限量"；权衡点：不把 TextSplitter 结果缓存或复用——两次 split 输入相同输出确定，代价可忽略，换来控制流一目了然。

```java
// __INJECT_03__
```

**逐行要点表**（讲控制流、数据变化、状态变化、异常路径、副作用、"不这样会怎样"）：

| 行 | 讲解 |
|---|---|
| :L45 | null 守卫：空产出 |
| :L48 | overlap 从预算取：重叠距离语义见批次47 :L95-96（兼任 TextSplitter 回退找句末标点的最大距离） |
| :L49-50 | **第一量**：按容忍上限 split——注释自答"切不动说明整段撑得住"；容忍=切开语义单元代价高于超出目标（批次47 :L125） |
| :L51-53 | **第二量**：量出多片才退回 maxChars 重切——顺序不能反：先按 maxChars 会把"撑得住但超目标"的段落提前切碎 |
| :L54-56 | 空切分 List.of()：空段落合法无产出 |
| :L58-61 | 元数据：outlinePath + provenance——每片共享同一元数据对象（不可变，安全共享） |
| :L64-66 | 逐片 of：段落无显式检索正文——回落 content（effectiveBody 语义，批次47 :L82） |
| :L67 | **pieces 标记**：多片必标（单片原样返回不背标记，批次47 :L68）——合并不得撤销契约的产出方落地 |

**边界与副作用**：

- 边界：两次 split 用同一 overlap——回退距离不随第二量变化，切片间重叠稳定。
- 副作用：零。
- 风险点：TextSplitter 的行为（切点质量/归一化）本批未验证——委托契约在 :L32 javadoc，实现侧批次49 兑现后需回归。

**【怎么用】**（调用现场）

- 调用现场一（注册表）：Spring 收进调度器注册表——八实现里最常命中的一件（散文主体）。
- 调用现场二（验证）：ChunkingFixtureTest 三种预算导出报告——TIGHT（300/60/5）下长段落的切分形态就在报告里人工核对。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```java
ParagraphChunker c = new ParagraphChunker();
ChunkBudget tight = new ChunkBudget(300, 60, 5);
List<ChunkDraft> out = c.chunk(new ParagraphBlock(null, "很长的段落…".repeat(50)),
                               ChunkContext.of(List.of(), tight));
out.size() > 1;                       // 多片
out.stream().allMatch(ChunkDraft::piece); // 全带切片标记
```

**【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游 | Dispatcher.chunkOne | ParagraphBlock + 上下文 | 无 |
| 下游 | ChunkPacker（批次49） | 一或多片草稿 | pieces 标记缺失 → 打包误合并（重叠复制/少切失效） |

---

#### 6.4 `CodeChunker` —— 行边界切分：每块重复围栏

**本文件要解决的一个问题**：代码块的半截行不可读、缺围栏不渲染——默认必须整块保留。但 txt 缩进段落会被解析成代码块、真代码文件可能远超预算，单块顶穿嵌入上限会被**静默截断**（尾部等于没入库）。这个实现按行边界降级，且每块补回围栏让半块代码独立合法。输入：CodeBlock + 上下文；输出：一或多片；失败面：null 块空产出。

**白话开场**：这段代码回答"结构化文本的降级切分怎么保可读性：切点为什么必须落行边界、围栏为什么每块重补、向量文本为什么反而剥掉围栏"。

**构造方式与手法**：`@Component` 无状态实现（:L35）；手法 = **度量与产出分离**——splitByLines 按行累加切"裸代码"，产出时再逐块包围栏；权衡点：向量文本取裸代码 segment（:L62 第二参）——``` 围栏对嵌入是零信息 token（与 HeadingChunker :L56 同一决策，本批第二次出现）。

```java
// __INJECT_04__
```

**逐行要点表**（讲控制流、数据变化、状态变化、异常路径、副作用、"不这样会怎样"）：

| 行 | 讲解 |
|---|---|
| :L47-48 | language/code null 落空串：无语言围栏合法、空代码不走切分 |
| :L55-57 | **统一判据落点**：`code.length() <= toleranceChars` 整块保留——超出才按 maxChars 行边界降级（批次47 契约的代码形态） |
| :L61 | 每块重复围栏 `"```" + language + "\n" + segment + "\n```"`：半块代码也是合法 markdown——前端预览与 LLM 回填都直接可用 |
| :L62 | 向量文本=裸代码：不带围栏（零信息 token）；也不带语言标签 |
| :L64 | pieces 标记：多片不可撤销 |
| :L70-88 | `splitByLines`：按行累加，行满落块——切点恒在行边界 |
| :L74 | addition 含项间换行 +1：行间 `\n` 也占预算 |
| :L75-77 | 超预算先落块再清空：`setLength(0)` 复用 StringBuilder 免新建 |
| :L79-82 | 非首行先补 `\n`：块内行间换行保真 |
| :L84-86 | 尾组收块 |
| :L87 | segments 空给 List.of(code)：防御空 code 路径——split("\n",-1) 对空串返回 [""]，此兜底保产出非空 |

**边界与副作用**：

- 边界：单行超预算（minified JS 一行几十 KB）→ :L75 判定不命中（current 空）→ 该行独立成块——**绝不从行中间切断**（:L68 javadoc 自答），块超预算由装配/嵌入侧兜。
- 副作用：零。
- 风险点：indented 代码块无语言（批次46 :L320）→ 围栏无标注 → 渲染按纯文本——语义损失可接受（原块就没语言信息）。

**【怎么用】**（调用现场）

- 调用现场一（注册表）：八实现之一，代码类文档（技术手册）的主力。
- 调用现场二（对照）：与 ParagraphChunker 的差别=降级切分自研（行边界简单）vs 委托（散文句末复杂）——两种姿势的适用分界。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```java
CodeChunker c = new CodeChunker();
CodeBlock big = new CodeBlock(null, "java", "line1\nline2\nline3…");
List<ChunkDraft> out = c.chunk(big, ChunkContext.of(List.of(), tight));
out.get(0).content().startsWith("```java"); // 每块围栏齐
out.get(0).effectiveBody();                  // 裸代码，无围栏
```

**【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游 | Dispatcher.chunkOne | CodeBlock + 上下文 | 无 |
| 下游 | ChunkPacker（批次49） | 一或多片 | pieces 标记缺失 → 半块代码被并坏 |

---

#### 6.5 `ListChunker` —— 字符贪心：清单不腰斩词条

**本文件要解决的一个问题**：清单的语义单元是"项"——"要交哪些材料"这类问题必须召回完整清单，切开后只能召回半份。但清单也必须能切（几百项的清单超预算），切法按**渲染后的字符体量**贪心分组、按项边界落刀。输入：ListBlock + 上下文；输出：一组或多组（每组含若干完整项）；失败面：空清单空产出。

**白话开场**：这段代码回答"度量选型怎么影响切分质量：为什么按项数切是错的、有序列表切块后编号怎么续、贪心累加的'非首项才判超'防什么"。

**构造方式与手法**：`@Component` 无状态实现（:L35）；手法 = **渲染函数复用为度量**（renderItem 同时算体量 :L62 与产出 :L84）——切分度量与最终渲染恒一致，不会"量的是 A 产出的是 B"；权衡点：贪心而非 DP——清单切块不需要最优解，顺序保持是硬要求（DP 可能打乱项序）。

```java
// __INJECT_05__
```

**逐行要点表**（讲控制流、数据变化、状态变化、异常路径、副作用、"不这样会怎样"）：

| 行 | 讲解 |
|---|---|
| :L44 | 空清单/null items List.of() |
| :L48-51 | 元数据：路径+溯源，各组共享 |
| :L54-56 | **budget 选型**：整份渲染体量 ≤ 容忍 → 用容忍值（整份不切）；否则用 maxChars——Math.max(1,…) 防御 0 预算 |
| :L53 | 整份撑得住就不切（注释自答）：切开后"要交哪些材料"只能召回半份 |
| :L60-69 | 贪心累加主循环：cost 超预算且非首项 → subList(start,i) 落块、重开组 |
| :L62 | itemCost = 渲染后体量 + 1（项间换行）——度量即产出（renderItem 复用） |
| :L63 | **非首项才判超**：单项自身超预算时独立成块（`i > start` 守卫）——硬切只会把词条腰斩（:L61 注释自答） |
| :L64 | subList 落块：startNumber 传 start+1——有序列表切块编号连续 |
| :L70 | 尾组收块：循环后剩余项必落 |
| :L71 | pieces 标记 |
| :L77-87 | buildDraft：项间 `\n` 拼接，startNumber 对有序生效（:L75 javadoc） |
| :L92-99 | renderedLength：整份体量（含换行）——budget 选型的输入 |
| :L104-106 | renderItem：有序 `N. ` / 无序 `- `——渲染形态同时是切分度量 |

**边界与副作用**：

- 边界：单项超预算独立成块且**块仍超预算**——与 CodeChunker 单行同理，原子性优先于预算。
- 副作用：零。
- 风险点：编号连续性依赖 items 顺序稳定（ListBlock 产出序即文档序，批次46 :L426 保证）——乱序输入的编号会错，但那是解析域的问题不是本类的。

**【怎么用】**（调用现场）

- 调用现场一（注册表）：清单类内容（FAQ/材料清单/步骤列表）的主力。
- 调用现场二（核对）：fixture 报告里切开的清单块应看到 `4. / 5. / 6.` 续号。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```java
ListChunker c = new ListChunker();
ListBlock list = new ListBlock(null, true, List.of("项一","项二","项三","项四"));
List<ChunkDraft> out = c.chunk(list, ChunkContext.of(List.of(), tight));
// 两块时第二块首项渲染为 "3. 项三"——编号连续
```

**【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游 | Dispatcher.chunkOne | ListBlock + 上下文 | 无 |
| 下游 | ChunkPacker（批次49） | 一或多组 | pieces 缺失 → 贪心分组被合并撤销 |

---

#### 6.6 `ImageChunker` —— 一图一块：URL 不进向量（立碑兑现）

**本文件要解决的一个问题**：图片的检索价值全在 VLM 描述文本里——URL 串进向量是纯噪声，会稀释描述的语义密度。这个实现一图一块整存整取：展示文本"描述+markdown 链接"（前端可点、LLM 可引用），向量文本只取描述。输入：ImageBlock（批次46 已换公开 URL+已生描述）+ 上下文；输出：单草稿；失败面：无资产图空产出。

**白话开场**：这段代码回答"最简单的切分器怎么承载最重要的检索决策：双形态文本的最小样例、caption 三级回落、可流动声明给打包阶段的信号"。

**构造方式与手法**：`@Component` 无状态实现（:L35）；手法 = **content 与 embeddingBody 的最小对比样例**——同一块的两种文本只差"链接+空行"；权衡点：无描述时向量文本给 null（:L60 三参 of 的第二参）——回落 content=链接本身，图召不回但块在、URL 可展示。

```java
// __INJECT_06__
```

**逐行要点表**（讲控制流、数据变化、状态变化、异常路径、副作用、"不这样会怎样"）：

| 行 | 讲解 |
|---|---|
| :L44 | null 块/无 asset List.of()：无资产图无产出 |
| :L48 | markdown 图链接拼装：`![caption](publicUrl)`——URL 是批次46 换好的公开地址 |
| :L50-51 | description 判空：blank 与 null 同等（批次46 :L226 空描述不入表 → 这里 description 为 null） |
| :L52 | content=描述+空行+markdown：展示文本完整（语义+可点链接）——**整存整取**（立碑承诺的展示侧） |
| :L54-58 | 元数据：**assets 进元数据**（:L56）——多 sink 拿 URL 渲染缩略图/答案配图 |
| :L60 | **立碑兑现（向量侧）**：三参 of——有描述给描述、无描述给 null（回落 content）；URL 恒不进向量（除非回落）——批次44/46"ImageBlock 整存整取（URL+VLM 描述随块走）"在此对账 |
| :L63-71 | pickCaption 三级回落：caption > altText > 空串——markdown alt 位恒非 null |

**边界与副作用**：

- 边界：单草稿恒不 pieces、不超预算（描述文本远小于预算）——八件里唯一"零降级路径"的实现。
- 副作用：零。
- 风险点：VLM 描述质量决定该块的检索上限（批次44 已登记的待偿欠账）——本类无法弥补空/差描述，:L60 的回落只是兜底不是修复。

**【怎么用】**（调用现场）

- 调用现场一（注册表）：图片类文档（架构图/流程图/报表截图）的唯一入口——批次44/46 链路的消费端。
- 调用现场二（对账）：把批次46 ImageBlock 的三文本（caption/alt/描述）与本类 :L48/:L60 的用法对上，立碑闭环。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```java
ImageChunker c = new ImageChunker();
ImageBlock img = new ImageBlock(null, new AssetRef("https://cdn/x.png", "image/png"),
        "系统架构图", "部署拓扑", "三层架构描述…");
List<ChunkDraft> out = c.chunk(img, ctx);
out.get(0).effectiveBody(); // "三层架构…"——URL 不在
out.get(0).content();       // "三层架构…\n\n![部署拓扑](https://cdn/x.png)"
```

**【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游 | Dispatcher.chunkOne | ImageBlock（URL 已公开化+描述已生成，批次46） | 无资产空产出 |
| 下游 | ChunkPacker（批次49）"可流动"声明（:L32） | 单草稿 | 打包若不识别可流动 → 图与解释文字被拆开（命中不带图） |

---

#### 6.7 `HtmlTableChunker` —— tr 边界切分：不切标签中间（立碑兑现）

**本文件要解决的一个问题**：HTML 表格（MinerU 从 PDF 版面还原的复杂表）不能按字符硬切——断面停在 `<td>` 中间整块变垃圾；也不能转管道表——合并单元格与格内换行展开成二维表会失真。这个实现按 `<tr>` 边界切、每块重复表头并包回完整 `<table>`，扫不出行边界时原样落块。输入：HtmlTableBlock + 上下文；输出：一或多片；失败面：空 HTML 空产出。

**白话开场**：这段代码回答"对不可信 HTML 做结构化切分的全部防御：正则扫描的边界、噪声清洗为什么在切分前、overhead 为什么要从预算里先扣、'切不动就原样落'的守门判定在哪"。

**构造方式与手法**：`@Component` 无状态实现（:L37）；手法 = **正则状态机（受限场景）**——tr 扫描 :L39-40 用非贪婪 DOTALL，清洗 :L45-46 用第二个正则；权衡点：不引 jsoup 解析（依赖换正确性：这里只需要 tr 序列与首标签，正则的失败模式已知且被 :L68 守门兜住）。

```java
// __INJECT_07__
```

**逐行要点表**（讲控制流、数据变化、状态变化、异常路径、副作用、"不这样会怎样"）：

| 行 | 讲解 |
|---|---|
| :L39-40 | ROW 正则：`<tr…>…</tr>` 非贪婪 + DOTALL（tr 内可跨行）+ 忽略大小写 |
| :L44-46 | NO_OP_SPAN：colspan/rowspan=1 不表达任何合并（javadoc 自答）——MinerU 逐格都写，十来行的表被撑到三倍 |
| :L57 | 空守卫：hasText 判 HTML |
| :L65 | **清洗在切分前**：span 噪声先删——否则体量度量与产出恒差一截 |
| :L67-70 | **立碑兑现（守门判定）**：rows<2（只有表头或扫不出行）原样落块——宁可超预算也不切在标签中间（:L67 注释自答）；批次44/46"HtmlTableBlock 不硬切"在此对账 |
| :L72-73 | openTag 取原始开标签（:L113-118）：作者写的 border/class 跟着每块走；header=首 tr |
| :L74 | maxRows：rowsPerChunk 硬上限（批次47 :L57 的 per-类型旋钮） |
| :L76-78 | budget 选型：行数不超硬上限且全表 ≤ 容忍 → 容忍值（整表不切）；否则 maxChars——注释自答"切开后每块虽重带表头，跨块的行间对比仍然做不了" |
| :L80 | **overhead 先扣**：外壳+表头每块重复，不扣则渲染出来必超（:L79 注释自答） |
| :L85-95 | 贪心分组：overCap（行数）或 overBudget（体量，非空才判 :L87）→ 落块重开 |
| :L89/:L96 | render 包回完整 table（:L120-126）：每块独立合法 HTML |
| :L97 | pieces 标记 |
| :L103-110 | splitRows：Matcher.find 循环收 tr 序列——首个即表头 |

**边界与副作用**：

- 边界：嵌套 table（td 里再有 table）时 ROW 正则会把内层 tr 也扫出——切分边界失真但不炸（每块仍包回外层壳）；MinerU 产物极少嵌套表，接受该已知限制（⑬.2 登记）。
- 副作用：零。
- 风险点：正则对畸形 HTML（tr 未闭合）扫不出行 → :L68 原样落块——失败模式是"不切"不是"切坏"，安全方向。

**【怎么用】**（调用现场）

- 调用现场一（注册表）：PDF/Word 版面表格（批次46 :L358 产出）的唯一入口。
- 调用现场二（对账）：批次46 ⑩ 反例 3"硬切断面停在标签中间"的反面教材——本类 :L67-70 就是那条反例的正面防线。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```java
HtmlTableChunker c = new HtmlTableChunker();
HtmlTableBlock t = new HtmlTableBlock(null, "<table class='grid'><tr><th>品名</th></tr>"
        + "<tr><td>A</td></tr><tr><td>B</td></tr>…</table>");
List<ChunkDraft> out = c.chunk(t, ChunkContext.of(List.of(), capOnly));
out.get(1).content().startsWith("<table class='grid'>"); // 原始开标签跟随
out.get(1).content().contains("<th>品名</th>");           // 表头每块重复
```

**【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游 | Dispatcher.chunkOne | HtmlTableBlock（批次46 :L358 产出） | 无 |
| 下游 | ChunkPacker（批次49） | 一或多片 | pieces 缺失 → 重带表头的块被并坏 |

---

#### 6.8 `TableChunker★` —— KV 双形态：向量喂模型读得懂的形态

**本文件要解决的一个问题**：结构化表格（CSV/Excel，批次43 的 headers+rows）的检索质量取决于向量文本的形态——markdown 表格靠位置对齐列名与值、嵌入模型读不懂位置。这个实现一块产双形态：展示=完整 markdown 表格、向量=`列名: 值` KV 行，且**表头不拼进向量**（防同表各块向量聚拢）。输入：TableBlock + 上下文；输出：一组或多组；失败面：无行无表头空产出。

**白话开场**：这段代码回答"检索导向的切分怎么反推渲染设计：KV 行为什么带列名、表头为什么反而省略、预算为什么刻意不扣章节前缀、Excel Alt+Enter 的换行为什么是 <br> 而不是空格"。

**构造方式与手法**：`@Component` 无状态实现（:L37）；手法 = **同源度量**——rowCost=KV 行渲染长度（:L75），切分度量与向量文本恒一致；权衡点：预算只量 KV 行不扣装配器追加的章节路径前缀（:L55-56 注释自答：真去扣，深层章节会把可用预算逼近 0，退化成每行一块、每块大半是逐字相同的前缀）。

```java
// __INJECT_08__
```

**逐行要点表**（讲控制流、数据变化、状态变化、异常路径、副作用、"不这样会怎样"）：

| 行 | 讲解 |
|---|---|
| :L49-53 | null/空守卫：headers 与 rows 双空才空产出（只无行有表头仍产块 :L66-69） |
| :L55-56 | **预算不扣前缀**（注释自答）：章节路径由装配器统一拼——本类只管 KV 行体量 |
| :L57 | maxRows：rowsPerChunk 硬上限 |
| :L59-62 | budget 选型：行数 ≤ 硬上限且 KV 全文 ≤ 容忍 → 容忍值（整表不切）；否则 maxChars |
| :L66-69 | 无行有表头：单块落表头——空数据表也入库 |
| :L72-87 | 贪心累加：rowCost 累加，overCap（:L76）或 overBudget（非空才判 :L77）先落块 |
| :L75 | rowCost=KV 渲染长度：**同源度量**——量什么切什么 |
| :L86/:L96 | buildDraft 双形态（:L96）：第一参 markdown 表格（展示）、第二参 KV 行（向量）——**本批核心讲点**（④ 4.1） |
| :L99-112 | renderKeyValueRows：逐行 KV 拼接、空行跳过 |
| :L117-134 | renderKeyValueRow：`; ` 拼 cell、跳空值、整行空返回空串；列号超表头给空 key（:L124 宽容错位数据） |
| :L139-141 | oneLine：格内换行压空格——key 与 value 夹断行影响检索（:L137 注释自答） |
| :L143-154 | renderMarkdownTable：表头+分隔行+数据行，尾换行剥 |
| :L164-175 | sanitizeCell：格内换行（Excel Alt+Enter）转 `<br>`（:L167 javadoc 自答：裸换行截断表格行、整块退化成普通段落）；竖线转义（:L168：字面 \| 被误判列分隔） |
| :L177-181 | appendSeparator：`---|` repeat 列数 |
| :L87 | pieces 标记 |

**【逐步回放】**（★类全链回放：一张 4 行 3 列的 Excel 报价表在 TIGHT 预算下怎么变块）

1. Dispatcher 查表命中（批次47 :L88）→ `chunk(TableBlock, ctx)`，ctx.budget()=TIGHT(300,60,5)。
2. :L49-53 守卫通过（3 表头+4 数据行）。
3. :L57 maxRows=5（rowsPerChunk=5）。
4. :L59-62 budget 选型：KV 全文（4 行 × ~40 字符）≈160 ≤ 容忍 900 → **budget=900，整表不切路径**。
5. :L72-87 贪心：4 行逐行累加 rowCost，永不触发 overCap（5 上限）/overBudget（900）→ 单组收尾 :L86。
6. :L96 buildDraft：content=完整 markdown 表（:L143 渲染，竖线转义+`<br>` 清洗），embeddingBody=4 行 KV（:L99 渲染，表头不拼）。
7. 单片 → pieces 原样返回（批次47 :L68）→ 打包阶段可与同节相邻草稿合并。
8. 装配（批次49）：向量文本 = "报价表 / 3.2 价格" 章节前缀 + KV 正文——表身份由 sheet 名经章节路径承载（:L34）。

**【怎么用】**（调用现场）

- 调用现场一（注册表）：CSV/Excel（批次43 TableBlock）的唯一入口——结构化数据的检索质量瓶颈件。
- 调用现场二（fixture）：ChunkingFixtureTest 的 order-records.csv 走本类，CAP_ONLY 预算（:L73）专门让 rowsPerChunk 起作用。
- 可照抄的最小调用（教学合成片段，**不带 `// :Lnn`**）：

```java
TableChunker c = new TableChunker();
TableBlock t = new TableBlock(null, List.of("品名","价格"), List.of(List.of("A","10"), List.of("B","20")));
List<ChunkDraft> out = c.chunk(t, ctx);
out.get(0).effectiveBody(); // "品名: A; 价格: 10\n品名: B; 价格: 20"——列名自带
out.get(0).content();       // "| 品名 | 价格 |\n| --- | --- |\n| A | 10 |…"
```

**【上下游】**（上游谁喂数据、下游谁吃产出、失败时两边各看到什么）

| 方向 | 谁 | 给/拿什么形态 | 失败时看到什么 |
|---|---|---|---|
| 上游 | Dispatcher.chunkOne | TableBlock（批次43 Csv/Excel 解析产） | 无 |
| 下游 | ChunkPacker → 装配器（批次49） | 一或多组双形态草稿 | pieces 缺失 → KV 组被并坏；表头若误入向量 → 同表块向量聚拢（topK 被同表碎片占满） |

**边界与副作用**：

- 边界：单行 KV 超预算 → 非空才判超（:L77）→ 整行原子成块——行是表格的原子单元。
- 副作用：零。
- 风险点：列名缺失（headers 短于行宽）时 KV 退化为 `: 值`——检索质量下降但不炸；深层章节的路径前缀挤占嵌入窗口由 :L55-56 决策规避，超长路径本身是装配侧的校验点（批次49）。
