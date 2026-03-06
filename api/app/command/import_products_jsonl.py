import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

# Allow running as a script: `python app/command/import_products_jsonl.py`
if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.core.database import Base, SessionLocal, engine
from app.models.product import Product


def _to_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return " ".join(parts) if parts else None
    text = str(value).strip()
    return text or None


def _parse_price(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        match = re.search(r"\d+(\.\d+)?", cleaned)
        if match:
            try:
                return float(match.group(0))
            except ValueError:
                return None
    return None


def _pick_image_url(images: Any) -> str | None:
    if not isinstance(images, list):
        return None

    for item in images:
        if isinstance(item, dict):
            for key in ("hi_res", "large", "thumb"):
                image_url = _to_text(item.get(key))
                if image_url:
                    return image_url
    return None


def _extract_brand(record: dict[str, Any]) -> str | None:
    details = record.get("details")
    if isinstance(details, dict):
        for key in ("Brand", "brand", "Manufacturer"):
            brand = _to_text(details.get(key))
            if brand:
                return brand
    return _to_text(record.get("store"))


def _extract_category(record: dict[str, Any]) -> str | None:
    categories = record.get("categories")
    if isinstance(categories, list):
        parts = [str(item).strip() for item in categories if str(item).strip()]
        if parts:
            return " > ".join(parts)
    return _to_text(record.get("category"))


def _extract_external_id(record: dict[str, Any]) -> str | None:
    for key in ("parent_asin", "asin", "external_id", "id"):
        value = _to_text(record.get(key))
        if value:
            return value[:100]
    return None


def _build_product(record: dict[str, Any]) -> Product | None:
    title = _to_text(record.get("title"))
    if not title:
        return None

    return Product(
        external_id=_extract_external_id(record),
        title=title[:500],
        brand=_extract_brand(record),
        description=_to_text(record.get("description")),
        category=_extract_category(record),
        price=_parse_price(record.get("price")),
        image_url=_pick_image_url(record.get("images")),
    )


def _import_jsonl(input_path: Path, batch_size: int, truncate: bool) -> None:
    Base.metadata.create_all(bind=engine)

    inserted = 0
    skipped = 0
    invalid = 0
    duplicate = 0

    session = SessionLocal()
    try:
        if truncate:
            session.query(Product).delete()
            session.commit()

        batch: list[Product] = []

        with input_path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, start=1):
                raw = line.strip()
                if not raw:
                    continue

                try:
                    record = json.loads(raw)
                except json.JSONDecodeError:
                    invalid += 1
                    continue

                if not isinstance(record, dict):
                    invalid += 1
                    continue

                product = _build_product(record)
                if not product:
                    skipped += 1
                    continue

                batch.append(product)
                if len(batch) >= batch_size:
                    i, d = _flush_batch(session, batch)
                    inserted += i
                    duplicate += d
                    batch = []

                if line_no % 5000 == 0:
                    print(
                        f"[line {line_no}] inserted={inserted} duplicate={duplicate} "
                        f"skipped={skipped} invalid={invalid}"
                    )

        if batch:
            i, d = _flush_batch(session, batch)
            inserted += i
            duplicate += d

        print(
            f"Done. inserted={inserted}, duplicate={duplicate}, "
            f"skipped={skipped}, invalid={invalid}"
        )
    finally:
        session.close()


def _flush_batch(session: Session, batch: list[Product]) -> tuple[int, int]:
    try:
        session.add_all(batch)
        session.commit()
        return len(batch), 0
    except IntegrityError:
        session.rollback()

    inserted = 0
    duplicate = 0
    for item in batch:
        try:
            session.add(item)
            session.commit()
            inserted += 1
        except IntegrityError:
            session.rollback()
            duplicate += 1
    return inserted, duplicate


def main() -> None:
    parser = argparse.ArgumentParser(description="Import products from JSONL into database.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to JSONL file. Example: ../data_format/meta_Cell_Phones_and_Accessories_65k_cleaned.jsonl",
    )
    parser.add_argument("--batch-size", type=int, default=500, help="Batch insert size.")
    parser.add_argument(
        "--truncate",
        action="store_true",
        help="Delete all current products before importing.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    if not input_path.is_file():
        raise ValueError(f"Input path is not a file: {input_path}")
    if args.batch_size <= 0:
        raise ValueError("--batch-size must be > 0")

    _import_jsonl(input_path=input_path, batch_size=args.batch_size, truncate=args.truncate)


if __name__ == "__main__":
    main()
