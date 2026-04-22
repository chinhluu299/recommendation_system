import torch
import torch.nn as nn
import torch.nn.functional as F


class KGATLayer(nn.Module):
    def __init__(self, embed_dim: int, n_relations_ckg: int, dropout: float = 0.1):
        super().__init__()
        self.embed_dim = embed_dim

        self.rel_embed = nn.Embedding(n_relations_ckg, embed_dim)
        self.W = nn.Linear(embed_dim, embed_dim, bias=False)
        self.dropout = nn.Dropout(dropout)

        nn.init.xavier_uniform_(self.W.weight)
        nn.init.normal_(self.rel_embed.weight, std=0.01)

    def forward(
        self,
        entity_emb: torch.Tensor,
        heads: torch.Tensor,
        rels: torch.Tensor,
        tails: torch.Tensor,
    ) -> torch.Tensor:

        n_entities = entity_emb.size(0)
        D = entity_emb.size(1)

        e_h = entity_emb[heads]
        e_t = entity_emb[tails]
        e_r = self.rel_embed(rels)

        gate = torch.tanh(e_h + e_r)
        score = (e_t * gate).sum(dim=-1)

        score_shifted = score - score.max().detach()
        score_exp = torch.exp(score_shifted)

        score_sum = torch.zeros(n_entities, device=score.device)
        score_sum.scatter_add_(0, heads, score_exp)
        attn = score_exp / (score_sum[heads] + 1e-10)

        agg = torch.zeros(n_entities, D, device=entity_emb.device)
        msg = attn.unsqueeze(-1) * e_t
        agg.scatter_add_(0, heads.unsqueeze(-1).expand_as(msg), msg)

        out = self.W(entity_emb + agg)
        out = F.leaky_relu(out, 0.2)
        out = self.dropout(out)
        return out


class KGAT(nn.Module):
    def __init__(self, cfg: dict):
        super().__init__()
        n_e = cfg["n_entities"]
        n_r = cfg["n_relations_ckg"]
        d = cfg.get("embed_dim", 64)
        L = cfg.get("n_layers", 3)
        drop = cfg.get("dropout", 0.1)

        self.embed_dim = d
        self.n_layers = L
        self.l2_reg = cfg.get("l2_reg", 1e-5)
        self.out_dim = d * (L + 1)

        self.entity_embed = nn.Embedding(n_e, d)
        self.layers = nn.ModuleList(
            [KGATLayer(d, n_r, dropout=drop) for _ in range(L)]
        )

        nn.init.normal_(self.entity_embed.weight, std=0.01)

    def forward(
        self,
        heads: torch.Tensor,
        rels: torch.Tensor,
        tails: torch.Tensor,
    ) -> torch.Tensor:
        h = self.entity_embed.weight
        all_layers = [h]
        for layer in self.layers:
            h = layer(h, heads, rels, tails)
            all_layers.append(h)
        return torch.cat(all_layers, dim=-1)

    def bpr_loss(
        self,
        user_ids: torch.Tensor,
        pos_items: torch.Tensor,
        neg_items: torch.Tensor,
        entity_emb: torch.Tensor,
    ) -> torch.Tensor:
        e_u = entity_emb[user_ids]
        e_pos = entity_emb[pos_items]
        e_neg = entity_emb[neg_items]

        score_pos = (e_u * e_pos).sum(dim=1)
        score_neg = (e_u.unsqueeze(1) * e_neg).sum(dim=2)

        bpr_loss = -F.logsigmoid(score_pos.unsqueeze(1) - score_neg).mean()

        init_emb = self.entity_embed.weight
        l2_loss = (
            init_emb[user_ids].norm(2, dim=-1).pow(2).mean() +
            init_emb[pos_items].norm(2, dim=-1).pow(2).mean() +
            init_emb[neg_items].norm(2, dim=-1).pow(2).mean() +
            entity_emb[user_ids].norm(2, dim=-1).pow(2).mean() +
            entity_emb[pos_items].norm(2, dim=-1).pow(2).mean() +
            entity_emb[neg_items].norm(2, dim=-1).pow(2).mean()
        ) / 6.0

        return bpr_loss + self.l2_reg * l2_loss

    def score(
        self,
        user_ids: torch.Tensor,
        item_ids: torch.Tensor,
        entity_emb: torch.Tensor,
    ) -> torch.Tensor:
        return (entity_emb[user_ids] * entity_emb[item_ids]).sum(-1)
