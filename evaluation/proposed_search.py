"""
proposed_search.py
──────────────────
Đánh giá KG pipeline (hệ thống đề xuất) trên bộ 100 test queries.
Mỗi query sinh 2 kết quả để so sánh:
  1. Proposed       — pipeline gốc (cold-start, KGAT bị skip)
  2. Proposed+KGAT  — pipeline + KGAT rerank cold-start (centroid user embedding)

Pipeline flow (từ app.search_pipeline):
  câu hỏi
    ↓ translate → nl2cypher (LLM sinh intent + Cypher)
    ↓ run_query trên Neo4j Knowledge Graph (filter + semantic)
    ↓ graph_scoring (filter_bonus + sem + popularity)
    ↓ [Mode 2 only] KGAT re-rank với centroid (cold-start)
    → danh sách ASIN xếp hạng

Input  : evaluation/filter_intent_queries_v3.json
Output : evaluation/proposed_results_3.json

So sánh: nếu tồn tại baseline_results sẽ in bảng so sánh kèm baseline.

Chạy:
    cd recommendation_system/api
    python3 ../evaluation/proposed_search.py
    python3 ../evaluation/proposed_search.py --k 5 10 20 --verbose
    python3 ../evaluation/proposed_search.py --out ../evaluation/proposed_results.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
# Script có thể chạy từ evaluation/ hoặc api/
# Cần thêm api/ vào sys.path để import offline.*

EVAL_DIR = Path(__file__).resolve().parent          # evaluation/
ROOT     = EVAL_DIR.parent                          # recommendation_system/
API_DIR  = ROOT / "api"

if str(API_DIR) not in sys.path:
    sys.path.insert(0, str(API_DIR))

QUERY_PATH    = EVAL_DIR / "filter_intent_queries_v2.json"
BASELINE_PATH = EVAL_DIR / "baseline_results_v2.json"
OUT_PATH      = EVAL_DIR / "proposed_results_2.json"


# ══════════════════════════════════════════════════════════════════════════════
# Metrics  (giống baseline_search.py để so sánh cùng thang đo)
# ══════════════════════════════════════════════════════════════════════════════

def rank_of(ranked: list[str], target: str) -> int | None:
    try:
        return ranked.index(target) + 1
    except ValueError:
        return None


def hit_at_k(rank: int | None, k: int) -> float:
    return 1.0 if (rank is not None and rank <= k) else 0.0


def mrr_at_k(rank: int | None, k: int) -> float:
    return (1.0 / rank) if (rank is not None and rank <= k) else 0.0


def ndcg_at_k(rank: int | None, k: int) -> float:
    """NDCG@K với binary relevance (IDCG = 1 vì chỉ có 1 item relevant)."""
    return (1.0 / math.log2(rank + 1)) if (rank is not None and rank <= k) else 0.0


def compute_metrics(ranked: list[str], target: str, k_values: list[int]) -> dict:
    rank = rank_of(ranked, target)
    m: dict = {"rank": rank}
    for k in k_values:
        m[f"hit@{k}"]  = hit_at_k(rank, k)
        m[f"mrr@{k}"]  = mrr_at_k(rank, k)
        m[f"ndcg@{k}"] = ndcg_at_k(rank, k)
    return m


def aggregate(records: list[dict], system: str, k_values: list[int]) -> dict:
    n = len(records)
    if n == 0:
        return {"system": system, "n": 0}
    row: dict = {"system": system, "n": n}
    for k in k_values:
        row[f"hit@{k}"]  = round(sum(r[f"hit@{k}"]  for r in records) / n, 4)
        row[f"mrr@{k}"]  = round(sum(r[f"mrr@{k}"]  for r in records) / n, 4)
        row[f"ndcg@{k}"] = round(sum(r[f"ndcg@{k}"] for r in records) / n, 4)
    return row


# ══════════════════════════════════════════════════════════════════════════════
# Pipeline wrapper
# ══════════════════════════════════════════════════════════════════════════════

def _import_pipeline():
    """Import search_ranked_with_trace từ app.search_pipeline."""
    try:
        from app.search_pipeline import search_ranked_with_trace
        return search_ranked_with_trace
    except ImportError as e:
        print(f"[ERR] Không thể import pipeline: {e}")
        print(f"      Đảm bảo chạy từ thư mục api/")
        print(f"      Ví dụ: cd recommendation_system/api && python3 ../evaluation/proposed_search.py")
        sys.exit(1)


def search_proposed(
    query: str,
    user_id: str | None,
    search_fn,
    cold_start_kgat: bool = False,
) -> tuple[list[str], dict, float]:
    """
    Gọi pipeline và trả về (ranked_asins, trace, latency_ms).

    Args:
        query           : câu hỏi tự nhiên
        user_id         : Amazon user_id để personalize (None = cold-start)
        search_fn       : search_ranked_with_trace function
        cold_start_kgat : nếu True, bật KGAT rerank với centroid cho cold-start
    """
    t0 = time.time()
    try:
        ranked, trace = search_fn(
            query=query,
            user_id=user_id,
            cold_start_kgat=cold_start_kgat,
        )
    except Exception as e:
        latency = (time.time() - t0) * 1000
        return [], {"error": str(e)}, latency

    latency = (time.time() - t0) * 1000
    return ranked, trace, latency


# ══════════════════════════════════════════════════════════════════════════════
# Print table
# ══════════════════════════════════════════════════════════════════════════════

def print_table(summary_rows: list[dict], k_values: list[int], title: str) -> None:
    import re
    metric_cols: list[str] = []
    for k in k_values:
        metric_cols += [f"Hit@{k}", f"MRR@{k}", f"NDCG@{k}"]

    sys_col_w = max(len(r["system"]) for r in summary_rows) + 2
    metric_w  = 8
    total_w   = sys_col_w + metric_w * len(metric_cols)
    sep       = "─" * total_w
    header    = f"{'System':<{sys_col_w}}" + "".join(f"{c:>{metric_w}}" for c in metric_cols)

    print(f"\n{'═'*total_w}")
    print(f"  {title}")
    print(f"{'═'*total_w}")
    print(header)

    prev_group = None
    for row in summary_rows:
        g = re.search(r'\((\w+)\)', row["system"])
        group = g.group(1) if g else "ALL"
        if group != prev_group:
            print(sep)
            prev_group = group
        vals = [row.get(f"{m.split('@')[0].lower()}@{m.split('@')[1]}", 0.0)
                for m in metric_cols]
        line = f"{row['system']:<{sys_col_w}}" + "".join(f"{v:>{metric_w}.4f}" for v in vals)
        print(line)
    print(f"{'═'*total_w}\n")


def print_comparison(proposed_rows: list[dict], baseline_path: Path, k_values: list[int]) -> None:
    """In bảng so sánh KG pipeline vs baseline (BM25 + Semantic nếu có)."""
    if not baseline_path.exists():
        return

    with open(baseline_path, encoding="utf-8") as f:
        bl = json.load(f)

    bl_rows = [r for r in bl.get("summary", [])
               if r["system"].startswith(("BM25", "Semantic"))]

    combined = list(proposed_rows) + bl_rows
    if combined:
        print_table(combined, k_values, "KG Pipeline vs Baseline")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Đánh giá KG + KGAT pipeline trên filter_intent_queries.json"
    )
    parser.add_argument("--queries", type=Path, default=QUERY_PATH,
                        help="File JSON chứa queries (default: filter_intent_queries.json)")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10, 20, 50, 100, 200],
                        help="Các giá trị K để tính metrics (default: 5 10 20)")
    parser.add_argument("--user-id", type=str, default=None,
                        help="Amazon user_id để personalize (default: cold-start)")
    parser.add_argument("--verbose", action="store_true",
                        help="In rank + trace từng query")
    parser.add_argument("--out", type=Path, default=OUT_PATH,
                        help="File JSON lưu kết quả (default: proposed_results.json)")
    parser.add_argument("--compare", action="store_true", default=True,
                        help="So sánh với BM25 baseline nếu baseline_results.json tồn tại")
    args = parser.parse_args()

    k_values = sorted(set(args.k))
    systems: list[tuple[str, bool]] = [
        ("Proposed",      False),   # pipeline gốc, cold-start KGAT tắt
        ("Proposed+KGAT", True),    # pipeline + KGAT rerank cold-start (centroid)
    ]
    system_names = [name for name, _ in systems]

    # ── 1. Load queries ────────────────────────────────────────────────────────
    if not args.queries.exists():
        print(f"[ERR] Không tìm thấy: {args.queries}")
        sys.exit(1)

    with open(args.queries, encoding="utf-8") as f:
        queries: list[dict] = json.load(f)

    filter_qs = [q for q in queries if q["query_type"] == "filter"]
    intent_qs = [q for q in queries if q["query_type"] == "intent"]

    print(f"\n{'─'*60}")
    print(f"  Systems : {system_names}")
    print(f"  Queries : {len(queries)} tổng  ({len(filter_qs)} filter + {len(intent_qs)} intent)")
    print(f"  K values: {k_values}")
    print(f"  User ID : {args.user_id or 'cold-start'}")

    # ── 2. Import pipeline ────────────────────────────────────────────────────
    print(f"\n[1/3] Import KG pipeline …")
    search_fn = _import_pipeline()
    print(f"    → OK (nl2cypher + Neo4j + KGAT reranker)")

    # ── 3. Evaluate ───────────────────────────────────────────────────────────
    print(f"\n[2/3] Chạy {len(queries)} queries × {len(systems)} systems …\n")

    per_query: list[dict] = []
    latencies: dict[str, list[float]] = {name: [] for name in system_names}
    errors: dict[str, list[str]] = {name: [] for name in system_names}

    for i, q in enumerate(queries, 1):
        qid    = q["id"]
        qtype  = q["query_type"]
        query  = q["query"]
        target = q["target_asin"]

        if args.verbose:
            print(f"  [{i:>3}/{len(queries)}] [{qtype:>6}] {query[:65]}")

        entry: dict = {
            "id":            qid,
            "query_type":    qtype,
            "query":         query,
            "target_asin":   target,
            "product_title": q.get("product_title", ""),
        }

        for sys_name, cold_kgat in systems:
            ranked, trace, latency = search_proposed(
                query=query,
                user_id=args.user_id,
                search_fn=search_fn,
                cold_start_kgat=cold_kgat,
            )
            latencies[sys_name].append(latency)

            m = compute_metrics(ranked, target, k_values)
            m["latency_ms"] = round(latency, 2)

            if trace.get("error"):
                errors[sys_name].append(f"[{qid}] {trace['error']}")
                m["error"] = trace["error"]

            entry[sys_name] = m

            # Lưu trace rút gọn theo step IDs của search_pipeline
            steps_summary = {}
            for step in trace.get("steps", []):
                sid = step.get("id", "")
                if sid == "nl2cypher":
                    steps_summary["where_clause"] = step.get("where_clause", "")
                elif sid == "neo4j":
                    steps_summary["filter_count"] = step.get("filter_count", 0)
                    steps_summary["sem_count"]    = step.get("sem_count", 0)
                elif sid == "graph_scoring":
                    steps_summary["candidate_count"] = step.get("count", 0)
                elif sid == "rerank":
                    payload = step.get("payload", {})
                    steps_summary["rerank_mode"]  = payload.get("mode", "")
                    steps_summary["rerank_error"] = payload.get("error", "")
            entry[f"{sys_name}_trace"] = steps_summary

            if args.verbose:
                r = m["rank"]
                print(f"       [{sys_name:<14}] rank={'None' if r is None else r:<5}  " +
                      "  ".join(f"Hit@{k}={int(m[f'hit@{k}'])}" for k in k_values) +
                      f"  ({latency:.0f}ms)")
                if m.get("error"):
                    print(f"       [ERR] {m['error'][:80]}")

        per_query.append(entry)

    # ── 4. Aggregate ──────────────────────────────────────────────────────────
    print(f"\n[3/3] Tổng hợp kết quả …")

    def agg(qs: list[dict], sys_name: str, label: str) -> dict:
        metrics_list = [q[sys_name] for q in qs if sys_name in q]
        return aggregate(metrics_list, f"{sys_name} ({label})", k_values)

    groups = [
        ("All",    per_query),
        ("Filter", [q for q in per_query if q["query_type"] == "filter"]),
        ("Intent", [q for q in per_query if q["query_type"] == "intent"]),
    ]
    summary_rows: list[dict] = []
    for label, qs in groups:
        for sys_name in system_names:
            summary_rows.append(agg(qs, sys_name, label))

    # ── 5. Print tables ───────────────────────────────────────────────────────
    print_table(summary_rows, k_values, "Proposed vs Proposed+KGAT — Evaluation Results")

    # So sánh với baseline (nếu có)
    if args.compare:
        print_comparison(summary_rows, BASELINE_PATH, k_values)

    # ── 6. Stats bổ sung ──────────────────────────────────────────────────────
    print("Chi tiết theo query type:")
    for label, qs in [("Filter", [q for q in per_query if q["query_type"] == "filter"]),
                       ("Intent", [q for q in per_query if q["query_type"] == "intent"])]:
        for sys_name in system_names:
            found       = sum(1 for q in qs if sys_name in q and q[sys_name]["rank"] is not None)
            found_top5  = sum(1 for q in qs if sys_name in q and q[sys_name].get("hit@5", 0))
            found_top10 = sum(1 for q in qs if sys_name in q and q[sys_name].get("hit@10", 0))
            n = len(qs)
            print(f"  [{sys_name:<14}] {label:6}: tìm thấy {found}/{n} targets "
                  f"| top-5: {found_top5} | top-10: {found_top10}")

    import statistics
    print(f"\nLatency (ms/query):")
    for sys_name in system_names:
        lats = latencies[sys_name]
        if not lats:
            continue
        print(f"  [{sys_name:<14}] mean={statistics.mean(lats):.1f}  "
              f"median={statistics.median(lats):.1f}  "
              f"min={min(lats):.1f}  max={max(lats):.1f}")

    for sys_name in system_names:
        errs = errors[sys_name]
        if errs:
            print(f"\n[WARN] [{sys_name}] {len(errs)} queries bị lỗi:")
            for e in errs[:10]:
                print(f"  {e}")
            if len(errs) > 10:
                print(f"  ... (còn {len(errs) - 10} lỗi nữa)")

    # ── 7. Save ───────────────────────────────────────────────────────────────
    results = {
        "systems":     system_names,
        "k_values":    k_values,
        "n_queries":   len(per_query),
        "n_filter":    len(filter_qs),
        "n_intent":    len(intent_qs),
        "n_errors":    {name: len(errors[name]) for name in system_names},
        "summary":     summary_rows,
        "per_query":   per_query,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✓ Kết quả chi tiết → {args.out}")
    print(f"\nCách chạy:")
    print(f"  cd recommendation_system/api")
    print(f"  python3 ../evaluation/proposed_search.py --verbose")
    print(f"  python3 ../evaluation/proposed_search.py --k 5 10 20 50")


if __name__ == "__main__":
    main()
