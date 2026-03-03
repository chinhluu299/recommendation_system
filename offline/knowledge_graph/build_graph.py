#!/usr/bin/env python3
"""
Build Knowledge Graph from Amazon product metadata CSV.

Node types  : Product, Brand, Category, Feature, Spec,
              Carrier, Technology, Accessory, Store, User
Edge types  : MANUFACTURED_BY, SOLD_BY, BELONGS_TO, SUBCATEGORY_OF,
              HAS_FEATURE, HAS_SPEC, SUPPORTS_CARRIER,
              USES_TECHNOLOGY, INCLUDES_ACCESSORY, BOUGHT_TOGETHER,
              RATE

Output layout:
  output/
    nodes/
      products.json, brands.json, categories.json, features.json,
      specs.json, carriers.json, technologies.json, accessories.json,
      stores.json, users.json
    edges/
      manufactured_by.json, sold_by.json, belongs_to.json,
      subcategory_of.json, has_feature.json, has_spec.json,
      supports_carrier.json, uses_technology.json,
      includes_accessory.json, bought_together.json, rate.json
    summary.json
"""

import ast
import csv
import json
import re
from collections import defaultdict
from pathlib import Path


# ─── Utilities ────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """snake_case slug for node IDs."""
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text.strip("_") or "unknown"


def safe_parse(val: str):
    """Parse Python-literal strings (list / dict) safely."""
    if not val or val.strip() in ("", "[]", "{}", "None", "nan"):
        return None
    try:
        return ast.literal_eval(val)
    except Exception:
        return None


def safe_float(val):
    try:
        return float(val) if val not in (None, "", "nan") else None
    except (ValueError, TypeError):
        return None


def safe_int(val):
    try:
        return int(float(val)) if val not in (None, "", "nan") else None
    except (ValueError, TypeError):
        return None


def lc(s) -> str:
    """Lowercase a string; pass None and non-strings through unchanged."""
    return s.lower() if isinstance(s, str) else s


def normalize_spec_value(val: str) -> str:
    """Collapse whitespace and lowercase spec values so '8 GB' == '8GB'."""
    return re.sub(r"\s+", "", val.lower())


# ─── Lookup tables ────────────────────────────────────────────────────────────

# keyword (lowercase) → canonical display name
CARRIER_LOOKUP = {
    "at&t":               "AT&T",
    "att":                "AT&T",
    "t-mobile":           "T-Mobile",
    "tmobile":            "T-Mobile",
    "t mobile":           "T-Mobile",
    "verizon":            "Verizon",
    "sprint":             "Sprint",
    "cricket":            "Cricket",
    "metro pcs":          "Metro PCS",
    "metro by t-mobile":  "Metro by T-Mobile",
    "boost":              "Boost Mobile",
    "us cellular":        "US Cellular",
    "tracfone":           "TracFone",
    "straight talk":      "Straight Talk",
    "google fi":          "Google Fi",
    "spectrum":           "Spectrum",
    "xfinity":            "Xfinity",
    "optimum":            "Optimum Mobile",
    "consumer cellular":  "Consumer Cellular",
    "republic wireless":  "Republic Wireless",
    "ting":               "Ting",
    "net10":              "Net10",
    "virgin mobile":      "Virgin Mobile",
    "simple mobile":      "Simple Mobile",
    "vodafone":           "Vodafone",
    "telcel":             "Telcel",
}

# longest keywords first so "4g lte" is matched before "4g" / "lte"
TECH_LOOKUP = {
    "4g lte":    "4G LTE",
    "5g nr":     "5G NR",
    "wi-fi 6":   "Wi-Fi 6",
    "wi-fi 5":   "Wi-Fi 5",
    "4g":        "4G",
    "5g":        "5G",
    "3g":        "3G",
    "2g":        "2G",
    "lte":       "LTE",
    "gsm":       "GSM",
    "cdma":      "CDMA",
    "wi-fi":     "Wi-Fi",
    "wifi":      "Wi-Fi",
    "bluetooth": "Bluetooth",
    "nfc":       "NFC",
    "volte":     "VoLTE",
    "usb":       "USB",
    "hotspot":   "Hotspot",
}
TECH_LOOKUP_SORTED = sorted(TECH_LOOKUP.items(), key=lambda x: len(x[0]), reverse=True)

