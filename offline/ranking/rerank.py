#!/usr/bin/env python3
"""
rerank.py – KGAT-based re-ranker cho query pipeline.

Nhận top-K sản phẩm từ Neo4j query engine → re-rank theo personalization.

─── Cách dùng ──────────────────────────────────────────────────────────────────

  from ranking.rerank import KGATReranker

  ranker = KGATReranker()   # load checkpoint một lần duy nhất

  # 1. Re-rank danh sách ASIN
  ranked_asins = ranker.rerank(
      user_id="AHATA6X6MYTC3VNBFJ3WIYVK257A",
      product_asins=["B00M78E4MS", "B075QWLV3J", "B01N9JY4JT"],
  )

  # 2. Re-rank trực tiếp records từ pipeline.ask()
  result = pipeline.ask("điện thoại pin lớn dưới 300k")
  ranked_records = ranker.rerank_records(
      user_id="AHATA6X6MYTC3VNBFJ3WIYVK257A",
      records=result.records,
  )

─── Cold-start ─────────────────────────────────────────────────────────────────
  Nếu user_id chưa từng xuất hiện trong tập huấn luyện, reranker dùng
  centroid embedding của tất cả users (average user). Điều này cho phép
  pipeline hoạt động ngay cả với user mới, dù chất lượng cá nhân hoá thấp hơn.
"""

from __future__ import annotations

import json
import pickle
import re
from pathlib import Path
from typing import Optional

import numpy as np
import torch

from ranking.model import KGAT

_ROOT    = Path(__file__).parent
DATA_DIR = _ROOT / "data"
CKPT_DIR = _ROOT / "checkpoints"

# Các key phổ biến trong Neo4j records chứa ASIN
_ASIN_KEY_CANDIDATES = [
    "p.asin", "asin", "product.asin", "p.parent_asin",
    "parent_asin", "ASIN", "item_id",
]
_ASIN_PATTERN = re.compile(r"^[A-Z0-9]{10}$")


