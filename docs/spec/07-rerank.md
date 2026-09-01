# Step 7 · Rerank

**Goal:** RRF 之后的候选（默认 50）用 cross-encoder 重新打分，截断为生成用的 TopK（默认 8）。

**Prerequisites:** Step 6 的 `RetrieveService`。

## 为什么

RRF 只融合排名，不理解「问题和这段话是否真相关」。Cross-encoder 同时看 query 和 document，适合精排小候选集。不要用 rerank 替代召回，也不要把 8B embedding 当成精排。

## 完成标准

- [ ] `Reranker.rerank(query, hits) -> list[ChunkHit]` 按新分数降序
- [ ] `RetrieveService`：ACL → 双路 recall_k → RRF 取 `rerank_candidates` → rerank → `top_k`
- [ ] 单测用 fake reranker（按关键词是否出现打分），不强制 CI 下载大模型
- [ ] 配置可切换：`RERANK_MODEL` 默认 `BAAI/bge-reranker-base`
- [ ] 候选少于 2 条时 skip 模型，原样返回

## Files

- Create: `src/rag/retrieve/rerank.py`
- Modify: `src/rag/retrieve/service.py`
- Modify: `src/rag/config.py`

```python
rerank_model: str = "BAAI/bge-reranker-base"
rerank_candidates: int = 50
```

- Modify: `pyproject.toml`：`"sentence-transformers>=3.0"`
- Create: `tests/test_rerank.py`
- Modify: `tests/test_hybrid.py` 或新建 `tests/test_retrieve_service.py`

## Interfaces

```python
class Reranker:
    def rerank(self, query: str, hits: list[ChunkHit]) -> list[ChunkHit]:
        """Return new list, same hits, score replaced by model score, sorted desc."""

class FakeReranker(Reranker):
    """For tests: score = 1.0 if query substring in content else 0.0."""

class CrossEncoderReranker(Reranker):
    def __init__(self, model_name: str): ...
```

`RetrieveService` 构造函数注入 `Reranker`，测试注入 `FakeReranker`。生产注入 `CrossEncoderReranker`。

流程：

```text
req.top_k = 8
recall = 50
lex, vec = gather(...)
fused = rrf(lex, vec, top_k=recall)          # 最多 50
fused = fused[:settings.rerank_candidates]
reranked = reranker.rerank(req.query, fused)
return reranked[:req.top_k]
```

注意：RRF 的 `top_k` 此时是候选数 50，不是最终 8。最终截断发生在 rerank 之后。

## FakeReranker 单测（必须有）

hits 顺序故意排错：

```python
query = "医院证明"
hits = [
    ChunkHit(..., content="食堂菜单", score=0.99),
    ChunkHit(..., content="病假需要医院证明", score=0.10),
]
out = FakeReranker().rerank(query, hits)
assert "医院证明" in out[0].content
```

再测 `RetrieveService`：lexical/vector 用 stub 返回固定列表，断言最终 `[:top_k]` 来自 reranker 排序。

## 真模型（手工）

第一次本地下载 `BAAI/bge-reranker-base` 可能较慢。CI 默认不跑真模型。可加：

```bash
pytest tests/test_rerank.py -k real --runslow
```

没有 GPU 用 CPU 即可，候选 50 条可接受。

## 不要做的事

- 不要对全库跑 cross-encoder
- 不要把 rerank 分数和 RRF 再加权混一次（rerank 分数直接作为最终 score）
- 不要在 rerank 里再打一遍 OpenAI embedding

## 常见坑

- sentence-transformers 把 query-document pair 顺序写反：必须 `(query, content)`。
- 在 async 事件循环里直接跑同步模型推理会卡住。用 `asyncio.to_thread(reranker.rerank, ...)`。
- 忘了截断 8 条：prompt 会膨胀，费用和幻觉都上升。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Rerank hybrid candidates with a cross-encoder.

EOF
)"
```

## 下一步

[08-citations.md](./08-citations.md)：答案必须能指回 chunk。