# raw unit string (lowercase, collapsed spaces) → canonical display unit
UNIT_LOOKUP: dict[str, str] = {
    # Storage / Memory
    "gb": "GB",  "gigabyte": "GB",  "gigabytes": "GB",
    "mb": "MB",  "megabyte": "MB",  "megabytes": "MB",
    "tb": "TB",  "terabyte": "TB",  "terabytes": "TB",
    # Battery
    "mah": "mAh",
    "milliampere hour": "mAh",  "milliampere-hour": "mAh",
    "milliampere hours": "mAh", "milliampere-hours": "mAh",
    # Frequency
    "mhz": "MHz", "megahertz": "MHz",
    "ghz": "GHz", "gigahertz": "GHz",
    # Camera
    "mp": "MP", "megapixel": "MP", "megapixels": "MP",
    # Display / Physical dimensions
    "inch": "inch", "inches": "inch",
    "mm": "mm", "millimeter": "mm", "millimeters": "mm",
    "cm": "cm", "centimeter": "cm", "centimeters": "cm",
    # Weight
    "g":  "g",  "gram": "g",   "grams": "g",
    "kg": "kg", "kilogram": "kg", "kilograms": "kg",
    "oz": "oz", "ounce": "oz",  "ounces": "oz",
    "lb": "lb", "lbs": "lb",   "pound": "lb", "pounds": "lb",
    # Power / Electrical
    "w":  "W",  "watt": "W",   "watts": "W",
    "mw": "mW",
    "v":  "V",  "volt": "V",   "volts": "V",
    # Time
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
}

# Regex: optional leading number + unit word(s).  Anchored to the full string.
_MEASURE_RE = re.compile(
    r"^\s*(\d+(?:[.,]\d+)?)"                         # integer or decimal (comma/dot)
    r"\s*"
    r"([a-zA-Z][a-zA-Z\s\-]*[a-zA-Z]|[a-zA-Z])"    # unit: 1+ letter words, may contain spaces/hyphens
    r"\s*$",
    re.IGNORECASE,
)

# Keys in `details` that are already handled by dedicated blocks or mapped to
# Product node properties.  Skip these when doing the dynamic Spec loop.
SPEC_SKIP_KEYS: frozenset = frozenset({
    "Brand", "Manufacturer",
    "Color",
    "Product Dimensions", "Item Weight",
    "Item model number", "Date First Available",
    "Screen Size", "Display resolution", "Scanner Resolution",
    "Form Factor", "Operating System", "Display technology", "Model Name",
    "Wireless Carrier",
    "Cellular Technology", "Connectivity Technology",
    "Connectivity technologies", "Wireless network technology",
    "Whats in the box",
})


# ─── Measurement parser ───────────────────────────────────────────────────────

def parse_measurement(val: str) -> tuple:
    """Tách '8 GB' → (8.0, 'GB'),  '5000 mAh' → (5000.0, 'mAh').
    Trả về (None, None) nếu không khớp hoặc đơn vị không có trong UNIT_LOOKUP.
    """
    if not val:
        return None, None
    m = _MEASURE_RE.match(val.strip())
    if not m:
        return None, None
    num_str  = m.group(1).replace(",", ".")
    raw_unit = re.sub(r"\s+", " ", m.group(2).strip().lower())
    canonical = UNIT_LOOKUP.get(raw_unit)
    if canonical is None:
        return None, None
    try:
        return float(num_str), canonical
    except ValueError:
        return None, None


# ─── Text extractors ──────────────────────────────────────────────────────────

def extract_carriers(text: str) -> list:
    text_l = text.lower()
    return [
        canon for kw, canon in CARRIER_LOOKUP.items()
        if re.search(rf"\b{re.escape(kw)}\b", text_l)
    ]


def normalize_tech(raw: str) -> str:
    """Map a raw tech string to its canonical name (best-effort)."""
    raw_l = raw.strip().lower()
    for kw, canon in TECH_LOOKUP_SORTED:
        if kw in raw_l:
            return canon
    return raw.strip()


