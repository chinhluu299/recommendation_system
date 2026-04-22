"""
evaluate.py — Đánh giá offline các mô hình gợi ý (Loại 1).

So sánh các phương pháp theo từng bước:
    Random → Popularity → MF/SVD → KGAT

Cách chạy:
    python -m baseline.evaluate
    python -m baseline.evaluate --top_k 10 20 --max_users 2000
"""

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch

from baseline._shared    import load_data, split_interactions, evaluate_rec
from baseline.random_rec import RandomRecommender
from baseline.popularity import PopularityRecommender
from baseline.mf_rec     import MFRecommender

# Đường dẫn tới các file checkpoint và kết quả
KGAT_CKPT  = Path(__file__).parent.parent / "ranking" / "checkpoints" / "best_model.pt"
KGAT_SPLIT = Path(__file__).parent.parent / "ranking" / "checkpoints" / "kgat_split.json"
RESULT_DIR = Path(__file__).parent / "results"


# ─────────────────────────────────────────────────────────────────────────────
# Hàm load mô hình KGAT từ checkpoint
# ─────────────────────────────────────────────────────────────────────────────

def load_kgat_scorer(ckpt_path: Path, ckg: np.ndarray, device: torch.device):
    """
    Load mô hình KGAT từ file checkpoint, tính embedding, và trả về hàm score.

    Trả về:
        scorer  : hàm nhận (user_id, item_ids) → list điểm số
        info    : chuỗi mô tả checkpoint (epoch, recall@10)
        hoặc (None, None) nếu không load được
    """
    if not ckpt_path.exists():
        print(f"  [bỏ qua] Không tìm thấy checkpoint: {ckpt_path}")
        return None, None

    # Đọc checkpoint
    ckpt = torch.load(ckpt_path, map_location=device, weights_only=False)
    cfg  = ckpt["cfg"]

    # Kiểm tra xem checkpoint có tương thích với dữ liệu hiện tại không
    ckpt_n_entities = cfg.get("n_entities", 0)
    ckg_n_entities  = int(ckg[:, [0, 2]].max()) + 1
    if ckpt_n_entities < ckg_n_entities:
        print(
            f"  [bỏ qua] Checkpoint không tương thích với dữ liệu hiện tại. "
            f"(checkpoint có {ckpt_n_entities} entities, dữ liệu cần >= {ckg_n_entities}). "
            f"Hãy train lại mô hình."
        )
        return None, None

    # Khởi tạo và load trọng số mô hình
    from ranking.model import KGAT
    model = KGAT(cfg).to(device)
    model.load_state_dict(ckpt["state_dict"])
    model.eval()

    # Tính embedding cho tất cả các entity một lần (để tái sử dụng khi scoring)
    ckg_tensor = torch.from_numpy(ckg).long().to(device)
    with torch.no_grad():
        entity_emb = model(ckg_tensor[:, 0], ckg_tensor[:, 1], ckg_tensor[:, 2]).cpu()

    # Hàm score: tính điểm giữa user và từng item bằng dot product
    def scorer(user_id: int, item_ids: list) -> list:
        user_vec  = entity_emb[user_id]
        item_vecs = entity_emb[item_ids]
        return (item_vecs * user_vec).sum(dim=-1).tolist()

    # Thông tin mô tả checkpoint
    epoch    = ckpt.get("epoch", "?")
    recall10 = ckpt.get("recall@10")
    info = f"epoch={epoch}" + (f", Recall@10={recall10:.4f}" if recall10 else "")

    return scorer, info


# ─────────────────────────────────────────────────────────────────────────────
# Hàm load tập train/val
# ─────────────────────────────────────────────────────────────────────────────

def load_train_val_split(interactions: dict) -> tuple:
    """
    Load tập train/val từ file đã lưu (để đảm bảo so sánh công bằng).
    Nếu chưa có file, tự chia bằng split_interactions.

    Trả về: (train_inter, val_inter, mô_tả_nguồn)
    """
    if KGAT_SPLIT.exists():
        raw = json.loads(KGAT_SPLIT.read_text(encoding="utf-8"))
        train_inter = {int(k): [int(x) for x in v] for k, v in raw["train_inter"].items()}
        val_inter   = {int(k): [int(x) for x in v] for k, v in raw["val_inter"].items()}
        return train_inter, val_inter, str(KGAT_SPLIT)

    # Fallback: chia ngẫu nhiên
    train_inter, val_inter = split_interactions(interactions, val_ratio=0.1, seed=42)
    return train_inter, val_inter, "tự chia (val_ratio=0.1, seed=42)"


# ─────────────────────────────────────────────────────────────────────────────
# Hàm tạo CKG chỉ từ tập train (tránh data leakage)
# ─────────────────────────────────────────────────────────────────────────────

def build_train_ckg(full_ckg: np.ndarray, train_inter: dict, n_relations: int) -> np.ndarray:
    """
    Tạo CKG chỉ dùng tập train — loại bỏ các cạnh RATE từ val/test.

    Lý do: nếu dùng toàn bộ CKG (gồm cả val), mô hình sẽ "thấy" dữ liệu test → không công bằng.
    """
    # Xóa tất cả các cạnh RATE và RATE_INV cũ khỏi CKG
    r_rate     = 0
    r_rate_inv = n_relations
    kg_only = full_ckg[(full_ckg[:, 1] != r_rate) & (full_ckg[:, 1] != r_rate_inv)]

    # Thêm lại các cạnh RATE chỉ từ tập train
    train_edges = []
    for user_id, item_list in train_inter.items():
        for item_id in item_list:
            train_edges.append((user_id, r_rate,     item_id))
            train_edges.append((item_id, r_rate_inv, user_id))

    if not train_edges:
        return kg_only

    return np.vstack([kg_only, np.array(train_edges, dtype=np.int64)])


