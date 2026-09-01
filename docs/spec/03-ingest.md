# Step 3 · Markdown 切块入库

**Goal:** 给定一篇 `.md` 文件，切块、调用 `text-embedding-3-small`、写入 Step 2 的表。

**Prerequisites:** Step 2 完成；有效的 `OPENAI_API_KEY`。

## 为什么

这是知识面的第一条流水线。先只支持 Markdown，PDF/DOCX 放到第 11 步。切块和 embedding 分开两个模块，parser 以后可以换，embedder 不许换模型。

## 完成标准

- [ ] 一篇至少 3 个段落的 Markdown，入库后 chunk 数 ≥ 2
- [ ] 每条 chunk 的 `embedding` 长度为 1536
- [ ] 调用的 OpenAI model 字符串精确等于 `text-embedding-3-small`
- [ ] 切块逻辑有单测（不打 API）：按空行/标题切，超长再按 token 上限切
- [ ] embedder 有单测：用 fake client 断言 model 名和输入条数
- [ ] pipeline 集成测试可用 fake embedder 走通 repository（可选：一次真 API 手工测）

## Files

- Create: `src/rag/ingest/__init__.py`
- Create: `src/rag/ingest/parser.py` — 只读 Markdown 文本
- Create: `src/rag/ingest/chunker.py`
- Create: `src/rag/ingest/embedder.py`
- Create: `src/rag/ingest/pipeline.py`
- Create: `tests/test_chunker.py`
- Create: `tests/test_embedder.py`
- Create: `tests/test_ingest_pipeline.py`
- Create: `fixtures/sample.md`（测试用样例文档）
- Modify: `pyproject.toml` 加入：

```toml
"openai>=1.40",
"llama-index-core>=0.11",
```

## Interfaces

```python
# parser.py
def read_markdown(path: str) -> str:
    """Return UTF-8 text. Raise FileNotFoundError / ValueError if not .md."""

# chunker.py
def split_markdown(text: str, *, max_chars: int = 800) -> list[str]:
    """
    Split by headings / blank lines first.
    If a section is longer than max_chars, split on sentence boundaries.
    Drop empty / whitespace-only pieces.
    Preserve original order.
    """

# embedder.py
class Embedder:
    def __init__(self, client: openai.AsyncOpenAI, model: str, dim: int): ...

    async def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Call embeddings API. Every vector length must == dim."""

# pipeline.py
class IngestPipeline:
    def __init__(self, repo: Repository, embedder: Embedder, chunker=split_markdown): ...

    async def ingest_markdown(
        self,
        path: str,
        *,
        owner_id: str,
    ) -> uuid.UUID:
        """read → split → embed → repo.create_document(status=ready)."""
```

## 切块规则（写进测试）

用 LlamaIndex 的 `SentenceSplitter` 也可以，但必须包在 `split_markdown` 里，测的是这个函数，不是 LlamaIndex 内部 API。

约定参数（可作 `split_markdown` 默认值）：

- `max_chars=800`（大约对应 3-small 很短的一段，远小于 8191 token 上限）
- 按 `\n#{1,6} ` 标题和空行优先断开
- 不要在单词中间切开（英文）
- 输入空字符串 → 返回 `[]`，pipeline 应抛 `ValueError("no chunks")`，不要写空 document

`fixtures/sample.md` 建议：

```markdown
# 请假制度

员工请假需提前一天在系统提交。

## 病假

病假超过三天需要医院证明。
```

期望至少切出 2 块，且某一块包含「医院证明」。

## Embedding 规则

```python
resp = await client.embeddings.create(
    model=settings.embedding_model,  # 必须来自 config，不要写死第二种模型
    input=batch,
)
```

- 批量：每批最多 64 条（与常见 API 限制对齐）。
- 返回顺序必须与输入 texts 顺序一致。
- 校验 `len(vec) == settings.embedding_dim`，否则 raise。
- 空字符串不要发给 API：chunker 已经丢掉空块。

**单测不要打真实 OpenAI。** 注入 fake：

```python
class FakeEmbeddings:
    async def create(self, model, input):
        assert model == "text-embedding-3-small"
        class Item:
            def __init__(self, index):
                self.embedding = [float(index)] * 1536
        class Resp:
            data = [Item(i) for i in range(len(input))]
        return Resp()
```

把 fake 接到 `Embedder(client=SimpleNamespace(embeddings=FakeEmbeddings()), ...)`。

## Pipeline 事务

`ingest_markdown` 只调用一次 `repo.create_document`。embedding 失败则不写库。不要先插 document 再逐条 update embedding。

## 测试清单

`tests/test_chunker.py`

```python
from rag.ingest.chunker import split_markdown

def test_split_markdown_keeps_order_and_drops_empty():
    text = "# A\n\nhello\n\n# B\n\nworld\n\n"
    chunks = split_markdown(text, max_chars=800)
    assert chunks[0].find("hello") >= 0
    assert any("world" in c for c in chunks)

def test_split_markdown_splits_long_section():
    text = "x" * 2000
    chunks = split_markdown(text, max_chars=800)
    assert len(chunks) >= 2
    assert all(len(c) <= 800 for c in chunks)
```

`tests/test_embedder.py`：断言 model 名、输出条数、维度。

`tests/test_ingest_pipeline.py`：fake embedder + 真实测试库，读 `fixtures/sample.md`，`get_chunks_by_document` 能拿到「医院证明」。

## 手工（可选，证明真 API）

```bash
python -c "
import asyncio
from rag.ingest.pipeline import ...
asyncio.run(pipeline.ingest_markdown('fixtures/sample.md', owner_id='u1'))
"
```

然后 `SELECT id, length(content), vector_dims(embedding) FROM chunks;` 应全是 1536。

## 常见坑

- 自己用 hash 当向量「先跑通」：第 4 步语义检索会假绿。测试可以用 fake；手工验收必须真模型。
- 把整篇 md 当成 1 个 chunk：检索粒度太粗。样例文件必须切出 ≥ 2。
- `input` 传入超长列表导致 API 4xx：必须分批。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Ingest Markdown into chunk embeddings.

EOF
)"
```

## 下一步

[04-vector-qa.md](./04-vector-qa.md)：用向量把问题变成答案。这是你第一次摸到完整 RAG。
