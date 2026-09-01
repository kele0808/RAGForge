# Step 11 · PDF / DOCX 解析

**Goal:** 除 Markdown 外，`.pdf` 和 `.docx` 也能变成文本，然后走**同一套** chunker → embedder → repository。解析可以换，切块和 embedding 不许分叉。

**Prerequisites:** Step 3 的 `split_markdown`/`Embedder`/`IngestPipeline`；Step 10 的 `/documents`。

## 为什么放最后

脏 PDF 是 RAG 效果的天花板，但不是你理解 RAG 的第一块积木。先用 Markdown 学会检索，再在解析层加 LlamaIndex/Docling。解析差时，回到这一层改 parser，不要改 RRF。

## 完成标准

- [ ] `parse_file(path) -> str` 按后缀分发 md/pdf/docx
- [ ] 不支持的后缀 `ValueError`
- [ ] PDF、DOCX 各有一个最小 fixture，解析结果包含已知句子
- [ ] `IngestPipeline.ingest_file` 替代只 ingest markdown；md 行为与 Step 3 兼容
- [ ] `POST /documents` 接受 `.md` `.pdf` `.docx`
- [ ] 解析失败：document 不要写成 `ready`；要么不插入，要么 `status=failed`（推荐整笔不插入，与 Step 3 事务一致）

## Files

- Modify: `src/rag/ingest/parser.py` — 增加 pdf/docx
- Modify: `src/rag/ingest/pipeline.py` — `ingest_file`
- Modify: `src/rag/api/ingest.py` — 后缀白名单
- Create: `fixtures/sample.docx`（可用测试里动态用 python-docx 生成，避免二进制 diff）
- Create: `fixtures/sample.pdf`（测试里用 reportlab 或 pypdf 生成更干净）
- Create: `tests/test_parser.py`
- Modify: `pyproject.toml`：

```toml
"llama-index-core>=0.11",
"pypdf>=5.0",
"python-docx>=1.1",
```

可以只用 pypdf + python-docx，不必强绑 LlamaIndex readers。若用 LlamaIndex，也必须包在 `parse_file` 后面，测试只测 `parse_file`。

## Interfaces

```python
SUPPORTED = {".md", ".markdown", ".pdf", ".docx"}

def parse_file(path: str) -> str:
    suffix = Path(path).suffix.lower()
    if suffix not in SUPPORTED:
        raise ValueError(f"unsupported type: {suffix}")
    if suffix in {".md", ".markdown"}:
        return read_markdown(path)
    if suffix == ".pdf":
        return read_pdf(path)
    return read_docx(path)
```

`read_pdf`：按页拼接，页之间插入 `\n\n`。页码信息第一期可以不写入 `chunks.page`（复杂）。若容易拿到 page 循环，则 `chunker` 仍按字符切，`page` 允许全 NULL。不要为了 page 精确对齐阻塞完成。

扫描件/纯图片 PDF：解析结果可能为空。空文本 → 与 Step 3 一样 `ValueError("no chunks")`。文档中写明：扫描件不在第一期范围。

## API

`POST /documents` 用原文件名后缀判断。`application/pdf`、docx mime 都接受。其它：400，body `{"detail": "unsupported type"}`。

## 测试

```python
def test_parse_pdf_extracts_sentence(tmp_path):
    # 生成一页写着 "病假需要医院证明" 的 pdf
    text = parse_file(str(pdf_path))
    assert "医院证明" in text

def test_rejects_xlsx():
    with pytest.raises(ValueError, match="unsupported"):
        parse_file("a.xlsx")
```

不要对真实「复杂排版年报 PDF」写回归；那是手工验收。

## 手工验收

找一份自己的 2–3 页文字版 PDF，入库后问一个只能从该 PDF 找到的事实，看 `/chat` 是否引用到。若表格全乱，记到项目 README「已知限制：复杂表格」，不要在这一步引入 DeepDoc。

## 和 RAGFlow 的边界

RAGFlow DeepDoc 更擅长扫描件和表格。本步目标是**管道接上**，不是打平解析质量。若以后要补解析，新建 `src/rag/ingest/deepdoc_adapter.py` 一类文件，不要把 DeepDoc 逻辑塞进 `retrieve/`。

## Commit

```bash
git commit -m "$(cat <<'EOF'
Parse PDF and DOCX through the same ingest pipeline.

EOF
)"
```

## 做完 11 步之后

第一期结束。你可以：

- 用 20–50 条真实问题做一张表：问题、是否命中、引用是否对（不必上 RAGAS）
- 再考虑 zhparser、多人 ACL 表、流式输出

不要马上上 GraphRAG。
