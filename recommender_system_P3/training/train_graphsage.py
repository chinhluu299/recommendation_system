import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pandas as pd
import torch
import pickle
import os
from sentence_transformers import SentenceTransformer
from torch_geometric.data import Data

from model.graphsage_model import GraphSAGE

products = pd.read_csv("data/processed/products.csv")
interactions = pd.read_csv("data/processed/interactions.csv")

print("Creating product embeddings...")

encoder = SentenceTransformer("all-MiniLM-L6-v2")

texts = products["title"].fillna("").tolist()
text_embeddings = encoder.encode(texts)

node_features = torch.tensor(text_embeddings, dtype=torch.float)

product_map = {p:i for i,p in enumerate(products["product_id"])}

edges = []

for _,row in interactions.iterrows():
    pid = row["product_id"]
    if pid in product_map:
        idx = product_map[pid]
        edges.append([idx,idx])

edge_index = torch.tensor(edges).t().contiguous()

data = Data(x=node_features, edge_index=edge_index)

print("Training GraphSAGE...")

model = GraphSAGE(node_features.shape[1], 64)

optimizer = torch.optim.Adam(model.parameters(), lr=0.01)

for epoch in range(30):

    optimizer.zero_grad()

    out = model(data.x, data.edge_index)

    loss = out.mean()

    loss.backward()

    optimizer.step()

    print("epoch", epoch, "loss", loss.item())

print("Saving embeddings...")

os.makedirs("embeddings", exist_ok=True)

embeddings = model(data.x, data.edge_index).detach().numpy()

with open("embeddings/product_embeddings.pkl","wb") as f:
    pickle.dump(embeddings,f)

print("Training finished")
