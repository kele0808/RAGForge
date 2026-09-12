# RAGForge

用 PostgreSQL + pgvector 从零搭一套可演进的 RAG：混合检索、RRF、权限过滤、带引用生成。按 [docs/spec/README.md](docs/spec/README.md) 分步实现；对照 [RAGFlow](https://github.com/infiniflow/ragflow) 批判性借鉴，不照抄。

当前源码做到 **Step 5**（入库 + 向量/全文 + RRF）。还没有 HTTP API（Step 10）。clone 之后先把测试跑绿。

## 克隆后怎么跑

测试库账号写死在 `tests/conftest.py`：`rag` / `rag`，库名 `ragforge_test`。应用库默认是同用户下的 `ragforge`。改用户名或密码的话，测试也会对不上。

**pytest 不打真实 OpenAI**，可以没有 API Key。真入库 / 真问答才需要 `OPENAI_API_KEY`。

### 1. 安装本机依赖

- **Python 3.13**（`requires-python = ">=3.13,<3.14"`，3.12 / 3.14 都不行）
- **[uv](https://docs.astral.sh/uv/)**：`curl -LsSf https://astral.sh/uv/install.sh | sh`
- **PostgreSQL**（建议 16）+ **[pgvector](https://github.com/pgvector/pgvector)**

macOS 示例：

```bash
brew install python@3.13 postgresql@16
# pgvector：按官方文档装进你的 Postgres；装好后能 `CREATE EXTENSION vector`
```

### 2. 拉代码并装包

```bash
git clone <this-repo>
cd RAGForge
uv sync --extra dev
```

### 3. 建库并启用 pgvector

用本机超级用户连上 Postgres（Homebrew 常见是你的系统用户）：

```bash
psql postgres <<'SQL'
CREATE USER rag WITH PASSWORD 'rag';
CREATE DATABASE ragforge OWNER rag;
CREATE DATABASE ragforge_test OWNER rag;
SQL

psql ragforge -c 'CREATE EXTENSION IF NOT EXISTS vector;'
psql ragforge_test -c 'CREATE EXTENSION IF NOT EXISTS vector;'
```

角色或库已存在就跳过对应语句。`CREATE EXTENSION` 需要超级用户，不要用 `rag` 去执行。

### 4. 环境变量

```bash
cp .env.example .env
```

按需填写 `.env`（不要提交）：

```bash
OPENAI_API_KEY=          # 只跑测试可留空
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/ragforge
```

必须是 `postgresql+asyncpg://`。Alembic 会自己换成同步的 `+psycopg`。

### 5. 迁移应用库

```bash
uv run alembic upgrade head
```

pytest 会在 `ragforge_test` 上自动 `upgrade head`，不用手迁测试库。

### 6. 跑测试

```bash
uv run pytest -q
```

全绿即环境可用。还没有 `uvicorn` 服务；问答入口是库里的 `ask()`，需要自己写调用脚本，并注入 retriever / generator。

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
| 语言 | Python 3.13 |
| Embedding | OpenAI `text-embedding-3-small`（1536 维） |
| 切块 | 自研 heading / 句子切块（LlamaIndex 尚未接入） |
| 存储 | PostgreSQL + pgvector + tsvector |
| 融合 | RRF |
| 精排 | Cross-encoder rerank（尚未做） |
| 编排 | LangGraph（尚未做） |
| API | FastAPI（尚未做） |

一个知识库只绑定这一个 embedding 模型。换模型必须改 `vector(1536)` 并全量重 embed。

## 计划目录

```text
RAGForge/
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
└── tests/                      # 与 src/rag/ 同目录
    ├── conftest.py
    ├── test_config.py
    ├── test_qa.py
    ├── generate/
    ├── ingest/
    ├── models/
    ├── retrieve/
    └── store/
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

## TODO

### 第一期（[docs/spec](docs/spec/README.md)）

- [x] Step 1 脚手架与配置
- [x] Step 2 PostgreSQL + pgvector 存储
- [x] Step 3 Markdown 切块入库
- [x] Step 4 向量检索 + 生成（第一条 RAG）
- [x] Step 5 全文检索 + RRF
- [ ] Step 6 按 owner 的 ACL
- [ ] Step 7 Cross-encoder rerank
- [ ] Step 8 结构化引用
- [ ] Step 9 改写 + LangGraph
- [ ] Step 10 FastAPI
- [ ] Step 11 PDF / DOCX 解析

### 第一期之后仍缺（企业落地常见，spec 故意没做）

- [ ] 真认证：现在 `user_id` 由调用方传入，没有登录 / JWT / SSO
- [ ] 文档级分享：多人 ACL、部门、权限变更后如何让检索立刻生效
- [ ] 更新与删除：改文件后重切块、级联删向量、避免脏 chunk
- [ ] 异步入库：大文件队列（Kafka / worker），而不是 HTTP 里同步 embedding
- [ ] 中文分词：`simple` tsvector 对连续中文很弱，需要 zhparser / ParadeDB 一类
- [ ] 扫描件与复杂表格：文字版 PDF 可以，DeepDoc / OCR 没有
- [ ] 模型不写 `[n]` 时的引用对齐（第一期不事后猜）
- [ ] 评测：黄金集 + RAGAS（命中率、忠实度），没有数不能调参
- [ ] 观测：检索 query、filter、chunk_id、延迟、费用（Langfuse 等）
- [ ] 流式输出、限流、幂等入库
- [ ] Docker Compose（API + PostgreSQL + 一键 `vector` 扩展）
- [ ] LangGraph checkpoint 持久化（进程挂了能续）
- [ ] 前端 / 管理界面（切块可视化、检索测试页）

不做（除非以后单独开需求）：GraphRAG、Elasticsearch、用 LlamaIndex/LangChain 当问答入口、运行时切换 embedding 模型。

## License

[MIT](LICENSE)
