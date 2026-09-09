from __future__ import annotations

def rrf_fuse(
        ranked_id_lists: list[list[str]],
        *,
        k: int = 60,
        top_k: int = 8,
) -> list[tuple[str, float]]:
    """
    把多路排名合成（id，rrf_score)， 分数降序，截到top_k
    RRF(d) = Σ(i=1→N) 1 / (k + rank_i(d))
    某一个id只出现在一路，就只加那一路
    """
    scores: dict[str, float] = {}
    for ranked in ranked_id_lists:
        seen: set[str] = set()
        for rank, chunk_id in enumerate(ranked, start=1):
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (k + rank)
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return ordered[:top_k]

