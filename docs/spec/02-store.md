# Step 2 · PostgreSQL 存储层

**Goal:** 能在同一事务里写入一篇 Document 和若干 Chunk（此时 embedding 可以先塞零向量或在测试里注入假向量）。

**Prerequisites:** Step 1 完成。本机已有 PostgreSQL，并能执行 `CREATE EXTENSION vector`。

## 为什么

检索和入库都只打这一层。表设计错了，后面 9 步都要迁移。这一步就把 `vector(1536)` 和 ACL 字段定死。

## 完成标准

- [ ] 扩展 `vector` 已启用
- [ ] 表 `documents`、`chunks` 存在
- [ ] `chunks.embedding` 类型为 `vector(1536)`
- [ ] 删除 document 时 chunk 级联删除
- [ ] 测试能插入 1 个 document + 2 个 chunk 再按 `document_id` 读出
- [ ] 没有任何检索/LLM 调用

## Files

- Create: `src/rag/models/__init__.py`
- Create: `src/rag/models/document.py`
- Create: `src/rag/models/chunk.py`
- Create: `src/rag/store/__init__.py`
- Create: `src/rag/store/db.py`
- Create: `src/rag/store/repository.py`
- Create: `alembic.ini`
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_init_documents_chunks.py`
- Create: `tests/test_repository.py`
- Modify: `pyproject.toml` — 加入：

```toml
"sqlalchemy>=2.0.32",
"asyncpg>=0.29",
"pgvector>=0.3",
"alembic>=1.13",
"greenlet>=3.0",
```

## 表结构（必须按这个来）

### documents

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK，应用生成 |
| source | TEXT | 文件路径或原始文件名，NOT NULL |
| status | TEXT | `pending` / `ready` / `failed`，默认 `pending` |
| owner_id | TEXT | 文档所有者，NOT NULL。第 6 步 ACL 用 |
| created_at | TIMESTAMPTZ | 默认 `now()` |

先不要单独的 `document_acl` 表。第 6 步用 `owner_id` 做「只有所有者能搜到」。以后要多人共享再加表，现在 YAGNI。

### chunks

| 列 | 类型 | 约束 |
|---|---|---|
| id | UUID | PK |
| document_id | UUID | FK → documents.id ON DELETE CASCADE |
| content | TEXT | NOT NULL |
| chunk_index | INT | 文档内顺序，从 0 开始 |
| page | INT | 可空，Markdown 为 NULL |
| tsv | TSVECTOR | 可空，第 5 步再填 |
| embedding | VECTOR(1536) | NOT NULL |
| created_at | TIMESTAMPTZ | 默认 `now()` |

索引（这一步就建）：

```sql
CREATE INDEX ix_chunks_document_id ON chunks (document_id);
CREATE INDEX ix_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);
```

`tsv` 的 GIN 索引放到第 5 步，因为还没写分词配置。

## Interfaces

```python
# src/rag/store/db.py
async def get_engine() -> AsyncEngine: ...
async def get_session() -> AsyncIterator[AsyncSession]: ...

# src/rag/store/repository.py
@dataclass(frozen=True)
class NewChunk:
    content: str
    chunk_index: int
    embedding: list[float]
    page: int | None = None

class Repository:
    def __init__(self, session: AsyncSession): ...

    async def create_document(
        self,
        *,
        source: str,
        owner_id: str,
        chunks: list[NewChunk],
    ) -> uuid.UUID:
        """Insert document + chunks in ONE transaction. Status becomes ready."""
        ...

    async def get_chunks_by_document(self, document_id: uuid.UUID) -> list[Chunk]:
        ...

    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        ...
```

`embedding` 长度必须等于 `settings.embedding_dim`。Repository 在插入前检查：

```python
if len(chunk.embedding) != settings.embedding_dim:
    raise ValueError("embedding dim mismatch")
```

## SQLAlchemy 模型要点

- 使用 `from pgvector.sqlalchemy import Vector`
- `embedding = mapped_column(Vector(1536), nullable=False)`
- 不要写 `Vector(settings.embedding_dim)` 到 Mapped 列里当运行时变量——Alembic 需要字面量 `1536`。在模型文件顶部写：

```python
EMBEDDING_DIM = 1536  # must match settings.embedding_dim
```

再加一个测试：`assert EMBEDDING_DIM == settings.embedding_dim`。

## Alembic

`alembic/env.py` 要从 `rag.store.db` 取 metadata，用同步 URL 跑 migration（把 `postgresql+asyncpg://` 换成 `postgresql://`）。

首次迁移必须包含 `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`，放在建表之前。

## 测试

测试需要真实 PostgreSQL。用环境变量 `DATABASE_URL` 指向测试库，例如 `ragforge_test`。不要 mock 掉 SQL。

`tests/test_repository.py`：

```python
import pytest
from rag.config import settings
from rag.store.repository import NewChunk, Repository

@pytest.mark.asyncio
async def test_create_document_inserts_chunks(db_session):
    repo = Repository(db_session)
    dim = settings.embedding_dim
    fake = [0.0] * dim
    doc_id = await repo.create_document(
        source="hello.md",
        owner_id="user-1",
        chunks=[
            NewChunk(content="hello", chunk_index=0, embedding=fake),
            NewChunk(content="world", chunk_index=1, embedding=fake),
        ],
    )
    rows = await repo.get_chunks_by_document(doc_id)
    assert len(rows) == 2
    assert rows[0].content == "hello"
    assert len(rows[0].embedding) == dim

@pytest.mark.asyncio
async def test_rejects_wrong_embedding_dim(db_session):
    repo = Repository(db_session)
    with pytest.raises(ValueError, match="dim"):
        await repo.create_document(
            source="bad.md",
            owner_id="user-1",
            chunks=[NewChunk(content="x", chunk_index=0, embedding=[0.0, 1.0])],
        )
```

`db_session` fixture 放在 `tests/conftest.py`：创建 engine、跑 migrations 或 `Base.metadata.create_all`、每个测试后 rollback 或 truncate。

建议测试库用法：

```bash
createdb ragforge_test
psql ragforge_test -c 'CREATE EXTENSION IF NOT EXISTS vector;'
DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/ragforge_test pytest tests/test_repository.py -v
```

- [ ] 写失败测试
- [ ] 实现模型和 repository
- [ ] `pytest tests/test_repository.py -v` 全绿

## 手工检查

```sql
\d chunks
-- embedding 应显示 vector(1536)
```

## 常见坑

- 忘了 `CREATE EXTENSION vector`：建表会报 type vector does not exist。
- 用了 `float[]` 而不是 `vector`：后面 HNSW 和 `<=>` 都不能用。
- 把 embedding 做成可空：第 3 步入库一半失败时会出现「能搜到没有向量的行」。这一步就 NOT NULL。
- Document 和 Chunk 分两个 commit：进程在中间挂了会有孤儿。必须同一 `session.commit()`。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Add PostgreSQL document and chunk storage.

EOF
)"
```

## 下一步

[03-ingest.md](./03-ingest.md)：用真 embedding 把 Markdown 切块写进去。
