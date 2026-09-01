# Step 1 · 工程脚手架

**Goal:** 可安装的 Python 包 + 能读配置 + pytest 能发现测试。

**你还不会 RAG 也没关系。** 这一步零检索，只把项目变成「能跑测试的空壳」。

## 为什么先做这个

后面每一步都 `from rag.config import settings`。模型名、维度、数据库 URL 必须有单一来源，否则 embedding 维度和 PG 列会对不上。

## 完成标准

- [ ] `uv sync` 或 `pip install -e ".[dev]"` 成功
- [ ] `pytest -q` 至少跑过 1 个测试且通过
- [ ] `settings.embedding_model == "text-embedding-3-small"`
- [ ] `settings.embedding_dim == 1536`
- [ ] `.env` 被 git 忽略，`.env.example` 在仓库里

## Files

- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/rag/__init__.py`
- Create: `src/rag/config.py`
- Create: `tests/test_config.py`
- Modify: `.gitignore`（若还没有 `.env`、`.venv/`、`__pycache__/`）

不要在这一步创建 ingest / retrieve / api 的空文件。没有用到的模块先不建。

## 依赖（写进 pyproject.toml）

```toml
[project]
name = "ragforge"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "pydantic-settings>=2.4",
  "pydantic>=2.8",
]

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "pytest-asyncio>=0.23",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/rag"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
pythonpath = ["src"]
```

后面步骤再往 `dependencies` 加：sqlalchemy、asyncpg、pgvector、alembic、openai、llama-index-core、fastapi、uvicorn、langgraph、httpx、sentence-transformers。**这一步不要提前加**，避免环境一下子很重。

## Interfaces

Produces:

```python
# src/rag/config.py
class Settings(BaseSettings):
    openai_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536
    database_url: str = "postgresql+asyncpg://rag:rag@localhost:5432/ragforge"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
```

字段名必须是这些。后续文档全部按 `settings.embedding_dim` 引用。

## 实现要点

1. `src/rag/__init__.py` 可以为空，或只写 `__version__ = "0.1.0"`。
2. `embedding_model` 不要做成运行时可改的枚举。默认值写死为 `text-embedding-3-small`。测试应断言默认值，防止以后有人改成 large 却忘了改 PG 列。
3. `.env.example` 内容：

```bash
OPENAI_API_KEY=
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIM=1536
DATABASE_URL=postgresql+asyncpg://rag:rag@localhost:5432/ragforge
```

`pydantic-settings` 默认把环境变量名当成字段的大写形式：`OPENAI_API_KEY` → `openai_api_key`。

## 测试

Create: `tests/test_config.py`

```python
from rag.config import Settings

def test_default_embedding_is_text_embedding_3_small():
    s = Settings(openai_api_key="sk-test")
    assert s.embedding_model == "text-embedding-3-small"
    assert s.embedding_dim == 1536
```

- [ ] **写测试**（上面这份）
- [ ] **先跑，确认失败**（此时还没有 `rag.config`）

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'rag'` 或 import 失败。

- [ ] **写 `config.py` 与 `pyproject.toml`**
- [ ] **再跑，确认通过**

```bash
pytest tests/test_config.py -v
```

Expected: `1 passed`

## 手工检查

```bash
python -c "from rag.config import settings; print(settings.embedding_model, settings.embedding_dim)"
```

应打印：`text-embedding-3-small 1536`

## Commit

```bash
git add pyproject.toml .env.example src/rag/__init__.py src/rag/config.py tests/test_config.py
git commit -m "$(cat <<'EOF'
Add Python package scaffold and embedding config.

EOF
)"
```

## 下一步

[02-store.md](./02-store.md)：PostgreSQL 表和 Repository。没有数据库，chunk 无处可放。
