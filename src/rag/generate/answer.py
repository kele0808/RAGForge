from __future__ import annotations
from openai import AsyncOpenAI
from rag.generate.prompt import build_prompt
from rag.types import ChunkHit

class  AnswerGenerator:

    def __init__(self, client: AsyncOpenAI, chat_model: str = "gpt-4o-mini") -> None:
        self.client = client
        self.chat_model = chat_model
    async def generate(self, question: str, chunks: list[ChunkHit]) -> None:
        prompt = build_prompt(question, chunks)
        resp = await self.client.chat.completions.create(
            model=self.chat_model,
            messages=[{"role":"user", "content":prompt}],
            temperature=0,
        )
        text = (resp.choices[0].message.content or "").strip()
        return text or "未找到"

