# 讲解达标样例（非 Java 对照）——node_rrf（Python · RRF 排名融合）

> **用途**：这是 `黄金样例.md`（Java/GHE 满深度基准）的**非 Java 对照样例**。同一套六段、同一套阈值（六段、≥8 跳调用链带真实类名、整方法逐行 + 每手法反例、用法带触发回放、结尾读法提示），只是语言换成 **Python + LangGraph**。它证明"黄金样例"教的是**深度与格式**，与语言无关——讲到任何别的项目（Java/Python/TS）时，按这个尺度产出**该语言**的内容，不要照搬本样例的 Python 词汇。
> **六段对应**：与 `黄金样例.md` 相同（①业务场景→小节一；②数据流/调用链→小节二；③实现→小节三；④用法→小节四）。**达标判定表 / 讲解自检表**在 `黄金样例.md`（第二节可对照，同一套标准）。
> **语言切换提醒**：本样例全程用 Python 词（`abc.ABC` / `@abstractmethod` / `typing.TypedDict` / `__call__` / `dict.get` / `sorted(lambda)`）。对照到 Java 时，`@abstractmethod`→抽象方法、横切收敛到基类 `__call__`→基类模板方法、`TypedDict`→带类型声明的状态对象；**不要把"装饰器/抽象基类"当成 Java 的"注解/切面"**——它们语义不同。

---

## 一、达标样例：NodeRrf（RRF 排名融合）——Python 完整示范

### 业务场景（具体到人、事、数值、期望）

售后维修工程师小张在知识库问答页输入「怎么测这块主板的短路问题？」。系统先用 BGE-M3 向量检索（topK 约 60 条）和 HyDE 假设答案检索（topK 约 55 条）各召回一批结果。`node_rrf` 拿到 `embedding_chunks`、`hyde_embedding_chunks` 两路结果，要在毫秒级把两路的**排名**融成一套统一分数（RRF 平滑参数 `k=60`），重排后交给下游精排。

小张期望：两路都命中的「主板短路维修手册」排第一——既不让某一路没召回的好文档丢失，也不会因为两路的分数量纲不同而错排。

### 数据流 · 完整调用链实例（从一次真实提问一路到生成返回）

```text
① 用户输入「如何用万用表测量电压？」→ 构造 init_state = {"original_query": "..."}（main_graph.py 的 __main__）
② KBQueryWorkflow() 构造：__init__ 依次 StateGraph(QueryGraphState) → _init_nodes() 创建 NodeRrf() 等实例
   → _register_nodes() 用 add_node("node_rrf", self.node_rrf) 注册 → _setup_routes() 设入口
   → _compiled_app = None（懒加载，首次执行才编译）
③ workflow.run(initial_state, stream=True) → 未编译则 self.compile() → self.workflow.compile() → 得 _compiled_app
④ _compiled_app.stream(initial_state)（或 invoke）→ LangGraph 从 set_entry_point("node_item_name_confirm") 的入口节点开始
⑤ NodeItemNameConfirm.__call__(state) → 继承 NodeBase.__call__（先 add_running_task(session_id, name, is_stream)）
   → 进 process(state)：_step_4_extract_info 调 ChatOpenAI.invoke 抽 item_names / rewritten_query
   → _step_5_vectorize_and_query 生成向量并 create_hybrid_search_requests → hybrid_search(...)
   → _step_6_align_item_names(按匹配规则优先级) → _step_7_check_confirmation → 写 state["item_names"]/state["answer"]
⑥ 条件路由 _route_after_item_name_confirm(state)：state.get("answer") 有 → return "node_answer_output"（反问/拒答直接输出）；
   没有 → return "node_multi_search"
⑦ 节点 node_multi_search（lambda x: x 虚拟分叉点，状态原样传）→ 并行 add_edge 到
   node_search_embedding / node_search_embedding_hyde / node_web_search_mcp（三路各自写 embedding_chunks / hyde_embedding_chunks / web_search_docs）
⑧ 三路 add_edge 汇到 node_join（lambda x: {} 虚拟合并点，只汇控制流、无业务逻辑）
⑨ node_join → node_rrf → NodeRrf.__call__(state) → NodeBase.__call__（log 开始/完成 + add_running_task；process 异常则 log error 并 raise）→ process(state)
⑩ process 读 state.get('embedding_chunks')/('hyde_embedding_chunks')，各取 entity → rrf_inputs = [(list, 1.0), (list, 1.0)]
   → 调 self._rrf_merge(rrf_inputs)
⑪ _rrf_merge 内：遍历每路 + enumerate(rank, start=1) → chunk_scores[chunk_id] += weight/(k+rank)
   → chunk_data.setdefault(chunk_id, doc) 只留首版 → 聚合后按分降序 sorted(key=lambda x: x[1], reverse=True)
   → 返回 [(doc, score)]（未截断则全量）
⑫ process 用 rrf_chunks = [doc for doc, _ in rrf_merge_results]（分离分数与文档）→ state['rrf_chunks'] = rrf_chunks
   → add_done_task(state.get("session_id"), self.name, state.get("is_stream")) → return state
⑬ node_rrf → node_rerank → NodeRerank.__call__ → _step_1_merge_multi_source_docs(state) 读 state.get("rrf_chunks")
   → 断崖检测动态 Top-K 截断
⑭ node_rerank → node_answer_output（组装 prompt → 生成 answer）→ END
```

