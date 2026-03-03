#!/usr/bin/env python3
"""
Convert knowledge graph JSON → CSV files for Neo4j LOAD CSV import.

Input  : ../knowledge_graph/output/{nodes,edges}/*.json
Output : csv/{nodes,edges}/*.csv  (created next to this script)

Usage:
    python3 convert_to_csv.py
"""

import csv
import json
from pathlib import Path


# ─── Paths ────────────────────────────────────────────────────────────────────

SCRIPT_DIR  = Path(__file__).parent
KG_DIR      = SCRIPT_DIR.parent / "output"
CSV_NODES   = SCRIPT_DIR / "csv" / "nodes"
CSV_EDGES   = SCRIPT_DIR / "csv" / "edges"

# ─── Node configs: (json_file, csv_file, extra_property_keys) ─────────────────
# Products get all flattened properties; others only need id + label.

PRODUCT_PROPS = [
    "asin", "title", "average_rating", "rating_number", "price",
    "color", "dimensions", "weight", "model_number",
    "date_first_available", "screen_size", "display_resolution",
    "form_factor", "operating_system", "display_technology", "model_name",
    "ram_gb", "storage_gb",   # shortcut properties cho Cypher filter (không cần MATCH Spec)
]

NODE_CONFIGS = {
    "products.json":    ("products.csv",    PRODUCT_PROPS),
    "brands.json":      ("brands.csv",      []),
    "categories.json":  ("categories.csv",  []),
    "features.json":    ("features.csv",    []),
    "specs.json":       ("specs.csv",       ["key", "value", "label", "numeric_value", "unit"]),
    "carriers.json":    ("carriers.csv",    []),
    "technologies.json":("technologies.csv",[]),
    "accessories.json": ("accessories.csv", []),
    "stores.json":      ("stores.csv",      []),
    "users.json":       ("users.csv",       ["user_id"]),
}

# ─── Edge configs ─────────────────────────────────────────────────────────────

# Edges không có properties (chỉ source, target, relationship)
EDGE_FILES = [
    "manufactured_by.json",
    "sold_by.json",
    "belongs_to.json",
    "subcategory_of.json",
    "has_feature.json",
    "has_spec.json",
    "supports_carrier.json",
    "uses_technology.json",
    "includes_accessory.json",
    "bought_together.json",
]

# Edges có properties bổ sung: (json_file, [extra_property_keys])
EDGE_FILES_WITH_PROPS = [
    ("rate.json", ["rating"]),
]


# ─── Helpers ─────────────────────────────────────────────────────────────────

def none_to_empty(val) -> str:
    """Convert None / missing values to empty string for CSV."""
    if val is None:
        return ""
    return str(val)


def write_node_csv(json_path: Path, csv_path: Path, prop_keys: list):
    with open(json_path, encoding="utf-8") as f:
        nodes = json.load(f)

    columns = ["id", "label"] + prop_keys
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for node in nodes:
            props = node.get("properties") or {}
            row = [node.get("id", ""), node.get("label", "")]
            for key in prop_keys:
                row.append(none_to_empty(props.get(key)))
            writer.writerow(row)

    print(f"  ✓  {csv_path.name:<35}  ({len(nodes):>6} rows)")


def write_edge_csv(json_path: Path, csv_path: Path, prop_keys: list = None):
    with open(json_path, encoding="utf-8") as f:
        edges = json.load(f)

    extra_keys = prop_keys or []
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["source", "target", "relationship"] + extra_keys)
        for edge in edges:
            props = edge.get("properties") or {}
            row = [
                edge.get("source", ""),
                edge.get("target", ""),
                edge.get("relationship", ""),
            ]
            for key in extra_keys:
                row.append(none_to_empty(props.get(key)))
            writer.writerow(row)

    print(f"  ✓  {csv_path.name:<35}  ({len(edges):>6} rows)")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=== Converting nodes ===")
    for json_name, (csv_name, prop_keys) in NODE_CONFIGS.items():
        json_path = KG_DIR / "nodes" / json_name
        csv_path  = CSV_NODES / csv_name
        if json_path.exists():
            write_node_csv(json_path, csv_path, prop_keys)
        else:
            print(f"  ✗  {json_name} not found — skipped")

    print("\n=== Converting edges ===")
    for edge_name in EDGE_FILES:
        json_path = KG_DIR / "edges" / edge_name
        csv_path  = CSV_EDGES / edge_name.replace(".json", ".csv")
        if json_path.exists():
            write_edge_csv(json_path, csv_path)
        else:
            print(f"  ✗  {edge_name} not found — skipped")

    for edge_name, prop_keys in EDGE_FILES_WITH_PROPS:
        json_path = KG_DIR / "edges" / edge_name
        csv_path  = CSV_EDGES / edge_name.replace(".json", ".csv")
        if json_path.exists():
            write_edge_csv(json_path, csv_path, prop_keys)
        else:
            print(f"  ✗  {edge_name} not found — skipped")

    print(f"\nDone. CSV files saved to: {SCRIPT_DIR / 'csv'}")
    print("\nNext step → copy csv/ into Neo4j import directory:")
    print("  Docker : docker cp csv/. <container>:/var/lib/neo4j/import/")
    print("  Local  : cp -r csv/* $NEO4J_HOME/import/")


if __name__ == "__main__":
    main()
