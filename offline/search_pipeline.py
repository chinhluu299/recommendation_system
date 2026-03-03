"""
search_pipeline.py
Pipeline tìm kiếm sản phẩm end-to-end.

Luồng:
  1. NL → WHERE clause (LLM)  →  filter_query + semantic_query
  2. Embed câu hỏi             (SentenceTransformer)
  3. Search Neo4j              (filter + vector)
  4. Score graph               (filter_bonus + sem×0.5 + pop×0.3)
  5. Rerank personalized       (0.5 × KGAT_norm + 0.5 × graph_norm)

Public API:
    search_ranked(query, user_id) → list[str]   # product_id sorted
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

# ── Config ────────────────────────────────────────────────────────────────────

_TOP_K        = 100
_FILTER_BONUS = 1.0
_SEM_W        = 0.5
_POP_W        = 0.3
_MIN_RATINGS  = 3

# ── Lazy singletons ───────────────────────────────────────────────────────────

_embed_model = None
_reranker    = None

def _embed(text: str) -> list[float]:
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("intfloat/multilingual-e5-small")
    return _embed_model.encode("query: " + text, normalize_embeddings=True).tolist()

def _get_reranker():
    global _reranker
    if _reranker is None:
        from offline.ranking.rerank import KGATReranker
        _reranker = KGATReranker()
    return _reranker

# ── Utilities ─────────────────────────────────────────────────────────────────

def _minmax(vals: list[float]) -> list[float]:
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return [0.5] * len(vals)
    return [(v - lo) / (hi - lo) for v in vals]

def _norm_pop(rows: list[dict]) -> dict[str, float]:
    """Bayesian popularity → min-max [0,1]."""
    valid = [r for r in rows
             if r.get("avg_rating") is not None and (r.get("rating_count") or 0) >= _MIN_RATINGS]
    if not valid:
        return {}
    mu = sum(r["avg_rating"] for r in valid) / len(valid)
    C  = _MIN_RATINGS
    bay = {
        r["product_id"]: (
            (C * mu + r.get("avg_rating", 0.0) * (r.get("rating_count") or 0))
            / (C + (r.get("rating_count") or 0))
            if (r.get("rating_count") or 0) >= _MIN_RATINGS else mu
        )
        for r in rows
    }
    lo, hi = min(bay.values()), max(bay.values())
    if hi == lo:
        return {k: 0.5 for k in bay}
    return {k: (v - lo) / (hi - lo) for k, v in bay.items()}

# ── Step 1: NL → Cypher ───────────────────────────────────────────────────────

_PROMPT_SCHEMA = """Bạn là hệ thống sinh điều kiện WHERE cho Cypher query Neo4j.

Các biến đã OPTIONAL MATCH sẵn:
  p  (Product)   — p.price, p.average_rating, p.rating_number, p.color, p.screen_size, p.operating_system
  b  (Brand)     — b.label  ('Samsung', 'Apple', ...)
  t  (Technology)— t.label  ('5G', '4G LTE', 'Wi-Fi', ...)
  c  (Carrier)   — c.label  ('AT&T', 'T-Mobile', 'Verizon', ...)
  s  (Spec)      — s.key ('ram'|'storage'), s.value ('8 GB', '128 GB', ...)
"""

_PROMPT_RULES = """
CHỈ trả về phần WHERE (bắt đầu bằng WHERE).
KHÔNG dùng: MATCH, RETURN, CALL, YIELD, CREATE, MERGE, DELETE, LIMIT, ORDER, WITH.
Dùng toLower() khi so sánh chuỗi. Kiểm tra p.price IS NOT NULL trước khi so sánh giá.
Không có filter rõ ràng → WHERE true. Chỉ Cypher thuần, không markdown.

Ví dụ:
  "Samsung dưới 300 đô"   → WHERE toLower(b.label) CONTAINS 'samsung' AND p.price IS NOT NULL AND p.price < 300
  "5G RAM 8GB"            → WHERE t.label = '5G' AND s.key = 'ram' AND s.value = '8 GB'
  "hỗ trợ AT&T"          → WHERE c.label = 'AT&T'
  "rating trên 4.5"       → WHERE p.average_rating >= 4.5
  "điện thoại tốt"        → WHERE true
