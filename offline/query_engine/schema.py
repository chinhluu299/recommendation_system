"""
schema.py
Mô tả schema của Knowledge Graph để đưa vào system prompt cho LLM.

Có 2 loại prompt:
  SYSTEM_PROMPT      — One-pass: LLM sinh Cypher trực tiếp (fallback cho aggregate)
  INTENT_SYSTEM_PROMPT — Two-pass: LLM sinh Intent JSON (dùng cho search/hybrid)

Enum values (Spec/Technology/Carrier) được load động từ Neo4j qua load_enum_values().
"""

from __future__ import annotations

# ─── Schema dạng text ─────────────────────────────────────────────────────────

SCHEMA_TEXT = """
## GRAPH SCHEMA — Smartphone Knowledge Graph

### NODE TYPES & PROPERTIES

| Node      | Properties quan trọng |
|-----------|----------------------|
| Product   | asin (ID), title, price (float/null), average_rating (1-5), rating_number, color, screen_size, form_factor, operating_system |
| Brand     | label (tên thương hiệu) |
| Store     | label (tên cửa hàng/seller) |
| Category  | label |
| Feature   | label (mô tả tính năng dạng text) |
| Spec      | key ("ram" hoặc "storage"), value (vd: "6 GB", "128 GB") |
| Carrier   | label (tên nhà mạng) |
| Technology| label (tên công nghệ) |
| Accessory | label (tên phụ kiện) |

### RELATIONSHIPS

(Product)-[:MANUFACTURED_BY]->(Brand)
(Product)-[-SOLD_BY]->(Store)
(Product)-[:BELONGS_TO]->(Category)
(Product)-[:HAS_FEATURE]->(Feature)
(Product)-[:HAS_SPEC]->(Spec)          -- Spec.key = "ram" | "storage"
(Product)-[:SUPPORTS_CARRIER]->(Carrier)
(Product)-[:USES_TECHNOLOGY]->(Technology)
(Product)-[:INCLUDES_ACCESSORY]->(Accessory)
(Product)-[:BOUGHT_TOGETHER]->(Product)
(Category)-[:SUBCATEGORY_OF]->(Category)

### GIÁ TRỊ MẪU (dùng đúng chuỗi này khi filter)

Brands    : 'Samsung', 'SAMSUNG', 'Apple', 'Motorola', 'Google', 'Xiaomi', 'LG',
            'BLU', 'TCL', 'Alcatel', 'UMIDIGI', 'Blackview', 'OnePlus', 'Nokia'
Carriers  : 'AT&T', 'T-Mobile', 'Verizon', 'Cricket', 'Sprint', 'Boost Mobile',
            'Metro PCS', 'TracFone', 'Straight Talk', 'Google Fi', 'US Cellular'
Technology: '5G', '4G LTE', '4G', '3G', '2G', 'LTE', 'GSM', 'CDMA',
            'Wi-Fi', 'Bluetooth', 'NFC', 'USB', 'Hotspot'
Spec.key  : 'ram', 'storage'
Spec.value: '2 GB','3 GB','4 GB','6 GB','8 GB','12 GB'  (RAM)
            '16 GB','32 GB','64 GB','128 GB','256 GB'    (storage)
"""

# ─── Few-shot examples ────────────────────────────────────────────────────────

FEW_SHOT_EXAMPLES = [
    {
        "question": "Tìm điện thoại của Samsung",
        "cypher": """MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand)
WHERE toLower(b.label) CONTAINS 'samsung'
RETURN p.asin AS asin, p.title AS title, p.price AS price, p.average_rating AS rating
ORDER BY p.average_rating DESC
LIMIT 20""",
    },
    {
        "question": "Điện thoại hỗ trợ AT&T giá dưới 200 đô",
        "cypher": """MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c:Carrier {label: 'AT&T'})
WHERE p.price IS NOT NULL AND p.price < 200
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
RETURN p.asin AS asin, p.title AS title, p.price AS price,
       p.average_rating AS rating, b.label AS brand
ORDER BY p.price ASC
LIMIT 15""",
    },
    {
        "question": "Điện thoại 5G RAM 8GB",
        "cypher": """MATCH (p:Product)-[:USES_TECHNOLOGY]->(t:Technology {label: '5G'})
MATCH (p)-[:HAS_SPEC]->(s:Spec {key: 'ram', value: '8 GB'})
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
RETURN p.asin AS asin, p.title AS title, p.price AS price,
       p.average_rating AS rating, b.label AS brand
ORDER BY p.average_rating DESC""",
    },
    {
        "question": "So sánh điện thoại Apple và Samsung về giá",
        "cypher": """MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand)
WHERE toLower(b.label) IN ['apple', 'samsung']
RETURN b.label AS brand,
       COUNT(p) AS so_san_pham,
       ROUND(AVG(p.price), 2) AS gia_trung_binh,
       MIN(p.price) AS gia_thap_nhat,
       MAX(p.price) AS gia_cao_nhat
ORDER BY gia_trung_binh DESC""",
    },
    {
        "question": "Top 10 điện thoại được đánh giá cao nhất",
        "cypher": """MATCH (p:Product)
WHERE p.average_rating IS NOT NULL AND p.rating_number >= 50
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
RETURN p.asin AS asin, p.title AS title, p.price AS price,
       p.average_rating AS rating, p.rating_number AS reviews, b.label AS brand
ORDER BY p.average_rating DESC, p.rating_number DESC
LIMIT 10""",
    },
    {
        "question": "Điện thoại hỗ trợ cả AT&T và T-Mobile",
        "cypher": """MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c1:Carrier {label: 'AT&T'})
MATCH (p)-[:SUPPORTS_CARRIER]->(c2:Carrier {label: 'T-Mobile'})
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
RETURN p.asin AS asin, p.title AS title, p.price AS price,
       p.average_rating AS rating, b.label AS brand
ORDER BY p.average_rating DESC
LIMIT 20""",
    },
    {
        "question": "Thương hiệu nào có nhiều sản phẩm nhất",
        "cypher": """MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand)
RETURN b.label AS brand, COUNT(p) AS so_san_pham,
       ROUND(AVG(p.average_rating), 2) AS rating_trung_binh
ORDER BY so_san_pham DESC
LIMIT 10""",
    },
]

