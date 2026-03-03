#!/usr/bin/env python3
"""
model.py – KGAT (Knowledge Graph Attention Network) for recommendation ranking.

Tham khảo: Wang et al. 2019, "KGAT: Knowledge Graph Attention Network for
Recommendation", KDD 2019. https://arxiv.org/abs/1905.07854

─── Kiến trúc tổng quan ────────────────────────────────────────────────────────

  1. Embedding Layer
     Mỗi entity (user, item, brand, ...) và relation trong CKG có một vector
     embedding khởi tạo ngẫu nhiên: E ∈ R^(n_entities × d).

  2. KGAT Propagation Layers (L lớp)
     Mỗi lớp thực hiện attentive aggregation trên CKG:

       Attention score cho cạnh (h, r, t):
         π(h, r, t) = softmax_{N(h)}( e_t^T · tanh(e_h + e_r) )

       Aggregate hàng xóm:
         e_h^{agg} = Σ_{(r,t)∈N(h)} π(h,r,t) · e_t

       Update embedding:
         e_h^{l+1} = LeakyReLU( W · (e_h^l + e_h^{agg}) )

     Cơ chế attention cho phép mô hình học mức độ quan trọng của từng neighbor
     dựa trên ngữ cảnh quan hệ — ví dụ item cùng brand được trọng số cao hơn
     item cùng accessory khi tính toán embedding cho user thích thương hiệu đó.

  3. Prediction Layer
     Final embedding = concat(e^0, e^1, ..., e^L)  — kết hợp thông tin đa-hop.
     Score(user u, item i) = e_u^T · e_i

  4. BPR Loss
     L_BPR = -Σ ln σ(score(u, i_pos) - score(u, i_neg)) + λ·||Θ||²
     Dùng negative sampling: với mỗi (u, i_pos), chọn ngẫu nhiên i_neg ∉ N(u).
"""

import torch
import torch.nn as nn
import torch.nn.functional as F


class KGATLayer(nn.Module):
    """
    Một lớp propagation của KGAT.

    Với mỗi head entity h, tính attention-weighted sum của neighbor embeddings:
      - Attention score : π(h,r,t) ∝ exp( e_t^T · tanh(e_h + e_r) )
      - Softmax được chuẩn hoá per-head (trên toàn bộ N(h))
      - Output         : LeakyReLU( W · (e_h + Σ π·e_t) )

    Args:
        embed_dim      : chiều embedding
        n_relations_ckg: số quan hệ trong CKG (bao gồm inverse)
        dropout        : dropout rate
    """

    def __init__(self, embed_dim: int, n_relations_ckg: int, dropout: float = 0.1):
        super().__init__()
        self.embed_dim = embed_dim

        # Relation embedding dùng để tính attention gate
        self.rel_embed = nn.Embedding(n_relations_ckg, embed_dim)
        # Projection sau aggregation
        self.W         = nn.Linear(embed_dim, embed_dim, bias=False)
        self.dropout   = nn.Dropout(dropout)

        nn.init.xavier_uniform_(self.W.weight)
        nn.init.normal_(self.rel_embed.weight, std=0.01)

    def forward(
        self,
        entity_emb: torch.Tensor,   # (n_entities, D)
        heads:      torch.Tensor,   # (n_edges,)  int64 — head entity IDs
        rels:       torch.Tensor,   # (n_edges,)  int64 — relation IDs
        tails:      torch.Tensor,   # (n_edges,)  int64 — tail entity IDs
    ) -> torch.Tensor:              # (n_entities, D)

        n_entities = entity_emb.size(0)
        D          = entity_emb.size(1)

        e_h = entity_emb[heads]          # (E, D)
        e_t = entity_emb[tails]          # (E, D)
        e_r = self.rel_embed(rels)        # (E, D)

        # ── Attention score ────────────────────────────────────────────────
        # gate = tanh(e_h + e_r) : "contextualised" head embedding
        # score = e_t^T · gate   : how relevant is tail t given (h, r)?
        gate  = torch.tanh(e_h + e_r)           # (E, D)
        score = (e_t * gate).sum(dim=-1)         # (E,)

        # ── Per-head softmax ───────────────────────────────────────────────
        # Dùng global-max shift để ổn định số học.
        # Chứng minh: với bất kỳ hằng số C nào,
        #   exp(s - C) / Σ_t exp(s_t - C) = exp(s) / Σ_t exp(s_t)
        # nên normalization không bị ảnh hưởng bởi shift toàn cục.
        score_shifted = score - score.max().detach()
        score_exp     = torch.exp(score_shifted)                     # (E,)

        score_sum = torch.zeros(n_entities, device=score.device)
        score_sum.scatter_add_(0, heads, score_exp)
        attn = score_exp / (score_sum[heads] + 1e-10)                # (E,)

        # ── Attentive aggregation ──────────────────────────────────────────
        agg     = torch.zeros(n_entities, D, device=entity_emb.device)
        msg     = attn.unsqueeze(-1) * e_t                           # (E, D)
        agg.scatter_add_(0, heads.unsqueeze(-1).expand_as(msg), msg) # (N, D)

        # ── Update ────────────────────────────────────────────────────────
        out = self.W(entity_emb + agg)       # residual connection
        out = F.leaky_relu(out, 0.2)
        out = self.dropout(out)
        return out                           # (N, D)


