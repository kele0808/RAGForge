from types import SimpleNamespace
import pytest
from rag.config import settings
from rag.ingest.embedder import Embedder

MODEL = "text-embedding-3-small"
DIM = 1536

class FakeEmbeddings:

    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    async def create(self, model, input):
        self.calls.append((model, list(input)))
        class Item:
            def __init__(self, index: int) -> None:
                self.index = index
                self.embedding = [float(index)] * DIM
        class Resp:
            def __init__(self, n: int) -> None:
                self.data = [Item(i) for i in range(n)]
        return Resp(len(input))

def _embedder(fake: FakeEmbeddings | None = None) -> tuple[Embedder, FakeEmbeddings]:
    fake = fake or FakeEmbeddings()
    client = SimpleNamespace(embeddings=fake)
    return Embedder(client=client, model=MODEL, dim=DIM), fake

@pytest.mark.asyncio
async def test_embed_texts_uses_configured_model_and_dim():
    embedder, fake = _embedder()
    vecs = await embedder.embed_text(["hello", "world"])
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == settings.embedding_model
    assert len(vecs) == 2
    assert all(len(v) == DIM for v in vecs)
    assert vecs[0][0] == 0.0
    assert vecs[1][0] == 1.0

@pytest.mark.asyncio
async def test_embed_texts_uses_batches_over_64():
    embedder, fake = _embedder()
    texts = [f"hello {i}" for i in range(65)]
    vecs = await embedder.embed_text(texts)
    assert len(fake.calls) == 2
    assert len(fake.calls[0][1]) == 64
    assert len(fake.calls[1][1]) == 1
    assert len(vecs) == 65

@pytest.mark.asyncio
async def test_embed_texts_empty_skip_string():
    embedder, _ = _embedder()
    with pytest.raises(ValueError, match="empty"):
        await embedder.embed_text(["ok", "   "])

@pytest.mark.asyncio
async def test_embed_texts_rejects_wrong_dim():
    class BadEmbedding:

        async def create(self, model, input):
            class Item:
                index = 0
                embedding = [0.0, 1.0]
            class Resp:
                data = [Item()]
            return Resp()
    embedder = Embedder(
        client=SimpleNamespace(embeddings=BadEmbedding()),
        model=MODEL,
        dim=DIM,
    )
    with pytest.raises(ValueError, match="dim"):
        await embedder.embed_text(["hello"])