# ─── System prompt đầy đủ ─────────────────────────────────────────────────────

# ─── Enum loader (dynamic, load từ Neo4j) ────────────────────────────────────

_enum_cache: dict | None = None

def load_enum_values() -> dict:
    """
    Query Neo4j lấy distinct values cho các node dùng exact-match filter.
    Kết quả được cache sau lần đầu gọi.

    Returns:
        {
            "ram_values":     ["2 GB", "4 GB", ...],
            "storage_values": ["16 GB", "32 GB", ...],
            "technologies":   ["5G", "4G LTE", ...],
            "carriers":       ["AT&T", "T-Mobile", ...],
        }
    """
    global _enum_cache
    if _enum_cache is not None:
        return _enum_cache

    try:
        from offline.query_engine.graph_search import run_query
        queries = {
            "ram_values":     "MATCH (s:Spec {key:'ram'})     RETURN DISTINCT s.value AS v ORDER BY v",
            "storage_values": "MATCH (s:Spec {key:'storage'}) RETURN DISTINCT s.value AS v ORDER BY v",
            "technologies":   "MATCH (t:Technology)            RETURN DISTINCT t.label AS v ORDER BY v",
            "carriers":       "MATCH (c:Carrier)               RETURN DISTINCT c.label AS v ORDER BY v",
        }
        _enum_cache = {
            key: [r["v"] for r in run_query(cypher) if r.get("v")]
            for key, cypher in queries.items()
        }
    except Exception:
        # Neo4j chưa chạy → dùng fallback tĩnh
        _enum_cache = {
            "ram_values":     ["2 GB", "3 GB", "4 GB", "6 GB", "8 GB", "12 GB"],
            "storage_values": ["16 GB", "32 GB", "64 GB", "128 GB", "256 GB"],
            "technologies":   ["5G", "4G LTE", "4G", "LTE", "3G", "GSM",
                               "Wi-Fi", "Bluetooth", "NFC"],
            "carriers":       ["AT&T", "T-Mobile", "Verizon", "Cricket",
                               "Sprint", "Boost Mobile", "TracFone",
                               "Straight Talk", "Google Fi"],
        }

    return _enum_cache


def _enum_section() -> str:
    """Sinh phần enum values để inject vào prompt."""
    try:
        enums = load_enum_values()
    except Exception:
        return ""
    return f"""
### GIÁ TRỊ CHÍNH XÁC TRONG KG (bắt buộc dùng đúng những giá trị này)

RAM values    : {enums["ram_values"]}
Storage values: {enums["storage_values"]}
Technology    : {enums["technologies"]}
Carrier       : {enums["carriers"]}
"""


# ─── Intent JSON prompt ───────────────────────────────────────────────────────

