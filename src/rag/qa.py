from __future__ import annotations

from idlelib.window import add_windows_to_menu

from rag.generate.answer import AnswerGenerator
from rag.retrieve.vector import VectorSearcher
async def ask(
        question: str,
        *,
        searcher: VectorSearcher,
        generator: AnswerGenerator,
) -> str:
    hits = await searcher.search(question, top_k=8)
    return await generator.generate(question, hits)