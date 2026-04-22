import argparse
import json
import pickle
import random
import time
from pathlib import Path

import numpy as np
import torch
import torch.optim as optim

from offline.ranking.model import KGAT

DATA_DIR = Path(__file__).parent / "data"
CKPT_DIR = Path(__file__).parent / "checkpoints"
CKPT_DIR.mkdir(exist_ok=True)
SPLIT_FILE = CKPT_DIR / "kgat_split.json"


def load_data():
    for name in ["entity2id.json", "relation2id.json", "interactions.pkl",
                 "ckg_triples.npy", "stats.json"]:
        if not (DATA_DIR / name).exists():
            raise FileNotFoundError(
                f"Thiếu file {name}. Chạy: python -m ranking.build_data"
            )

    entity2id = json.loads((DATA_DIR / "entity2id.json").read_text())
    relation2id = json.loads((DATA_DIR / "relation2id.json").read_text())
    stats = json.loads((DATA_DIR / "stats.json").read_text())
    with open(DATA_DIR / "interactions.pkl", "rb") as f:
        interactions = pickle.load(f)
    ckg = np.load(DATA_DIR / "ckg_triples.npy")

    return entity2id, relation2id, interactions, ckg, stats


class BPRSampler:
    MAX_RETRY = 20

    def __init__(self, interactions: dict, n_items: int, item_offset: int):
        self.interactions = interactions
        self.item_offset = item_offset
        self.item_max = item_offset + n_items - 1
        self.user_list = list(interactions.keys())

    def sample(self, batch_size: int, n_negs: int = 5, entity_emb: torch.Tensor = None, hard_ratio: float = 0.0) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        users, pos_items, neg_items = [], [], []

        n_hard = int(n_negs * hard_ratio) if entity_emb is not None else 0
        n_random = n_negs - n_hard

        while len(users) < batch_size:
            u = random.choice(self.user_list)
            pos_set = self.interactions[u]
            if not pos_set:
                continue
            i_pos = random.choice(pos_set)

            u_negs = []
            while len(u_negs) < n_random:
                i_neg = random.randint(self.item_offset, self.item_max)
                if i_neg not in pos_set:
                    u_negs.append(i_neg)

            if n_hard > 0:
                hard_negs = self._sample_hard_negs(u, pos_set, entity_emb, n_hard)
                u_negs.extend(hard_negs)

            users.append(u)
            pos_items.append(i_pos)
            neg_items.append(u_negs)

        return (
            torch.tensor(users, dtype=torch.long),
            torch.tensor(pos_items, dtype=torch.long),
            torch.tensor(neg_items, dtype=torch.long),
        )

    def _sample_hard_negs(
        self,
        u: int,
        pos_set: set,
        entity_emb: torch.Tensor,
        n_hard: int,
        pool_size: int = 100,
    ) -> list[int]:
        pool = []
        attempts = 0
        while len(pool) < pool_size and attempts < pool_size * 3:
            i = random.randint(self.item_offset, self.item_max)
            if i not in pos_set:
                pool.append(i)
            attempts += 1

        if not pool:
            return []

        with torch.no_grad():
            u_emb = entity_emb[u]
            pool_ids = torch.tensor(pool, dtype=torch.long,
                                    device=entity_emb.device)
            i_embs = entity_emb[pool_ids]
            scores = (i_embs @ u_emb)

            k = min(n_hard, len(pool))
            top_idx = torch.topk(scores, k).indices.cpu().tolist()

        return [pool[idx] for idx in top_idx]


