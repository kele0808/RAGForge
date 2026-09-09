from types import SimpleNamespace
import pytest
from rag.generate.answer import  AnswerGenerator
from rag.qa import ask
from rag.types import ChunkHit


class FakeCompletions:
    def __init__(self) -> None:
        self.calls: list[dict] = []
        self.content: str | None = "需要医院证明"
    
    async def create(self, **kwargs):
        self.calls.append(kwargs)
        class Msg:
            def __init__(self, content: str | None) -> None:
                self.content = content
        class Choice:
            def __init__(self, content: str | None) -> None:
                self.message= Msg(content)
        class Resp:
            def __init__(self, content: str | None) -> None:
                self.choices = [Choice(content)]
        return Resp(self.content)

def _client(fake: FakeCompletions) -> SimpleNamespace:
    return SimpleNamespace(chat=SimpleNamespace(completions=fake))

@pytest.mark.asyncio
async def test_generate_sends_grounded_prompt():
    fake = FakeCompletions()
    gen = AnswerGenerator(client=_client(fake), chat_model="gpt-4o-mini")
    hits = [ChunkHit("1", "d", "医院证明", "a.md", None, 0.9)]
    text = await gen.generate("病假要什么", hits)
    assert text == "需要医院证明"
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == "gpt-4o-mini"
    assert fake.calls[0]["temperature"] == 0

@pytest.mark.asyncio
async def test_ask_uses_serach_hits():
    class FakeSearcher:
        async def search(self, query: str, *, top_k: int) -> list[ChunkHit]:
            assert query == "病假要什么"
            assert top_k == 8
            return [ChunkHit("1", "d", "医院证明", "a.md", None, 0.9)]

    fake = FakeCompletions()
    answer = await ask(
        "病假要什么",
        searcher=FakeSearcher(),
        generator=AnswerGenerator(client=_client(fake)),
    )
    assert answer == "需要医院证明"
    assert "医院证明" in fake.calls[0]["messages"][0]["content"]