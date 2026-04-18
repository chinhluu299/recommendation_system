
import json
import pickle
from pathlib import Path

import numpy as np

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT      = Path(__file__).parent.parent              # ver2/
KG_OUTPUT = ROOT / "knowledge_graph" / "output"
DATA_DIR  = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Ngưỡng: RATE edge có rating >= giá trị này được coi là positive interaction
POS_RATING_THRESHOLD = 3

# Chỉ giữ user có ít nhất MIN_USER_INTERACTIONS positive interactions
MIN_USER_INTERACTIONS = 3

# Thứ tự load node files: users trước, products sau (đảm bảo entity IDs nhất quán)
_NODE_ORDER = ["users.json", "products.json"]

# Các quan hệ KG (không tính RATE)
KG_RELATIONS = [
    "MANUFACTURED_BY",
    "SOLD_BY",
    "BELONGS_TO",
    "SUBCATEGORY_OF",
    "HAS_FEATURE",
    "HAS_SPEC",
    "SUPPORTS_CARRIER",
    "USES_TECHNOLOGY",
    "INCLUDES_ACCESSORY",
    "BOUGHT_TOGETHER",
]

# Map tên quan hệ → tên file edge
RELATION_TO_FILE = {
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
}


# ── Step 1: entity2id ─────────────────────────────────────────────────────────

def build_entity2id() -> dict[str, int]:
    """
    Gán integer ID cho toàn bộ entity trong KG.
    Thứ tự ưu tiên: users → products → các entity còn lại.
    Điều này đảm bảo:
      - user IDs  : 0 .. n_users-1
      - item IDs  : n_users .. n_users+n_items-1
    Giúp train.py dễ xác định offset.
    """
    node_dir   = KG_OUTPUT / "nodes"
    all_files  = {p.name: p for p in node_dir.glob("*.json")}

    ordered = []
    for name in _NODE_ORDER:
        if name in all_files:
            ordered.append(all_files[name])
    for p in sorted(all_files.values()):
        if p not in ordered:
            ordered.append(p)

    entity2id: dict[str, int] = {}
    for node_file in ordered:
        nodes = json.loads(node_file.read_text(encoding="utf-8"))
        for node in nodes:
            nid = node["id"]
            if nid not in entity2id:
                entity2id[nid] = len(entity2id)
    return entity2id


# ── Step 2: relation2id ───────────────────────────────────────────────────────

def build_relation2id() -> dict[str, int]:
    """
    RATE = 0, rồi đến các KG relations.
    Inverse của quan hệ r có ID = r + n_relations_original.
    """
    rels = ["RATE"] + KG_RELATIONS
    return {r: i for i, r in enumerate(rels)}


# ── Step 3: Positive interactions từ RATE edges ───────────────────────────────

def load_interactions(
    entity2id: dict[str, int],
) -> tuple[dict[int, list[int]], int]:
    """
    Đọc edges/rate.json → dict {user_int: [item_int, ...]}.
    Chỉ giữ các cặp có rating >= POS_RATING_THRESHOLD.

    Trả về (interactions, n_skipped).
    """
    rate_file = KG_OUTPUT / "edges" / "rate.json"
    if not rate_file.exists():
        raise FileNotFoundError(
            f"Không tìm thấy {rate_file}. "
            "Hãy chạy knowledge_graph/build_graph.py trước."
        )

    edges      = json.loads(rate_file.read_text(encoding="utf-8"))
    inter: dict[int, list[int]] = {}
    skipped = 0

    for edge in edges:
        props  = edge.get("properties") or {}
        rating = props.get("rating")
        if rating is None or float(rating) < POS_RATING_THRESHOLD:
            skipped += 1
            continue

        uid_str = edge["source"]
        pid_str = edge["target"]
        if uid_str not in entity2id or pid_str not in entity2id:
            skipped += 1
            continue

        u = entity2id[uid_str]
        p = entity2id[pid_str]
        inter.setdefault(u, []).append(p)

    # Loại bỏ duplicate
    for u in inter:
        inter[u] = list(set(inter[u]))

    # Lọc user có quá ít interaction
    before = len(inter)
    inter = {u: items for u, items in inter.items() if len(items) >= MIN_USER_INTERACTIONS}
    n_filtered = before - len(inter)
    skipped += n_filtered
    print(f"      Lọc {n_filtered} user có < {MIN_USER_INTERACTIONS} interactions  "
          f"(còn lại {len(inter)} users)")

    return inter, skipped


# ── Step 4: KG triples (forward + inverse) ────────────────────────────────────

