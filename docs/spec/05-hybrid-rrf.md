# Step 5 · 全文检索与 RRF

**Goal:** 关键词一路 + 向量一路，用 Reciprocal Rank Fusion 合并，取代「只按向量排序」。

**Prerequisites:** Step 4 的 `ChunkHit` / `VectorSearcher` 可用。

## 为什么

向量擅长「意思相近」，不擅长订单号、接口名、人名精确匹配。企业里这两类问题都有。RRF 只看排名不看分数，避开 BM25 和 cosine 量纲不同的问题。本项目**不用** RAGFlow 那种加权求和。

## 完成标准

- [ ] 入库时自动填充 `chunks.tsv`
- [ ] `LexicalSearcher.search(query, top_k)` 能靠精确词命中 chunk
- [ ] `rrf_fuse(rank_lists, k=60)` 单测覆盖：只在一路出现、两路都出现、空列表
- [ ] `HybridRetriever.retrieve` 先两路召回再 RRF，返回 `list[ChunkHit]`
- [ ] `ask()` 改为走 HybridRetriever，而不是直接 VectorSearcher
- [ ] 有一个测试：query 为独特 token（如 `ADX-156`），纯向量可能很弱，RRF 后该 chunk 仍进 TopK（构造数据保证全文能中）

## Files

- Create: `src/rag/retrieve/lexical.py`
- Create: `src/rag/retrieve/fusion.py`
- Create: `src/rag/retrieve/service.py`
- Modify: `src/rag/ingest/pipeline.py` — 写入前计算 tsv，或在 SQL 用 `to_tsvector`
- Modify: `src/rag/store/repository.py` — 允许插入时带 tsv，或由 DB 生成
- Modify: `src/rag/qa.py` — 改用 HybridRetriever
- Create: `tests/test_fusion.py`
- Create: `tests/test_lexical.py`
- Create: `tests/test_hybrid.py`
- Alembic 新修订：`0002_chunks_tsv_gin.py`

```sql
CREATE INDEX ix_chunks_tsv ON chunks USING gin (tsv);
```

## 中文/英文全文

第一期用 PostgreSQL 自带配置，简单可跑：

```sql
to_tsvector('simple', content)
plainto_tsquery('simple', query)
```

`simple` 不分中文词，但空格/标点分隔的英文、数字、代码符号够用。中文连续句子会偏弱——第 5 步接受这个限制，文档里写明。不要这一步就上 `zhparser`（需要额外扩展，环境难复现）。

生成 tsv 的推荐方式（写入时）：

```sql
tsv = to_tsvector('simple', :content)
```

在 repository insert 用 SQLAlchemy：`func.to_tsvector("simple", content)`。

检索：

```sql
SELECT c.id, ..., ts_rank_cd(c.tsv, q) AS rank
FROM chunks c, plainto_tsquery('simple', :query) q
WHERE c.tsv @@ q
  AND d.status = 'ready'
ORDER BY rank DESC
LIMIT :top_k
```

`ChunkHit.score` 对全文一路可暂存 `ts_rank_cd`；RRF **不要用这个 score**，只用该路内部的名次。

## RRF

公式：

```text
RRF(d) = Σ 1 / (k + rank_i(d))
```

- `rank_i` 从 **1** 开始（第 1 名是 1，不是 0）
- 默认 `k=60`
- 某条 chunk 只出现在一路：只加那一路
- 两路同一 `chunk_id` 必须当成同一文档合并
- 最终按 RRF 分数降序，截断到 `top_k`

```python
# fusion.py
def rrf_fuse(
    ranked_id_lists: list[list[str]],
    *,
    k: int = 60,
    top_k: int = 8,
) -> list[tuple[str, float]]:
    """Return (id, rrf_score) sorted desc."""
```

单测必须手算一个小例子：

```text
list A: [id1, id2, id3]
list B: [id2, id4]
k=60
id2 = 1/61 + 1/61
id1 = 1/61
id3 = 1/63
id4 = 1/62
order: id2, id1, id4, id3
```

把这个数字写进 assert（允许 float 误差 `1e-9`）。

## Interfaces

```python
class LexicalSearcher:
    async def search(self, query: str, *, top_k: int = 50) -> list[ChunkHit]: ...

class HybridRetriever:
    def __init__(self, lexical: LexicalSearcher, vector: VectorSearcher, rrf_k: int = 60): ...

    async def retrieve(self, query: str, *, top_k: int = 8, recall_k: int = 50) -> list[ChunkHit]:
        """
        Run lexical and vector with recall_k each.
        Fuse with RRF.
        Rebuild ChunkHit list (content from either side; prefer vector hit's score field
        replaced by rrf score).
        """
```

两路并行：`asyncio.gather(lexical.search(...), vector.search(...))`。

命中详情：用 dict 以 `chunk_id` 为键合并 ChunkHit，RRF 之后把 `score` 改成 RRF 分。

## 召回数量

- 每一路 `recall_k=50`
- 融合后 `top_k=8` 给生成
- 生成侧仍然只用这 8 条，不要把 50 条塞进 prompt

## 改 qa.py

```python
async def ask(question, *, retriever: HybridRetriever, generator: AnswerGenerator) -> str:
    hits = await retriever.retrieve(question, top_k=8)
    return await generator.generate(question, hits)
```

删除对 `VectorSearcher.search` 的直接依赖（测试可以仍单测 VectorSearcher）。

## 测试：精确 token

插入两个 chunk：

- A content: `发票号 ADX-156 已作废`
- B content: 一段与发票无关、但 embedding fake 成更靠近 query 的向量

Query：`ADX-156`

Lexical 必须把 A 放在第 1。RRF 之后 A 必须在返回列表里。这样证明混合检索不是摆设。

## 常见坑

- 用 `to_tsvector('english', ...)` 处理中文：english stemmer 会把情况弄更糟。用 `simple`。
- 把 ts_rank 和 cosine 直接相加：这正是我们拒绝的做法。测试里不要出现 `0.7 * a + 0.3 * b`。
- `rank` 从 0 起：RRF 会和论文不一致，单测会失败。从 1 开始。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Add lexical search and RRF hybrid retrieval.

EOF
)"
```

## 下一步

[06-acl.md](./06-acl.md)：检索前按用户过滤文档。
