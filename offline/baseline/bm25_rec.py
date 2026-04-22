"""
bm25_rec.py — Baseline: BM25 Content-based Recommendation.

Đại diện cho "keyword search" trong hệ thống.

Cách hoạt động:
  1. Xây dựng BM25 index từ text của từng sản phẩm (title + categories + features).
  2. Với mỗi user: ghép text của các sản phẩm trong tập train thành "profile query".
  3. Score mỗi candidate item = BM25(profile_query, item_text).

Không dùng thư viện ngoài — BM25 được implement inline.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent.parent / "data"


# ── Minimal BM25 ──────────────────────────────────────────────────────────────

def _tokenize(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9 ]", " ", text.lower()).split()


class _BM25Index:
    """BM25 Okapi, không phụ thuộc thư viện ngoài."""

    def __init__(self, corpus: list[list[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b  = b
        n       = len(corpus)
        dl      = [len(doc) for doc in corpus]
        avgdl   = sum(dl) / n if n else 1.0

        # IDF
        df: Counter = Counter()
        for doc in corpus:
            for term in set(doc):
                df[term] += 1
        self.idf = {
            t: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
            for t, freq in df.items()
        }

        # TF + doc len
        self._tf    = [Counter(doc) for doc in corpus]
        self._dl    = dl
        self._avgdl = avgdl

    def scores(self, query_tokens: list[str]) -> list[float]:
        result = []
        for tf_doc, dl in zip(self._tf, self._dl):
            s = 0.0
            for t in query_tokens:
                if t in tf_doc:
                    tf  = tf_doc[t]
                    idf = self.idf.get(t, 0.0)
                    s  += idf * tf * (self.k1 + 1) / (
                        tf + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                    )
            result.append(s)
        return result


# ── BM25 Recommender ──────────────────────────────────────────────────────────

class BM25Recommender:
    """
    Content-based recommender dùng BM25.

    Parameters
    ----------
    train_inter : {user_int: [item_int, ...]}
    entity2id   : {entity_str: int}  — để map ASIN → item_int
    id2entity   : {int: entity_str}  — inverse
    """

    name = "BM25 (content)"

    def __init__(
        self,
        train_inter: dict,
        entity2id:   dict,
        id2entity:   dict,
    ):
        self._train_inter = train_inter
        self._id2entity   = id2entity

        # ASIN → item_int
        self._asin2id: dict[str, int] = {}
        for eid_str, eid_int in entity2id.items():
            if eid_str.startswith("product_"):
                asin = eid_str[len("product_"):]
                self._asin2id[asin] = eid_int

        # Load sản phẩm từ meta_filtered.csv
        meta = pd.read_csv(DATA_DIR / "meta_filtered.csv", usecols=["parent_asin", "title", "features", "categories"])
        meta["parent_asin"] = meta["parent_asin"].astype(str)
        meta = meta.drop_duplicates("parent_asin").set_index("parent_asin")

        # Xây text cho mỗi item_int
        self._item_text: dict[int, str] = {}
        for asin, iid in self._asin2id.items():
            if asin not in meta.index:
                self._item_text[iid] = ""
                continue
            row   = meta.loc[asin]
            title = str(row.get("title", "") or "")
            cats  = str(row.get("categories", "") or "")
            feats = str(row.get("features", "") or "")
            self._item_text[iid] = f"{title} {cats} {feats}"

        # Xây BM25 index (thứ tự theo item_ids sẽ được truyền lúc score)
        # Index được xây lazy khi gọi score lần đầu với item_ids cụ thể
        self._cached_item_ids: list[int] | None = None
        self._index: _BM25Index | None          = None

    def _build_index(self, item_ids: list[int]) -> None:
        if self._cached_item_ids == item_ids:
            return
        corpus = [_tokenize(self._item_text.get(i, "")) for i in item_ids]
        self._index            = _BM25Index(corpus)
        self._cached_item_ids  = item_ids

    def score(self, user_id: int, item_ids: list[int]) -> list[float]:
        self._build_index(item_ids)

        # Xây user profile từ training items
        profile_tokens: list[str] = []
        for iid in self._train_inter.get(user_id, []):
            profile_tokens.extend(_tokenize(self._item_text.get(iid, "")))

        if not profile_tokens:
            return [0.0] * len(item_ids)

        return self._index.scores(profile_tokens)
