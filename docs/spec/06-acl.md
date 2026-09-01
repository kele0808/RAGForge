# Step 6 · ACL：检索前过滤

**Goal:** 用户只能搜到 `documents.owner_id == user_id` 的 chunk。过滤发生在 SQL 里，不是拿到结果再丢。

**Prerequisites:** Step 5 的 HybridRetriever。

## 为什么

企业 RAG 没权限就是事故。向量库先搜再过滤，在「用户只能看 1% 文档」时会召回不足或漏出邻居文档。本项目从这一步起，所有检索 SQL 必须带 `owner_id` 条件。

## 完成标准

- [ ] `RetrieveRequest.user_id` 为必填
- [ ] lexical / vector / hybrid 三条路径都过滤 `documents.owner_id`
- [ ] 用户 A 的 query 不能返回用户 B 的 chunk，即使向量更近
- [ ] 没有 `user_id` 的旧 `search(query)` 对外接口删除或变成 private
- [ ] 测试覆盖：两用户两篇文档，交叉查询为空或仅自己的

## Files

- Create: `src/rag/retrieve/acl.py`
- Modify: `src/rag/retrieve/lexical.py`
- Modify: `src/rag/retrieve/vector.py`
- Modify: `src/rag/retrieve/service.py`
- Modify: `src/rag/qa.py` — `ask(..., user_id=...)`
- Modify: `src/rag/types.py` — `RetrieveRequest`
- Create: `tests/test_acl.py`

## Interfaces

```python
# types.py
@dataclass(frozen=True)
class RetrieveRequest:
    user_id: str
    query: str
    top_k: int = 8

# acl.py
def owner_clause():
    """Return a SQLAlchemy expression: Document.owner_id == user_id. Used by searchers."""

# service.py
class RetrieveService:
    async def retrieve(self, req: RetrieveRequest) -> list[ChunkHit]:
        if not req.user_id.strip():
            raise ValueError("user_id required")
        ...
```

本步把 `HybridRetriever.retrieve(query)` 改成 `RetrieveService.retrieve(RetrieveRequest)`。对外只保留这一个入口。Lexical/Vector 的 `search` 增加必填参数 `user_id: str`。

## SQL 约束（必须长这样）

```sql
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.status = 'ready'
  AND d.owner_id = :user_id
  AND ...
```

禁止：

```python
hits = await search(...)
return [h for h in hits if h.owner == user]  # 不允许作为唯一 ACL
```

后过滤可以当单测里的反例说明，不能当实现。

## 测试

准备：

- user-a 文档 A，chunk 内容 `alpha-secret-token`
- user-b 文档 B，chunk 内容 `beta-secret-token`

用例：

1. `RetrieveRequest(user_id="user-a", query="alpha-secret-token")` → 只有 A。
2. `RetrieveRequest(user_id="user-a", query="beta-secret-token")` → `[]`（即使 B 全文能匹配）。
3. `user_id=""` → `ValueError`。

向量路同样测：把 B 的 embedding 设成和 query 完全相同，A 设成全 0；user-a 查询仍不得返回 B。

## ask() 签名

```python
async def ask(
    question: str,
    *,
    user_id: str,
    retriever: RetrieveService,
    generator: AnswerGenerator,
) -> str:
```

漏传 `user_id` 必须是 TypeError，不要默认 `"admin"`。

## 常见坑

- 只给 vector 加了 owner 过滤，lexical 忘了：关键词能泄漏。
- JOIN documents 却过滤 `chunks` 上不存在的 user 列。
- 用 `IN (SELECT doc_id FROM ...)` 子查询一次性塞一万个 id：本步 owner 模型不需要；不要过早设计成把 ACL 列表拉到应用层。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Filter retrieval by document owner before search.

EOF
)"
```

## 下一步

[07-rerank.md](./07-rerank.md)：对融合后的候选做 cross-encoder 精排。