**读法提示**：断在 ⑤~⑨ 中间任意一跳 = 你还没懂的点（比如「`entity` 字段是谁写的」「三路怎么并行汇聚」「`_route_after_item_name_confirm` 何时返回 `node_answer_output`」），当场问、那一跳回炉。尤其别把 ⑧ 的 `node_join` 当"有逻辑"的中转站——它是 `lambda x: {}` 空壳，真正的融合发生在 ⑨~⑫。

### 实现 · 每个手法配代码逐行讲

**手法① 多路取列表 + 兜底（`process` 前 6 行）**：

```python
def process(self, state: QueryGraphState) -> QueryGraphState:
    embedding_search_list = [
        doc.get('entity') for doc in (state.get('embedding_chunks') or []) if isinstance(doc, dict)
    ]
    hyde_embedding_search_list = [
        doc.get('entity') for doc in (state.get('hyde_embedding_chunks') or []) if isinstance(doc, dict)
    ]
```

- `state.get('embedding_chunks') or []`：**兜底防 None**。`embedding_chunks` 可能没被写入（某路搜索失败/为空），`or []` 保证下面能 `for`。**反例**：直接 `state['embedding_chunks']` 遇 None 抛 `KeyError`/TypeError，整图崩。
- `doc.get('entity')`：检索结果里每项是 `{"entity": {...}, ...}` 的字典，这里只取 `entity`（真正的文档负载）。
- `isinstance(doc, dict)`：**过滤非字典**。**反例**：混进 `None`/字符串时 `.get` 直接崩。
- 为什么只取向量/HyDE 两路、**不取网络搜索**：注释明确"排除网络搜索（rerank 节点做）"——web 那路由下游 `node_rerank` 决定是否并入，此处融合只做「向量 + HyDE」，是**职责边界**。

**手法② 加权 RRF 融合（`_rrf_merge` 整方法，逐行 + 反例）**：

```python
def _rrf_merge(self, rrf_inputs, k: int = 60, max_results: int = None) -> List[Tuple[Dict[str, Any], float]]:
    chunk_scores = {}   # 每个 chunk_id 累计的 RRF 得分（跨两路融合）
    chunk_data = {}     # 每个 chunk_id 对应的文档（只保留第一次出现）
    for rrf_input, weight in rrf_inputs:            # 遍历每路：(该路文档列表, 该路权重)
        for rank, doc in enumerate(rrf_input, start=1):   # rank 从 1 计（排第几）
            chunk_id = doc.get('chunk_id')          # 用 chunk_id 当聚合键：合并"两路都命中"的同一块
            chunk_scores[chunk_id] = chunk_scores.get(chunk_id, 0.0) + weight / (k + rank)
                # RRF 公式：score += weight/(k+rank)。排名越靠前(rank 越小)分越高；
                # 用"相加"融合两路：两路都命中的 chunk 分更高 → 天然去重 + 抬升"多路共识"文档。
                # 反例：若直接加 BGE-M3 的 cos 相似度与 HyDE 的相似度，两路量纲/分布不同，硬加=错排；
                #   RRF 只比"排名"，量纲天然可比，这正是选 RRF 而非直接加权分数相加的原因。
            chunk_data.setdefault(chunk_id, doc)    # 只保留首次遇到的文档版本
                # 反例：若不去重，同 chunk_id 会以两个不同版本重复出现 → 下游 rerank 拿到重复文档且版本打架。
    unsorted_results = [(chunk_data[cid], score) for cid, score in chunk_scores.items()]
    sorted_results = sorted(unsorted_results, key=lambda x: x[1], reverse=True)
        # key=x[1] 即按"分数"降序；reverse=True 让分数高在前。
        # 反例：若只对"文档列表"排序而丢了 score，就丢了 RRF 信息，只剩召回顺序 ≈ 没融。
    return sorted_results[:max_results] if max_results else sorted_results
        # 动态截断：max_results=None 返回全量；否则取前 N。断崖截断交给下游 node_rerank，本节点只做融合。
```

