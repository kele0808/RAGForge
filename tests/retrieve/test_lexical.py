import pytest
from rag.config import settings
from rag.retrieve.lexical import LexicalSearcher
from rag.store.repository import NewChunk, Repository

def _vec() -> list[float]:
    return [0.1] * settings.embedding_dim

@pytest.mark.asyncio
async def test_lexical_hits_exact_token_first(db_session):
    repo = Repository(db_session)
    await repo.create_document(
        source="invoice.md",
        owner_id="kele",
        chunks=[
            NewChunk(content="发票号 ADX-156 已作废", chunk_index=0, embedding=_vec()),
            NewChunk(content="请假需要提前一天", chunk_index=1, embedding=_vec()),
        ]
    )
    hits = await LexicalSearcher(db_session).search("ADX-156", top_k=8)
    assert hits
    assert "ADX-156" in hits[0].content

@pytest.mark.asyncio
async def test_lexical_no_match_returns_empty(db_session):
    repo = Repository(db_session)
    await repo.create_document(
        source="a.md",
        owner_id="kele",
        chunks=[NewChunk(content="请假需要提前一天", chunk_index=0, embedding=_vec()),]
    )
    hits = await LexicalSearcher(db_session).search("ADX-156", top_k=8)
    assert hits == []

@pytest.mark.asyncio
async def test_lexical_blank_returns_empty(db_session):
    repo = Repository(db_session)
    await repo.create_document(
        source="a.md",
        owner_id="kele",
        chunks=[]
    )
    with pytest.raises(ValueError, match="empty"):
        await LexicalSearcher(db_session).search("   ", top_k=8)



