"""Đánh giá BM25 và Semantic Search trên bộ 100 test queries."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

EVAL_DIR   = Path(__file__).resolve().parent
ROOT       = EVAL_DIR.parent
DATA_DIR   = ROOT / "offline" / "data"
META_PATH  = DATA_DIR / "meta_filtered.csv"
QUERY_PATH = EVAL_DIR / "filter_intent_queries_v2.json"
OUT_PATH   = EVAL_DIR / "baseline_results_v2.json"


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


def build_product_text(row: pd.Series) -> str:
    # Title lặp 2 lần để boost weight khi matching
    parts: list[str] = []
    title = str(row.get("title") or "").strip()
    if title:
        parts.append(title)
        parts.append(title)
    for col in ("main_category", "categories", "features"):
        val = str(row.get(col) or "").strip()
        if val and val not in ("nan", "[]", "{}"):
            parts.append(val)
    return " ".join(parts)


def tokenize(text: str) -> list[str]:
    return re.sub(r"[^a-z0-9\s]", " ", text.lower()).split()


class BM25Index:
    def __init__(self, corpus_texts: list[str], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b  = b

        tokenized = [tokenize(t) for t in corpus_texts]
        n         = len(tokenized)
        dl        = [len(d) for d in tokenized]
        self._avgdl = sum(dl) / n if n else 1.0

        df: Counter[str] = Counter()
        for doc in tokenized:
            for term in set(doc):
                df[term] += 1

        self._idf: dict[str, float] = {
            t: math.log((n - freq + 0.5) / (freq + 0.5) + 1)
            for t, freq in df.items()
        }

        self._tf  = [Counter(doc) for doc in tokenized]
        self._dl  = dl

    def search(self, query: str, top_k: int) -> list[int]:
        tokens = tokenize(query)
        scores: list[float] = []
        for tf_doc, dl in zip(self._tf, self._dl):
            s = 0.0
            for t in tokens:
                if t in tf_doc:
                    tf  = tf_doc[t]
                    idf = self._idf.get(t, 0.0)
                    s  += idf * tf * (self.k1 + 1) / (
                        tf + self.k1 * (1 - self.b + self.b * dl / self._avgdl)
                    )
            scores.append(s)

        n = len(scores)
        k = min(top_k, n)
        top_idx = np.argpartition(scores, -k)[-k:]
        top_idx = top_idx[np.argsort(np.array(scores)[top_idx])[::-1]]
        return top_idx.tolist()


class SemanticIndex:
    DEFAULT_MODEL = "intfloat/multilingual-e5-small"

    def __init__(self, corpus_texts: list[str],
                 model_name: str = DEFAULT_MODEL,
                 batch_size: int = 64,
                 cache_path: Path | None = None):
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        self._model      = SentenceTransformer(model_name)

        # multilingual-e5 yêu cầu prefix "passage: " cho corpus
        prefixed = ["passage: " + t[:512] for t in corpus_texts]

        if cache_path and cache_path.exists():
            print(f"    Semantic: load embeddings từ cache {cache_path.name} …", end=" ", flush=True)
            self._doc_emb = np.load(str(cache_path))
            print("xong")
        else:
            print(f"    Semantic: encode {len(prefixed):,} docs với {model_name} …", flush=True)
            self._doc_emb = self._model.encode(
                prefixed,
                batch_size=batch_size,
                show_progress_bar=True,
                normalize_embeddings=True,
                convert_to_numpy=True,
            )
            if cache_path:
                np.save(str(cache_path), self._doc_emb)
                print(f"    Semantic: đã cache embeddings → {cache_path.name}")

    def search(self, query: str, top_k: int) -> list[int]:
        q_emb  = self._model.encode(
            ["query: " + query],
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        scores = (self._doc_emb @ q_emb.T).ravel()
        k      = min(top_k, len(scores))
        top_idx = np.argpartition(scores, -k)[-k:]
        top_idx = top_idx[np.argsort(scores[top_idx])[::-1]]
        return top_idx.tolist()


def print_table(summary_rows: list[dict], k_values: list[int]) -> None:
    metric_cols = []
    for k in k_values:
        metric_cols += [f"Hit@{k}", f"MRR@{k}", f"NDCG@{k}"]

    sys_col_w = max(len(r["system"]) for r in summary_rows) + 2
    metric_w  = 8
    total_w   = sys_col_w + metric_w * len(metric_cols)

    sep    = "─" * total_w
    header = f"{'System':<{sys_col_w}}" + "".join(f"{c:>{metric_w}}" for c in metric_cols)

    systems_in_table = sorted({r["system"].split(" (")[0] for r in summary_rows})
    title = "  BASELINE COMPARISON — " + " vs ".join(systems_in_table)

    print(f"\n{'═'*total_w}")
    print(title)
    print(f"{'═'*total_w}")
    print(header)

    prev_group = None
    for row in summary_rows:
        group = re.search(r'\((\w+)\)', row["system"])
        group = group.group(1) if group else "ALL"
        if group != prev_group:
            print(sep)
            prev_group = group
        vals = [row.get(f"{m.split('@')[0].lower()}@{m.split('@')[1]}", 0.0)
                for m in metric_cols]
        line = f"{row['system']:<{sys_col_w}}" + "".join(f"{v:>{metric_w}.4f}" for v in vals)
        print(line)

    print(f"{'═'*total_w}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Đánh giá BM25, Semantic Search baseline"
    )
    parser.add_argument("--queries", type=Path, default=QUERY_PATH,
                        help="File JSON chứa queries")
    parser.add_argument("--meta", type=Path, default=META_PATH,
                        help="File CSV chứa sản phẩm")
    parser.add_argument("--k", type=int, nargs="+", default=[5, 10, 20],
                        help="Các giá trị K để tính metrics (default: 5 10 20)")
    parser.add_argument("--top-k", type=int, default=100,
                        help="Số kết quả tối đa mỗi query (default: 100)")
    parser.add_argument("--no-semantic", action="store_true",
                        help="Bỏ qua Semantic Search")
    parser.add_argument("--sem-model", type=str,
                        default=SemanticIndex.DEFAULT_MODEL,
                        help=f"SentenceTransformer model (default: {SemanticIndex.DEFAULT_MODEL})")
    parser.add_argument("--sem-cache", type=Path, default=None,
                        help="Path lưu/đọc cache embedding numpy (.npy). "
                             "VD: --sem-cache /tmp/sem_emb.npy")
    parser.add_argument("--verbose", action="store_true",
                        help="In rank từng query khi chạy")
    parser.add_argument("--out", type=Path, default=OUT_PATH,
                        help="File JSON lưu kết quả chi tiết")
    args = parser.parse_args()

    k_values  = sorted(set(args.k))
    max_k     = max(k_values)
    top_k_ret = max(args.top_k, max_k)

    if not args.queries.exists():
        print(f"[ERR] Không tìm thấy: {args.queries}")
        sys.exit(1)

    with open(args.queries, encoding="utf-8") as f:
        queries: list[dict] = json.load(f)

    filter_qs = [q for q in queries if q["query_type"] == "filter"]
    intent_qs = [q for q in queries if q["query_type"] == "intent"]
    print(f"\n{'─'*60}")
    print(f"  Queries : {len(queries)} tổng  "
          f"({len(filter_qs)} filter + {len(intent_qs)} intent)")
    print(f"  K values: {k_values}  |  Retrieve top-{top_k_ret} per query")

    # ── 2. Load product corpus ─────────────────────────────────────────────────
    print(f"\n[1/3] Đọc corpus từ {args.meta.name} …")
    meta = pd.read_csv(
        args.meta,
        usecols=["parent_asin", "title", "main_category", "categories",
                 "features", "description", "store"],
        dtype={"parent_asin": str},
    ).drop_duplicates("parent_asin").reset_index(drop=True)
    print(f"    → {len(meta):,} sản phẩm")

    asins = meta["parent_asin"].tolist()
    texts = [build_product_text(row) for _, row in meta.iterrows()]

    print(f"\n[2/3] Xây search indexes …")

    t0 = time.time()
    print("    BM25: building index …", end=" ", flush=True)
    bm25 = BM25Index(texts)
    print(f"xong ({time.time()-t0:.1f}s)")

    semantic = None
    if not args.no_semantic:
        t0 = time.time()
        semantic = SemanticIndex(texts, model_name=args.sem_model,
                                 cache_path=args.sem_cache)
        print(f"    Semantic: xong ({time.time()-t0:.1f}s)")

    systems = (["BM25"]
               + (["Semantic"]  if semantic else []))
    print(f"    Systems: {systems}")

    print(f"\n[3/3] Đánh giá {len(queries)} queries …\n")

    per_query: list[dict] = []

    for i, q in enumerate(queries, 1):
        qid    = q["id"]
        qtype  = q["query_type"]
        query  = q["query"]
        target = q["target_asin"]

        if args.verbose:
            print(f"  [{i:>3}/{len(queries)}] [{qtype:>6}] {query[:60]}")

        entry: dict = {
            "id":            qid,
            "query_type":    qtype,
            "query":         query,
            "target_asin":   target,
            "product_title": q.get("product_title", ""),
        }

        t0 = time.time()
        ranked_bm25 = [asins[j] for j in bm25.search(query, top_k=top_k_ret)]
        m_bm25 = compute_metrics(ranked_bm25, target, k_values)
        m_bm25["latency_ms"] = round((time.time() - t0) * 1000, 2)
        entry["BM25"] = m_bm25

        if args.verbose:
            r = m_bm25["rank"]
            print(f"       BM25     rank={'None' if r is None else r:<5}  " +
                  "  ".join(f"Hit@{k}={int(m_bm25[f'hit@{k}'])}" for k in k_values) +
                  f"  ({m_bm25['latency_ms']:.0f}ms)")

        if semantic:
            t0 = time.time()
            ranked_sem = [asins[j] for j in semantic.search(query, top_k=top_k_ret)]
            m_sem = compute_metrics(ranked_sem, target, k_values)
            m_sem["latency_ms"] = round((time.time() - t0) * 1000, 2)
            entry["Semantic"] = m_sem

            if args.verbose:
                r = m_sem["rank"]
                print(f"       Semantic rank={'None' if r is None else r:<5}  " +
                      "  ".join(f"Hit@{k}={int(m_sem[f'hit@{k}'])}" for k in k_values) +
                      f"  ({m_sem['latency_ms']:.0f}ms)")

        per_query.append(entry)

    def agg(qs: list[dict], system: str, label: str) -> dict:
        metrics_list = [q[system] for q in qs if system in q]
        return aggregate(metrics_list, f"{system} ({label})", k_values)

    summary_rows: list[dict] = []
    groups = [
        ("All",    per_query),
        ("Filter", [q for q in per_query if q["query_type"] == "filter"]),
        ("Intent", [q for q in per_query if q["query_type"] == "intent"]),
    ]
    for label, qs in groups:
        for sys_name in systems:
            summary_rows.append(agg(qs, sys_name, label))

    print_table(summary_rows, k_values)

    print("Chi tiết theo query type:")
    for label, qs in [("Filter", [q for q in per_query if q["query_type"] == "filter"]),
                      ("Intent", [q for q in per_query if q["query_type"] == "intent"])]:
        for sys_name in systems:
            found    = sum(1 for q in qs if sys_name in q and q[sys_name]["rank"] is not None)
            top5     = sum(1 for q in qs if sys_name in q and q[sys_name].get("hit@5", 0))
            top10    = sum(1 for q in qs if sys_name in q and q[sys_name].get("hit@10", 0))
            n        = len(qs)
            print(f"  [{sys_name:<8}] {label:6}: tìm thấy {found}/{n} "
                  f"(top-{top_k_ret}) | @5={top5} | @10={top10}")

    print("\nLatency trung bình (ms/query):")
    for sys_name in systems:
        lat = np.mean([q[sys_name]["latency_ms"] for q in per_query if sys_name in q])
        print(f"  {sys_name:<10}: {lat:.1f} ms")

    results = {
        "systems":   systems,
        "k_values":  k_values,
        "n_queries": len(per_query),
        "n_filter":  len(filter_qs),
        "n_intent":  len(intent_qs),
        "summary":   summary_rows,
        "per_query": per_query,
    }

    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\nKết quả chi tiết → {args.out}")


if __name__ == "__main__":
    main()
