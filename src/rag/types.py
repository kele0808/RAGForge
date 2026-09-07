from  __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class ChunkHit:
    chunk_id: str
    document_id: str
    content: str
    source: str
    page: int | None
    score: float # 余弦相似度，越大越近