INTENT_SYSTEM_PROMPT = """Bạn là hệ thống phân tích câu hỏi tìm kiếm sản phẩm.
Nhiệm vụ: chuyển câu hỏi tiếng Việt thành JSON intent. KHÔNG sinh Cypher.

""" + """### GRAPH SCHEMA

Node: Product  — asin, title, price (float), average_rating (1-5), rating_number
Node: Brand    — label
Node: Carrier  — label
Node: Technology — label
Node: Spec     — key ("ram" | "storage"), value
Node: Category — label
Node: Feature  — label (mô tả tính năng free text)

""" + """### OUTPUT FORMAT (JSON thuần, không markdown)

{
  "query_type": "search" | "aggregate" | "compare",
  "structured": {
    "brand":      string | null,
    "technology": string | null,
    "carrier":    string | null,
    "spec": {
      "ram":     string | null,
      "storage": string | null
    } | null,
    "price": {"op": "<"|">"|"<="|">="|"=", "value": number} | null,
    "rating": {"op": "<"|">"|"<="|">="|"=", "value": number} | null
  },
  "semantic_query": string | null,
  "sort":  "rating_desc" | "price_asc" | "price_desc" | "reviews_desc" | null,
  "limit": number
}

### QUY TẮC

1. query_type = "aggregate" nếu câu hỏi thống kê, đếm, so sánh tổng hợp nhiều brand.
2. structured chứa thông tin CÓ THỂ filter chính xác (brand, spec, price...).
3. semantic_query chứa các mô tả tính năng / use-case KHÔNG map được vào structured
   (ví dụ: "pin trâu", "chụp ảnh đẹp", "chơi game mượt"). Giữ nguyên tiếng Việt.
4. Nếu câu hỏi hoàn toàn structured (brand/spec/price rõ ràng) → semantic_query = null.
5. Nếu câu hỏi hoàn toàn semantic → structured = null.
5.1 Nếu có nhiều brand (ví dụ: "Samsung và Xiaomi"), trả về structured.brand là mảng:
    "brand": ["Samsung", "Xiaomi"].
6. Với spec value: ghi đúng format có space, ví dụ "8 GB" không phải "8GB".
7. Chỉ trả về JSON, không giải thích.
8. QUAN TRỌNG — Nếu không chắc chắn về giá trị của một field (đơn vị mơ hồ, không rõ
   ràng, có thể hiểu nhiều nghĩa), đặt field đó = null thay vì đoán.
   Ví dụ: "khoảng 400k" → price = null (không rõ đơn vị USD hay VND, "khoảng" không có op rõ).
   Ví dụ: "giá tầm trung" → price = null (không có con số cụ thể).
   Ví dụ: "camera 64MP" → semantic_query (không có field nào trong structured cho camera).

### VÍ DỤ

Câu hỏi: "điện thoại Samsung 5G RAM 8GB dưới 300 đô"
{"query_type":"search","structured":{"brand":"Samsung","technology":"5G","carrier":null,"spec":{"ram":"8 GB","storage":null},"price":{"op":"<","value":300},"rating":null},"semantic_query":null,"sort":"rating_desc","limit":100}

Câu hỏi: "điện thoại pin trâu chơi game tốt"
{"query_type":"search","structured":null,"semantic_query":"pin trâu chơi game tốt","sort":"rating_desc","limit":100}

Câu hỏi: "Samsung 5G pin trâu giá tầm trung"
{"query_type":"search","structured":{"brand":"Samsung","technology":"5G","carrier":null,"spec":null,"price":null,"rating":null},"semantic_query":"pin trâu giá tầm trung","sort":"rating_desc","limit":100}

Câu hỏi: "điện thoại hãng Samsung và Xiaomi"
{"query_type":"search","structured":{"brand":["Samsung","Xiaomi"],"technology":null,"carrier":null,"spec":null,"price":null,"rating":null},"semantic_query":null,"sort":"rating_desc","limit":100}

Câu hỏi: "thương hiệu nào có nhiều sản phẩm nhất"
{"query_type":"aggregate","structured":null,"semantic_query":null,"sort":null,"limit":10}

Câu hỏi: "điện thoại 5G cổng mở, camera 64MP, quay 8K, giá khoảng 400k"
{"query_type":"search","structured":{"brand":null,"technology":"5G","carrier":null,"spec":null,"price":null,"rating":null},"semantic_query":"cổng mở camera 64MP quay 8K giá khoảng 400k","sort":"rating_desc","limit":100}
"""


# ─── One-pass Cypher prompt (giữ nguyên, dùng cho fallback aggregate) ─────────

SYSTEM_PROMPT = f"""Bạn là chuyên gia chuyển đổi câu hỏi tiếng Việt thành câu truy vấn Cypher cho Neo4j.

{SCHEMA_TEXT}

## QUY TẮC BẮT BUỘC

1. Chỉ trả về DUY NHẤT câu Cypher, không giải thích, không markdown code block.
2. Luôn dùng LIMIT (mặc định 100) trừ khi câu hỏi yêu cầu đếm/thống kê.
3. Khi filter Brand/Carrier/Technology bằng tên, dùng toLower() để tránh lỗi hoa/thường:
   WHERE toLower(b.label) CONTAINS 'samsung'
4. price có thể null — luôn kiểm tra IS NOT NULL khi filter giá.
5. Dùng OPTIONAL MATCH cho thông tin phụ (brand, store) để không bỏ sót sản phẩm.
6. Khi hỏi "rẻ nhất / đắt nhất" → ORDER BY price ASC/DESC + WHERE price IS NOT NULL.
7. Khi hỏi "tốt nhất / được đánh giá cao" → ORDER BY average_rating DESC, rating_number DESC.
8. Alias cột bằng tiếng Việt nếu phù hợp (gia, ten_san_pham, thuong_hieu...).

no_thinking
## VÍ DỤ

""" + "\n\n".join(
    f"Câu hỏi: {ex['question']}\nCypher:\n{ex['cypher']}"
    for ex in FEW_SHOT_EXAMPLES
)