def split_interactions(
    interactions: dict,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[dict, dict]:
    rng = random.Random(seed)
    train = {}
    val = {}

    for u, items in interactions.items():
        if len(items) < 2:
            train[u] = items[:]
            continue
        shuffled = items[:]
        rng.shuffle(shuffled)
        n_val = max(1, int(len(shuffled) * val_ratio))
        train[u] = shuffled[:-n_val]
        val[u] = shuffled[-n_val:]

    return train, val


def build_fixed_split(
    interactions: dict,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[dict, dict]:
    rng = random.Random(seed)
    train = {}
    val = {}
    for u in sorted(interactions.keys()):
        items = sorted(set(interactions[u]))
        if len(items) < 2:
            train[u] = items[:]
            continue
        shuffled = items[:]
        rng.shuffle(shuffled)
        n_val = max(1, int(len(shuffled) * val_ratio))
        train[u] = shuffled[:-n_val]
        val[u] = shuffled[-n_val:]
    return train, val


def load_or_create_split(
    interactions: dict,
    split_file: Path,
    val_ratio: float = 0.1,
    seed: int = 42,
) -> tuple[dict, dict]:
    if split_file.exists():
        raw = json.loads(split_file.read_text(encoding="utf-8"))
        train_raw = raw.get("train_inter", {})
        val_raw = raw.get("val_inter", {})
        train = {int(k): [int(x) for x in v] for k, v in train_raw.items()}
        val = {int(k): [int(x) for x in v] for k, v in val_raw.items()}
        return train, val

    train, val = build_fixed_split(interactions, val_ratio=val_ratio, seed=seed)
    payload = {
        "seed": seed,
        "val_ratio": val_ratio,
        "train_inter": {str(k): v for k, v in train.items()},
        "val_inter": {str(k): v for k, v in val.items()},
    }
    split_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return train, val


def build_train_only_ckg(
    ckg: np.ndarray,
    train_inter: dict,
    n_relations_original: int,
) -> np.ndarray:
    r_rate = 0
    r_rate_inv = n_relations_original

    kg_only = ckg[(ckg[:, 1] != r_rate) & (ckg[:, 1] != r_rate_inv)]

    train_rate = []
    for u, items in train_inter.items():
        for p in items:
            train_rate.append((u, r_rate, p))
            train_rate.append((p, r_rate_inv, u))

    if not train_rate:
        return kg_only

    train_rate_arr = np.array(train_rate, dtype=np.int64)
    return np.vstack([kg_only, train_rate_arr])


@torch.no_grad()
def evaluate(
    entity_emb: torch.Tensor,
    val_inter: dict,
    train_inter: dict,
    item_ids: torch.Tensor,
    top_k: int = 10,
    max_users: int = 1000,
) -> tuple[float, float]:
    device = entity_emb.device
    e_items = entity_emb[item_ids]
    item_set = set(item_ids.tolist())

    users = list(val_inter.keys())[:max_users]
    recall_list, ndcg_list = [], []

    for u in users:
        pos_val = val_inter.get(u, [])
        if not pos_val:
            continue

        e_u = entity_emb[u].unsqueeze(0)
        scores = (e_u * e_items).sum(-1)

        for p in train_inter.get(u, []):
            if p in item_set:
                idx = (item_ids == p).nonzero(as_tuple=True)[0]
                if len(idx):
                    scores[idx[0]] = -1e9

        topk_indices = scores.topk(top_k).indices
        topk_items = set(item_ids[topk_indices].tolist())

        relevant = set(pos_val) & item_set
        if not relevant:
            continue

        hits = relevant & topk_items
        recall_list.append(len(hits) / len(relevant))

        ndcg = 0.0
        for p in hits:
            rank = topk_indices.tolist().index(
                (item_ids == p).nonzero(as_tuple=True)[0].item()
            ) + 1
            ndcg += 1.0 / np.log2(rank + 1)
        ideal = sum(1.0 / np.log2(i + 2) for i in range(min(len(relevant), top_k)))
        ndcg_list.append(ndcg / ideal if ideal > 0 else 0.0)

    recall = float(np.mean(recall_list)) if recall_list else 0.0
    ndcg = float(np.mean(ndcg_list)) if ndcg_list else 0.0
    return recall, ndcg


def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Device : {device}")

    print("Loading data ...")
    entity2id, relation2id, interactions, ckg, stats = load_data()

    n_entities = stats["n_entities"]
    n_relations = stats["n_relations_original"]
    n_rel_ckg = 2 * n_relations
    n_items = stats["n_items"]
    item_offset = stats["item_offset"]

    print(f"  entities={n_entities}, items={n_items}, "
          f"item_offset={item_offset}, CKG triples={len(ckg)}")

    train_inter, val_inter = load_or_create_split(
        interactions=interactions,
        split_file=SPLIT_FILE,
        val_ratio=0.1,
        seed=42,
    )

    ckg_train = build_train_only_ckg(
        ckg=ckg,
        train_inter=train_inter,
        n_relations_original=n_relations,
    )

    ckg_t = torch.from_numpy(ckg_train).long().to(device)
    ckg_heads = ckg_t[:, 0]
    ckg_rels = ckg_t[:, 1]
    ckg_tails = ckg_t[:, 2]
    n_pos = sum(len(v) for v in train_inter.values())
    steps_epoch = max(1, n_pos // args.batch_size)

    item_ids = torch.arange(item_offset, item_offset + n_items,
                            dtype=torch.long, device=device)

    cfg = {
        "n_entities": n_entities,
        "n_relations_ckg": n_rel_ckg,
        "embed_dim": args.embed_dim,
        "n_layers": args.n_layers,
        "dropout": args.dropout,
        "l2_reg": args.l2_reg,
    }
    model = KGAT(cfg).to(device)
    opt = optim.Adam(model.parameters(), lr=args.lr)
    sched = optim.lr_scheduler.StepLR(opt, step_size=10, gamma=0.5)
    sampler = BPRSampler(train_inter, n_items, item_offset)

    best_recall = 0.0
    history = []

    print(f"\nTraining: epochs={args.epochs}, batch={args.batch_size}, "
          f"steps/epoch={steps_epoch}, lr={args.lr}")
    print(f"Model   : embed_dim={args.embed_dim}, n_layers={args.n_layers}, "
          f"out_dim={model.out_dim}\n")
    print(f"Fixed split file: {SPLIT_FILE}")
    print(f"CKG edges (train-only): {len(ckg_train):,}  |  original: {len(ckg):,}\n")

    for epoch in range(1, args.epochs + 1):
        model.train()
        t0 = time.time()
        total_loss = 0.0

        for _ in range(steps_epoch):
            opt.zero_grad()

            entity_emb = model(ckg_heads, ckg_rels, ckg_tails)

            if epoch < 2:
                users, pos_items, neg_items = sampler.sample(args.batch_size, n_negs=2)
            else:
                users, pos_items, neg_items = sampler.sample(
                    args.batch_size,
                    n_negs=2,
                    entity_emb=entity_emb.detach(),
                    hard_ratio=0.5,
                )

            users, pos_items, neg_items = (
                users.to(device), pos_items.to(device), neg_items.to(device)
            )

            loss = model.bpr_loss(users, pos_items, neg_items, entity_emb)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
            opt.step()
            total_loss += loss.item()

        sched.step()
        avg_loss = total_loss / steps_epoch
        elapsed = time.time() - t0

        recall, ndcg = 0.0, 0.0
        model.eval()
        with torch.no_grad():
            entity_emb_eval = model(ckg_heads, ckg_rels, ckg_tails)
        recall, ndcg = evaluate(
            entity_emb_eval, val_inter, train_inter, item_ids, top_k=10
        )

        if recall > best_recall:
            best_recall = recall
            torch.save(
                {
                    "epoch": epoch,
                    "cfg": cfg,
                    "state_dict": model.state_dict(),
                    "recall@10": recall,
                    "ndcg@10": ndcg,
                    "loss": avg_loss,
                },
                CKPT_DIR / "best_model.pt",
            )
            print(f"  [*] New best  Recall@10={recall:.4f}  NDCG@10={ndcg:.4f}")

        row = {
            "epoch": epoch,
            "loss": round(avg_loss, 6),
            "recall10": round(recall, 6),
            "ndcg10": round(ndcg, 6),
        }
        history.append(row)

        print(
            f"Epoch {epoch:3d}/{args.epochs}  "
            f"loss={avg_loss:.4f}  "
            f"Recall@10={recall:.4f}  NDCG@10={ndcg:.4f}  "
            f"({elapsed:.1f}s)"
        )

    torch.save(
        {"epoch": args.epochs, "cfg": cfg, "state_dict": model.state_dict()},
        CKPT_DIR / "last_model.pt",
    )
    (CKPT_DIR / "history.json").write_text(
        json.dumps(history, indent=2), encoding="utf-8"
    )

    print(f"\nDone.  Best Recall@10 = {best_recall:.4f}")
    print(f"Checkpoints: {CKPT_DIR}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Train KGAT ranking model")
    p.add_argument("--epochs", type=int, default=20, help="số epochs")
    p.add_argument("--batch_size", type=int, default=1024, help="batch size cho BPR sampler")
    p.add_argument("--lr", type=float, default=5e-5, help="learning rate (Adam)")
    p.add_argument("--embed_dim", type=int, default=64, help="chiều embedding")
    p.add_argument("--n_layers", type=int, default=3, help="số lớp KGAT")
    p.add_argument("--dropout", type=float, default=0.1, help="dropout rate")
    p.add_argument("--l2_reg", type=float, default=1e-5, help="L2 regularisation weight")
    args = p.parse_args()
    train(args)
