"""
random_rec.py — Baseline: Random Recommendation.

Gán điểm ngẫu nhiên cho mọi item, không phụ thuộc user.
Đây là lower-bound — mọi model thực sự phải vượt qua baseline này.
"""

from __future__ import annotations

import random


class RandomRecommender:
    name = "Random"

    def __init__(self, seed: int = 42):
        self._rng = random.Random(seed)

    def score(self, user_id: int, item_ids: list[int]) -> list[float]:
        return [self._rng.random() for _ in item_ids]
