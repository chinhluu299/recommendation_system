"""
popularity.py — Baseline: Popularity-based Recommendation.

Rank items theo số lượt tương tác trong tập train.
Không cá nhân hóa — mọi user đều nhận cùng danh sách top items.
Đây là baseline phi cá nhân hóa quan trọng nhất.
"""

from __future__ import annotations

from collections import Counter


class PopularityRecommender:
    name = "Popularity"

    def __init__(self, train_inter: dict):
        """
        train_inter: {user_int: [item_int, ...]}
        """
        counts: Counter = Counter()
        for items in train_inter.values():
            counts.update(items)
        self._counts = counts

    def score(self, user_id: int, item_ids: list[int]) -> list[float]:
        return [float(self._counts.get(item, 0)) for item in item_ids]