def parse_tech_list(val: str) -> list:
    """Parse comma-separated technology string → list of canonical names."""
    if not val:
        return []
    seen, result = set(), []
    for part in val.split(","):
        canon = normalize_tech(part)
        if canon and canon not in seen:
            seen.add(canon)
            result.append(canon)
    return result


def parse_carriers_field(val: str) -> list:
    """Parse 'Wireless Carrier' detail field."""
    if not val:
        return []
    lower = val.lower()
    if "unlocked" in lower:
        return []
    carriers, seen = [], set()
    for kw, canon in CARRIER_LOOKUP.items():
        if re.search(rf"\b{re.escape(kw)}\b", lower) and canon not in seen:
            seen.add(canon)
            carriers.append(canon)
    return carriers


def parse_accessories(val: str) -> list:
    """Parse 'Whats in the box' → accessory list (skip 'Device'/'Phone')."""
    skip = {"device", "phone", "smartphone", "handset", ""}
    if not val:
        return []
    return [
        p.strip() for p in val.split(",")
        if p.strip().lower() not in skip
    ]


# ─── Graph builder ────────────────────────────────────────────────────────────

def build_graph(csv_path: str, reviews_path: str = None) -> tuple:
    nodes: dict = {}      # id → node dict
    edges: list = []
    edge_keys: set = set()

    def add_node(nid: str, ntype: str, label: str, props: dict = None):
        if nid not in nodes:
            n = {"id": nid, "type": ntype, "label": lc(label)}
            if props:
                n["properties"] = props
            nodes[nid] = n

    def add_edge(src: str, tgt: str, rel: str, props: dict = None):
        key = (src, tgt, rel)
        if key not in edge_keys:
            edge_keys.add(key)
            e = {"source": src, "target": tgt, "relationship": rel}
            if props:
                e["properties"] = props
            edges.append(e)

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asin = row.get("parent_asin", "").strip()
            if not asin:
                continue

            pid = f"product_{asin}"
            title      = row.get("title", "").strip()
            store_name = row.get("store", "").strip()
            price_raw  = row.get("price", "").strip()
            price      = safe_float(price_raw) if price_raw else None

            details    = safe_parse(row.get("details", "")) or {}
            feat_texts = safe_parse(row.get("features", "")) or []
            cats_list  = safe_parse(row.get("categories", "")) or []
            bt_raw     = safe_parse(row.get("bought_together", ""))

            # ── Product node ──────────────────────────────────────────
            prod_props = {
                "asin":           asin,          # identifier — giữ nguyên
                "title":          lc(title),
                "average_rating": safe_float(row.get("average_rating")),
                "rating_number":  safe_int(row.get("rating_number")),
                "price":          price,
            }
            for detail_key, prop_key in [
                ("Color",              "color"),
                ("Product Dimensions", "dimensions"),
                ("Item Weight",        "weight"),
                ("Item model number",  "model_number"),
                ("Date First Available", "date_first_available"),
                ("Screen Size",        "screen_size"),
                ("Display resolution", "display_resolution"),
                ("Scanner Resolution", "display_resolution"),
                ("Form Factor",        "form_factor"),
                ("Operating System",   "operating_system"),
                ("Display technology", "display_technology"),
                ("Model Name",         "model_name"),
            ]:
                if detail_key in details and prop_key not in prod_props:
                    prod_props[prop_key] = lc(details[detail_key])

            add_node(pid, "Product", title or asin, prod_props)

            # ── Brand ─────────────────────────────────────────────────
            brand_name = (
                details.get("Brand")
                or details.get("Manufacturer")
                or store_name
            )
            if brand_name:
                bid = f"brand_{slugify(brand_name)}"
                add_node(bid, "Brand", brand_name)
                add_edge(pid, bid, "MANUFACTURED_BY")

            # ── Store ─────────────────────────────────────────────────
            if store_name:
                sid = f"store_{slugify(store_name)}"
                add_node(sid, "Store", store_name)
                add_edge(pid, sid, "SOLD_BY")

            # ── Categories ────────────────────────────────────────────
            # List order: broad → specific  e.g. ['Cell Phones & Acc...', 'Cell Phones']
            for cat_name in cats_list:
                cid = f"cat_{slugify(cat_name)}"
                add_node(cid, "Category", cat_name)

            if cats_list:
                # Product belongs to most specific (last)
                add_edge(pid, f"cat_{slugify(cats_list[-1])}", "BELONGS_TO")
                # Build hierarchy: child SUBCATEGORY_OF parent
                for i in range(1, len(cats_list)):
                    child_id  = f"cat_{slugify(cats_list[i])}"
                    parent_id = f"cat_{slugify(cats_list[i - 1])}"
                    add_edge(child_id, parent_id, "SUBCATEGORY_OF")

            # ── Features ─────────────────────────────────────────────
            for feat_text in feat_texts:
                if not feat_text or not feat_text.strip():
                    continue
                fid = f"feature_{slugify(feat_text.strip())}"
                add_node(fid, "Feature", feat_text.strip())
                add_edge(pid, fid, "HAS_FEATURE")

            # ── Specs (dynamic) ───────────────────────────────────────
            for dkey, raw_val in details.items():
                if dkey in SPEC_SKIP_KEYS or not raw_val or not str(raw_val).strip():
                    continue
                val  = str(raw_val).strip()
                skey = slugify(dkey)                          # e.g. "battery_capacity"
                val_slug = slugify(normalize_spec_value(val)) # dedup: "8 GB" == "8GB"
                spec_id  = f"spec_{skey}_{val_slug}"

                spec_props: dict = {"key": skey, "value": lc(val), "label": lc(dkey)}
                num_val, unit = parse_measurement(val)
                if num_val is not None:
                    spec_props["numeric_value"] = num_val
                    spec_props["unit"] = lc(unit)

                    # Gắn thêm vào Product props để Cypher filter không cần MATCH Spec
                    canon_unit = lc(unit)
                    if skey in ("ram", "ram_memory_installed_size"):
                        # RAM có thể lưu dạng MB ("4096 MB") hoặc GB ("4 GB")
                        # → chuẩn hóa về GB, dùng setdefault để giá trị đầu tiên thắng
                        if canon_unit == "gb":
                            prod_props.setdefault("ram_gb", num_val)
                        elif canon_unit == "mb":
                            prod_props.setdefault("ram_gb", round(num_val / 1024, 2))
                    elif skey == "memory_storage_capacity":
                        prod_props["storage_gb"] = num_val

                add_node(spec_id, "Spec", f"{dkey}: {val}", spec_props)
                add_edge(pid, spec_id, "HAS_SPEC")

            # ── Carriers ─────────────────────────────────────────────
            # Only use the structured "Wireless Carrier" field.
            # Scanning free-text features causes ~6x false positives
            # (precision 13%) because product descriptions casually
            # mention carrier names without implying compatibility.
            carrier_names = set(
                parse_carriers_field(details.get("Wireless Carrier", ""))
            )

            for cn in carrier_names:
                cid = f"carrier_{slugify(cn)}"
                add_node(cid, "Carrier", cn)
                add_edge(pid, cid, "SUPPORTS_CARRIER")

            # ── Technologies ──────────────────────────────────────────
            tech_names = set()
            tech_names.update(
                parse_tech_list(details.get("Cellular Technology", ""))
            )
            tech_names.update(
                parse_tech_list(
                    details.get("Connectivity Technology")
                    or details.get("Connectivity technologies", "")
                )
            )
            tech_names.update(
                parse_tech_list(details.get("Wireless network technology", ""))
            )
            # remove empty / generic strings
            tech_names.discard("")
            tech_names.discard("Cellular")

            for tn in tech_names:
                tid = f"tech_{slugify(tn)}"
                add_node(tid, "Technology", tn)
                add_edge(pid, tid, "USES_TECHNOLOGY")

            # ── Accessories ───────────────────────────────────────────
            for acc_name in parse_accessories(details.get("Whats in the box", "")):
                aid = f"accessory_{slugify(acc_name)}"
                add_node(aid, "Accessory", acc_name)
                add_edge(pid, aid, "INCLUDES_ACCESSORY")

            # ── Bought Together ───────────────────────────────────────
            if isinstance(bt_raw, list):
                for related_asin in bt_raw:
                    add_edge(pid, f"product_{related_asin}", "BOUGHT_TOGETHER")

    # ── Users & RATE edges (from reviews) ────────────────────────────────
    if reviews_path:
        with open(reviews_path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                user_id = row.get("user_id", "").strip()
                asin    = row.get("parent_asin", "").strip()
                rating  = safe_float(row.get("rating"))
                ts      = safe_int(row.get("timestamp"))
                if not user_id or not asin:
                    continue
                uid = f"user_{user_id}"
                add_node(uid, "User", user_id, {"user_id": user_id})
                pid = f"product_{asin}"
                props = {"rating": rating}
                if ts is not None:
                    props["timestamp"] = ts
                add_edge(uid, pid, "RATE", props)

    return nodes, edges


# ─── Save helpers ─────────────────────────────────────────────────────────────

NODE_FILES = {
    "Product":    "products.json",
    "Brand":      "brands.json",
    "Category":   "categories.json",
    "Feature":    "features.json",
    "Spec":       "specs.json",
    "Carrier":    "carriers.json",
    "Technology": "technologies.json",
    "Accessory":  "accessories.json",
    "Store":      "stores.json",
    "User":       "users.json",
}

EDGE_FILES = {
    "MANUFACTURED_BY":    "manufactured_by.json",
    "SOLD_BY":            "sold_by.json",
    "BELONGS_TO":         "belongs_to.json",
    "SUBCATEGORY_OF":     "subcategory_of.json",
    "HAS_FEATURE":        "has_feature.json",
    "HAS_SPEC":           "has_spec.json",
    "SUPPORTS_CARRIER":   "supports_carrier.json",
    "USES_TECHNOLOGY":    "uses_technology.json",
    "INCLUDES_ACCESSORY": "includes_accessory.json",
    "BOUGHT_TOGETHER":    "bought_together.json",
    "RATE":               "rate.json",
}


def save_split(nodes: dict, edges: list, output_dir: str) -> dict:
    out = Path(output_dir)
    nodes_dir = out / "nodes"
    edges_dir = out / "edges"
    nodes_dir.mkdir(parents=True, exist_ok=True)
    edges_dir.mkdir(parents=True, exist_ok=True)

    # Group by type
    by_type: dict = defaultdict(list)
    for node in nodes.values():
        by_type[node["type"]].append(node)

    for ntype, filename in NODE_FILES.items():
        with open(nodes_dir / filename, "w", encoding="utf-8") as f:
            json.dump(by_type.get(ntype, []), f, ensure_ascii=False, indent=2)

    # Group by relationship
    by_rel: dict = defaultdict(list)
    for edge in edges:
        by_rel[edge["relationship"]].append(edge)

    for rel, filename in EDGE_FILES.items():
        with open(edges_dir / filename, "w", encoding="utf-8") as f:
            json.dump(by_rel.get(rel, []), f, ensure_ascii=False, indent=2)

    summary = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "nodes_by_type": {t: len(lst) for t, lst in by_type.items()},
        "edges_by_relationship": {r: len(lst) for r, lst in by_rel.items()},
    }
    with open(out / "summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary


# ─── Entry point ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    script_dir   = Path(__file__).parent
    csv_path     = script_dir.parent / "data" / "meta_filtered.csv"
    reviews_path = script_dir.parent / "data" / "reviews_filtered.csv"
    output_dir   = script_dir / "output"

    print(f"[1/3] Reading  : {csv_path}")
    print(f"         + reviews: {reviews_path}")
    nodes, edges = build_graph(str(csv_path), str(reviews_path))

    print(f"[2/3] Saving to: {output_dir}")
    summary = save_split(nodes, edges, str(output_dir))

    print("[3/3] Done!\n")
    print(f"  Total nodes : {summary['total_nodes']}")
    print(f"  Total edges : {summary['total_edges']}")

    print("\n  Nodes by type:")
    for t, c in sorted(summary["nodes_by_type"].items()):
        print(f"    {t:<15}  {c:>6}")

    print("\n  Edges by relationship:")
    for r, c in sorted(summary["edges_by_relationship"].items()):
        print(f"    {r:<25}  {c:>6}")