class KGAT(nn.Module):
    """
    Mô hình KGAT hoàn chỉnh.

    Config dict (cfg):
      n_entities      : tổng số entity (user + item + KG entities)
      n_relations_ckg : số quan hệ trong CKG = 2 × n_relations_original
      embed_dim       : chiều embedding cơ sở             (default 64)
      n_layers        : số lớp KGAT                       (default 3)
      dropout         : dropout rate                      (default 0.1)
      l2_reg          : hệ số L2 regularisation           (default 1e-5)

    Forward:
      Trả về entity embeddings sau propagation, shape (n_entities, embed_dim*(n_layers+1))
      — concat các output từ lớp 0 (initial) đến lớp L.
      Concat đa-lớp giúp model nắm thông tin ở nhiều mức hop khác nhau.
    """

    def __init__(self, cfg: dict):
        super().__init__()
        n_e  = cfg["n_entities"]
        n_r  = cfg["n_relations_ckg"]
        d    = cfg.get("embed_dim", 64)
        L    = cfg.get("n_layers", 3)
        drop = cfg.get("dropout", 0.1)

        self.embed_dim = d
        self.n_layers  = L
        self.l2_reg    = cfg.get("l2_reg", 1e-5)
        self.out_dim   = d * (L + 1)          # chiều sau concat

        self.entity_embed = nn.Embedding(n_e, d)
        self.layers       = nn.ModuleList(
            [KGATLayer(d, n_r, dropout=drop) for _ in range(L)]
        )

        nn.init.normal_(self.entity_embed.weight, std=0.01)

    # ── Forward ───────────────────────────────────────────────────────────────

    def forward(
        self,
        heads: torch.Tensor,    # (n_edges,) int64
        rels:  torch.Tensor,    # (n_edges,) int64
        tails: torch.Tensor,    # (n_edges,) int64
    ) -> torch.Tensor:          # (n_entities, out_dim)
        """
        Thực hiện L lớp message passing trên CKG.
        Trả về embedding sau khi concat tất cả các lớp (đa-hop representation).
        """
        h          = self.entity_embed.weight       # (N, D) — layer 0
        all_layers = [h]
        for layer in self.layers:
            h = layer(h, heads, rels, tails)
            all_layers.append(h)
        return torch.cat(all_layers, dim=-1)         # (N, D*(L+1))

    # ── BPR Loss ──────────────────────────────────────────────────────────────

    def bpr_loss(
        self,
        user_ids:   torch.Tensor,   # (B,) int64
        pos_items:  torch.Tensor,   # (B,) int64
        neg_items:  torch.Tensor,   # (B,) int64
        entity_emb: torch.Tensor,   # (N, out_dim) từ forward()
    ) -> torch.Tensor:              # scalar
        """
        Bayesian Personalised Ranking loss + L2 regularisation.

        BPR muốn model rank positive item cao hơn negative item:
          L = -mean( log σ(score_pos - score_neg) ) + λ·||init_emb||²

        L2 chỉ penalise initial embeddings (entity_embed.weight) — tránh
        over-regularise các output của attention layers.
        """
        e_u   = entity_emb[user_ids]    # (B, D*)
        e_pos = entity_emb[pos_items]   # (B, D*)
        e_neg = entity_emb[neg_items]   # (B, D*)

        # score_pos = (e_u * e_pos).sum(-1)   # (B,)
        # score_neg = (e_u * e_neg).sum(-1)   # (B,)

        # bpr_loss = -F.logsigmoid(score_pos - score_neg).mean()
        
        score_pos = (e_u * e_pos).sum(dim=1)                     # (B,)
        score_neg = (e_u.unsqueeze(1) * e_neg).sum(dim=2)        # (B, n_negs)

        # unsqueeze score_pos → (B, 1) để broadcast đúng với (B, n_negs)
        bpr_loss = -F.logsigmoid(score_pos.unsqueeze(1) - score_neg).mean()
        # L2 trên initial embeddings của các entity trong batch
        init_emb = self.entity_embed.weight
        # l2_loss  = (
        #     init_emb[user_ids ].norm(2, dim=-1).pow(2).mean() +
        #     init_emb[pos_items].norm(2, dim=-1).pow(2).mean() +
        #     init_emb[neg_items].norm(2, dim=-1).pow(2).mean()
        # ) / 3.0
        l2_loss = (
            init_emb[user_ids].norm(2, dim=-1).pow(2).mean() +
            init_emb[pos_items].norm(2, dim=-1).pow(2).mean() +
            init_emb[neg_items].norm(2, dim=-1).pow(2).mean() +
            # thêm output embeddings
            entity_emb[user_ids].norm(2, dim=-1).pow(2).mean() +
            entity_emb[pos_items].norm(2, dim=-1).pow(2).mean() +
            entity_emb[neg_items].norm(2, dim=-1).pow(2).mean()
        ) / 6.0

        return bpr_loss + self.l2_reg * l2_loss

    # ── Score ─────────────────────────────────────────────────────────────────

    def score(
        self,
        user_ids:   torch.Tensor,   # (B,)
        item_ids:   torch.Tensor,   # (B,)
        entity_emb: torch.Tensor,   # (N, out_dim)
    ) -> torch.Tensor:              # (B,)
        """Tính personalised score cho từng cặp (user, item)."""
        return (entity_emb[user_ids] * entity_emb[item_ids]).sum(-1)
