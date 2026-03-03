# Ranking – KGAT Personalized Re-ranker

## Vị trí trong pipeline

```
User query (tiếng Việt)
    │
    ▼
NL → Cypher  (query_engine/nl2cypher.py)
    │
    ▼
Neo4j KG query  →  top-K sản phẩm thô  (query_engine/graph_search.py)
    │
    ▼
KGAT Re-ranker  →  top-K đã personalize  ← [ranking/rerank.py]
    │
    ▼
LLM format answer  (query_engine/pipeline.py)
```

Query engine trả về sản phẩm khớp với **điều kiện lọc** (brand, price, feature…)
nhưng thứ tự là ngẫu nhiên hoặc theo Neo4j internal order.
KGAT re-ranker sắp xếp lại danh sách đó dựa trên **lịch sử rating của từng user**
và **cấu trúc Knowledge Graph**, cho ra ranking cá nhân hoá.

---

## Tại sao dùng KGAT?

### Vấn đề với CF thuần (BPR-MF, LightGCN)

Collaborative Filtering chỉ học từ ma trận user-item (RATE edges).
Dataset có **20 283 users × 1 179 items** và **26 167 interactions** dương tính,
tức là mật độ matrix = 0.11% — rất sparse. CF thuần sẽ bị cold-start nặng
cho items ít được rate và users mới.

### Tại sao KG giúp ích?

Knowledge Graph bổ sung thông tin phụ (side information) cho items:

| Quan hệ | Ý nghĩa |
|---|---|
| MANUFACTURED_BY | Item → Brand |
| BELONGS_TO | Item → Category |
| HAS_FEATURE | Item → Feature text |
| USES_TECHNOLOGY | Item → Technology |
| SUPPORTS_CARRIER | Item → Carrier |
| HAS_SPEC | Item → Spec (RAM, Storage) |
| SOLD_BY | Item → Store |
| INCLUDES_ACCESSORY | Item → Accessory |

Nếu user A thích item X (Samsung, 4G LTE), và user A chưa tương tác với item Y
(cũng Samsung, 4G LTE), KG cho phép model suy luận user A có thể thích Y — điều
CF thuần không làm được.

### Tại sao KGAT cụ thể?

KGAT (Wang et al., KDD 2019) dùng **graph attention** thay vì uniform aggregation:

- Với mỗi entity `h`, attention `π(h, r, t)` học mức độ quan trọng của
  neighbor `t` qua quan hệ `r`.
- Ví dụ: với user thích điện thoại Samsung, neighbor "Brand=Samsung" được
  assign attention cao hơn "Accessory=USB Cable" khi tính embedding.
- Multi-hop propagation (3 lớp) cho phép model nắm bắt thông tin từ xa:
  user → item → brand → other items cùng brand.

So sánh nhanh:

| Model | Dùng KG? | Personalized? | Attention? |
|---|---|---|---|
| BPR-MF | ✗ | ✓ | ✗ |
| LightGCN | ✗ | ✓ | ✗ |
| KGCN | ✓ | ✓ | ✗ (uniform) |
| **KGAT** | **✓** | **✓** | **✓ (per-relation)** |

---

## Kiến trúc KGAT

### Collaborative Knowledge Graph (CKG)

Ghép **user-item interactions** và **KG triples** thành một đồ thị thống nhất:

```
CKG = {(u, RATE, i) : u rate i ≥ 3.0}
    ∪ {(i, RATE_inv, u) : inverse}
    ∪ {(h, r, t) : các KG edges}
    ∪ {(t, r_inv, h) : inverse KG edges}
```

Số nodes: 27 989  |  Số CKG triples: ~95 000 (47 503 × 2)

### Embedding Layer

Mỗi entity và relation được gán một vector khởi tạo:
```
E ∈ R^(27989 × 64)   — entity embeddings
R ∈ R^(22 × 64)      — relation embeddings (11 gốc × 2 với inverse)
```

### KGAT Propagation Layer (×3)

Với mỗi head entity `h`:

```
Attention score:
  π(h, r, t) = softmax_{(r,t)∈N(h)}( e_t^T · tanh(e_h + e_r) )

Aggregation:
  e_h^{agg} = Σ π(h,r,t) · e_t

Update:
  e_h^{l+1} = LeakyReLU( W · (e_h^l + e_h^{agg}) )
```

