from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from rag.ingest.embedder import Embedder
from rag.models.chunk import Chunk
from rag.models.document import Document
from rag.types import ChunkHit

class VectorSearcher:

    def __init__(self, session: AsyncSession, embedder: Embedder) -> None:
        self.session = session
        self.embedder = embedder

    async def search(self, query: str, *, top_k: int) -> list[ChunkHit]:
        if top_k <= 0:
            return []
        if not query.strip():
            raise ValueError("Query must not be empty")
        vectors = await self.embedder.embed_text([query])
        qvec = vectors[0]
        distance = Chunk.embedding.cosine_distance(qvec)
        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.content,
                Document.source,
                Chunk.page,
                (1 - distance).label("score"),
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.status == "ready")
            .order_by(distance)
            .limit(top_k)
        )

        rows = (await self.session.execute(stmt)).all()

        return [
            ChunkHit(
                chunk_id=str(row.id),
                document_id=str(row.document_id),
                content=row.content,
                source=row.source,
                page=row.page,
                score=float(row.score),
            )
            for row in rows
        ]