from __future__ import annotations
import uuid
from datetime import datetime
from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Integer, Text, DateTime, func
from sqlalchemy.dialects.postgresql import TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column
from rag.models.document import Base
EMBEDDING_DIM = 1536 # must match settings.embedding_dim

class Chunk(Base):
    __tablename__ = 'chunks'
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('documents.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    content: Mapped[str] = mapped_column(
        Text, nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tsv: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False)
