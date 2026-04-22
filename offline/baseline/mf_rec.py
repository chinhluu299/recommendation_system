"""
mf_rec.py — Baseline: Matrix Factorization (Truncated SVD).

Đại diện cho "Collaborative Filtering truyền thống" trong so sánh.

Cách hoạt động:
  1. Xây user-item matrix R (binary: 1 nếu user tương tác với item).
  2. SVD: R ≈ U × S × Vᵀ  →  user_emb = U·S, item_emb = Vᵀ.T
  3. Score(u, i) = user_emb[u] · item_emb[i]

Cold-start: user không có trong train → dùng zero vector (score = 0 cho mọi item,
tương đương popularity fallback nếu cần, nhưng ở đây để 0 vì mục đích ablation).
"""

from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import svds


class MFRecommender:
    """
    Matrix Factorization bằng Truncated SVD.

    Parameters
    ----------
    train_inter : {user_int: [item_int, ...]}
    n_users     : tổng số user (để tạo ma trận đúng kích thước)
    n_items     : tổng số item
    item_offset : item_ids bắt đầu từ item_offset (= n_users)
    k           : số latent factors
    """

    name = "MF / SVD (CF)"

    def __init__(
        self,
        train_inter: dict,
        n_users:     int,
        n_items:     int,
        item_offset: int,
        k:           int = 64,
    ):
        self._item_offset = item_offset
        self._n_items     = n_items

        # Xây sparse user-item matrix (binary)
        rows, cols, data = [], [], []
        for u, items in train_inter.items():
            for item in items:
                col = item - item_offset
                if 0 <= col < n_items:
                    rows.append(u)
                    cols.append(col)
                    data.append(1.0)

        mat = csr_matrix(
            (data, (rows, cols)),
            shape=(n_users, n_items),
            dtype=np.float32,
        )

        # Truncated SVD
        k_actual = min(k, min(mat.shape) - 1)
        U, S, Vt = svds(mat, k=k_actual)

        # Sắp xếp theo singular value giảm dần (svds trả theo chiều tăng)
        order = np.argsort(S)[::-1]
        U, S, Vt = U[:, order], S[order], Vt[order, :]

        self._user_emb: np.ndarray = U * S          # (n_users, k)
        self._item_emb: np.ndarray = Vt.T           # (n_items, k)

    def score(self, user_id: int, item_ids: list[int]) -> list[float]:
        if user_id >= len(self._user_emb):
            return [0.0] * len(item_ids)

        u_vec = self._user_emb[user_id]              # (k,)
        cols  = [i - self._item_offset for i in item_ids]
        scores = []
        for col in cols:
            if 0 <= col < self._n_items:
                scores.append(float(self._item_emb[col] @ u_vec))
            else:
                scores.append(0.0)
        return scores
