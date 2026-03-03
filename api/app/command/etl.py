"""
etl.py – Nạp dữ liệu từ offline/data/*.csv vào PostgreSQL.

Chạy từ thư mục api/:
    python -m app.command.etl

Thứ tự:
  1. products   (meta_filtered.csv)   → bảng products
  2. users      (reviews_filtered.csv) → bảng users  (unique user_id)
  3. interactions (reviews_filtered.csv) → bảng interactions
"""

from __future__ import annotations

import ast
import csv
import sys
from pathlib import Path

# Thêm api/ vào sys.path khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "api"))

from sqlalchemy.orm import Session

from app.core.database import SessionLocal, engine, Base
from app.models.product import Product
from app.models.user import User
from app.models.interaction import Interaction

DATA_DIR = Path(__file__).resolve().parents[3] / "offline" / "data"
META_CSV = DATA_DIR / "meta_filtered.csv"
REVIEWS_CSV = DATA_DIR / "reviews_filtered.csv"

BATCH = 500  # rows per commit


# ── helpers ───────────────────────────────────────────────────────────────────

def _safe_eval(value: str) -> object:
    """Parse Python literal string safely; return None on failure."""
    try:
        return ast.literal_eval(value)
    except Exception:
        return None


def _first_image_url(images_str: str) -> str | None:
    """Extract first large image URL from the images column."""
    images = _safe_eval(images_str)
    if not isinstance(images, list):
        return None
    for img in images:
        if isinstance(img, dict):
            url = img.get("large") or img.get("hi_res") or img.get("thumb")
            if url:
                return url
    return None


def _first_text(value_str: str) -> str | None:
    """Return first element if list, else the raw string (truncated to 2000 chars)."""
    parsed = _safe_eval(value_str)
    if isinstance(parsed, list) and parsed:
        return str(parsed[0])[:2000]
    if value_str:
        return value_str[:2000]
    return None


def _float_or_none(value: str) -> float | None:
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


# ── step 1: products ──────────────────────────────────────────────────────────

def load_products(db: Session) -> dict[str, int]:
    """Load meta_filtered.csv → products table.

    Returns mapping {parent_asin: product.id}.
    """
    print(f"[ETL] Loading products from {META_CSV} ...")
    if not META_CSV.exists():
        print(f"  ERROR: {META_CSV} not found")
        return {}

    asin_to_id: dict[str, int] = {}
    batch: list[Product] = []
    total = 0
    skipped = 0

    with META_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asin = row.get("parent_asin", "").strip()
            title = row.get("title", "").strip()
            if not asin or not title:
                skipped += 1
                continue

            # Skip if already in DB (re-run safe)
            existing = db.query(Product.id).filter(Product.external_id == asin).scalar()
            if existing:
                asin_to_id[asin] = existing
                skipped += 1
                continue

            product = Product(
                external_id=asin,
                title=title[:500],
                brand=(row.get("store") or "").strip()[:255] or None,
                description=_first_text(row.get("description", "")),
                category=(row.get("main_category") or "").strip()[:255] or None,
                price=_float_or_none(row.get("price", "")),
                image_url=_first_image_url(row.get("images", "")),
            )
            batch.append(product)
            total += 1

            if len(batch) >= BATCH:
                db.bulk_save_objects(batch)
                db.flush()
                # Collect IDs
                for p in batch:
                    if p.external_id:
                        pid = db.query(Product.id).filter(Product.external_id == p.external_id).scalar()
                        if pid:
                            asin_to_id[p.external_id] = pid
                db.commit()
                print(f"  ... {total} products inserted")
                batch = []

    if batch:
        db.bulk_save_objects(batch)
        db.flush()
        for p in batch:
            if p.external_id:
                pid = db.query(Product.id).filter(Product.external_id == p.external_id).scalar()
                if pid:
                    asin_to_id[p.external_id] = pid
        db.commit()

    # Also fetch already-existing products
    for row_asin, row_id in db.query(Product.external_id, Product.id).all():
        if row_asin:
            asin_to_id[row_asin] = row_id

    print(f"[ETL] Products done: {total} inserted, {skipped} skipped. Total in map: {len(asin_to_id)}")
    return asin_to_id


# ── step 2 + 3: users & interactions ─────────────────────────────────────────

def load_users_and_interactions(db: Session, asin_to_id: dict[str, int]) -> None:
    """Load reviews_filtered.csv → users + interactions."""
    print(f"[ETL] Loading users & interactions from {REVIEWS_CSV} ...")
    if not REVIEWS_CSV.exists():
        print(f"  ERROR: {REVIEWS_CSV} not found")
        return

    # Cache user external_id → internal id
    uid_map: dict[str, int] = {}
    for u in db.query(User.external_user_id, User.id).filter(User.external_user_id.isnot(None)).all():
        uid_map[u.external_user_id] = u.id

    interactions_batch: list[Interaction] = []
    total_users = 0
    total_interactions = 0
    skipped = 0

    with REVIEWS_CSV.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ext_uid = row.get("user_id", "").strip()
            asin = row.get("parent_asin", "").strip()
            if not ext_uid or not asin:
                skipped += 1
                continue

            product_id = asin_to_id.get(asin)
            if not product_id:
                skipped += 1
                continue

            # Upsert user
            if ext_uid not in uid_map:
                user = User(
                    external_user_id=ext_uid,
                    email=None,
                    password_hash="ETL_DEMO_NO_PASSWORD",
                    full_name=ext_uid[:40],
                    is_active=True,
                )
                db.add(user)
                db.flush()
                uid_map[ext_uid] = user.id
                total_users += 1

            user_id = uid_map[ext_uid]

            interactions_batch.append(
                Interaction(
                    user_id=user_id,
                    product_id=product_id,
                    action_type="review",
                )
            )
            total_interactions += 1

            if len(interactions_batch) >= BATCH:
                db.bulk_save_objects(interactions_batch)
                db.commit()
                print(f"  ... {total_users} users, {total_interactions} interactions")
                interactions_batch = []

    if interactions_batch:
        db.bulk_save_objects(interactions_batch)
        db.commit()

    print(f"[ETL] Done: {total_users} users, {total_interactions} interactions, {skipped} skipped")


# ── main ──────────────────────────────────────────────────────────────────────

def _migrate(db: Session) -> None:
    """Thêm các cột mới nếu chưa tồn tại (ALTER TABLE safe)."""
    migrations = [
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS external_user_id VARCHAR(100) UNIQUE",
        "ALTER TABLE users ALTER COLUMN email DROP NOT NULL",
        "CREATE INDEX IF NOT EXISTS ix_users_external_user_id ON users (external_user_id)",
    ]
    for sql in migrations:
        try:
            db.execute(__import__("sqlalchemy").text(sql))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"  [migrate] skip: {e}")


def run():
    Base.metadata.create_all(bind=engine)
    db: Session = SessionLocal()
    try:
        _migrate(db)
        asin_to_id = load_products(db)
        load_users_and_interactions(db, asin_to_id)
        print("[ETL] All done!")
    finally:
        db.close()


if __name__ == "__main__":
    run()
