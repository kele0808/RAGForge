from __future__ import annotations
import uuid
from dataclasses import  dataclass
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from rag.config import settings
from rag.models.chunk import Chunk
from rag.models.document import Document

@dataclass(frozen=True)
class NewChunk:
    """
    入库时描述，要插一条chunk，frozen表示不可变，防止被下游偷改
    """
    content: str
    chunk_index: int
    embedding: list[float]
    page: int | None = None
class Repository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
    async def create_document(
            self,
            *,
            source: str,
            owner_id: str,
            chunks: list[NewChunk],
    ) -> uuid.UUID:
        """
        在同一个事务里面插入 Document 和它所有的 Chunk，返回document_id
        :param self:
        :param source:
        :param owner_id:
        :param chunks:
        :return:
        """
        for c in chunks:
            if len(c.embedding) != settings.embedding_dim:
                raise ValueError (
                    f"embedding dim mismatch, got {len(c.embedding)}, expected {settings.embedding_dim}"
                )
        # 新建Document, flush(不 commit）拿到auto-generated id
        doc = Document(source=source, owner_id=owner_id, status="ready")
        self.session.add(doc)
        await self.session.flush()

        # 批量建chunk，绑定到doc.id
        self.session.add_all(
            [
                Chunk(
                    document_id=doc.id,
                    content=c.content,
                    chunk_index=c.chunk_index,
                    page=c.page,
                    embedding=c.embedding,
                )
                for c in chunks
            ]
        )

        # 一次commit 所有操作要么全成功，要么全回滚
        await self.session.commit()
        return doc.id
    async def get_chunks_by_document(self, document_id: uuid.UUID) -> list[Chunk]:
        stmt = (
            select(Chunk)
            .where(Chunk.document_id == document_id)
            .order_by(Chunk.chunk_index)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
    async def get_document(self, document_id: uuid.UUID) -> Document | None:
        return await self.session.get(Document, document_id)

