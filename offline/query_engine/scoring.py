from __future__ import annotations
from dataclasses import dataclass

TOTAL_LIMIT = 100
FILTER_BONUS = 1.0
SEM_WEIGHT = 0.5
POP_WEIGHT = 0.3
MIN_RATINGS = 3


@dataclass
class HybridResult:
    product_id: str
    score: float
    from_filter: bool = False
    from_semantic: bool = False
    sem_score: float = 0.0
    pop_score: float = 0.0


def _normalize_popularity(
    rows: list[dict],
    min_ratings: int = MIN_RATINGS,
) -> dict[str, float]:
    valid = [
        r for r in rows
        if r.get("avg_rating") is not None and (r.get("rating_count") or 0) >= min_ratings
    ]
    if not valid:
        return {}

    global_mean = sum(r["avg_rating"] for r in valid) / len(valid)
    C = min_ratings

    bayesian: dict[str, float] = {}
    for r in rows:
        pid = r["product_id"]
        count = r.get("rating_count") or 0
        avg = r.get("avg_rating") or 0.0
        bayesian[pid] = (
            (C * global_mean + avg * count) / (C + count)
            if count >= min_ratings
            else global_mean
        )

    vals = list(bayesian.values())
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return {pid: 0.5 for pid in bayesian}
    return {pid: (v - lo) / (hi - lo) for pid, v in bayesian.items()}


def hybrid_merge(
    filter_rows: list[dict],
    semantic_rows: list[dict],
    total_limit: int = TOTAL_LIMIT,
) -> list[HybridResult]:
    filter_set = set(r["product_id"] for r in filter_rows)
    sem_map = {r["product_id"]: r.get("sem_score", 0.0) for r in semantic_rows}

    all_rows: dict[str, dict] = {}
    for r in semantic_rows:
        all_rows[r["product_id"]] = r
    for r in filter_rows:
        all_rows[r["product_id"]] = r
    pop_map = _normalize_popularity(list(all_rows.values()))

    results: dict[str, HybridResult] = {}

    for row in filter_rows:
        pid = row["product_id"]
        sem = sem_map.get(pid, 0.0)
        pop = pop_map.get(pid, 0.0)
        results[pid] = HybridResult(
            product_id=pid,
            score=FILTER_BONUS + sem * SEM_WEIGHT + pop * POP_WEIGHT,
            from_filter=True,
            from_semantic=pid in sem_map,
            sem_score=sem,
            pop_score=pop,
        )

    for row in semantic_rows:
        pid = row["product_id"]
        if pid not in results:
            sem = row.get("sem_score", 0.0)
            pop = pop_map.get(pid, 0.0)
            results[pid] = HybridResult(
                product_id=pid,
                score=sem * SEM_WEIGHT + pop * POP_WEIGHT,
                from_filter=False,
                from_semantic=True,
                sem_score=sem,
                pop_score=pop,
            )

    return sorted(results.values(), key=lambda r: r.score, reverse=True)[:total_limit]
