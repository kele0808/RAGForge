from pathlib import Path
from types import SimpleNamespace
import pytest
from sqlalchemy import select
from rag.config import settings
from rag.ingest.embedder import Embedder
from rag.ingest.pipeline import IngestPipeline
from rag.models.document import Document
from rag.store.repository import Repository
REPO_DIR = Path(__file__).resolve().parent.parent
SAMPLE = REPO_DIR / 'fixtures' / 'sample.md'
MODEL = "text-embedding-3-small"
DIM = 1536
class FakeEmbeddings:
    async def create(self, model, input):
        class Item:
            def __init__(self, index: int) -> None:
                self.index = index
                self.embedding = [float(index)] * DIM
        class Resp:
            def __init__(self, n: int) -> None:
                self.data = [Item(i) for i in range(n)]
        return Resp(len(input))
def _pipeline(db_session) -> IngestPipeline:
    embedder = Embedder(
        client=SimpleNamespace(embeddings=FakeEmbeddings()),
        model=MODEL,
        dim=DIM,
    )
    return IngestPipeline(repo=Repository(db_session), embedder=embedder)

@pytest.mark.asyncio
async def test_ingest_sample_md_md_keeps_hospital_proof(db_session):
    pipe = _pipeline(db_session)
    doc_id = await pipe.ingest_markdown(str(SAMPLE), owner_id="kele")
    repo = Repository(db_session)
    doc = await repo.get_document(doc_id)
    assert doc is not None
    assert doc.status == "ready"
    assert doc.source == "sample.md"
    rows = await repo.get_chunks_by_document(doc_id)
    assert len(rows) >= 2
    assert any("医院证明" in r.content for r in rows)
    assert all(len(r.embedding) == settings.embedding_dim for r in rows )

@pytest.mark.asyncio
async def test_ingest_empty_markdown_does_not_write(db_session, tmp_path):
    """没有 chunk 就不要留下空 document。"""
    empty = tmp_path / "empty.md"
    empty.write_text("   \n\n", encoding="utf-8")
    pipe = _pipeline(db_session)
    with pytest.raises(ValueError, match="no chunks"):
        await pipe.ingest_markdown(str(empty), owner_id="kele")
    leftover = (await db_session.execute(select(Document))).scalars().all()
    assert leftover == []
@pytest.mark.asyncio
async def test_ingest_embed_failure_does_not_write(db_session):
    """embed 失败则整单不写库。"""
    class Boom:
        async def embed_text(self, texts: list[str]) -> list[list[float]]:
            raise RuntimeError("openai down")
    pipe = IngestPipeline(repo=Repository(db_session), embedder=Boom())
    with pytest.raises(RuntimeError, match="openai down"):
        await pipe.ingest_markdown(str(SAMPLE), owner_id="kele")
    leftover = (await db_session.execute(select(Document))).scalars().all()
    assert leftover == []