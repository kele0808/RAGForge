# Step 8 · 引用生成

**Goal:** 答案文本带 `[1]`、`[2]`，并能映射到 `chunk_id` / source / 原文片段。检索仍不负责引用；引用是生成面的工作。

**Prerequisites:** Step 7 返回的 `list[ChunkHit]` 已按相关度排好。

## 为什么

没有引用的 RAG 无法审计。引用必须来自**本次检索返回的列表下标**，不要生成后再用向量去猜「这句话像哪一段」（RAGFlow 的 insert_citations 只当后路，本项目第一期不做事后对齐）。

## 完成标准

- [ ] `Answer` 含 `text` 与 `citations: list[Citation]`
- [ ] prompt 要求模型使用 `[n]`，n 从 1 开始，对应资料编号
- [ ] 解析模型输出中的 `[n]`，非法编号丢掉，不抛给用户当链接
- [ ] 没有任何资料时：text 说明未找到，`citations == []`
- [ ] 单测不打 LLM：给定 fake 模型输出 `根据[1]需要医院证明`，解析出 chunk 0

## Files

- Modify: `src/rag/types.py`
- Modify: `src/rag/generate/prompt.py`
- Modify: `src/rag/generate/answer.py`
- Create: `src/rag/generate/citations.py`
- Modify: `src/rag/qa.py` — 返回 `Answer` 而不是 `str`
- Create: `tests/test_citations.py`
- Modify: `tests/test_prompt.py`

## Interfaces

```python
@dataclass(frozen=True)
class Citation:
    n: int                 # 1-based
    chunk_id: str
    document_id: str
    source: str
    page: int | None
    quote: str             # chunk.content 全文或截断到 200 字

@dataclass(frozen=True)
class Answer:
    text: str
    citations: list[Citation]

def parse_citation_numbers(text: str) -> list[int]:
    """Unique [n] in order of first appearance. Ignore n<1."""

def bind_citations(text: str, chunks: list[ChunkHit]) -> list[Citation]:
    """Keep n that satisfy 1 <= n <= len(chunks)."""
```

`AnswerGenerator.generate` 改为返回 `Answer`。

## Prompt 追加规则

在资料列表后加：

```text
引用规则：
- 使用 [1]、[2] 表示依据上面的资料编号。
- 不要使用资料列表里不存在的编号。
- 不要编造资料。
```

资料编号必须与列表顺序一致：第一条资料是 `[1]`，即 `chunks[0]`。

## 解析

正则：`\[(\d+)\]`

例：

```python
text = "病假需医院证明[1]。食堂规定与此无关。"
chunks = [hit_hospital, hit_canteen]
cites = bind_citations(text, chunks)
assert cites[0].chunk_id == hit_hospital.chunk_id
assert cites[0].n == 1
```

`[99]` 在只有 2 条资料时应被忽略。

模型若完全不输出引用，但确实用了资料：第一期**不强制失败**。`citations` 可以为空。可在 README 里记为已知限制。不要写复杂的事后向量对齐。

## qa.py

```python
async def ask(...) -> Answer:
    hits = await retriever.retrieve(req)
    return await generator.generate(question, hits)
```

所有原先期望 `str` 的测试改为 `answer.text`。

## 空检索

`hits == []`：

- 不调用「假装有资料」的 prompt 列表，或调用但资料区写「（无）」
- 仍可调用 LLM，或直接返回固定中文：`未在资料中找到相关内容。`
- 推荐**不调用 LLM**，节省费用且行为稳定：

```python
if not chunks:
    return Answer(text="未在资料中找到相关内容。", citations=[])
```

单测这条，不需要 fake LLM。

## 常见坑

- 用 `chunk_id` 的 UUID 当引用标记：prompt 又长又容易抄错。用短数字。
- 引用 `[1]` 却绑定 `chunks[1]`（0-base 错位）。
- 把 citations 做成字符串拼在答案末尾而不可解析。必须结构化 `list[Citation]`。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Return structured citations from generated answers.

EOF
)"
```

## 下一步

[09-graph.md](./09-graph.md)：多轮改写 + LangGraph 编排。
