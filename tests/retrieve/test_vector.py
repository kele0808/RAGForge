from idlelib.window import add_windows_to_menu

import pytest
from rag.config import settings
from rag.retrieve.vector import VectorSearcher
from rag.store.repository import NewChunk, Repository

class FakeEmbedder:
    async def embed_text(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] * settings.embedding_dim] * len(texts)

def _ones() -> list[float]:
    return [1.0] * settings.embedding_dim

def neg_ones() -> list[float]:
    return [-1.0] * settings.embedding_dim

@pytest.mark.asyncio
async def test_search_ranks_identical_vector_first(db_session):
    """
    query 全是1 -> 必须全部命中 embedding 全1 的chunk
    :param db_session:
    :return:
    """
    repo = Repository(db_session)
    await repo.create_document(
        source="a.md",
        owner_id="kele",
        chunks=[
            NewChunk(content="医院证明", chunk_index=0, embedding=_ones()),
            NewChunk(content="年终奖", chunk_index=1, embedding=neg_ones()),
        ]
    )
    searcher = VectorSearcher(db_session, FakeEmbedder())
    hits = await searcher.search("病假需要什么", top_k=2)
    assert len(hits) == 2
    assert hits[0].content == "医院证明"
    assert hits[0].source == "a.md"
    assert hits[0].score >= hits[1].score

@pytest.mark.asyncio
async def test_search_empty_db_returns_empty(db_session):
    searcher = VectorSearcher(db_session, FakeEmbedder())
    assert await searcher.search("anything", top_k=8) == []

@pytest.mark.asyncio
async def test_search_top_k_zero_returns_empty(db_session):
    searcher = VectorSearcher(db_session, FakeEmbedder())
    assert await searcher.search("anything", top_k=0) == []

@pytest.mark.asyncio
async def test_search_blank_query_raises(db_session):
    searcher = VectorSearcher(db_session, FakeEmbedder())
    with pytest.raises(ValueError, match="empty"):
        await searcher.search("   ", top_k=8)