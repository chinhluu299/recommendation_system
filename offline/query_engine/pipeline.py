from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from offline.query_engine.nl2cypher import generate_queries
from offline.query_engine.graph_search import run_query
from offline.query_engine.scoring import hybrid_merge, HybridResult
from offline.query_engine._llm_client import chat


_embed_model = None

def _get_embed_model():
    global _embed_model
    if _embed_model is None:
        from sentence_transformers import SentenceTransformer
        _embed_model = SentenceTransformer("intfloat/multilingual-e5-small")
    return _embed_model

def _embed(text: str) -> list[float]:
    return _get_embed_model().encode(
        "query: " + text, normalize_embeddings=True
    ).tolist()


_reranker = None

def _get_reranker():
    global _reranker
    if _reranker is None:
        from offline.ranking.rerank import KGATReranker
        _reranker = KGATReranker()
    return _reranker


def _minmax(values: list[float]) -> list[float]:
    lo, hi = min(values), max(values)
    if hi == lo:
        return [0.5] * len(values)
    return [(v - lo) / (hi - lo) for v in values]


@dataclass
class SearchResult:
    product_id: str
    final_score: float
    graph_score: float
    kgat_score: float
    from_filter: bool
    sem_score: float
    pop_score: float


def search(
    question: str,
    user_id: str | None = None,
    top_k: int = 100,
) -> tuple[list[SearchResult], dict[str, Any]]:
    trace: dict[str, Any] = {"question": question, "user_id": user_id, "steps": []}

    try:
        queries = generate_queries(question)
    except Exception as e:
        trace["error"] = f"[Bước 1] Sinh Cypher thất bại: {e}"
        return [], trace

    trace["steps"].append({
        "id": "nl2cypher",
        "where_clause": queries["where_clause"],
        "filter_query": queries["filter_query"],
        "semantic_query": queries["semantic_query"],
    })

    try:
        embedding = _embed(question)
    except Exception as e:
        trace["error"] = f"[Bước 2] Embed thất bại: {e}"
        return [], trace

    try:
        filter_rows = run_query(queries["filter_query"])
        semantic_rows = run_query(queries["semantic_query"], {"query_embedding": embedding})
    except Exception as e:
        trace["error"] = f"[Bước 3] Neo4j query thất bại: {e}"
        return [], trace

    trace["steps"].append({
        "id": "neo4j_search",
        "filter_count": len(filter_rows),
        "semantic_count": len(semantic_rows),
    })

    merged: list[HybridResult] = hybrid_merge(filter_rows, semantic_rows, total_limit=top_k)
    if not merged:
        trace["steps"].append({"id": "graph_scoring", "count": 0})
        return [], trace

    graph_map = {r.product_id: r for r in merged}
    asins = [r.product_id for r in merged]

    trace["steps"].append({
        "id": "graph_scoring",
        "count": len(merged),
        "top5": [
            {
                "product_id": r.product_id,
                "score": round(r.score, 4),
                "filter": r.from_filter,
                "sem": round(r.sem_score, 4),
                "pop": round(r.pop_score, 4),
            }
            for r in merged[:5]
        ],
    })

    try:
        reranker = _get_reranker()
        kgat_pairs: list[tuple[str, float]] = reranker.rerank(
            user_id or "",
            asins,
            return_scores=True,
        )
        kgat_map = dict(kgat_pairs)
        rerank_ok = True
    except Exception as e:
        kgat_map = {pid: 0.0 for pid in asins}
        rerank_ok = False
        trace["steps"].append({"id": "rerank", "error": str(e), "fallback": True})

    g_vals = [graph_map[pid].score for pid in asins]
    k_vals = [kgat_map.get(pid, 0.0) for pid in asins]
    g_norm = _minmax(g_vals)
    k_norm = _minmax(k_vals)

    results: list[SearchResult] = []
    for pid, gn, kn in zip(asins, g_norm, k_norm):
        hr = graph_map[pid]
        results.append(SearchResult(
            product_id=pid,
            final_score=0.5 * kn + 0.5 * gn,
            graph_score=hr.score,
            kgat_score=kgat_map.get(pid, 0.0),
            from_filter=hr.from_filter,
            sem_score=hr.sem_score,
            pop_score=hr.pop_score,
        ))

    results.sort(key=lambda r: -r.final_score)

    if rerank_ok:
        trace["steps"].append({
            "id": "rerank",
            "top5": [
                {
                    "product_id": r.product_id,
                    "final": round(r.final_score, 4),
                    "graph": round(r.graph_score, 4),
                    "kgat": round(r.kgat_score, 4),
                }
                for r in results[:5]
            ],
        })

    return results[:top_k], trace


def search_ranked(query: str, user_id: str | None = None) -> list[str]:
    results, _ = search(query, user_id=user_id)
    return [r.product_id for r in results]


def search_ranked_with_trace(
    query: str,
    user_id: str | None = None,
) -> tuple[list[str], dict[str, Any]]:
    results, trace = search(query, user_id=user_id)
    return [r.product_id for r in results], trace


@dataclass
class QueryResult:
    question: str
    cypher: str
    records: list[dict]
    answer: str
    error: str | None = None
    mode: str = "hybrid"


def ask(question: str, user_id: str | None = None, format_answer: bool = True) -> QueryResult:
    results, trace = search(question, user_id=user_id)

    if not results:
        err = trace.get("error", "Không tìm thấy kết quả.")
        return QueryResult(question, "", [], err, error=err)

    records = [
        {
            "product_id": r.product_id,
            "final_score": round(r.final_score, 4),
            "from_filter": r.from_filter,
        }
        for r in results
    ]

    cypher = next(
        (s.get("filter_query", "") for s in trace.get("steps", []) if s.get("id") == "nl2cypher"),
        "",
    )

    if format_answer:
        sample = records[:30]
        rows_text = "\n".join(str(r) for r in sample)
        if len(records) > 30:
            rows_text += f"\n... (còn {len(records) - 30} kết quả nữa)"
        answer = chat(
            [{
                "role": "user",
                "content": (
                    f"Câu hỏi: {question}\n\n"
                    f"Kết quả tìm kiếm ({len(records)} sản phẩm):\n{rows_text}\n\n"
                    "Hãy trình bày ngắn gọn bằng tiếng Việt."
                ),
            }],
            max_tokens=4000,
            temperature=0.7,
        )
    else:
        answer = f"{len(records)} kết quả tìm thấy."

    return QueryResult(question, cypher, records, answer)