"""

_FORBIDDEN = {"MATCH", "RETURN", "CALL", "YIELD", "CREATE", "MERGE", "DELETE", "DETACH"}

def _build_queries(question: str) -> tuple[str, str, str]:
    """
    Gọi LLM sinh WHERE clause, build filter_query + semantic_query.
    Returns: (filter_query, semantic_query, where_clause)
    """
    from offline.query_engine.schema import load_enum_values
    from offline.query_engine._llm_client import chat

    try:
        e = load_enum_values()
        enum_hint = (f"\nRAM: {e.get('ram_values',[])}  Storage: {e.get('storage_values',[])}"
                     f"  Technology: {e.get('technologies',[])}  Carrier: {e.get('carriers',[])}\n")
    except Exception:
        enum_hint = ""

    raw = chat(
        [
            {"role": "system", "content": _PROMPT_SCHEMA + enum_hint + _PROMPT_RULES},
            {"role": "user",   "content": question},
        ],
        max_tokens=256,
        temperature=0.1,
    )

    # Strip markdown fences
    where = re.sub(r"^```(?:cypher)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    where = re.sub(r"\s*```$", "", where).strip()
    if not where:
        raise ValueError("LLM trả về rỗng.")
    if not where.upper().startswith("WHERE"):
        where = "WHERE " + where

    upper = where.upper()
    for kw in _FORBIDDEN:
        if kw in upper:
            raise ValueError(f"WHERE clause chứa từ khoá không hợp lệ '{kw}': {where!r}")

    filter_q = (
        "MATCH (p:Product)\n"
        "OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)\n"
        "OPTIONAL MATCH (p)-[:USES_TECHNOLOGY]->(t:Technology)\n"
        "OPTIONAL MATCH (p)-[:SUPPORTS_CARRIER]->(c:Carrier)\n"
        "OPTIONAL MATCH (p)-[:HAS_SPEC]->(s:Spec)\n"
        f"{where}\n"
        "WITH DISTINCT p\n"
        "OPTIONAL MATCH (u:User)-[r:RATING]->(p)\n"
        "WITH p.id AS product_id, COUNT(r) AS rating_count, AVG(r.score) AS avg_rating\n"
        f"RETURN product_id, rating_count, avg_rating\n"
        f"LIMIT {_TOP_K}"
    )

    sem_q = (
        f"CALL db.index.vector.queryNodes('product_text_index', {_TOP_K}, $query_embedding) "
        "YIELD node AS p, score AS sem_score "
        "OPTIONAL MATCH (u:User)-[r:RATING]->(p) "
        "WITH p.id AS product_id, sem_score, COUNT(r) AS rating_count, AVG(r.score) AS avg_rating "
        "RETURN product_id, sem_score, rating_count, avg_rating"
    )

    return filter_q, sem_q, where

# ── Step 4: Graph scoring ─────────────────────────────────────────────────────

@dataclass
class _Candidate:
    product_id:  str
    graph_score: float
    from_filter: bool

def _graph_score(filter_rows: list[dict], sem_rows: list[dict]) -> list[_Candidate]:
    """Tính graph_score = filter_bonus + sem×0.5 + pop×0.3 cho từng sản phẩm."""
    sem_map = {r["product_id"]: r.get("sem_score", 0.0) for r in sem_rows}

    all_rows = {r["product_id"]: r for r in sem_rows}
    all_rows.update({r["product_id"]: r for r in filter_rows})
    pop_map = _norm_pop(list(all_rows.values()))

    results: dict[str, _Candidate] = {}

    for r in filter_rows:
        pid = r["product_id"]
        results[pid] = _Candidate(
            product_id  = pid,
            graph_score = _FILTER_BONUS + sem_map.get(pid, 0.0) * _SEM_W + pop_map.get(pid, 0.0) * _POP_W,
            from_filter = True,
        )
    for r in sem_rows:
        pid = r["product_id"]
        if pid not in results:
            results[pid] = _Candidate(
                product_id  = pid,
                graph_score = r.get("sem_score", 0.0) * _SEM_W + pop_map.get(pid, 0.0) * _POP_W,
                from_filter = False,
            )

    return sorted(results.values(), key=lambda c: -c.graph_score)[:_TOP_K]

# ── Public API ────────────────────────────────────────────────────────────────

def search_ranked(query: str, user_id: str | None = None) -> list[str]:
    """
    Tìm kiếm và trả về list product_id sorted theo final_score.

    final_score = 0.5 × KGAT_norm + 0.5 × graph_norm
    """
    from offline.query_engine.graph_search import run_query

    # Bước 1 & 2
    filter_q, sem_q, _where = _build_queries(query)
    embedding = _embed(query)

    # Bước 3
    filter_rows = run_query(filter_q)
    sem_rows    = run_query(sem_q, {"query_embedding": embedding})

    # Bước 4
    candidates = _graph_score(filter_rows, sem_rows)
    if not candidates:
        return []

    asins      = [c.product_id  for c in candidates]
    g_vals     = [c.graph_score for c in candidates]

    # Bước 5
    try:
        kgat_pairs = _get_reranker().rerank(user_id or "", asins, return_scores=True)
        k_vals = [score for _, score in kgat_pairs]
    except Exception:
        k_vals = [0.0] * len(asins)

    g_norm = _minmax(g_vals)
    k_norm = _minmax(k_vals)
    final  = [0.5 * k + 0.5 * g for k, g in zip(k_norm, g_norm)]

    ranked = sorted(zip(asins, final), key=lambda x: -x[1])
    return [pid for pid, _ in ranked]
