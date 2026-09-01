# 00 · 系统概览（先读，不写代码）

本页是地图，不是任务。写代码从 [01-scaffold.md](./01-scaffold.md) 开始。

## RAG 在本项目里的含义

用户问题不会直接丢给 LLM。流程固定为：

1. 事先把文档切成 chunk，算 embedding，和原文一起存进 PostgreSQL。
2. 提问时，用同一套 embedding 模型把问题变成向量，同时用分词做全文检索。
3. 两路结果用 RRF 合成，再 rerank，取出若干 chunk。
4. 把这些 chunk 放进 prompt，让模型只根据它们回答，并带引用。

没有检索到的内容，模型必须说找不到。这是本项目和「随便聊」的分界。

## 数据模型（逻辑）

```text
User ──(acl)──► Document ──(1:N)──► Chunk
                                  ├─ content
                                  ├─ tsv          # 全文
                                  ├─ embedding    # vector(1536)
                                  ├─ page / source
                                  └─ chunk_index
```

- **Document**：一篇文件的元数据（路径、状态、谁能看）。
- **Chunk**：检索的最小单位。问答时返回的是 chunk，不是整篇文档。
- **ACL**：存在 document 上（或 document_acl 表），检索时先过滤 `doc_id`，再搜向量。绝不能先搜 50 条再丢掉无权限的。

## 运行时两条链路

**入库（离线，可异步）**

```text
文件 → parser → chunker → embedder → repository.insert（同一事务）
```

**问答（在线）**

```text
question → rewrite? → retrieve(user, question) → generate(question, chunks) → answer + citations
```

`retrieve` 不调 LLM。`generate` 不直接打 PG。

## 检索内部顺序（第 5–7 步才全部出现）

```text
1. ACL：user → 允许的 doc_id 集合
2. lexical：tsvector TopN
3. vector：embedding <=> query TopN
4. RRF：合并两路排名
5. rerank：cross-encoder 打分，截 TopK
6. 返回 ChunkHit[]（文本、出处、分数）
```

第 4 步只有第 3 项。第 5 步加上 2 和 4。第 6 步加上 1。第 7 步加上 5。

## 固定接口名（后面每步都用这些名字）

```python
class ChunkHit:
    chunk_id: str
    document_id: str
    content: str
    source: str          # 文件名或路径
    page: int | None
    score: float

class RetrieveRequest:
    user_id: str
    query: str
    top_k: int = 8

class RetrieveService:
    async def retrieve(self, req: RetrieveRequest) -> list[ChunkHit]: ...

class Answer:
    text: str
    citations: list[ChunkHit]
```

第 4 步可以暂时没有 `user_id`；第 6 步必须有。

## 明确不做（YAGNI）

- 不做 GraphRAG / RAPTOR / 知识图谱
- 不用 Elasticsearch
- 不在本仓库实现 Agent 工具调用（工单/CRM）
- 不把 LlamaIndex QueryEngine 当成问答入口
- 不支持运行时切换 embedding 模型
- 第一期不做多租户计费、工作流画布、前端 UI

## 环境

```bash
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/ragforge
```

本地 PostgreSQL 需要扩展：

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

中文全文检索第 5 步再用；第 2 步先把 `tsv` 列建好即可。
