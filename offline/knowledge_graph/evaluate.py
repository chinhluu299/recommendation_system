import ast
import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path


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
_TECH_SORTED = sorted(TECH_LOOKUP.items(), key=lambda x: len(x[0]), reverse=True)


def safe_parse(val):
    try:
        return ast.literal_eval(val) if val else None
    except Exception:
        return None


def slugify(text: str) -> str:
    text = str(text).lower().strip()
    text = re.sub(r"[^a-z0-9\s]", "", text)
    text = re.sub(r"\s+", "_", text)
    return text.strip("_") or "unknown"


def normalize_spec_value(val: str) -> str:
    return re.sub(r"\s+", "", val.lower())


def _canonical_carrier(raw: str):
    lower = raw.strip().lower()
    for kw, canon in CARRIER_LOOKUP.items():
        if re.search(rf"\b{re.escape(kw)}\b", lower):
            return canon
    return None


def _canonical_tech(raw: str) -> str:
    lower = raw.strip().lower()
    for kw, canon in _TECH_SORTED:
        if kw in lower:
            return canon
    return raw.strip()


def load_graph(output_dir: str):
    out = Path(output_dir)
    nodes: dict = {}
    for f in sorted((out / "nodes").glob("*.json")):
        for n in json.loads(f.read_text(encoding="utf-8")):
            nodes[n["id"]] = n

    edges: list = []
    for f in sorted((out / "edges").glob("*.json")):
        edges.extend(json.loads(f.read_text(encoding="utf-8")))

    return nodes, edges


def build_product_lookup(nodes: dict, edges: list) -> dict:
    product_to: dict = defaultdict(lambda: defaultdict(set))
    for e in edges:
        src, rel, tgt = e["source"], e["relationship"], e["target"]
        if not src.startswith("product_"):
            continue
        tgt_node = nodes.get(tgt)
        if tgt_node:
            product_to[src][rel].add(tgt_node["label"].lower())
    return product_to


def eval_carrier(csv_path: str, product_to: dict) -> dict:
    TP = FP = FN = 0
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = f"product_{row['parent_asin']}"
            details = safe_parse(row.get("details", "")) or {}
            raw = details.get("Wireless Carrier", "")

            if "unlocked" in raw.lower():
                true_set: set = set()
            else:
                true_set = set()
                for part in raw.split(","):
                    canon = _canonical_carrier(part)
                    if canon:
                        true_set.add(canon.lower())

            pred_set = product_to[pid].get("SUPPORTS_CARRIER", set())

            TP += len(true_set & pred_set)
            FP += len(pred_set - true_set)
            FN += len(true_set - pred_set)

    prec = TP / (TP + FP) if (TP + FP) else 0.0
    rec  = TP / (TP + FN) if (TP + FN) else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "TP": TP, "FP": FP, "FN": FN}


def eval_tech(csv_path: str, product_to: dict) -> dict:
    TECH_KEYS = [
        "Cellular Technology",
        "Connectivity Technology",
        "Connectivity technologies",
        "Wireless network technology",
    ]
    SKIP = {"cellular", ""}

    TP = FP = FN = 0
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = f"product_{row['parent_asin']}"
            details = safe_parse(row.get("details", "")) or {}

            true_set: set = set()
            for k in TECH_KEYS:
                val = details.get(k, "")
                if val:
                    for part in val.split(","):
                        canon = _canonical_tech(part)
                        if canon.lower() not in SKIP:
                            true_set.add(canon.lower())

            pred_set = product_to[pid].get("USES_TECHNOLOGY", set())

            TP += len(true_set & pred_set)
            FP += len(pred_set - true_set)
            FN += len(true_set - pred_set)

    prec = TP / (TP + FP) if (TP + FP) else 0.0
    rec  = TP / (TP + FN) if (TP + FN) else 0.0
    f1   = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"precision": round(prec, 4), "recall": round(rec, 4),
            "f1": round(f1, 4), "TP": TP, "FP": FP, "FN": FN}


def eval_brand(csv_path: str, product_to: dict) -> dict:
    correct = wrong = missing = total = 0
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            pid = f"product_{row['parent_asin']}"
            details = safe_parse(row.get("details", "")) or {}
            true_brand = (
                details.get("Brand")
                or details.get("Manufacturer")
                or row.get("store", "")
            )
            if not true_brand:
                continue
            total += 1
            pred_brands = product_to[pid].get("MANUFACTURED_BY", set())
            if not pred_brands:
                missing += 1
            elif true_brand.lower() in pred_brands:
                correct += 1
            else:
                wrong += 1

    return {
        "accuracy":     round(correct / total, 4) if total else 0.0,
        "missing_rate": round(missing / total, 4) if total else 0.0,
        "wrong_rate":   round(wrong   / total, 4) if total else 0.0,
        "total":        total,
    }


