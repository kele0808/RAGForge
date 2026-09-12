import pytest
from rag.config import settings
from rag.retrieve.lexical import LexicalSearcher
from rag.retrieve.vector import VectorSearcher
from rag.retrieve.service import HybridRetriever
from rag.store.repository import  NewChunk, Repository

class FakeEmbedder:
    async def embed_text(self, texts: list[str]) -> list[list[float]]:
        return [[1.0] * settings.embedding_dim] * len(texts)

def _ones() -> list[float]:
    return  [1.0] * settings.embedding_dim
def _neg_ones() -> list[float]:
    return [-1.0] * settings.embedding_dim

@pytest.mark.asyncio
async def test_hybrid_keeps_exact_token_when_vector_is_wrong(db_session):
    """向量更像 B，全文能中 A；融合后 A 必须还在名单里。"""
    repo = Repository(db_session)
    await repo.create_document(
        source="mix.md",
        owner_id="kele",
        chunks=[
            NewChunk(content="发票号 ADX-156 已作废", chunk_index=0, embedding=_neg_ones()),
            NewChunk(content="请假需要提前一天请假", chunk_index=1, embedding=_ones()),
        ]
    )
    retriever = HybridRetriever(
        lexical=LexicalSearcher(db_session),
        vector=VectorSearcher(db_session, FakeEmbedder()),
    )
    hits = await retriever.retrieve("ADX-156", top_k=8, recall_k=50)
    contents = [h.content for h in hits]
    assert any("ADX-156" in content for content in contents)
