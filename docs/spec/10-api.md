# Step 10 · FastAPI

**Goal:** 三个 HTTP 接口：入库、检索、问答。API 层只做参数校验和调用前几步的 service，不含检索公式。

**Prerequisites:** Step 9 的 `run_rag`；Step 3 的 `IngestPipeline`。

## 完成标准

- [ ] `uvicorn rag.main:app` 能启动
- [ ] `POST /documents` 上传或传本地路径，返回 `document_id`
- [ ] `POST /retrieve` 返回 `ChunkHit` 列表，**不**生成答案
- [ ] `POST /chat` 返回 `Answer`（text + citations）
- [ ] 所有需要检索的接口都要 `user_id`
- [ ] API 测试用 `httpx.AsyncClient` + 注入 fake 依赖，CI 可不启真实 PG（用 override）；至少 chat/retrieve 有 1 个认证失败/缺 user_id 的 422

## Files

- Create: `src/rag/main.py`
- Create: `src/rag/api/__init__.py`
- Create: `src/rag/api/deps.py`
- Create: `src/rag/api/ingest.py`
- Create: `src/rag/api/retrieve.py`
- Create: `src/rag/api/chat.py`
- Create: `tests/test_api_chat.py`
- Create: `tests/test_api_ingest.py`
- Modify: `pyproject.toml`：`"fastapi>=0.115"`, `"uvicorn[standard]>=0.30"`, `"python-multipart>=0.0.9"`, `"httpx>=0.27"`

## 路由契约

### POST /documents

Request：`multipart/form-data`

- `file`: 第 10 步只接受 `.md`（PDF 第 11 步）
- `owner_id`: string

Response 201：

```json
{"document_id": "<uuid>", "chunk_count": 3}
```

文件类型不对：400。

### POST /retrieve

```json
{"user_id": "user-a", "query": "病假要什么", "top_k": 8}
```

Response 200：

```json
{"hits": [{"chunk_id": "...", "content": "...", "source": "...", "page": null, "score": 0.12}]}
```

注意：这个接口给调试/评测用，产品问答走 `/chat`。

### POST /chat

```json
{
  "user_id": "user-a",
  "question": "那病假呢",
  "history": [{"role": "user", "content": "请假要提前一天吗"}, {"role": "assistant", "content": "要"}]
}
```

Response 200：

```json
{
  "text": "...[1]",
  "citations": [{"n": 1, "chunk_id": "...", "source": "a.md", "quote": "..."}]
}
```

## main.py

```python
from fastapi import FastAPI
from rag.api.ingest import router as ingest_router
from rag.api.retrieve import router as retrieve_router
from rag.api.chat import router as chat_router

app = FastAPI(title="RAGForge")
app.include_router(ingest_router)
app.include_router(retrieve_router)
app.include_router(chat_router)
```

不要在 import 时连接数据库失败就 crash 到无法收集路由；engine 在 first request 或 lifespan 里初始化。

## 依赖注入

`deps.py` 提供：

- `get_session`
- `get_retrieve_service`
- `get_pipeline`
- `get_graph_runner`

测试里 `app.dependency_overrides[get_retrieve_service] = lambda: fake`。

## 校验

- `top_k` 范围 1–20，默认 8
- `user_id` min_length 1
- `question` min_length 1，max_length 2000
- history 最多 20 轮

用 Pydantic v2 模型，不要手写一堆 if。

## 测试

缺 `user_id`：

```python
async def test_chat_requires_user_id(client):
    r = await client.post("/chat", json={"question": "hi"})
    assert r.status_code == 422
```

chat 注入 fake graph：返回固定 `Answer`，断言 JSON 里 `citations` 结构。

## 不要做的事

- 不要做登录 JWT（第一期 `user_id` 由调用方传入；文档写明这不是生产认证）
- 不要做流式 SSE（可列为后续）
- 不要在 API 层写 RRF

## Commit

```bash
git commit -m "$(cat <<'EOF'
Expose ingest, retrieve, and chat over FastAPI.

EOF
)"
```

## 下一步

[11-parsers.md](./11-parsers.md)：PDF/DOCX 进入同一条 ingest 管线。