**手法③ 分离"分数"与"文档"（`process` 后半段）**：

```python
    rrf_merge_results = self._rrf_merge(rrf_inputs)
    rrf_chunks = [doc for doc, _ in rrf_merge_results]   # 只取文档，不取 score
    state['rrf_chunks'] = rrf_chunks
    add_done_task(state.get("session_id"), self.name, state.get("is_stream"))
    return state
```

- `doc for doc, _ in ...`：**分离开**——下游 `node_rerank` 只吃 `dict`（读 `rrf_doc.get('content')`），不要分数。**反例**：把整个 `(doc, score)` 元组塞回 `state['rrf_chunks']`，`node_rerank` 拿到的不是 dict 而是 tuple → `.get` 崩。
- `add_done_task(session_id, name, is_stream)`：**任务追踪**（横切，普通函数调用）。基类 `__call__` 开场 `add_running_task`，这里 `add_done_task` 收尾，成对记录"节点开始/完成"。

### 用法 · 可照写的最小完整示例（来自 `node_rrf.py` 的 `__main__`）

```python
from processor.query_processor.nodes.node_rrf import NodeRrf

mock_state = {
    "embedding_chunks": [
        {"entity": {"chunk_id": "chunk_1", "content": "向量#1"}},
        {"entity": {"chunk_id": "chunk_2", "content": "向量#2"}},
        {"entity": {"chunk_id": "chunk_3", "content": "向量#3"}},
    ],
    "hyde_embedding_chunks": [
        {"entity": {"chunk_id": "chunk_1", "content": "HyDE#1"}},
        {"entity": {"chunk_id": "chunk_4", "content": "HyDE#2"}},
        {"entity": {"chunk_id": "chunk_2", "content": "HyDE#3"}},
    ],
}
node = NodeRrf()
result = node(mock_state)     # 走 NodeBase.__call__ → process → _rrf_merge
# → result["rrf_chunks"]：chunk_1（两路都中，1/61+1/61）排最前，chunk_2 其次（1/62+1/63），chunk_4 又其次（HyDE rank2=1/62），
#   chunk_3 最后（向量 rank3=1/63）；全是 dict，不含 score（RRF 只比排名，顺序由分数决定，与召回先后无关）
```

**触发回放**：在真实流里，输入两路召回（`embedding_chunks` + `hyde_embedding_chunks`）→ `NodeRrf.__call__` → `_rrf_merge` → 输出 `state['rrf_chunks']`（融合后的文档字典列表）→ `node_rerank._step_1_merge_multi_source_docs` 直接 `rrf_doc.get('content')` 取文——**下游拿到的是干净 dict**，正呼应③里"分离分数与文档"那一手的动机。

**收尾洞察**：这个节点你从头到尾看不到任何"直接加相似度分数"的动作——它只用 `rank` 把多路"共识"提出来。这就是 RRF 这一类"融合排序"的通式：**多路召回 + 只比排名、不比原始分数**。再看一遍会发现：**业务节点里完全没有 RRF 公式的灵活性代码（k、权重、是否截断都不知道），只管"取列表 → 交给 `_rrf_merge` → 写回 state"——真正的算法收敛在 `_rrf_merge`，节点只做编排**。这比十句"单一职责"都直观。

---

## 二、达标判定表 / 讲解自检表

与本样例**同一套标准**，见 `黄金样例.md` 第二节（每段详细度基准）与第三节（讲解产出自检）。本样例遵守：场景带数值（小张 / k=60）、调用链 14 跳带真实类名、整方法逐行 + 每手法反例、用法可照写 + 触发回放 + 收尾洞察。
