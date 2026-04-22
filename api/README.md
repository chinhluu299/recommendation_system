# FastAPI Ecommerce Recommendation API (Prototype)

## 1) Setup

```bash
cd recommendation_system/api
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

## 2) Import Product Data (JSONL)

Project có sẵn command import dữ liệu JSONL vào bảng `products`:
Note: Tải dữ liệu 65k trên nhóm Zalo

```bash
python3 -m app.command.import_products_jsonl \
  --input ../../data_format/meta_Cell_Phones_and_Accessories_65k_cleaned.jsonl
```

Nếu muốn xóa toàn bộ dữ liệu cũ trước khi import:

```bash
python3 -m app.command.import_products_jsonl \
  --input ../../data_format/meta_Cell_Phones_and_Accessories_65k_cleaned.jsonl \
  --truncate
```

Lưu ý:
- Nếu bạn đang đứng ở thư mục `recommendation_system/api`, đường dẫn đúng tới dữ liệu là `../../data_format/...` (không phải `../data_format/...`).
- Command cũng hỗ trợ chạy trực tiếp file:
  `python3 app/command/import_products_jsonl.py --input ../../data_format/...`

## 3) API Design

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

## 4) Database Tables

- `users`
- `products`
- `interactions`

## 5) Gemini Client (Optional)

Thêm vào `.env` để dùng `GeminiClient` trong pipeline riêng của bạn:

```env
GEMINI_API_KEY=your_api_key
GEMINI_MODEL=gemini-2.0-flash
GEMINI_TIMEOUT_SECONDS=12
```

## 6) Example Recommendation Payload

```json
{
  "user_id": 1,
  "query": "iphone",
  "limit": 10
}
```

Recommendation response:

```json
{
  "items": [
    {"product_id": 10, "score": 0.98},
    {"product_id": 22, "score": 0.95}
  ]
}
```
