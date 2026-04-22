from __future__ import annotations

import argparse
import time
from pathlib import Path

import numpy as np
import pandas as pd


NEO4J_URI = "bolt://localhost:7687"
NEO4J_USER = "neo4j"
NEO4J_PASS = "1234567890"
NEO4J_DB = "recphones"

DATA_DIR = Path(__file__).parent.parent / "data"
EMBED_MODEL = "intfloat/multilingual-e5-small"
VECTOR_DIM = 384
INDEX_NAME = "product_text_index"
MAX_CHARS = 1000


def build_product_text(row: pd.Series) -> str:
    parts = []

    title = str(row.get("title") or "").strip()
    if title:
        parts.append(title)
        parts.append(title)

    if row.get("main_category"):
        parts.append(str(row["main_category"]))

    if row.get("categories"):
        parts.append(str(row["categories"]))

    if row.get("description"):
        parts.append(str(row["description"]))

    if row.get("features"):
        parts.append(str(row["features"]))

    if row.get("details"):
        parts.append(str(row["details"]))

    try:
        price = float(row.get("price", float("nan")))
        import math
        if not math.isnan(price):
            parts.append(f"price {price:.2f} USD")
    except (TypeError, ValueError):
        pass

    if row.get("average_rating"):
        parts.append(f"rating {row['average_rating']}")

    text = " | ".join(filter(None, parts))
    return text[:MAX_CHARS]


def _get_driver():
    from neo4j import GraphDatabase
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASS))


def _create_vector_index(driver, recreate: bool) -> None:
    with driver.session(database=NEO4J_DB) as session:
        if recreate:
            session.run(f"DROP INDEX {INDEX_NAME} IF EXISTS")
            print(f"  Đã xoá index cũ: {INDEX_NAME}")

        session.run(f"""
            CREATE VECTOR INDEX {INDEX_NAME} IF NOT EXISTS
            FOR (p:Product)
            ON (p.text_embedding)
            OPTIONS {{
                indexConfig: {{
                    `vector.dimensions`: {VECTOR_DIM},
                    `vector.similarity_function`: 'cosine'
                }}
            }}
        """)
        print(f"  Vector index '{INDEX_NAME}' đã sẵn sàng.")


def _write_embeddings_batch(session, batch: list[tuple[str, list[float]]]) -> None:
    session.run(
        """
        UNWIND $rows AS row
        MATCH (p:Product {asin: row.asin})
        SET p.text_embedding = row.emb
        """,
        rows=[{"asin": asin, "emb": emb} for asin, emb in batch],
    )


def build(batch_size: int, recreate: bool, skip_existing: bool) -> None:
    print(f"Loading embed model: {EMBED_MODEL} ...")
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(EMBED_MODEL)
    print(f"  Model loaded. Dim={VECTOR_DIM}\n")

    print("Loading meta_filtered.csv ...")
    meta = pd.read_csv(
        DATA_DIR / "meta_filtered.csv",
        dtype={"parent_asin": str},
    ).drop_duplicates("parent_asin").set_index("parent_asin")
    print(f"  {len(meta)} sản phẩm trong meta\n")

    driver = _get_driver()

    print("Setting up vector index ...")
    _create_vector_index(driver, recreate)
    print()

    print("Fetching product ASINs từ Neo4j ...")
    with driver.session(database=NEO4J_DB) as session:
        rows = session.run(
            "MATCH (p:Product) RETURN p.asin AS asin, "
            "(p.text_embedding IS NOT NULL) AS has_emb"
        ).data()

    all_asins = [r["asin"] for r in rows]
    has_emb = {r["asin"] for r in rows if r["has_emb"]}
    print(f"  Tổng Product nodes: {len(all_asins)}")
    print(f"  Đã có embedding:    {len(has_emb)}")

    if skip_existing:
        todo = [a for a in all_asins if a not in has_emb]
        print(f"  Cần embed:          {len(todo)}\n")
    else:
        todo = all_asins
        print(f"  Embed lại tất cả: {len(todo)}\n")

    if not todo:
        print("Không có gì cần embed. Xong.")
        driver.close()
        return

    t0 = time.time()
    n_done = 0
    n_skip = 0

    with driver.session(database=NEO4J_DB) as session:
        batch_buf: list[tuple[str, list[float]]] = []

        for asin in todo:
            if asin not in meta.index:
                n_skip += 1
                continue

            text = "passage: " + build_product_text(meta.loc[asin])
            emb = model.encode(text, normalize_embeddings=True).tolist()
            batch_buf.append((asin, emb))

            if len(batch_buf) >= batch_size:
                _write_embeddings_batch(session, batch_buf)
                n_done += len(batch_buf)
                elapsed = time.time() - t0
                print(f"  [{n_done}/{len(todo)}] {elapsed:.1f}s  "
                      f"({n_done/elapsed:.1f} products/s)")
                batch_buf = []

        if batch_buf:
            _write_embeddings_batch(session, batch_buf)
            n_done += len(batch_buf)

    elapsed = time.time() - t0
    print(f"\nDone. {n_done} embeddings đã ghi ({elapsed:.1f}s).")
    if n_skip:
        print(f"Bỏ qua {n_skip} ASINs không có trong meta.")

    driver.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Build Neo4j vector index cho Product nodes")
    p.add_argument("--batch_size", type=int, default=32, help="Batch size khi ghi Neo4j")
    p.add_argument("--recreate", action="store_true", help="Xoá và tạo lại index")
    p.add_argument("--no_skip", action="store_true", help="Embed lại cả nodes đã có embedding")
    args = p.parse_args()
    build(
        batch_size=args.batch_size,
        recreate=args.recreate,
        skip_existing=not args.no_skip,
    )
