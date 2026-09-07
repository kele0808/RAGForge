from __future__ import annotations
from rag.types import ChunkHit
def build_prompt(question: str,  chunks: list[ChunkHit]) -> str:
    """ 只根据资料回答，资料不够就说未找到，不要编造"""
    if chunks:
        body= "\n\n".join(
            f"[{i}] source={hit.source} page={hit.page}\n{hit.content}"
            for i, hit in enumerate(chunks, start=1)
        )
    else:
        body= " 无资料 "
    return (
        "你是问答助手， 只能根据下面的「资料」回答。\n"
        "资料不足时明确说未找到， 不要编造。 \n\n"
        f"资料：\n{body}\n\n"
        f"问题：{question}"
    )