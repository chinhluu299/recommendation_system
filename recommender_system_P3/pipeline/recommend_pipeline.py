
import pandas as pd
import numpy as np
import pickle

products = pd.read_csv("data/processed/products.csv")

with open("embeddings/product_embeddings.pkl","rb") as f:
    product_embeddings = pickle.load(f)

def expand_query(query):
    return [query, query+" accessory", query+" replacement"]

def retrieve_candidates(queries):

    ids=[]

    for q in queries:

        for i,row in products.iterrows():

            title=str(row["title"]).lower()

            if q.lower() in title:
                ids.append(i)

    return list(set(ids))[:50]

def rank_products(user_vec, candidates):

    
    scores=[]

    for idx in candidates:

        emb = product_embeddings[idx]

        score = np.dot(user_vec, emb)

        scores.append((idx, score))

    scores.sort(key=lambda x:x[1], reverse=True)

    return scores[:10]

def recommend(user_id, query):

    queries = expand_query(query)

    candidates = retrieve_candidates(queries)

    user_vector = np.mean(product_embeddings, axis=0)

    ranked = rank_products(user_vector, candidates)

    results=[]

    for idx,score in ranked:

        p = products.iloc[idx]

        results.append({
            "product_id": p["product_id"],
            "title": p["title"],
            "score": float(score)
        })

    return results
