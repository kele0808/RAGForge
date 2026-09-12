import uuid

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
        owner_id="kele",
        chunks=[
            NewChunk(content="hello", chunk_index=0, embedding=fake),
            NewChunk(content="world", chunk_index=1, embedding=fake),
        ],
    )
    rows = await repo.get_chunks_by_document(doc_id)
    assert len(rows) == 2
    assert rows[0].content == "hello"
    assert rows[1].content == "world"
    assert len(rows[0].embedding) == dim

@pytest.mark.asyncio
async def test_rejects_wrong_embedding_dim(db_session):
    repo = Repository(db_session)
    with pytest.raises(ValueError, match="dim"):
        await repo.create_document(
            source="hello.md",
            owner_id="kele",
            chunks=[NewChunk(content="hello", chunk_index=0, embedding=[0.0, 1.0])],
        )

@pytest.mark.asyncio
async def test_get_document_returns_none_unknown_id(db_session):
    repo = Repository(db_session)
    result = await repo.get_document(uuid.uuid4())
    assert result is None

@pytest.mark.asyncio
async def test_rejects_bad_chunk_even_if_first_ones_are_good(db_session):
    """校验必须扫描所有 chunks，不能扫到第一个就 return。"""
    repo = Repository(db_session)
    dim = settings.embedding_dim
    good = [0.0] * dim
    bad = [0.0, 1.0]  # 明显错的维度
    with pytest.raises(ValueError, match="dim"):
        await repo.create_document(
            source="mixed.md",
            owner_id="user-1",
            chunks=[
                NewChunk(content="good1", chunk_index=0, embedding=good),
                NewChunk(content="good2", chunk_index=1, embedding=good),
                NewChunk(content="BAD", chunk_index=2, embedding=bad),  # 第三个才坏
            ],
        )