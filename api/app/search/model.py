"""KGAT model — Wang et al. KDD 2019."""
import torch
import torch.nn as nn
import torch.nn.functional as F


class KGATLayer(nn.Module):
    def __init__(self, embed_dim: int, n_relations_ckg: int, dropout: float = 0.1):
        super().__init__()
        self.embed_dim = embed_dim
        self.rel_embed = nn.Embedding(n_relations_ckg, embed_dim)
        self.W         = nn.Linear(embed_dim, embed_dim, bias=False)
        self.dropout   = nn.Dropout(dropout)
        nn.init.xavier_uniform_(self.W.weight)
        nn.init.normal_(self.rel_embed.weight, std=0.01)

    def forward(self, entity_emb, heads, rels, tails):
        n, D   = entity_emb.size()
        e_h    = entity_emb[heads]
        e_t    = entity_emb[tails]
        e_r    = self.rel_embed(rels)
        gate   = torch.tanh(e_h + e_r)
        score  = (e_t * gate).sum(dim=-1)
        score  = score - score.max().detach()
        exp_s  = torch.exp(score)
        s_sum  = torch.zeros(n, device=score.device)
        s_sum.scatter_add_(0, heads, exp_s)
        attn   = exp_s / (s_sum[heads] + 1e-10)
        agg    = torch.zeros(n, D, device=entity_emb.device)
        agg.scatter_add_(0, heads.unsqueeze(-1).expand_as(attn.unsqueeze(-1) * e_t),
                         attn.unsqueeze(-1) * e_t)
        return F.leaky_relu(self.W(entity_emb + agg), 0.2)


class KGAT(nn.Module):
    def __init__(self, cfg: dict):
        super().__init__()
        d, L = cfg.get("embed_dim", 64), cfg.get("n_layers", 3)
        self.embed_dim    = d
        self.n_layers     = L
        self.l2_reg       = cfg.get("l2_reg", 1e-5)
        self.out_dim      = d * (L + 1)
        self.entity_embed = nn.Embedding(cfg["n_entities"], d)
        self.layers       = nn.ModuleList(
            [KGATLayer(d, cfg["n_relations_ckg"], cfg.get("dropout", 0.1)) for _ in range(L)]
        )
        nn.init.normal_(self.entity_embed.weight, std=0.01)

    def forward(self, heads, rels, tails):
        h = self.entity_embed.weight
        layers = [h]
        for layer in self.layers:
            h = layer(h, heads, rels, tails)
            layers.append(h)
        return torch.cat(layers, dim=-1)

    def bpr_loss(self, user_ids, pos_items, neg_items, entity_emb):
        e_u   = entity_emb[user_ids]
        e_pos = entity_emb[pos_items]
        e_neg = entity_emb[neg_items]
        score_pos = (e_u * e_pos).sum(dim=1)
        score_neg = (e_u.unsqueeze(1) * e_neg).sum(dim=2)
        bpr = -F.logsigmoid(score_pos.unsqueeze(1) - score_neg).mean()
        init = self.entity_embed.weight
        l2 = (
            init[user_ids].norm(2, dim=-1).pow(2).mean() +
            init[pos_items].norm(2, dim=-1).pow(2).mean() +
            init[neg_items].norm(2, dim=-1).pow(2).mean() +
            entity_emb[user_ids].norm(2, dim=-1).pow(2).mean() +
            entity_emb[pos_items].norm(2, dim=-1).pow(2).mean() +
            entity_emb[neg_items].norm(2, dim=-1).pow(2).mean()
        ) / 6.0
        return bpr + self.l2_reg * l2

    def score(self, user_ids, item_ids, entity_emb):
        return (entity_emb[user_ids] * entity_emb[item_ids]).sum(-1)