def load_kg_triples(
    entity2id:   dict[str, int],
    relation2id: dict[str, int],
) -> np.ndarray:
    """
    Đọc tất cả KG edge files → array (N, 3) [head, rel_id, tail].
    Mỗi edge được thêm cả chiều forward và inverse:
      forward : (h, r,         t)
      inverse : (t, r+n_rel,   h)
    """
    n_rel   = len(relation2id)
    triples = []

    for rel_name in KG_RELATIONS:
        edge_file = KG_OUTPUT / "edges" / RELATION_TO_FILE[rel_name]
        if not edge_file.exists():
            continue

        edges = json.loads(edge_file.read_text(encoding="utf-8"))
        r_id  = relation2id[rel_name]
        r_inv = r_id + n_rel

        for edge in edges:
            h_str = edge["source"]
            t_str = edge["target"]
            if h_str not in entity2id or t_str not in entity2id:
                continue
            h = entity2id[h_str]
            t = entity2id[t_str]
            triples.append((h, r_id,  t))   # forward
            triples.append((t, r_inv, h))   # inverse

    return np.array(triples, dtype=np.int32) if triples else np.zeros((0, 3), dtype=np.int32)


# ── Step 5: CKG = KG triples + user-item interactions (cả hai chiều) ──────────

def build_ckg_triples(
    interactions: dict[int, list[int]],
    relation2id:  dict[str, int],
    kg_triples:   np.ndarray,
) -> np.ndarray:
    """
    Ghép KG triples và user-item interaction triples vào CKG.
    RATE edge: (user, r_rate, item) và inverse (item, r_rate_inv, user).
    """
    n_rel      = len(relation2id)
    r_rate     = relation2id["RATE"]
    r_rate_inv = r_rate + n_rel

    iu_triples = []
    for u, items in interactions.items():
        for p in items:
            iu_triples.append((u, r_rate,     p))
            iu_triples.append((p, r_rate_inv, u))

    if iu_triples:
        iu_arr = np.array(iu_triples, dtype=np.int32)
        return np.vstack([kg_triples, iu_arr])
    return kg_triples


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("[1/5] Building entity2id ...")
    entity2id = build_entity2id()
    n_users = sum(1 for k in entity2id if k.startswith("user_"))
    n_items = sum(1 for k in entity2id if k.startswith("product_"))
    print(f"      {len(entity2id)} entities  (users={n_users}, items={n_items})")

    print("[2/5] Building relation2id ...")
    relation2id = build_relation2id()
    n_rel = len(relation2id)
    print(f"      {n_rel} relations gốc  →  {2*n_rel} quan hệ trong CKG (với inverse)")

    print("[3/5] Loading positive interactions ...")
    interactions, skipped = load_interactions(entity2id)
    n_pos = sum(len(v) for v in interactions.values())
    print(f"      {len(interactions)} users có interaction, {n_pos} positive pairs  (bỏ qua {skipped})")

    print("[4/5] Loading KG triples ...")
    kg_triples = load_kg_triples(entity2id, relation2id)
    print(f"      {len(kg_triples)} KG triples (forward + inverse)")

    print("[5/5] Building CKG ...")
    ckg = build_ckg_triples(interactions, relation2id, kg_triples)
    print(f"      {len(ckg)} CKG triples tổng cộng")

    # ── Save ──────────────────────────────────────────────────────────────────
    (DATA_DIR / "entity2id.json").write_text(
        json.dumps(entity2id, ensure_ascii=False), encoding="utf-8"
    )
    (DATA_DIR / "relation2id.json").write_text(
        json.dumps(relation2id, ensure_ascii=False), encoding="utf-8"
    )
    with open(DATA_DIR / "interactions.pkl", "wb") as f:
        pickle.dump(interactions, f)
    np.save(DATA_DIR / "ckg_triples.npy", ckg)

    stats = {
        "n_entities":               len(entity2id),
        "n_users":                  n_users,
        "n_items":                  n_items,
        "n_other_entities":         len(entity2id) - n_users - n_items,
        "item_offset":              n_users,          # items start at this int ID
        "n_relations_original":     n_rel,
        "n_relations_ckg":          2 * n_rel,
        "n_kg_triples_with_inv":    int(len(kg_triples)),
        "n_ckg_triples":            int(len(ckg)),
        "n_positive_interactions":  n_pos,
        "n_users_with_interactions": len(interactions),
        "pos_rating_threshold":     POS_RATING_THRESHOLD,
        "min_user_interactions":    MIN_USER_INTERACTIONS,
    }
    (DATA_DIR / "stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    print("\nSaved to", DATA_DIR)
    for k, v in stats.items():
        print(f"  {k:<40} {v}")
