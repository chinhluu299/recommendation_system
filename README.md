# Recommendation System

Hệ thống gợi ý điện thoại sử dụng **Knowledge Graph (Neo4j) + LLM + KGAT**.

- `offline/` — Training pipeline (build KG, vector index, KGAT)
- `api/` — Backend (FastAPI)
- `web/` — Frontend (Next.js)
- `evaluation/` — Đánh giá baseline vs proposed

## Yêu cầu

- Python 3.11+, Node.js 20+
- Neo4j (database `recphones`) chạy tại `bolt://localhost:7687`
- LLM endpoint OpenAI-compatible tại `http://localhost:1234/v1` (vd LM Studio với `gpt-oss-20b`)

---

## A. Offline — chuẩn bị dữ liệu & train (chạy trước)

Chạy tuần tự trong thư mục `offline/`:

```bash
cd offline

# 1) Build Knowledge Graph từ meta_filtered.csv + reviews_filtered.csv vào Neo4j
python3 knowledge_graph/build_graph.py
# Sau khi build graph thì add data vào neo4j
python3 knowledge_graph/neo4j/convert_to_csv.py
python3 knowledge_graph/neo4j/import_all.py
# 2) Nạp text embedding vào Neo4j (tạo product_text_index dùng cho semantic search)
python3 knowledge_graph/build_vector_index.py

# 3) Build dữ liệu train KGAT (entity2id.json, ckg_triples.npy, train/test split)
python3 ranking/build_data.py

# 4) Train KGAT → checkpoints/best_model.pt
python3 ranking/train.py
```

Sau bước này, Neo4j đã có đồ thị + vector index và `offline/ranking/checkpoints/best_model.pt` đã tồn tại — sẵn sàng cho online.

---

## B. Online — chạy service

### 1. Backend (API)

```bash
cd api
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Lưu ý: Sửa thông tin kết nối DB Postgres trong env `DATABASE_URL` và `NEO4J_URI`.

Swagger: http://localhost:8000/docs

### 2. Frontend (Web)

```bash
cd web
npm install
npm run dev
```

App: http://localhost:3000

### 3. Đánh giá (Evaluation)

```bash
cd evaluation
python3 baseline_search.py              # BM25 + Semantic → baseline_results.json
python3 proposed_search.py              # LLM+Cypher (+KGAT) → proposed_results.json
python3 visualization/visualize.py      # Sinh hit_rate.png, mrr_ndcg.png
```
