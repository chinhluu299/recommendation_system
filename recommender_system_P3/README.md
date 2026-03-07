
# Local Recommendation System (GraphSAGE + FastAPI + Amazon meta_8k ETL)

This project is designed for **local demo** of a recommendation engine.

Features:
- ETL pipeline for Amazon `meta_8k.json`
- Generate users and interactions automatically
- Train GraphSAGE embeddings
- FastAPI service for recommendations
- Demo test script

Everything runs **locally (no paid APIs)**.

---

# Project Structure

recommender-project
│
├── data
│   ├── raw
│   │   └── meta_8k.json       # place your dataset here
│   │
│   └── processed
│       ├── products.csv
│       ├── users.csv
│       └── interactions.csv
│
├── etl
│   └── etl_amazon.py          # convert json → csv
│
├── training
│   └── train_graphsage.py     # train embeddings
│
├── model
│   └── graphsage_model.py
│
├── embeddings
│
├── pipeline
│   └── recommend_pipeline.py
│
├── api
│   └── main.py
│
├── tests
│   └── test_api.py
│
└── requirements.txt

---

# Installation

pip install -r requirements.txt

---

# Step 1 — ETL Dataset

Place your dataset:

data/raw/meta_8k.json

Run:

python etl/etl_amazon.py

This generates:

data/processed/products.csv
data/processed/users.csv
data/processed/interactions.csv

---

# Step 2 — Train Graph Model

python training/train_graphsage.py

This generates:

embeddings/product_embeddings.pkl

---

# Step 3 — Run API

python -m uvicorn api.main:app --reload

Open:

http://localhost:8000/docs

---

# Step 4 — Test API

python tests/test_api.py
