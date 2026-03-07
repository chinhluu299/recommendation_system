import json
import pandas as pd
import random
import os

RAW_PATH = "data/raw/meta_8k.json"
OUT_DIR = "data/processed"

os.makedirs(OUT_DIR, exist_ok=True)

products = []

print("Reading dataset...")

with open(RAW_PATH, "r", encoding="utf-8") as f:
    for line in f:
        data = json.loads(line)

        products.append({
            "product_id": data.get("parent_asin"),
            "title": data.get("title"),
            "category": data.get("main_category"),
            "rating": data.get("average_rating")
        })

products_df = pd.DataFrame(products)

products_df = products_df.drop_duplicates(subset="product_id")

products_df.to_csv(f"{OUT_DIR}/products.csv", index=False)

print("Products created:", len(products_df))

# generate users

users = []
for i in range(1,501):
    users.append({"user_id": f"U{i}"})

users_df = pd.DataFrame(users)

users_df.to_csv(f"{OUT_DIR}/users.csv", index=False)

print("Users created:", len(users_df))

# generate interactions

product_ids = products_df["product_id"].tolist()

interactions = []

for user in users_df["user_id"]:

    sampled = random.sample(product_ids, min(len(product_ids), random.randint(5,20)))

    for p in sampled:

        action = random.choice(["view","purchase"])

        interactions.append({
            "user_id": user,
            "product_id": p,
            "action": action
        })

interactions_df = pd.DataFrame(interactions)

interactions_df.to_csv(f"{OUT_DIR}/interactions.csv", index=False)

print("Interactions created:", len(interactions_df))

print("ETL finished")
