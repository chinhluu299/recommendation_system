// ============================================================
// Query 10 — Phân tích mức độ phổ biến của công nghệ + hệ số giá
//
// Mục đích : Aggregation + sub-aggregation trên Technology node
//            Kiểm tra full-graph traversal với nhiều chiều phân tích
// Kỳ vọng  : NodeByLabelScan (Technology) + Expand + aggregate
// ============================================================

MATCH (p:Product)-[:USES_TECHNOLOGY]->(t:Technology)
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
WITH
  t.label                                                  AS technology,
  COUNT(DISTINCT p)                                        AS product_count,
  COUNT(DISTINCT b)                                        AS brand_count,
  AVG(CASE WHEN p.price IS NOT NULL THEN p.price END)      AS avg_price,
  AVG(CASE WHEN p.average_rating IS NOT NULL THEN p.average_rating END) AS avg_rating,
  COUNT(CASE WHEN p.price IS NOT NULL THEN 1 END)          AS priced_count
ORDER BY product_count DESC
LIMIT 15
RETURN
  technology,
  product_count,
  brand_count,
  ROUND(avg_price, 2)  AS avg_price,
  ROUND(avg_rating, 2) AS avg_rating,
  priced_count;

// ── Công nghệ nào tương quan với giá cao nhất ────────────────
// MATCH (p:Product)-[:USES_TECHNOLOGY]->(t:Technology)
// WHERE p.price IS NOT NULL
// RETURN t.label AS tech, COUNT(p) AS products, ROUND(AVG(p.price),2) AS avg_price
// ORDER BY avg_price DESC LIMIT 10;

// ── Sản phẩm hỗ trợ nhiều công nghệ nhất ────────────────────
// MATCH (p:Product)-[:USES_TECHNOLOGY]->(t:Technology)
// WITH p, COLLECT(t.label) AS techs, COUNT(t) AS tech_count
// ORDER BY tech_count DESC LIMIT 10
// RETURN p.asin, p.title, tech_count, techs;

// PROFILE
// MATCH (p:Product)-[:USES_TECHNOLOGY]->(t:Technology)
// RETURN t.label, COUNT(p) ORDER BY COUNT(p) DESC LIMIT 15;