class KGATReranker:
    """
    Load KGAT checkpoint một lần → phục vụ nhiều request re-ranking.

    Args:
        checkpoint    : đường dẫn tới file .pt  (default: checkpoints/best_model.pt)
        device        : "auto" | "cpu" | "cuda"
        fallback_score: score cho sản phẩm không có trong KG
                        (default 0.0 — sắp xếp sau các sản phẩm đã biết)
    """

    def __init__(
        self,
        checkpoint: str | Path | None = None,
        device: str = "auto",
        fallback_score: float = 0.0,
    ):
        if checkpoint is None:
            checkpoint = CKPT_DIR / "best_model.pt"

        self.device = (
            torch.device("cuda" if torch.cuda.is_available() else "cpu")
            if device == "auto"
            else torch.device(device)
        )
        self.fallback_score = fallback_score
        self._user_centroid: Optional[torch.Tensor] = None

        self._load(Path(checkpoint))

    # ── Setup ──────────────────────────────────────────────────────────────────

    def _load(self, ckpt_path: Path) -> None:
        if not ckpt_path.exists():
            raise FileNotFoundError(
                f"Checkpoint không tồn tại: {ckpt_path}\n"
                "Chạy: python -m ranking.train"
            )

        print(f"[KGATReranker] Loading {ckpt_path.name} ...")
        ckpt = torch.load(ckpt_path, map_location=self.device, weights_only=False)

        self.model = KGAT(ckpt["cfg"]).to(self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

        # Mappings
        self.entity2id: dict[str, int] = json.loads(
            (DATA_DIR / "entity2id.json").read_text(encoding="utf-8")
        )

        # Tập user thực sự được train (có interactions trong tập train)
        # Dùng để phân biệt "embedding đã học" vs "embedding random chưa train"
        split_file = CKPT_DIR / "kgat_split.json"
        if split_file.exists():
            split = json.loads(split_file.read_text(encoding="utf-8"))
            trained_int_ids = set(int(k) for k in split.get("train_inter", {}).keys())
            trained_int_ids |= set(int(k) for k in split.get("val_inter", {}).keys())
            self._trained_user_ids: set[int] = trained_int_ids
        else:
            # Fallback: coi tất cả là cold-start
            self._trained_user_ids = set()

        # Pre-compute entity embeddings (frozen, dùng cho mọi request)
        ckg = np.load(DATA_DIR / "ckg_triples.npy")
        ckg_t = torch.from_numpy(ckg).long().to(self.device)
        with torch.no_grad():
            self._entity_emb = self.model(ckg_t[:, 0], ckg_t[:, 1], ckg_t[:, 2])

        meta = ckpt.get("recall@10")
        print(
            f"[KGATReranker] Ready.  "
            f"entities={self._entity_emb.shape[0]}, "
            f"emb_dim={self._entity_emb.shape[1]}"
            + (f", Recall@10={meta:.4f}" if meta else "")
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def rerank(
        self,
        user_id: str,
        product_asins: list[str],
        *,
        return_scores: bool = False,
    ) -> list[str] | list[tuple[str, float]]:
        """
        Re-rank danh sách ASIN theo personalized score của user.

        Args:
            user_id       : raw user_id string (khớp với users.json)
            product_asins : danh sách ASIN cần rank
            return_scores : nếu True, trả về [(asin, score), ...] thay vì [asin, ...]

        Returns:
            Danh sách ASIN đã sort (cao nhất trước), hoặc tuples nếu return_scores=True.
        """
        if not product_asins:
            return []

        scores = self._score_asins(f"user_{user_id}", product_asins)
        ranked = sorted(zip(product_asins, scores), key=lambda x: x[1], reverse=True)

        return ranked if return_scores else [a for a, _ in ranked]

    def rerank_records(
        self,
        user_id: str,
        records: list[dict],
        asin_key: str | None = None,
    ) -> list[dict]:
        """
        Re-rank list records từ Neo4j (output của query_engine.pipeline.ask()).

        Args:
            user_id  : raw user_id string
            records  : list[dict] từ run_query()
            asin_key : key trong record chứa ASIN.
                       Nếu None, tự động detect từ danh sách candidate keys.

        Returns:
            List record đã re-rank (record tốt nhất đứng đầu).
            Trả về records gốc nếu không tìm được key ASIN.
        """
        if not records:
            return records

        key = asin_key or _detect_asin_key(records)
        if key is None:
            return records

        asins  = [str(r.get(key, "")) for r in records]
        scores = self._score_asins(f"user_{user_id}", asins)
        paired = sorted(zip(records, scores), key=lambda x: x[1], reverse=True)
        return [r for r, _ in paired]

    # ── Scoring ────────────────────────────────────────────────────────────────

    def _score_asins(self, uid_str: str, asins: list[str]) -> list[float]:
        """Tính personalised score cho mỗi ASIN."""
        e_u = self._get_user_emb(uid_str)

        scores = []
        with torch.no_grad():
            for asin in asins:
                pid_str = f"product_{asin}"
                if pid_str in self.entity2id:
                    pid   = self.entity2id[pid_str]
                    e_p   = self._entity_emb[pid]
                    score = float((e_u * e_p).sum())
                else:
                    score = self.fallback_score
                scores.append(score)
        return scores

    def _get_user_emb(self, uid_str: str) -> torch.Tensor:
        """
        Lấy embedding của user.
        - User đã được train: dùng embedding đã học.
        - User trong KG nhưng không được train (bị lọc): fallback centroid.
        - User mới hoàn toàn: fallback centroid.
        """
        if uid_str in self.entity2id:
            uid = self.entity2id[uid_str]
            if uid in self._trained_user_ids:
                return self._entity_emb[uid]
            # User có trong KG nhưng embedding chưa được train → dùng centroid

        # Cold-start: tính một lần rồi cache (chỉ trung bình user đã train)
        if self._user_centroid is None:
            if self._trained_user_ids:
                idx = torch.tensor(
                    list(self._trained_user_ids), dtype=torch.long, device=self.device
                )
            else:
                idx = torch.tensor(
                    [v for k, v in self.entity2id.items() if k.startswith("user_")],
                    dtype=torch.long, device=self.device,
                )
            self._user_centroid = (
                self._entity_emb[idx].mean(0) if len(idx) > 0
                else torch.zeros(self._entity_emb.shape[1], device=self.device)
            )
        return self._user_centroid

    # ── Batch API (tùy chọn, dùng khi có nhiều users cùng lúc) ───────────────

    @torch.no_grad()
    def batch_score(
        self,
        user_ids: list[str],
        product_asins: list[str],
    ) -> np.ndarray:
        """
        Tính ma trận score cho nhiều users và nhiều items cùng lúc.

        Returns:
            ndarray (n_users, n_items) — score[i][j] = score(user_i, item_j)
        """
        e_users = torch.stack([
            self._get_user_emb(f"user_{uid}") for uid in user_ids
        ])   # (U, D*)

        e_items = []
        for asin in product_asins:
            pid_str = f"product_{asin}"
            if pid_str in self.entity2id:
                e_items.append(self._entity_emb[self.entity2id[pid_str]])
            else:
                e_items.append(torch.zeros(self._entity_emb.shape[1],
                                           device=self.device))
        e_items = torch.stack(e_items)   # (I, D*)

        scores = (e_users @ e_items.T)   # (U, I)
        return scores.cpu().numpy()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _detect_asin_key(records: list[dict]) -> Optional[str]:
    """Tìm key trong record dict chứa ASIN (10 ký tự alphanum hoa)."""
    if not records:
        return None
    sample = records[0]

    for key in _ASIN_KEY_CANDIDATES:
        if key in sample:
            return key

    # Fallback: tìm key có giá trị trông như ASIN
    for key, val in sample.items():
        if isinstance(val, str) and _ASIN_PATTERN.match(val):
            return key
    return None
