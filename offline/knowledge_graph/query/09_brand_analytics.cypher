// ============================================================
// Query 09 — Phân tích thương hiệu: số SP, rating, giá trung bình
//
// Mục đích : Aggregation nặng trên toàn graph
//            Kiểm tra hiệu năng GROUP BY + multi-aggregate
// Kỳ vọng  : Full scan Brand + Expand + aggregation
// ============================================================

MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand)
WITH
  b.label                                        AS brand,
  COUNT(p)                                       AS total_products,
  COUNT(CASE WHEN p.price IS NOT NULL THEN 1 END) AS priced_count,
  AVG(CASE WHEN p.average_rating IS NOT NULL THEN p.average_rating END) AS avg_rating,
  AVG(CASE WHEN p.price IS NOT NULL THEN p.price END)                    AS avg_price,
  MIN(p.price)                                   AS min_price,
  MAX(p.price)                                   AS max_price,
  SUM(p.rating_number)                           AS total_reviews
ORDER BY avg_rating DESC, total_products DESC
LIMIT 20
RETURN
  brand,
  total_products,
  priced_count,
  ROUND(avg_rating, 2)   AS avg_rating,
  ROUND(avg_price, 2)    AS avg_price,
  min_price,
  max_price,
  total_reviews;

// ── Top brand theo tổng lượt review ──────────────────────────
// MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand)
// RETURN b.label AS brand, SUM(p.rating_number) AS total_reviews
// ORDER BY total_reviews DESC LIMIT 10;

// PROFILE
// MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand)
// RETURN b.label, COUNT(p) AS cnt ORDER BY cnt DESC LIMIT 10;