# ─────────────────────────────────────────────────────────────────────────────
# Hàm chính
# ─────────────────────────────────────────────────────────────────────────────

def run(top_ks: list, max_users: int, save: bool) -> None:
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Thiết bị: {device}\n")

    # 1. Load dữ liệu
    print("Đang load dữ liệu ...")
    _, interactions, stats, _ = load_data()
    n_users     = stats["n_users"]
    n_items     = stats["n_items"]
    item_offset = stats["item_offset"]
    n_relations = stats["n_relations_original"]

    ckg_path = Path(__file__).parent.parent / "ranking" / "data" / "ckg_triples.npy"
    full_ckg = np.load(ckg_path)

    # 2. Chia train/val
    train_inter, val_inter, split_src = load_train_val_split(interactions)
    train_ckg = build_train_ckg(full_ckg, train_inter, n_relations)

    # Tất cả item ID (dùng để tạo danh sách ứng viên khi ranking)
    all_item_ids = list(range(item_offset, item_offset + n_items))

    print(f"  Nguồn split          : {split_src}")
    print(f"  Tương tác train      : {sum(len(v) for v in train_inter.values())}")
    print(f"  Người dùng trong val : {sum(1 for v in val_inter.values() if v)}")
    print(f"  CKG train (cạnh)     : {len(train_ckg):,} / tổng {len(full_ckg):,}")

    # 3. Khởi tạo các mô hình cần đánh giá
    print("\nĐang khởi tạo các mô hình ...")
    models = []  # danh sách (hàm_score, tên_mô_hình)

    # Baseline 1: gợi ý ngẫu nhiên
    random_rec = RandomRecommender(seed=42)
    models.append((random_rec.score, "Random"))

    # Baseline 2: gợi ý theo độ phổ biến
    popularity_rec = PopularityRecommender(train_inter)
    models.append((popularity_rec.score, "Popularity"))

    # Baseline 3: Matrix Factorization (SVD)
    print("  Đang train MF/SVD (k=64) ...")
    mf_rec = MFRecommender(train_inter, n_users, n_items, item_offset, k=64)
    models.append((mf_rec.score, "MF / SVD"))

    # Baseline 4: KGAT (Knowledge Graph Attention Network)
    kgat_scorer, kgat_info = load_kgat_scorer(KGAT_CKPT, train_ckg, device)
    if kgat_scorer:
        models.append((kgat_scorer, f"KGAT ({kgat_info})"))
    else:
        print("  [!] Không có checkpoint KGAT — bỏ qua mô hình này.")

    # 4. Đánh giá từng mô hình và in kết quả
    results = []
    name_width = max(len(name) for _, name in models) + 2

    separator = "=" * (name_width + 14 * len(top_ks) * 2)
    print(f"\n{separator}")
    print(f"  ĐÁNH GIÁ OFFLINE — Loại 1   (max_users={max_users})")
    print(separator)

    # In header bảng
    header = (
        f"{'Mô hình':<{name_width}}"
        + "".join(f"{'Recall@'+str(k):>13}" for k in top_ks)
        + "".join(f"{'NDCG@'+str(k):>13}"   for k in top_ks)
    )
    print(header)
    print("-" * len(header))

    for score_fn, name in models:
        t_start = time.time()
        row = {"model": name}
        recall_list = []
        ndcg_list   = []

        for k in top_ks:
            recall, ndcg = evaluate_rec(
                score_fn, val_inter, train_inter, all_item_ids,
                top_k=k, max_users=max_users,
            )
            recall_list.append(recall)
            ndcg_list.append(ndcg)
            row[f"recall@{k}"] = round(recall, 6)
            row[f"ndcg@{k}"]   = round(ndcg,   6)

        elapsed = time.time() - t_start
        line = (
            f"{name:<{name_width}}"
            + "".join(f"{v:>13.4f}" for v in recall_list)
            + "".join(f"{v:>13.4f}" for v in ndcg_list)
            + f"   ({elapsed:.1f}s)"
        )
        print(line)
        results.append(row)

    print("-" * len(header))

    # 5. Lưu kết quả ra file JSON
    if save:
        RESULT_DIR.mkdir(exist_ok=True)
        out_path = RESULT_DIR / "type1_comparison.json"
        out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nKết quả đã lưu: {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Loại 1: Đánh giá offline mô hình gợi ý")
    parser.add_argument("--top_k",     type=int, nargs="+", default=[10, 20],
                        help="Các giá trị K cần đánh giá (mặc định: 10 20)")
    parser.add_argument("--max_users", type=int, default=1000,
                        help="Số lượng user tối đa để đánh giá (mặc định: 1000)")
    parser.add_argument("--no_save",   action="store_true",
                        help="Không lưu kết quả ra file")
    args = parser.parse_args()

    run(top_ks=args.top_k, max_users=args.max_users, save=not args.no_save)
