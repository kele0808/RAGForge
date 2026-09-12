# Step 6 · ACL：检索前过滤

**Goal:** 用户只能搜到 `owner_id == user_id` 的 chunk。过滤在 SQL 里，经过 `visible_clause`，不是拿到结果再丢。

**Prerequisites:** Step 5 的 HybridRetriever。

## 为什么

企业 RAG 没权限就是事故。向量库先搜再过滤，在「用户只能看 1% 文档」时会召回不足或漏出邻居文档。本步起，所有检索 SQL 必须带可见性条件。

最终企业形态会有租户、知识库、用户组、分享、JWT。那些**不在本步做**。本步只证明：别人的文档进不了召回，并且过滤只写在一处，以后换授权表不用改两条 searcher。

## 本步 / 以后

| | 本步做完就能测 | 以后另一步再加 |
|---|---|---|
| 谁能看见 | `documents.owner_id == user_id` | `document_acl` 多行授权、用户组 |
| 写在哪 | 只在 `visible_clause(user_id)` | 只改这个函数 + 入库多写授权行 |
| 身份 | 调用方传入 `user_id` | JWT / 网关注入，不信任请求体 |
| 不做 | — | 分享 API、多租户、计费 |

## 完成标准

- [ ] `RetrieveRequest.user_id` 为必填
- [ ] lexical / vector / hybrid 都调用 `visible_clause`，不各自写死 `owner_id`
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
- Create: `tests/retrieve/test_acl.py`

本步**不**新建表、不写 Alembic。`owner_id` 第 2 步已经有了。

## Interfaces

```python
# types.py
@dataclass(frozen=True)
class RetrieveRequest:
    user_id: str
    query: str
    top_k: int = 8

# acl.py
def visible_clause(user_id: str):
    """本步：Document.owner_id == user_id。以后只改这里。"""

# service.py
class RetrieveService:
    async def retrieve(self, req: RetrieveRequest) -> list[ChunkHit]:
        if not req.user_id.strip():
            raise ValueError("user_id required")
        ...
```

本步把 `HybridRetriever.retrieve(query)` 改成 `RetrieveService.retrieve(RetrieveRequest)`。对外只保留这一个入口。Lexical/Vector 的 `search` 增加必填 `user_id: str`，内部调用 `visible_clause(user_id)`。

## SQL 约束（必须长这样）

```sql
FROM chunks c
JOIN documents d ON d.id = c.document_id
WHERE d.status = 'ready'
  AND d.owner_id = :user_id
  AND ...
```

`owner_id` 条件必须来自 `visible_clause`，不要在 lexical / vector 里各写一份字面量。

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

向量路同样测：把 B 的 embedding 设成和 query 完全相同，A 设成全 **-1**（不要用全 0，cosine 会是 NaN）。user-a 查询仍不得返回 B。

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
- 用 `IN (SELECT doc_id FROM ...)` 把 ID 拉到应用层：本步不需要。
- 本步就建 `document_acl`、分享、JWT：范围过大，先把「别人的文档不可见」做绿。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Filter retrieval by document owner before search.

EOF
)"
```

## 下一步

[07-rerank.md](./07-rerank.md)：对融合后的候选做 cross-encoder 精排。

授权表 / 分享 / JWT 不插在 6 和 7 之间，等 11 步主线跑通或单独开一步再做。
