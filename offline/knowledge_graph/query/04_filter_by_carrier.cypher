// ============================================================
// Query 04 — Sản phẩm hỗ trợ nhà mạng cụ thể
//
// Mục đích : 1-hop traversal Product→Carrier
//            Kiểm tra index trên Carrier.label
// Kỳ vọng  : NodeByLabelScan (Carrier) + Expand ngược về Product
// ============================================================

MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c:Carrier {label: 'AT&T'})
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
RETURN
  p.asin           AS asin,
  p.title          AS title,
  p.price          AS price,
  p.average_rating AS rating,
  b.label          AS brand
ORDER BY p.average_rating DESC
LIMIT 20;

// ── Đếm số sản phẩm theo từng carrier ────────────────────────
// MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c:Carrier)
// RETURN c.label AS carrier, COUNT(p) AS product_count
// ORDER BY product_count DESC;

// PROFILE
// MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c:Carrier {label: 'AT&T'})
// RETURN p.asin;
