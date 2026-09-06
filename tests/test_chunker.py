from rag.ingest.chunker import split_markdown

def test_split_markdown_keeps_order_and_drops_empty():

    text = "# A\n\nhello\n\n# B\n\nworld\n\n"
    chunks = split_markdown(text, max_chars=800)
    assert "hello" in chunks[0]
    assert any("world" in c for c in chunks)
def test_split_markdown_splits_long_section():
    text = "x" * 2000
    chunks = split_markdown(text, max_chars=800)
    assert len(chunks) >= 2
    assert all(len(c) <= 800 for c in chunks)

def test_empty_input_returns_empty_chunks():

    assert split_markdown("") == []
    assert split_markdown("\n   \n") == []

def test_heading_is_kept_in_chunks():

    text = "# 病假\\n病假超过三天需要医院证明"
    chunks = split_markdown(text, max_chars=800)
    assert len(chunks) == 1
    assert "# 病假" in chunks[0]
    assert "医院证明" in chunks[0]

def test_overlapped_percent_default_is_off():
    """默认 0：和显式传 0 完全一样，下一块不以 recap 开头。"""
    text = "# A\n\nhello\n\n# B\n\nworld"
    assert split_markdown(text) == split_markdown(text, overlapped_percent=0)

def test_overlapped_percent_prepends_previous_tail():
    """开启后：下一块以「上一块尾部 percent%」开头"""
    text = "# A\n\n" + ("a" * 400) + "\n\n# B\n\n" + ("b" * 400)
    chunks = split_markdown(text, max_chars=800, overlapped_percent=10)
    assert len(chunks) >= 2
    tail = chunks[0][int(len(chunks[0]) * 0.9) :]
    assert chunks[1].startswith(tail)

def test_overlapped_percent_out_of_range_raises():
    import pytest

    with pytest.raises(ValueError, match="overlapped_percent"):
        split_markdown("hello", overlapped_percent=-1)
    with pytest.raises(ValueError, match="overlapped_percent"):
        split_markdown("hello", overlapped_percent=101)