from __future__ import annotations
import uuid
from collections.abc import Callable, Sequence
from pathlib import Path
from rag.ingest.chunker import split_markdown
from rag.ingest.embedder import Embedder
from rag.ingest.parser import read_markdown
from rag.store.repository import Repository, NewChunk

class IngestPipeline:
    def __init__(
            self,
            repo: Repository,
            embedder: Embedder,
            chunker: Callable[[str], Sequence[str]] = split_markdown,
            ) -> None:
        self.repo = repo
        self.embedder = embedder
        self.chunker = chunker

    async def ingest_markdown(self,
                              path: str,
                              *,
                              owner_id: str) -> uuid.UUID:
        """
        读文件 -> 切块 -> embed -> 一次写入 -> embed 失败 则不会入库
        :param path:
        :param owner_id:
        :return:
        """
        text = read_markdown(path)
        pieces = list(self.chunker(text))
        if not pieces:
            raise ValueError("no chunks")
        vectors = await self.embedder.embed_text(pieces)
        chunks = [
            NewChunk(content=content, chunk_index=i, embedding=vec)
            for i, (content, vec) in enumerate(zip(pieces, vectors, strict=True))
        ]
        return await self.repo.create_document(
            source=Path(path).name,
            owner_id=owner_id,
            chunks=chunks,
        )
