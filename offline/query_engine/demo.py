#!/usr/bin/env python3
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from offline.query_engine.graph_search import test_connection, count_nodes
from offline.search_pipeline          import search_ranked

_DEMO_USER = "AHATA6X6MYTC3VNBFJ3WIYVK257A"

SAMPLE_QUESTIONS = [
    "Tìm 5 điện thoại rẻ nhất có giá niêm yết",
    "Điện thoại Samsung hỗ trợ 5G",
    "Điện thoại hỗ trợ cả AT&T và T-Mobile giá dưới 200 đô",
    "Điện thoại RAM 8GB storage 256GB",
    "Điện thoại được đánh giá cao nhất",
]

SEP = "─" * 60


def run_query(question: str) -> None:
    print(f"\n{'='*60}")
    print(f"Câu hỏi : {question}")
    print(SEP)
    try:
        results = search_ranked(question, user_id=_DEMO_USER)
        print(f"Kết quả : {len(results)} sản phẩm")
        for i, pid in enumerate(results[:10], 1):
            print(f"  {i:2}. {pid}")
        if len(results) > 10:
            print(f"  ... (còn {len(results) - 10} nữa)")
    except Exception as e:
        print(f"[LỖI] {e}")
    print(f"{'='*60}\n")


def run_batch() -> None:
    print(f"\nBatch mode — {len(SAMPLE_QUESTIONS)} câu hỏi\n")
    for i, q in enumerate(SAMPLE_QUESTIONS, 1):
        print(f"[{i}/{len(SAMPLE_QUESTIONS)}] {q}")
        run_query(q)


def run_interactive() -> None:
    print("\n" + "="*60)
    print("  Smartphone Search — NL → KG Pipeline")
    print("  'exit' để thoát | 'batch' để chạy câu mẫu")
    print("="*60)

    if not test_connection():
        print("\n[LỖI] Không kết nối được Neo4j.")
        sys.exit(1)

    stats = count_nodes()
    print(f"\nKết nối OK — {sum(stats.values()):,} nodes")

    while True:
        try:
            q = input("\nHỏi> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nThoát.")
            break
        if not q:
            continue
        if q.lower() in ("exit", "quit", "thoát"):
            break
        if q.lower() == "batch":
            run_batch()
        else:
            run_query(q)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("question", nargs="?")
    p.add_argument("--batch", action="store_true")
    args = p.parse_args()

    if args.batch:
        run_batch()
    elif args.question:
        run_query(args.question)
    else:
        run_interactive()
