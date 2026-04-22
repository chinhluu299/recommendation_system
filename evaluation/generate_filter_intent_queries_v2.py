"""
generate_filter_intent_queries_v2.py
──────────────────────────────────────
Ver2: Queries đơn giản hơn, tối đa 2-3 điều kiện, tập trung vào
      spec types mà pipeline có thể extract tốt.

Thay đổi so với ver1:
  - Filter queries: tối đa 3 điều kiện, ưu tiên brand > network > storage > RAM
  - Loại bỏ khỏi filter: battery, display_type, color, dual_sim, specials
    (pipeline không có key spec tương ứng → LLM bỏ qua → gây nhiễu)
  - Filter pool: valid_spec_count ≥ 1 + có brand HOẶC network
    (thay vì valid_spec_count ≥ 3 của ver1)
  - Brand lấy từ cột `store` (có sẵn trong data, không cần regex phức tạp)
  - Intent queries: đơn giản 1-2 nhu cầu, thêm brand-based và price-based intents
  - Thêm price-range trong một số filter queries (pipeline hỗ trợ price_min/max)

Pipeline intent schema hỗ trợ (confirmed từ search_pipeline.py):
  brand, technology (5G/4G LTE), carrier,
  price_min, price_max, rating_min,
  specs: ram (gb), memory_storage_capacity (gb),
         standing_screen_display_size (inch),
         other_camera_features (mp), processor (ghz)
  NOTE: battery (mAh), display type, color KHÔNG có key → không đưa vào filter query

Chạy:
    python3 generate_filter_intent_queries_v2.py
    python3 generate_filter_intent_queries_v2.py --seed 123
    python3 generate_filter_intent_queries_v2.py --out custom_output.json
"""

from __future__ import annotations

import ast
import json
import random
import re
import argparse
from pathlib import Path

import pandas as pd

# ── Paths ──────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).resolve().parent.parent
DATA_DIR  = ROOT / "offline" / "data"
META_PATH = DATA_DIR / "meta_filtered.csv"
OUT_PATH  = Path(__file__).resolve().parent / "filter_intent_queries_v2.json"

# ── Config ─────────────────────────────────────────────────────────────────────
N_FILTER = 50
N_INTENT = 50

# Từ khóa trong TITLE xác định đây là điện thoại thực sự (giữ nguyên từ ver1)
PHONE_TITLE_PATTERNS = re.compile(
    r'\b(smartphone|cell phone|android phone|mobile phone'
    r'|iphone\s*\d|galaxy\s+[a-z]\d|pixel\s*\d|moto\s+[a-z]'
    r'|redmi|poco\s+[a-z]|oneplus\s*\d|unlocked\s+phone'
    r'|gsm\s+phone|lte\s+phone|5g\s+phone|4g\s+phone'
    r'|flip\s+phone|prepaid\s+phone|feature\s+phone'
    r'|unlocked\s+smartphone|factory\s+unlocked'
    r')',
    re.IGNORECASE
)

EXCLUDE_TITLE_PATTERNS = re.compile(
    r'\b(screen\s*protector|tempered\s*glass|privacy\s*screen'
    r'|phone\s*case|phone\s*cover|protective\s*case'
    r'|charging\s*cable|usb\s*cable|data\s*cable|aux\s*cable'
    r'|sim\s*card|sim\s*tray|sim\s*adapter'
    r'|power\s*bank|wall\s*charger|car\s*charger|wireless\s*charger'
    r'|earphone|headphone|earbud|headset|earpiece'
    r'|phone\s*holder|car\s*mount|phone\s*stand'
    r'|stylus\s*pen|replacement\s*part|repair\s*part'
    r'|home\s*button|back\s*cover\s*replacement'
    r'|prepaid\s*minutes|prepaid\s*plan|phone\s*plan'
    r'|unlock\s*service|unlocking\s*service'
    r'|screen\s*repair|battery\s*replacement'
    r'|bling|glitter|rhinestone|decorat'
    r'|keyboard\s*for|mount\s*for|stand\s*for|case\s*for'
    r'|pcs\s+\w+\s+accessories|accessories\s+set'
    r')',
    re.IGNORECASE
)

