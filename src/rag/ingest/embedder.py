from __future__ import annotations

from openai import AsyncOpenAI
_BATCH_SIZE = 64
class Embedder:
    def __init__(self, client: AsyncOpenAI, model: str, dim: int) -> None:
        self.client = client
        self.model = model
        self.dim = dim

    async def embed_text(self, texts: list[str]) -> list[list[float]]:
        """
        按输入返回向量，空列表直接返回
        :param texts:
        :return:
        """
        if not texts:
            return []
        if any(not t.strip() for t in texts):
            raise ValueError("empty text cannot be embedded")
        vectors: list[list[float]] = []
        for start in range(0, len(texts), _BATCH_SIZE):
            batch = texts[start:start + _BATCH_SIZE]
            resp = await self.client.embeddings.create(
                model=self.model,
                input=batch,
            )
            items = sorted(resp.data, key=lambda d : getattr(d, "index", 0))
            for item in items:
                vec = list(item.embedding)
                if len(vec) != self.dim:
                    raise ValueError(f"embedding dimension mismatch: {len(vec)}")

                vectors.append(vec)
        return vectors


