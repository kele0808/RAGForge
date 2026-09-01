# Step 4 · 第一条 RAG：向量检索 + 生成

**Goal:** `question → embed → cosine TopK → prompt → LLM 答案`。没有 ACL、没有全文、没有 RRF、没有引用格式。

**Prerequisites:** Step 3 能入库。库里至少有 `fixtures/sample.md`。

## 为什么这是「第一次 RAG」

到这里你才走完「检索增强生成」：模型看到的不是全库，只是最近的几条 chunk。如果切块或 embedding 错了，这一步的答案会明显胡说——这是你要亲眼看到的现象。

## 完成标准

- [ ] `VectorSearcher.search(query, top_k=8)` 返回按余弦相似度从高到低的 chunk
- [ ] 问「病假三天以上要什么」能命中含「医院证明」的 chunk（真 embedding 或对 fixture 的集成测试）
- [ ] `generate_answer(question, chunks)` 的 prompt 含全部 chunk 原文，并写明「只能根据资料回答」
- [ ] 资料里没有的问题，答案须包含「没有」或「未找到」这类否定（prompt 约束 + 单测可用 fake LLM 断言 prompt 里有该指令）
- [ ] retrieve 模块不 import `rag.generate`，generate 不 import `rag.ingest`

## Files

- Create: `src/rag/retrieve/__init__.py`
- Create: `src/rag/retrieve/vector.py`
- Create: `src/rag/generate/__init__.py`
- Create: `src/rag/generate/prompt.py`
- Create: `src/rag/generate/answer.py`
- Create: `src/rag/qa.py` — 组合函数，供命令行/测试调用，**还不是** LangGraph
- Create: `tests/test_vector_search.py`
- Create: `tests/test_prompt.py`
- Create: `tests/test_qa.py`
- Modify: `pyproject.toml` 如需：无新强制依赖（OpenAI 已有）

第 4 步不要创建 `acl.py` / `fusion.py` / `lexical.py` / `graph/`。

## Interfaces

```python
@dataclass(frozen=True)
class ChunkHit:
    chunk_id: str
    document_id: str
    content: str
    source: str
    page: int | None
    score: float  # cosine similarity, higher is better

class VectorSearcher:
    def __init__(self, session: AsyncSession, embedder: Embedder): ...

    async def search(self, query: str, *, top_k: int = 8) -> list[ChunkHit]:
        """Embed query with the SAME model, then pgvector cosine KNN."""

def build_prompt(question: str, chunks: list[ChunkHit]) -> str: ...

class AnswerGenerator:
    def __init__(self, client: openai.AsyncOpenAI, chat_model: str = "gpt-4o-mini"): ...

    async def generate(self, question: str, chunks: list[ChunkHit]) -> str: ...

# qa.py
async def ask(question: str, *, searcher: VectorSearcher, generator: AnswerGenerator) -> str:
    hits = await searcher.search(question, top_k=8)
    return await generator.generate(question, hits)
```

`config.py` 本步可增加（有默认值）：

```python
chat_model: str = "gpt-4o-mini"
```

Chat 模型和 embedding 模型分开。**禁止**用 embedding 模型去 chat，也禁止用 chat 模型去 embed。

## 向量检索 SQL

使用 cosine 距离操作符 `<=>`。pgvector 的 cosine **距离**越小越近，相似度可用 `1 - distance` 作为 `score`。

```sql
SELECT c.id, c.document_id, c.content, d.source, c.page,
       1 - (c.embedding <=> :qvec) AS score
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.status = 'ready'
ORDER BY c.embedding <=> :qvec
LIMIT :top_k;
```

必须用同一 `Embedder.embed_texts([query])` 得到 `:qvec`。不要自己实现对 query 的另一种编码。

空库或 `top_k=0`：返回 `[]`，`generate` 仍要能运行并回答「未找到」。

## Prompt（必须包含这些句子）

`build_prompt` 输出中文或英文都可以，但必须语义上包含：

1. 你是问答助手，只能根据「资料」回答。
2. 资料不足时明确说找不到，不要编造。
3. 逐条列出资料，格式：

```text
[1] source={source} page={page}
{content}
```

4. 最后是用户问题。

单测：

```python
def test_prompt_includes_all_chunks_and_grounding_instruction():
    chunks = [
        ChunkHit("1", "d", "医院证明", "a.md", None, 0.9),
        ChunkHit("2", "d", "提前一天", "a.md", None, 0.8),
    ]
    p = build_prompt("病假要什么", chunks)
    assert "医院证明" in p
    assert "提前一天" in p
    assert "病假要什么" in p
```

再写一个测试断言 prompt 里有「不要编造」或 `must not invent` / `未找到` 指令（选一种语言写死，测试匹配该字符串）。

## generate

```python
await client.chat.completions.create(
    model=settings.chat_model,
    messages=[{"role": "user", "content": build_prompt(question, chunks)}],
    temperature=0,
)
```

`temperature=0` 便于复现。返回 `choices[0].message.content`，空则当「未找到」。

单测注入 fake chat client，不要打真实 API。

## 测试数据策略

**单元测试（vector SQL）：** 可插入已知向量：

- chunk A embedding 全 1
- chunk B embedding 全 0
- query embedding 全 1 → 必须先返回 A

不必调用 OpenAI。给 `VectorSearcher` 注入 fake embedder 返回全 1。

**Prompt 测试：** 不上网。

**qa 集成（可选手工）：** 真 key + 已 ingest 的 sample.md，问「病假超过三天需要什么」，stdout 应出现「证明」。

## 模块边界

```text
retrieve/vector.py  → store, ingest.embedder
generate/*          → retrieve 的 ChunkHit（可把 ChunkHit 放到 src/rag/types.py）
qa.py               → retrieve + generate
```

如果 `ChunkHit` 被两处使用，本步允许新建 `src/rag/types.py` 防止循环 import。推荐现在就建：

```python
# src/rag/types.py
@dataclass(frozen=True)
class ChunkHit:
    ...
```

retrieve 和 generate 都从 `rag.types` 导入。

## 常见坑

- Query 用 `encode`、入库用 `embed_texts` 两套不同前缀：3-small 没有 BGE 那种 query instruction，**入库和查询都走同一个 `embeddings.create`**。
- `ORDER BY score DESC` 却把 `<=>` 距离当成 score：排序会反。要么 `ORDER BY embedding <=> q`，要么 `ORDER BY (1-distance) DESC`，不要混。
- 把检索和生成写在一个函数里无法单测：必须拆 `search` / `build_prompt` / `generate`。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Add vector search and grounded answer generation.

EOF
)"
```

## 下一步

[05-hybrid-rrf.md](./05-hybrid-rrf.md)：加上关键词检索和 RRF。你会看到「专有名词」 suddenly 能搜准。
