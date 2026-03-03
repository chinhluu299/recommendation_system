"""
nl2cypher.py
NL question → filter_query + semantic_query (Cypher cho Neo4j).

LLM chỉ sinh phần WHERE — toàn bộ MATCH/RETURN được build bởi code.
"""
from __future__ import annotations
import re
from offline.query_engine.schema  import load_enum_values
from offline.query_engine.scoring import TOTAL_LIMIT

MAX_TOK = 512   # WHERE clause ngắn, không cần nhiều token

# ── Prompt ────────────────────────────────────────────────────────────────────

_FILTER_SCHEMA = """Bạn là hệ thống sinh điều kiện WHERE cho Cypher query Neo4j.

## CÁC BIẾN ĐÃ ĐƯỢC OPTIONAL MATCH SẴN

| Biến | Node       | Property quan trọng |
|------|------------|---------------------|
| p    | Product    | p.price (float/null), p.average_rating (1-5), p.rating_number, p.color, p.screen_size, p.operating_system |
| b    | Brand      | b.label (tên thương hiệu: 'Samsung', 'Apple', ...) |
| t    | Technology | t.label ('5G', '4G LTE', 'Wi-Fi', 'Bluetooth', ...) |
| c    | Carrier    | c.label ('AT&T', 'T-Mobile', 'Verizon', ...) |
| s    | Spec       | s.key ('ram' | 'storage'), s.value ('8 GB', '128 GB', ...) |
"""

_FILTER_SUFFIX = """
## NHIỆM VỤ

Sinh điều kiện WHERE để lọc sản phẩm. Các biến p, b, t, c, s đã có sẵn.

## QUY TẮC CỨNG

- CHỈ sinh phần WHERE (bắt đầu bằng `WHERE`)
- TUYỆT ĐỐI KHÔNG dùng: MATCH, CALL, YIELD, RETURN, CREATE, MERGE, DELETE, LIMIT, ORDER, WITH
- Dùng toLower() khi so sánh chuỗi (brand, carrier, technology)
- Luôn kiểm tra `p.price IS NOT NULL` trước khi so sánh giá
- Nếu không có filter rõ ràng → trả về: WHERE true
- Chỉ trả về Cypher thuần, không markdown, không giải thích

## VÍ DỤ

Câu hỏi: "điện thoại Samsung dưới 300 đô"
WHERE toLower(b.label) CONTAINS 'samsung' AND p.price IS NOT NULL AND p.price < 300

Câu hỏi: "điện thoại 5G RAM 8GB"
WHERE t.label = '5G' AND s.key = 'ram' AND s.value = '8 GB'

Câu hỏi: "iPhone giá từ 200 đến 500 đô"
WHERE toLower(b.label) CONTAINS 'apple' AND p.price IS NOT NULL AND p.price >= 200 AND p.price <= 500

Câu hỏi: "điện thoại hỗ trợ AT&T"
WHERE c.label = 'AT&T'

Câu hỏi: "điện thoại rating trên 4.5"
WHERE p.average_rating >= 4.5

Câu hỏi: "điện thoại tốt"
WHERE true
"""

_FORBIDDEN_KWS = {"CREATE", "MERGE", "DELETE", "DETACH", "CALL", "MATCH", "RETURN"}


def _build_prompt() -> str:
    try:
        enums = load_enum_values()
    except Exception:
        enums = {}
    enum_block = (
        "\n\n## ENUM VALUES (dùng chính xác các giá trị này)\n"
        f"- RAM: {enums.get('ram_values', [])}\n"
        f"- Storage: {enums.get('storage_values', [])}\n"
        f"- Technology: {enums.get('technologies', [])}\n"
        f"- Carrier: {enums.get('carriers', [])}\n"
    )
    return _FILTER_SCHEMA + enum_block + _FILTER_SUFFIX


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:cypher)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _validate(where: str) -> None:
    upper = where.upper()
    for kw in _FORBIDDEN_KWS:
        if kw in upper:
            raise ValueError(f"WHERE clause không được chứa '{kw}': {where!r}")


def _call_llm(messages: list[dict]) -> str:
    from offline.query_engine._llm_client import chat
    return chat(messages, max_tokens=MAX_TOK, temperature=0.1)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_queries(question: str) -> dict:
    """
    Sinh filter_query + semantic_query từ câu hỏi tự nhiên.

    Returns:
        {
            "filter_query"  : Cypher lọc theo điều kiện structured,
            "semantic_query": Cypher tìm kiếm theo vector embedding ($query_embedding),
            "where_clause"  : WHERE clause gốc (để debug/trace),
        }
    Raises:
        ValueError nếu LLM trả về output không hợp lệ.
    """
    where = _clean(_call_llm([
        {"role": "system", "content": _build_prompt()},
        {"role": "user",   "content": question},
    ]))
    if not where:
        raise ValueError("LLM trả về WHERE clause rỗng.")
    if not where.upper().startswith("WHERE"):
        where = "WHERE " + where
    _validate(where)

    filter_query = (
        "MATCH (p:Product)\n"
        "OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)\n"
        "OPTIONAL MATCH (p)-[:USES_TECHNOLOGY]->(t:Technology)\n"
        "OPTIONAL MATCH (p)-[:SUPPORTS_CARRIER]->(c:Carrier)\n"
        "OPTIONAL MATCH (p)-[:HAS_SPEC]->(s:Spec)\n"
        f"{where}\n"
        "WITH DISTINCT p\n"
        "OPTIONAL MATCH (u:User)-[r:RATING]->(p)\n"
        "WITH p.id AS product_id, COUNT(r) AS rating_count, AVG(r.score) AS avg_rating\n"
        f"RETURN product_id, rating_count, avg_rating\n"
        f"LIMIT {TOTAL_LIMIT}"
    )

    semantic_query = (
        f"CALL db.index.vector.queryNodes('product_text_index', {TOTAL_LIMIT}, $query_embedding) "
        "YIELD node AS p, score AS sem_score "
        "OPTIONAL MATCH (u:User)-[r:RATING]->(p) "
        "WITH p.id AS product_id, sem_score, COUNT(r) AS rating_count, AVG(r.score) AS avg_rating "
        "RETURN product_id, sem_score, rating_count, avg_rating"
    )

    return {
        "filter_query":   filter_query,
        "semantic_query": semantic_query,
        "where_clause":   where,
    }


# Backward-compat alias
nl_to_cypher = generate_queries
