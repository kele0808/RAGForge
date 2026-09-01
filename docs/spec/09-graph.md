# Step 9 · 问题改写与 LangGraph

**Goal:** 多轮对话时把「那病假呢」改写成独立问题，再走既有 `RetrieveService` + `AnswerGenerator`。LangGraph 只编排，不拥有索引。

**Prerequisites:** Step 8 的 `ask` 返回 `Answer`。

## 为什么现在才上图

前 8 步没有图也能问答。图的价值是：状态、多轮、以后加「检索不够就再搜一次」。过早上 LangGraph 会让你分不清是检索错了还是图错了。

## 完成标准

- [ ] `rewrite_question(question, history) -> str`：无 history 时原样返回
- [ ] 有 history 时，fake LLM 可测：prompt 含历史和当前句
- [ ] `rag_graph` 节点顺序：`rewrite → retrieve → generate`
- [ ] 单轮（history=[]）与直接 `ask` 行为一致（同一 retriever/generator 注入时）
- [ ] graph 不 import `rag.ingest`，不写 PG

## Files

- Create: `src/rag/generate/rewrite.py`
- Create: `src/rag/graph/__init__.py`
- Create: `src/rag/graph/state.py`
- Create: `src/rag/graph/rag_graph.py`
- Create: `tests/test_rewrite.py`
- Create: `tests/test_graph.py`
- Modify: `pyproject.toml`：`"langgraph>=0.2"`
- Modify: `src/rag/config.py` 如需：无新配置也可以

## State

```python
class Turn(TypedDict):
    role: str   # "user" | "assistant"
    content: str

class RAGState(TypedDict):
    user_id: str
    question: str
    history: list[Turn]
    rewritten: str
    hits: list[ChunkHit]      # 若 TypedDict 难放 dataclass，用 list[dict]
    answer: Answer | None
```

若 TypedDict 与 dataclass 别扭，hits 在图里用 `list[ChunkHit]` 的普通 dataclass state（LangGraph 支持 pydantic/dataclass）。推荐 `pydantic.BaseModel` 做 state，字段同上。

## rewrite 规则

无 history：

```python
def rewrite_question(question: str, history: list[Turn], llm=None) -> str:
    if not history:
        return question.strip()
    ...
```

有 history：调用 chat 模型，prompt 必须要求：

- 输出**一句**完整、可检索的独立问题
- 不要回答问题
- 把指代（这/那/它/病假呢）解析成实体

单测无 LLM：`history=[]` → 等于原句。

有 LLM 的单测用 fake：捕获 messages，断言系统/用户内容里同时出现上一轮「请假要提前一天」和本轮「那病假呢」。

## Graph 节点

```python
async def node_rewrite(state) -> dict:
    rewritten = await rewriter.rewrite(state.question, state.history)
    return {"rewritten": rewritten}

async def node_retrieve(state) -> dict:
    hits = await retriever.retrieve(RetrieveRequest(
        user_id=state.user_id,
        query=state.rewritten,
        top_k=8,
    ))
    return {"hits": hits}

async def node_generate(state) -> dict:
    answer = await generator.generate(state.rewritten, state.hits)
    return {"answer": answer}
```

边：`rewrite → retrieve → generate → END`。

入口函数：

```python
async def run_rag(
    *,
    user_id: str,
    question: str,
    history: list[Turn] | None = None,
) -> Answer:
```

## 测试

`tests/test_graph.py`：

- 注入 fake retriever（记录收到的 query）和 fake generator
- history 为空：retriever 收到的 query == 原始 question
- history 非空 + fake rewriter 返回 `病假超过三天需要什么`：retriever 收到改写后的句子，而不是「那病假呢」

不要在图测试里打真实 OpenAI。

## 不要做的事

- 不要用 LangChain `RetrievalQA`
- 不要在 graph 里做切块入库
- 不要加 multi-agent、工具调用
- 不要 checkpoint 到 Postgres（第一期内存跑通即可）

## Commit

```bash
git commit -m "$(cat <<'EOF'
Orchestrate rewrite, retrieve, and generate with LangGraph.

EOF
)"
```

## 下一步

[10-api.md](./10-api.md)：把入库和问答暴露成 HTTP。
