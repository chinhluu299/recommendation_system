
from fastapi import FastAPI
from pipeline.recommend_pipeline import recommend

app = FastAPI(title="Recommendation API")

@app.post("/recommend")
def recommend_products(data: dict):

    user_id = data["userId"]
    query = data["query"]

    results = recommend(user_id, query)

    return {"recommendations": results}
