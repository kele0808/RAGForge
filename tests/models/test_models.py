from rag.config import settings
from rag.models.chunk import EMBEDDING_DIM, Chunk
from rag.models.document import Base, Document

def test_embedding_dim_matches_settings():
    assert settings.embedding_dim == EMBEDDING_DIM


def test_models_registered_in_metadata():
    """documents 和 chunks 都必须注册到 Base.metadata，Alembic autogen 才能看到。"""
    table_names = set(Base.metadata.tables.keys())
    assert "documents" in table_names
    assert "chunks" in table_names


def test_chunk_has_cascade_on_document_fk():
    """删 document 时 chunk 必须级联删。"""
    chunks_table = Chunk.__table__
    fk = next(iter(chunks_table.foreign_keys))
    assert fk.ondelete == "CASCADE"