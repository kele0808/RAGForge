from __future__ import annotations

from typing import Any

from rag.models import document
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from rag.models.chunk import Chunk
from rag.models.document import Document
from rag.types import ChunkHit

class LexicalSearcher:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def search(self, query: str, *, top_k: int = 50) -> list[ChunkHit]:
        if top_k <= 0:
            return []
        if not query.strip():
            raise ValueError("Query must not be empty")

        tsquery = func.plainto_tsquery("simple", query)
        rank = func.ts_rank_cd(Chunk.tsv, tsquery)
        stmt = (
            select(
                Chunk.id,
                Chunk.document_id,
                Chunk.content,
                Document.source,
                Chunk.page,
                rank.label("score"),
            )
            .join(Document, Document.id == Chunk.document_id)
            .where(Document.status == 'ready')
            .where(Chunk.tsv.op("@@")(tsquery))
            .order_by(rank.desc())
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