def eval_spec(csv_path: str, nodes: dict) -> dict:
    SPEC_FIELDS = {"RAM": "ram", "Memory Storage Capacity": "storage"}
    raw_ids: set = set()
    norm_ids: set = set()

    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            details = safe_parse(row.get("details", "")) or {}
            for dkey, skey in SPEC_FIELDS.items():
                val = details.get(dkey, "").strip()
                if val:
                    raw_ids.add(f"spec_{skey}_{slugify(val)}")
                    norm_ids.add(f"spec_{skey}_{slugify(normalize_spec_value(val))}")

    actual = sum(1 for n in nodes.values() if n["type"] == "Spec")
    return {
        "raw_unique_ids":              len(raw_ids),
        "normalized_unique_ids":       len(norm_ids),
        "nodes_merged_by_normalization": len(raw_ids) - len(norm_ids),
        "actual_spec_nodes_in_graph":  actual,
    }


def eval_feature(csv_path: str, nodes: dict, edges: list) -> dict:
    total_raw = 0
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            feats = safe_parse(row.get("features", "")) or []
            total_raw += sum(1 for ft in feats if ft and ft.strip())

    feat_nodes = sum(1 for n in nodes.values() if n["type"] == "Feature")
    feat_edges = sum(1 for e in edges if e["relationship"] == "HAS_FEATURE")

    return {
        "raw_feature_texts":        total_raw,
        "unique_feature_nodes":     feat_nodes,
        "dedup_ratio":              round(1 - feat_nodes / total_raw, 4) if total_raw else 0.0,
        "has_feature_edges":        feat_edges,
        "avg_products_per_feature": round(feat_edges / feat_nodes, 2) if feat_nodes else 0.0,
    }


def eval_completeness(product_to: dict) -> dict:
    RELS = [
        "MANUFACTURED_BY", "BELONGS_TO", "SOLD_BY",
        "USES_TECHNOLOGY", "SUPPORTS_CARRIER",
        "HAS_FEATURE", "HAS_SPEC",
    ]
    total = len(product_to)
    if not total:
        return {}
    counts: dict = defaultdict(int)
    for rels in product_to.values():
        for rel in RELS:
            if rel in rels:
                counts[rel] += 1
    return {rel: round(counts[rel] / total, 4) for rel in RELS}


def eval_integrity(nodes: dict, edges: list) -> dict:
    broken_by_rel: dict = defaultdict(int)
    for e in edges:
        if e["source"] not in nodes or e["target"] not in nodes:
            broken_by_rel[e["relationship"]] += 1

    total_broken = sum(broken_by_rel.values())
    return {
        "total_edges":     len(edges),
        "broken_edges":    total_broken,
        "integrity_rate":  round(1 - total_broken / len(edges), 4) if edges else 1.0,
        "broken_by_rel":   dict(broken_by_rel),
    }


def evaluate_all(output_dir: str, csv_path: str) -> dict:
    print(f"  Loading graph from {output_dir} …")
    nodes, edges = load_graph(output_dir)
    print(f"  {len(nodes):,} nodes  |  {len(edges):,} edges")

    product_to = build_product_lookup(nodes, edges)
    print(f"  {len(product_to):,} product nodes found in edges")

    return {
        "carrier":      eval_carrier(csv_path, product_to),
        "technology":   eval_tech(csv_path, product_to),
        "brand":        eval_brand(csv_path, product_to),
        "spec":         eval_spec(csv_path, nodes),
        "feature":      eval_feature(csv_path, nodes, edges),
        "completeness": eval_completeness(product_to),
        "integrity":    eval_integrity(nodes, edges),
    }


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python evaluate.py <output_dir> <meta_csv>")
        print("  output_dir  directory containing nodes/ and edges/ sub-folders")
        print("  meta_csv    path to meta_filtered.csv")
        sys.exit(1)

    output_dir = sys.argv[1]
    csv_path = sys.argv[2]

    metrics = evaluate_all(output_dir, csv_path)
    with open("evaluate_metrics.json", "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2, ensure_ascii=False)
    print(json.dumps(metrics, indent=2))

