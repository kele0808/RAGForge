import pytest
from rag.retrieve.fusion import rrf_fuse

def test_rrf_hand_calculated_example():

    fused = rrf_fuse(
        [["id1", "id2", "id3"], ["id2", "id4"]],
        k=60,
        top_k=8,
    )
    ids = [i for i, _ in fused]
    scores = {i: s for i, s in fused}
    assert ids == ["id2", "id1", "id4", "id3"]
    assert scores["id2"] == pytest.approx(1 / 61 + 1 / 62)
    assert scores["id1"] == pytest.approx(1 / 61)
    assert scores["id4"] == pytest.approx(1 / 62)
    assert scores["id3"] == pytest.approx(1 / 63)