"""
_shared.py — Tiện ích dùng chung cho tất cả baselines.

- load_data()          : đọc entity2id, interactions, stats (từ ranking/data/)
- split_interactions() : train/val split (giống train.py, seed cố định)
- evaluate_rec()       : generic Recall@K / NDCG@K cho bất kỳ scorer nào
"""

from __future__ import annotations

import json
import math
import pickle
import random
from pathlib import Path
from typing import Callable

import numpy as np
import torch

RANKING_DATA = Path(__file__).parent.parent / "ranking" / "data"


# ── Load ──────────────────────────────────────────────────────────────────────

def load_data() -> tuple[dict, dict, dict, dict]:
    """
    Trả về:
        entity2id   : {str → int}
        interactions: {user_int: [item_int, ...]}
        stats       : dict với n_items, n_users, item_offset, ...
        id2entity   : {int → str}  (inverse của entity2id)
    """
    entity2id    = json.loads((RANKING_DATA / "entity2id.json").read_text())
    interactions = pickle.loads((RANKING_DATA / "interactions.pkl").read_bytes())
    stats        = json.loads((RANKING_DATA / "stats.json").read_text())
    id2entity    = {v: k for k, v in entity2id.items()}
    return entity2id, interactions, stats, id2entity


# ── Train / Val split (đồng nhất với train.py) ────────────────────────────────

def split_interactions(
    interactions: dict,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[dict, dict]:
    rng   = random.Random(seed)
    train = {}
    val   = {}
    for u, items in interactions.items():
        if len(items) < 2:
            train[u] = items[:]
            continue
        shuffled = items[:]
        rng.shuffle(shuffled)
        n_val    = max(1, int(len(shuffled) * val_ratio))
        train[u] = shuffled[:-n_val]
        val[u]   = shuffled[-n_val:]
    return train, val


# ── Generic evaluation ────────────────────────────────────────────────────────

def evaluate_rec(
    scorer:      Callable[[int, list[int]], list[float]],
    val_inter:   dict,
    train_inter: dict,
    item_ids:    list[int],
    top_k:       int  = 10,
    max_users:   int  = 1000,
) -> tuple[float, float]:
    """
    Tính Recall@K và NDCG@K cho một scorer bất kỳ.

    scorer(user_id, item_ids) → list of float scores (cùng thứ tự với item_ids)
    Training positives bị mask (score = -inf) trước khi rank.
    """
    item_set      = set(item_ids)
    item_to_idx   = {item: idx for idx, item in enumerate(item_ids)}  # O(1) lookup
    all_users     = [u for u, v in val_inter.items() if v]  # chỉ user có val items
    # Random sample để tránh bias insertion-order (ví dụ: user nhỏ = active user hơn)
    rng = np.random.default_rng(seed=42)
    if len(all_users) > max_users:
        users = rng.choice(all_users, size=max_users, replace=False).tolist()
    else:
        users = all_users
    recall_list   = []
    ndcg_list     = []

    # Pre-build train_pos index arrays for fast mask
    train_mask_cache: dict[int, np.ndarray] = {}

    for u in users:
        pos_val = val_inter.get(u, [])

        scores = scorer(u, item_ids)          # list[float], len = n_items
        scores_arr = np.array(scores, dtype=np.float32)

        # Mask training positives
        if u not in train_mask_cache:
            mask_idx = np.array(
                [item_to_idx[p] for p in train_inter.get(u, []) if p in item_to_idx],
                dtype=np.intp,
            )
            train_mask_cache[u] = mask_idx
        scores_arr[train_mask_cache[u]] = -np.inf

        top_indices = np.argpartition(scores_arr, -top_k)[-top_k:]
        top_indices = top_indices[np.argsort(scores_arr[top_indices])[::-1]]
        topk_items  = {item_ids[i] for i in top_indices}

        relevant = set(pos_val) & item_set
        if not relevant:
            continue

        hits = relevant & topk_items
        recall_list.append(len(hits) / len(relevant))

        # NDCG: dùng lookup dict để tránh O(n) index()
        rank_of = {item_ids[idx]: rank + 1 for rank, idx in enumerate(top_indices)}
        ndcg = sum(1.0 / math.log2(rank_of[p] + 1) for p in hits)
        ideal = sum(1.0 / math.log2(i + 2) for i in range(min(len(relevant), top_k)))
        ndcg_list.append(ndcg / ideal if ideal > 0 else 0.0)

    recall = float(np.mean(recall_list)) if recall_list else 0.0
    ndcg   = float(np.mean(ndcg_list))   if ndcg_list  else 0.0
    return recall, ndcg
