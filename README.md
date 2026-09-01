# folio-rag

企业级 RAG：文档入库 PostgreSQL，检索后生成带引用的答案。

当前仓库只有说明和 MIT 许可证，源码按下面的目录自己建。

## 做什么

把文档切块、向量化后写入 PostgreSQL，问答时先检索再生成。检索先做权限过滤，再全文 + 向量双路召回，RRF 融合后 rerank，最后只根据命中的 chunk 回答并带出处。

## 架构

```text
文档 → 解析 / 切块 / Embedding → PostgreSQL
                                    ├─ chunk 正文
                                    ├─ tsvector 全文
                                    ├─ pgvector 向量
                                    └─ doc_id / ACL

用户问题 → 改写 → Retrieval Service → 生成 + 引用
                     ├─ ACL
                     ├─ 全文召回 + 向量召回
                     ├─ RRF
                     └─ Rerank TopK
```

约定：

- LlamaIndex 只负责解析、切块、写入，不直接出答案。
- PostgreSQL 是唯一索引，文档、向量、权限同一事务。
- Retrieval Service 先 ACL，再混合召回；接口只返回 chunk 和出处。
- 生成只根据检索结果回答，找不到就说没有。
- LangGraph 只编排「改写 → 检索 → 生成」。

## 选型

| 层 | 选择 |
|---|---|
| 语言 | Python |
| Embedding | OpenAI `text-embedding-3-small`（1536 维） |
| 切块 | LlamaIndex |
| 存储 | PostgreSQL + pgvector + tsvector |
| 融合 | RRF |
| 精排 | Cross-encoder rerank |
| 编排 | LangGraph |
| API | FastAPI |

一个知识库只绑定这一个 embedding 模型。换模型必须改 `vector(1536)` 并全量重 embed。

## 计划目录

```text
folio-rag/
├── pyproject.toml
├── .env.example
├── alembic.ini
├── alembic/
│   └── versions/
├── src/rag/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口
│   ├── config.py               # OPENAI_API_KEY, embedding=text-embedding-3-small
│   ├── models/
│   │   ├── document.py         # 文档、状态、ACL
│   │   └── chunk.py            # content, tsv, embedding vector(1536)
│   ├── ingest/
│   │   ├── parser.py           # 解析 PDF/DOCX
│   │   ├── chunker.py          # LlamaIndex 切块
│   │   ├── embedder.py         # OpenAI text-embedding-3-small
│   │   └── pipeline.py         # parse → chunk → embed → 写 PG
│   ├── store/
│   │   ├── db.py               # SQLAlchemy / asyncpg
│   │   └── repository.py       # 文档、chunk 读写
│   ├── retrieve/
│   │   ├── acl.py              # 先按 user 滤 doc_id
│   │   ├── lexical.py          # PG tsvector
│   │   ├── vector.py           # pgvector cosine
│   │   ├── fusion.py           # RRF
│   │   ├── rerank.py           # cross-encoder
│   │   └── service.py          # ACL → 双路召回 → RRF → rerank
│   ├── generate/
│   │   ├── rewrite.py          # 多轮改写
│   │   ├── prompt.py           # 只根据 chunk 回答
│   │   └── answer.py           # 生成 + 引用
│   ├── graph/
│   │   └── rag_graph.py        # LangGraph: rewrite → retrieve → generate
│   └── api/
│       ├── ingest.py           # POST /documents
│       ├── retrieve.py         # POST /retrieve
│       └── chat.py             # POST /chat
└── tests/
    ├── test_chunker.py
    ├── test_fusion.py
    └── test_retrieve.py
```

依赖方向：

```text
api → graph → generate
            → retrieve → store → PostgreSQL
ingest → embedder(text-embedding-3-small) → store
```

## 建议实现顺序

第一次做 RAG，不要按目录一次铺开。

1. Markdown 切块 → `text-embedding-3-small` → 写入 PG → 向量 TopK → LLM 生成
2. 加上 tsvector 全文检索和 RRF
3. 再补 ACL、rerank、引用、LangGraph、FastAPI

## 运行前准备

- Python 3.12+
- PostgreSQL，启用 `vector` 扩展
- OpenAI API Key

环境变量（实现时放到 `.env`，不要提交）：

```bash
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
DATABASE_URL=postgresql://user:pass@localhost:5432/rag
```

## License

[MIT](LICENSE)
