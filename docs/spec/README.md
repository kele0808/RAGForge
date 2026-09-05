# RAGForge Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从零做出一套可落地的 RAG：文档进 PostgreSQL，混合检索后生成带引用的答案。

**参考项目:** 每一步实现前，对照 [infiniflow/ragflow](https://github.com/infiniflow/ragflow) 的等价实现做批判性借鉴。规则见 [`.cursor/rules/ragforge-learning-norms.mdc`](../../.cursor/rules/ragforge-learning-norms.mdc)。RAGFlow 是同领域的生产项目，栈不同（Peewee+MySQL+ES+MinIO+Redis vs. 我们只用 SQLAlchemy+Postgres/pgvector）——是参考系，不是模板。

**Architecture:** LlamaIndex 只负责解析/切块/写入。PostgreSQL 是唯一索引（正文 + tsvector + pgvector + ACL）。Retrieval Service 先 ACL，再全文+向量召回，RRF 融合后 rerank，只返回 chunk。LangGraph 只编排「改写 → 检索 → 生成」。

**Tech Stack:** Python 3.12+ · FastAPI · SQLAlchemy 2 / asyncpg · Alembic · pgvector · OpenAI `text-embedding-3-small` · LlamaIndex · LangGraph · pytest

## Global Constraints

- 语言：Python 3.12+，包路径固定为 `src/rag/`
- Embedding：只允许 `text-embedding-3-small`，维度固定 `1536`；一个库一个模型，换模型必须改列类型并全量重 embed
- 存储：PostgreSQL 是唯一索引；文档、chunk、向量、ACL 同一事务
- 检索：先 ACL，再召回；检索接口不调用 LLM
- 生成：只根据给定 chunk 回答；没有命中就明确说没有找到，禁止编造
- 融合：RRF，不是加权求和
- 测试：每一步先写失败测试再写实现（TDD）
- 密钥：只放 `.env`，不要提交；提交 `.env.example`
- 不要一次铺开全部目录；按下面 11 步，每步结束必须能运行或测试

## 你现在在哪

你只听说过 RAG，还没写过。所以前四步只做最小闭环：

```text
Markdown → 切块 → embedding → 写入 PG → 向量 TopK → LLM 生成
```

第 5 步起才加全文、权限、精排、引用、编排、HTTP、PDF。不要跳步。

## 步骤总览

| 步 | 文档 | 做完你能证明什么 |
|---|---|---|
| 1 | [01-scaffold.md](./01-scaffold.md) | `pytest` 能跑，配置能读到 embedding 模型名 |
| 2 | [02-store.md](./02-store.md) | PG 里有 documents / chunks 表，能插入一条 chunk |
| 3 | [03-ingest.md](./03-ingest.md) | 一篇 Markdown 变成带 1536 维向量的多条 chunk |
| 4 | [04-vector-qa.md](./04-vector-qa.md) | 问一句能根据向量检索生成答案（第一条 RAG） |
| 5 | [05-hybrid-rrf.md](./05-hybrid-rrf.md) | 订单号/专有名词靠全文召回，语义靠向量，RRF 合并 |
| 6 | [06-acl.md](./06-acl.md) | 用户看不到没有权限的文档 |
| 7 | [07-rerank.md](./07-rerank.md) | 候选 50 条压成 Top 8，精排分数可测 |
| 8 | [08-citations.md](./08-citations.md) | 答案里带 `[1]` 并能对上 chunk_id |
| 9 | [09-graph.md](./09-graph.md) | 多轮指代改写后走同一条检索-生成图 |
| 10 | [10-api.md](./10-api.md) | HTTP 可入库、可检索、可问答 |
| 11 | [11-parsers.md](./11-parsers.md) | PDF/DOCX 也能进同一套管线 |

## 依赖方向

```text
api → graph → generate
            → retrieve → store → PostgreSQL
ingest → embedder(text-embedding-3-small) → store
```

后一步可以调用前一步的接口，不许反向依赖（例如 retrieve 不得 import generate）。

## 每一步怎么用这份 spec

1. 只打开**当前步**的文档，不要提前读后面的实现细节当作业。
2. 按文档里的文件列表创建文件；路径必须一致，后面的步骤会按这些名字引用。
3. 先写测试，跑红，再写实现，跑绿，再按文档里的 commit message 提交。
4. 「完成标准」全部勾上再进入下一步。
