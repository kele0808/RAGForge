from __future__ import annotations
import asyncio
from dataclasses import replace
from rag.retrieve.fusion import rrf_fuse
from rag.retrieve.lexical import LexicalSearcher
from rag.retrieve.vector import VectorSearcher
from rag.types import ChunkHit

class HybridRetriever:
    def __init__(
            self,
            lexical: LexicalSearcher,
            vector: VectorSearcher,
            rrf_k: int = 60,
    ) -> None:
        self.lexical = lexical
        self.vector = vector
        self.rrf_k = rrf_k

    async def retrieve(
            self,
            query: str,
            *,
            top_k: int = 8,
            recall_k: int = 50,
    ) -> list[ChunkHit]:
        lex_hits, vec_hits = await asyncio.gather(
            self.lexical.search(query, top_k=recall_k),
            self.vector.search(query, top_k=recall_k),
        )
        # todo 没看懂
        by_id: dict[str, ChunkHit] = {h.chunk_id: h for h in lex_hits}
        by_id.update({h.chunk_id: h for h in vec_hits})

        fused = rrf_fuse(
            [
                [h.chunk_id for h in lex_hits],
                [h.chunk_id for h in vec_hits],
            ],
            k=self.rrf_k,
            top_k=top_k,
        )
        return [replace(by_id[cid], score=score) for cid, score in fused]
