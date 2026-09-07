from rag.generate.prompt import build_prompt
from rag.types import ChunkHit
def test_prompt_includes_all_chunks_and_grounding_instruction():
    chunks = [
        ChunkHit(1, "d", "医院证明", "a.md", None, 0.9),
        ChunkHit(2, "d", "提前一天", "a.md", None, 0.8),
    ]
    p = build_prompt("请假要什么", chunks)
    assert "医院证明" in p
    assert "提前一天" in p
    assert "未找到" in p
def test_prompt_empty_chunks_still_forbids_invention():
    p = build_prompt("可乐 好喝", [])
    assert "可乐" in p
    assert "不要编造" in p
    assert "无资料" in p