from __future__ import annotations


from rag.generate.answer import AnswerGenerator
from rag.retrieve.service import HybridRetriever
async def ask(
        question: str,
        *,
        retriever: HybridRetriever,
        generator: AnswerGenerator,
) -> str:
    hits = await retriever.retrieve(question, top_k=8)
    return await generator.generate(question, hits)