# ── Brand mapping (store → display name) ──────────────────────────────────────
# Key: lowercase substring to match in store field
# Value: display name dùng trong query
BRAND_MAP: dict[str, str] = {
    "apple":      "iPhone",
    "samsung":    "Samsung",
    "motorola":   "Motorola",
    "google":     "Google Pixel",
    "lg":         "LG",
    "nokia":      "Nokia",
    "sony":       "Sony",
    "oneplus":    "OnePlus",
    "xiaomi":     "Xiaomi",
    "huawei":     "Huawei",
    "zte":        "ZTE",
    "alcatel":    "Alcatel",
    "tcl":        "TCL",
    "blu":        "BLU",
    "blackberry": "BlackBerry",
    "kyocera":    "Kyocera",
    "cat phones": "CAT",
    "doro":       "Doro",
    "coolpad":    "Coolpad",
}

# Các brand có thể query bằng tên đặc trưng trong intent
BRAND_INTENT_QUERIES: dict[str, list[str]] = {
    "iPhone":       ["iPhone pin tốt chụp ảnh đẹp",
                     "iPhone màn hình sắc nét hiệu năng cao",
                     "Apple iPhone bộ nhớ lớn dùng lâu dài"],
    "Samsung":      ["Samsung điện thoại màn hình đẹp pin trâu",
                     "Samsung 5G giá tốt hiệu năng ổn",
                     "Samsung Android bộ nhớ lớn camera tốt"],
    "Motorola":     ["Motorola điện thoại bền pin lâu giá rẻ",
                     "Motorola 4G đủ dùng hàng ngày",
                     "Motorola mỏng nhẹ thiết kế đẹp"],
    "Google Pixel": ["Google Pixel camera tốt nhất Android cập nhật nhanh",
                     "Pixel điện thoại chụp ảnh đẹp phần mềm sạch",
                     "Google Pixel 5G hiệu năng tốt"],
    "OnePlus":      ["OnePlus sạc nhanh màn hình mượt hiệu năng cao",
                     "OnePlus 5G mượt mà không lag"],
    "Nokia":        ["Nokia điện thoại bền cập nhật Android lâu dài",
                     "Nokia giá rẻ pin tốt đơn giản dễ dùng"],
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def safe_list(val) -> list[str]:
    if not isinstance(val, str) or not val.strip():
        return []
    try:
        r = ast.literal_eval(val)
        return [str(x).strip() for x in r if str(x).strip()] if isinstance(r, list) else []
    except Exception:
        return []


def is_real_phone(title: str, features: list[str]) -> bool:
    if EXCLUDE_TITLE_PATTERNS.search(title):
        return False
    feat_text = " ".join(features[:3])
    combined = title + " " + feat_text
    return bool(PHONE_TITLE_PATTERNS.search(combined))


def extract_brand(store: str) -> str | None:
    """Trích xuất tên brand từ store field."""
    if not store or not isinstance(store, str):
        return None
    store_lower = store.strip().lower()
    for key, display in BRAND_MAP.items():
        if key in store_lower:
            return display
    return None


def extract_specs_v2(features: list[str], title: str) -> dict:
    """
    Ver2: Chỉ trích xuất specs mà pipeline intent schema hỗ trợ trực tiếp.
    Loại bỏ: battery, display_type, color, dual_sim, specials.
    """
    blob = " ".join(features) + " " + title
    s: dict = {}

    # Storage (8/16/32/64/128/256/512 GB, không phải RAM)
    m = re.search(r'\b(512|256|128|64|32|16|8)\s*GB\b(?!\s*RAM|\s*of\s*RAM)', blob)
    s["storage"] = m.group(0).replace(" ", "") if m else None

    # RAM (1–16 GB RAM)
    m = re.search(r'\b(\d{1,2})\s*GB\s*RAM\b|RAM[:\s]+(\d{1,2})\s*GB', blob, re.I)
    if m:
        val = m.group(1) or m.group(2)
        s["ram"] = f"{val}GB" if val and 1 <= int(val) <= 16 else None
    else:
        s["ram"] = None

    # Network (chỉ giữ loại pipeline extract được)
    if re.search(r'\b5G\b', blob):
        s["network"] = "5G"
    elif re.search(r'\b4G\s*LTE\b', blob):
        s["network"] = "4G LTE"
    elif re.search(r'\b4G\b', blob):
        s["network"] = "4G"
    elif re.search(r'\b3G\b', blob):
        s["network"] = "3G"
    else:
        s["network"] = None

    # Screen size (3.0" – 7.9")
    m = re.search(r'\b([3-7]\.\d)\s*["\']?\s*(?:inch(?:es?)?|in\b)', blob, re.I)
    if not m:
        m = re.search(r'([3-7]\.\d)\s*["″]\s*(?:FHD|HD|OLED|AMOLED|IPS|QHD|display|screen)', blob, re.I)
    s["screen"] = f'{m.group(1)} inch' if m else None

    # Đếm specs hợp lệ (chỉ 3 spec chính: storage, network, ram)
    s["valid_spec_count"] = sum(1 for k in ("storage", "network", "ram") if s.get(k))

    return s


# ── Build FILTER query (ver2) ──────────────────────────────────────────────────

def build_filter_query_v2(brand: str | None, specs: dict, price: float | None,
                           rng: random.Random) -> str:
    """
    Tạo filter query tối đa 3 điều kiện.
    Ưu tiên: brand > network > storage > RAM
    Thêm price range nếu còn chỗ và price available.
    """
    parts: list[str] = []

    # 1. Brand (ưu tiên cao nhất)
    if brand:
        parts.append(brand)

    # 2. Network
    if specs.get("network") and len(parts) < 3:
        parts.append(specs["network"])

    # 3. Storage
    if specs.get("storage") and len(parts) < 3:
        parts.append(specs["storage"])

    # 4. RAM (nếu chưa đủ 3 và chưa có brand thì thêm RAM)
    if specs.get("ram") and len(parts) < 3 and (not brand or len(parts) < 3):
        parts.append(f"RAM {specs['ram']}")

    # 5. Price range (nếu chỉ có 1 điều kiện và có giá)
    if len(parts) == 1 and price and price > 0:
        if price < 150:
            parts.append("dưới $150")
        elif price < 300:
            parts.append("dưới $300")
        elif price < 500:
            parts.append("dưới $500")

    # Chọn tối đa 3 phần
    selected = parts[:3]

    if len(selected) >= 2:
        return "điện thoại " + " ".join(selected)

    # Fallback khi chỉ có 1 điều kiện
    if brand:
        return f"điện thoại {brand}"
    if specs.get("network"):
        return f"điện thoại {specs['network']} Android mở khóa"
    return "điện thoại Android mở khóa unlocked"


# ── Build INTENT query (ver2) ──────────────────────────────────────────────────

# Simplified rules: ít pattern hơn, query ngắn gọn hơn
INTENT_RULES_V2: list[tuple[re.Pattern, list[str]]] = [
    # Gaming
    (re.compile(r'snapdragon\s*8|gaming\s*phone|game\s*phone|120Hz|144Hz|adreno\s*7', re.I),
     ["điện thoại chơi game mượt pin trâu",
      "smartphone gaming hiệu năng cao màn hình refresh cao",
      "điện thoại chơi game không lag màn hình lớn"]),

    # Pro camera
    (re.compile(r'night\s*mode|optical\s*zoom|periscope|108\s*MP|50\s*MP', re.I),
     ["điện thoại camera đẹp zoom xa chụp ban đêm tốt",
      "smartphone camera chuyên nghiệp quay video 4K",
      "điện thoại chụp ảnh đẹp thay máy ảnh compact"]),

    # Big battery
    (re.compile(r'\b(600[0-9]|[789]\d{3}|[12]\d{4})\s*mAh\b', re.I),
     ["điện thoại pin trâu dùng cả ngày không lo hết pin",
      "smartphone pin lớn cho người dùng nhiều",
      "điện thoại pin khủng đi dã ngoại xa nhà"]),

    # Budget
    (re.compile(r'android\s*go|entry.?level|budget|affordable', re.I),
     ["điện thoại giá rẻ đủ dùng Facebook Zalo hàng ngày",
      "smartphone giá phải chăng cho sinh viên",
      "điện thoại cơ bản 4G giá thấp"]),

    # Senior / Elderly
    (re.compile(r'senior|elder|big\s*button|large\s*button|easy.?use.*senior', re.I),
     ["điện thoại cho người già chữ to dễ dùng",
      "smartphone đơn giản âm lượng lớn cho người cao tuổi"]),

    # Rugged / Waterproof
    (re.compile(r'IP6[78]|rugged|military\s*grade|waterproof|shock.?proof', re.I),
     ["điện thoại chống nước IP68 bền cho công trường",
      "smartphone rugged không sợ mưa bụi va đập",
      "điện thoại bền nhất cho người làm ngoài trời"]),

    # Fast charging
    (re.compile(r'\b(65|67|80|100|120|150)\s*W|\bsuperVOOC\b|\bflash\s*charge', re.I),
     ["điện thoại sạc nhanh đầy pin trong 30 phút",
      "smartphone sạc siêu nhanh không cần cắm sạc cả đêm"]),

    # AMOLED / Display
    (re.compile(r'AMOLED|OLED|90Hz|high\s*refresh', re.I),
     ["điện thoại màn hình AMOLED sắc nét xem phim đẹp",
      "smartphone màn hình mượt 90Hz+ scroll mạng xã hội"]),

    # Compact
    (re.compile(r'compact|mini\s+phone|small\s+phone|\b4\.[0-5]"', re.I),
     ["điện thoại nhỏ gọn một tay cầm bỏ túi tiện",
      "smartphone size nhỏ nhẹ cho nữ"]),

    # Big screen
    (re.compile(r'\b6\.[5-9]"|\b7\.\d"|\bPro Max\b|\bXL\b', re.I),
     ["điện thoại màn hình lớn 6.5 inch xem phim đọc sách",
      "smartphone màn hình to đa nhiệm chia đôi màn hình"]),

    # 5G
    (re.compile(r'\b5G\b'),
     ["điện thoại 5G kết nối nhanh tầm trung",
      "smartphone 5G mở khóa dùng được nhiều mạng",
      "điện thoại 5G pin tốt giá hợp lý"]),

    # Flagship
    (re.compile(r'snapdragon\s*(8\s*gen|888|865)|dimensity\s*9\d{3}|A16\s*bionic', re.I),
     ["điện thoại cao cấp mạnh nhất camera đỉnh",
      "smartphone flagship không lag mọi tác vụ"]),

    # Renewed
    (re.compile(r'renewed|refurbished|certified\s*refurb', re.I),
     ["điện thoại tân trang giá rẻ chất lượng đảm bảo",
      "smartphone đã qua sử dụng còn mới giá tốt"]),
]

INTENT_FALLBACK_V2 = [
    "điện thoại Android tầm trung pin tốt camera ổn",
    "smartphone 4G mở khóa dùng tốt hàng ngày",
    "điện thoại đa nhiệm RAM đủ lớn không giật lag",
    "smartphone giá tốt camera đủ đẹp pin cả ngày",
    "điện thoại dùng Zalo Facebook TikTok mượt mà",
    "smartphone bền bỉ cập nhật phần mềm lâu dài",
    "điện thoại mỏng nhẹ thiết kế đẹp màn hình sắc",
    "smartphone cân bằng giá hiệu năng đáng mua",
]


def build_intent_query_v2(features: list[str], title: str, specs: dict,
                           brand: str | None, price: float | None,
                           rng: random.Random) -> str:
    """
    Tạo intent query đơn giản 1-2 nhu cầu.
    Ưu tiên brand-specific query nếu brand nổi tiếng, sau đó theo feature pattern.
    """
    blob = " ".join(features) + " " + title

    # 30% chance: dùng brand-specific intent nếu brand nổi tiếng
    if brand and brand in BRAND_INTENT_QUERIES and rng.random() < 0.30:
        return rng.choice(BRAND_INTENT_QUERIES[brand])

    # Thêm price-based intent nếu price rõ ràng
    if price and price > 0 and rng.random() < 0.20:
        if price < 100:
            return rng.choice([
                f"điện thoại giá rẻ dưới $100 đủ dùng 4G",
                f"smartphone giá thấp nhất đủ dùng hàng ngày",
            ])
        elif price < 200:
            return rng.choice([
                f"điện thoại tầm $150 pin tốt camera ổn",
                f"smartphone giá rẻ $100-200 đáng mua",
            ])
        elif price < 400:
            return rng.choice([
                f"điện thoại tầm trung $200-400 camera tốt",
                f"smartphone $300 cân bằng hiệu năng giá cả",
            ])

    # Pattern matching
    for pattern, options in INTENT_RULES_V2:
        if pattern.search(blob):
            return rng.choice(options)

    # Fallback dựa trên specs
    if specs.get("network") == "5G":
        return rng.choice(["điện thoại 5G pin tốt giá hợp lý",
                           "smartphone 5G mở khóa dùng nhiều mạng"])

    return rng.choice(INTENT_FALLBACK_V2)


# ── Stratified sampling ────────────────────────────────────────────────────────

def stratified_sample(pool: pd.DataFrame, n: int, rng: random.Random,
                       exclude: set[str] | None = None) -> pd.DataFrame:
    """Sample đa dạng theo store/brand."""
    if exclude:
        pool = pool[~pool["parent_asin"].isin(exclude)]
    if len(pool) <= n:
        return pool.reset_index(drop=True)

    pool = pool.sort_values("valid_spec_count", ascending=False)
    stores = pool["store"].fillna("Unknown").unique().tolist()
    rng.shuffle(stores)

    selected: list[str] = []
    per_store = max(1, n // max(len(stores), 1))

    for store in stores:
        sub = pool[pool["store"].fillna("Unknown") == store]
        take = min(per_store, len(sub))
        chosen = list(sub["parent_asin"].values[:take])
        selected.extend(chosen)
        if len(selected) >= n:
            break

    if len(selected) < n:
        remaining = pool[~pool["parent_asin"].isin(selected)]
        extra = list(remaining["parent_asin"].values[:n - len(selected)])
        selected.extend(extra)

    result = pool[pool["parent_asin"].isin(selected[:n])]
    return result.reset_index(drop=True)


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate simplified filter/intent queries for pipeline evaluation (ver2)"
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    rng = random.Random(args.seed)

    # ── 1. Load data ───────────────────────────────────────────────────────────
    print(f"[1/4] Đọc dữ liệu từ {META_PATH} …")
    df = pd.read_csv(
        META_PATH,
        usecols=["parent_asin", "title", "main_category", "features",
                 "details", "store", "price", "average_rating", "rating_number"],
    ).dropna(subset=["parent_asin", "title"])
    print(f"    → {len(df):,} sản phẩm tổng")

    # ── 2. Filter chỉ giữ điện thoại thực sự ──────────────────────────────────
    print("\n[2/4] Lọc điện thoại hợp lệ …")
    df["features_list"] = df["features"].apply(safe_list)

    mask = df.apply(
        lambda r: is_real_phone(str(r["title"]), r["features_list"]),
        axis=1
    )
    phone_df = df[mask].copy().reset_index(drop=True)
    print(f"    → {len(phone_df):,} điện thoại hợp lệ")

    # Trích xuất specs và brand
    phone_df["specs"]  = phone_df.apply(
        lambda r: extract_specs_v2(r["features_list"], str(r["title"])), axis=1
    )
    phone_df["brand"]  = phone_df["store"].apply(
        lambda s: extract_brand(str(s)) if pd.notna(s) else None
    )
    phone_df["valid_spec_count"] = phone_df["specs"].apply(
        lambda s: s["valid_spec_count"]
    )

    # ── 3. Chọn sản phẩm cho filter queries ───────────────────────────────────
    print("\n[3/4] Chọn sản phẩm và sinh queries …")

    # Ver2: filter pool = có ít nhất 1 spec + có brand HOẶC network
    def qualifies_for_filter(row) -> bool:
        has_brand   = bool(row["brand"])
        has_network = bool(row["specs"].get("network"))
        return row["valid_spec_count"] >= 1 and (has_brand or has_network)

    filter_pool = phone_df[phone_df.apply(qualifies_for_filter, axis=1)].copy()
    print(f"    Filter pool (≥1 spec + brand/network): {len(filter_pool):,} sản phẩm")

    filter_df = stratified_sample(filter_pool, N_FILTER, rng)
    used_asins = set(filter_df["parent_asin"])

    # Intent: từ toàn bộ phone pool
    intent_df = stratified_sample(phone_df, N_INTENT, rng, exclude=used_asins)
    print(f"    Filter set: {len(filter_df)} | Intent set: {len(intent_df)}")

    # ── 4. Sinh queries ────────────────────────────────────────────────────────
    results: list[dict] = []
    case_id = 1

    # --- FILTER queries ---
    for _, row in filter_df.iterrows():
        specs  = row["specs"]
        brand  = row["brand"]
        price  = float(row["price"]) if pd.notna(row.get("price")) else None
        query  = build_filter_query_v2(brand, specs, price, rng)
        query  = re.sub(r'\s{2,}', ' ', query).strip()

        # extracted_specs: chỉ giữ spec dùng trong filter
        ext_specs: dict = {}
        if brand:
            ext_specs["brand"] = brand
        if specs.get("network"):
            ext_specs["network"] = specs["network"]
        if specs.get("storage"):
            ext_specs["storage"] = specs["storage"]
        if specs.get("ram"):
            ext_specs["ram"] = specs["ram"]

        results.append({
            "id":               case_id,
            "query_type":       "filter",
            "query":            query,
            "target_asin":      str(row["parent_asin"]),
            "product_title":    str(row["title"]),
            "product_brand":    str(row.get("store", "") or ""),
            "product_price":    price,
            "product_rating":   float(row["average_rating"]) if pd.notna(row.get("average_rating")) else None,
            "product_features": row["features_list"][:3],
            "extracted_specs":  ext_specs,
        })
        case_id += 1

    # --- INTENT queries ---
    for _, row in intent_df.iterrows():
        specs  = row["specs"]
        brand  = row["brand"]
        price  = float(row["price"]) if pd.notna(row.get("price")) else None
        query  = build_intent_query_v2(
            row["features_list"], str(row["title"]), specs, brand, price, rng
        )
        query  = re.sub(r'\s{2,}', ' ', query).strip()

        results.append({
            "id":               case_id,
            "query_type":       "intent",
            "query":            query,
            "target_asin":      str(row["parent_asin"]),
            "product_title":    str(row["title"]),
            "product_brand":    str(row.get("store", "") or ""),
            "product_price":    price,
            "product_rating":   float(row["average_rating"]) if pd.notna(row.get("average_rating")) else None,
            "product_features": row["features_list"][:3],
            "extracted_specs":  {k: v for k, v in specs.items()
                                  if v and k != "valid_spec_count" and v is not False},
        })
        case_id += 1

    # ── 5. Lưu file ────────────────────────────────────────────────────────────
    out_path = args.out
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    filter_count = sum(1 for r in results if r["query_type"] == "filter")
    intent_count = sum(1 for r in results if r["query_type"] == "intent")

    print(f"\n[4/4] Đã lưu {len(results)} queries → {out_path}")
    print("\n" + "=" * 65)
    print("TỔNG KẾT")
    print("=" * 65)
    print(f"  Filter queries (keyword)  : {filter_count:>3}")
    print(f"  Intent queries (use-case) : {intent_count:>3}")
    print(f"  Tổng                      : {len(results):>3}")

    # Thống kê filter queries
    brand_queries   = sum(1 for r in results[:filter_count] if "brand" in r["extracted_specs"])
    network_queries = sum(1 for r in results[:filter_count] if "network" in r["extracted_specs"])
    print(f"\n  Filter có brand   : {brand_queries}/{filter_count}")
    print(f"  Filter có network : {network_queries}/{filter_count}")
    print("=" * 65)

    print("\n--- Mẫu FILTER queries (ver2, đơn giản hơn) ---")
    for r in results[:10]:
        print(f"  [{r['id']:>2}] {r['query']}")
        print(f"        specs: {r['extracted_specs']}")
        print(f"        → {r['product_title'][:60]}")

    print("\n--- Mẫu INTENT queries (ver2, ngắn gọn hơn) ---")
    for r in results[filter_count:filter_count + 10]:
        print(f"  [{r['id']:>2}] {r['query']}")
        print(f"        → {r['product_title'][:60]}")


if __name__ == "__main__":
    main()
