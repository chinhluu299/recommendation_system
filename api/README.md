# FastAPI Ecommerce Recommendation API (Prototype)

## 1) Setup

```bash
cd api
cp .env.example .env
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Lưu ý: driver PostgreSQL đang dùng `psycopg` (v3), nên `DATABASE_URL` cần có dạng:
`postgresql+psycopg://postgres:123456@localhost:5432/reco_demo`

Start PostgreSQL:

```bash
docker compose up -d
```

Run API:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger: `http://localhost:8000/docs`

## 2) API Design

Base path: `/api/v1`
Response chuẩn chung cho tất cả endpoint:

```json
{
  "data": {},
  "message": "Success",
  "code": 200
}
```

- `POST /auth/register`: đăng ký user, trả JWT token
- `POST /auth/login`: đăng nhập, trả JWT token
- `GET /products/search?query=...`: tìm sản phẩm
- `GET /products/{product_id}`: lấy chi tiết sản phẩm
- `POST /interactions`: ghi hành vi `view` hoặc `purchase`
- `POST /recommendations`: gọi core service `/recommend` để lấy gợi ý
- `GET /health`: kiểm tra service

## 3) Database Tables

- `users`
- `products`
- `interactions`

Bạn có thể tự nạp dữ liệu Amazon Review 2023 (Cellphone & accessories) vào bảng `products`.

## 4) Example Recommendation Payload

```json
{
  "user_id": 1,
  "query": "iphone",
  "limit": 10
}
```

Core service expected response:

```json
{
  "items": [
    {"product_id": 10, "score": 0.98},
    {"product_id": 22, "score": 0.95}
  ]
}
```