Lý do dùng `tanh(e_h + e_r)` làm gate thay vì chỉ `e_h`:
relation embedding `e_r` inject context "đang đi qua quan hệ r", giúp model
phân biệt "user thích item vì brand" khác "user thích item vì technology".

### Prediction

```
final_emb   = concat(e^0, e^1, e^2, e^3)   # (27989, 256)
score(u, i) = final_emb[u] · final_emb[i]
```

Concat multi-layer giúp model nắm thông tin 0-hop (ban đầu), 1-hop, 2-hop,
3-hop cùng lúc — mỗi hop capture level of connectivity khác nhau.

### BPR Loss

```
L = -Σ_{(u,i⁺,i⁻)} log σ(score(u,i⁺) - score(u,i⁻))  +  λ·||E||²
```

- **Negative sampling**: với mỗi `(u, i_pos)`, chọn ngẫu nhiên `i_neg` không
  thuộc positive set của u.
- **L2 reg** chỉ trên initial embeddings, tránh over-penalise attention weights.
- **Positive threshold**: RATE ≥ 3.0 được coi là positive.

---

## Files

```
ranking/
├── build_data.py    Đọc knowledge_graph/output/ JSON → serialize training data
├── model.py         Kiến trúc KGAT (KGATLayer + KGAT + BPR loss)
├── train.py         Training loop, BPR sampler, Recall@10 / NDCG@10 evaluation
├── rerank.py        KGATReranker: load checkpoint → re-rank records từ pipeline
├── data/            (auto-generated bởi build_data.py)
│   ├── entity2id.json
│   ├── relation2id.json
│   ├── interactions.pkl
│   ├── ckg_triples.npy
│   └── stats.json
└── checkpoints/     (auto-generated bởi train.py)
    ├── best_model.pt
    ├── last_model.pt
    └── history.json
```

---

## Cách chạy

```bash
# Từ thư mục ver2/

# 1. Tạo dữ liệu huấn luyện
python -m ranking.build_data

# 2. Huấn luyện (mặc định 30 epochs, embed_dim=64, 3 layers)
python -m ranking.train

# Tuỳ chỉnh hyperparameter
python -m ranking.train --epochs 50 --embed_dim 64 --n_layers 3 --lr 1e-3
```

---

## Tích hợp vào pipeline

```python
from ranking.rerank import KGATReranker
from query_engine.pipeline import ask

ranker = KGATReranker()   # load một lần, giữ trong memory

result = ask("điện thoại Samsung pin lớn")

# Re-rank theo personalization
ranked = ranker.rerank_records(
    user_id="AHATA6X6MYTC3VNBFJ3WIYVK257A",
    records=result.records,
)
```

### Cold-start

Nếu `user_id` chưa xuất hiện trong tập train, reranker tự động dùng
**centroid embedding** của toàn bộ users (trung bình hoá → profile "user trung bình").
Kết quả vẫn có chất lượng hơn random vì KG side information của items vẫn được
tận dụng — sản phẩm có nhiều đặc điểm nổi bật trong KG sẽ được rank cao hơn.

---

## Hyperparameters mặc định

| Param | Giá trị | Lý do |
|---|---|---|
| embed_dim | 64 | Cân bằng capacity vs. tốc độ với 28K entities |
| n_layers | 3 | Bắt đầu capture 3-hop: user→item→brand→related_item |
| dropout | 0.1 | Nhẹ nhàng, tránh underfit trên sparse data |
| l2_reg | 1e-5 | Standard cho recommendation models |
| lr | 1e-3 | Adam, giảm ×0.5 mỗi 10 epochs |
| batch_size | 1024 | Phù hợp memory CPU/GPU |
| pos_threshold | 3.0 | Neutral/positive trên thang 1-5 |

---

## Metrics đánh giá

- **Recall@10**: tỷ lệ relevant items xuất hiện trong top-10
- **NDCG@10**: Normalised Discounted Cumulative Gain, thưởng item ở rank cao hơn

Đánh giá theo **leave-10%-out**: 10% interactions cuối của mỗi user dùng làm val set.
