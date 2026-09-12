# 00 · 系统概览（先读，不写代码）

本页是地图，不是任务。写代码从 [01-scaffold.md](./01-scaffold.md) 开始。

**节奏（全项目）：** 最终形态按企业 RAG 来想；每一步只做当前能测绿的切片，做完再加下一片。接口留升级点，实现不提前铺全家桶。对照 RAGFlow 等现成项目：好的采纳，不好的按我们的方案。

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
- **ACL**：权限挂在 Document 上，Chunk 继承。第 6 步用 `owner_id` 经 `visible_clause` 过滤；以后加授权表时只改这一处。检索时可见性在**同一条 SQL** 里，绝不能先搜 50 条再丢掉无权限的。

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
1. ACL：visible_clause(user_id) 写进两条召回 SQL（第 6 步 = owner；以后可换成 EXISTS 授权表）
2. lexical：tsvector TopN（已带可见性）
3. vector：embedding <=> query TopN（已带可见性）
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
- 第一期不做多租户计费、工作流画布、前端 UI、JWT 登录、用户组/分享 API
- 表和接口按能演进预留（一个可见性函数、同一条 ingest 管线），但预留 ≠ 提前实现

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
