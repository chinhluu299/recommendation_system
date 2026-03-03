// ============================================================
// Query 08 — Tìm sản phẩm cạnh tranh (cùng brand, cùng category)
//
// Mục đích : 3-hop pattern — Product←Brand→Product + Category join
//            Kiểm tra hiệu năng multi-hop graph traversal
// Kỳ vọng  : Expand từ Brand → cặp sản phẩm → filter overlap
// ============================================================

MATCH (p1:Product)-[:MANUFACTURED_BY]->(b:Brand)<-[:MANUFACTURED_BY]-(p2:Product)
MATCH (p1)-[:BELONGS_TO]->(c:Category)<-[:BELONGS_TO]-(p2)
WHERE p1.asin < p2.asin                  -- tránh duplicate (A,B) và (B,A)
  AND p1.price IS NOT NULL
  AND p2.price IS NOT NULL
RETURN
  b.label          AS brand,
  c.label          AS category,
  p1.asin          AS asin_1,
  p1.title         AS title_1,
  p1.price         AS price_1,
  p1.average_rating AS rating_1,
  p2.asin          AS asin_2,
  p2.title         AS title_2,
  p2.price         AS price_2,
  p2.average_rating AS rating_2,
  abs(p1.price - p2.price) AS price_diff
ORDER BY price_diff ASC
LIMIT 20;

// ── Chỉ lấy sản phẩm của Samsung để hẹp phạm vi ─────────────
// MATCH (p1:Product)-[:MANUFACTURED_BY]->(b:Brand {label: 'Samsung'})<-[:MANUFACTURED_BY]-(p2)
// MATCH (p1)-[:BELONGS_TO]->(c:Category)<-[:BELONGS_TO]-(p2)
// WHERE p1.asin < p2.asin
// RETURN p1.title, p2.title, p1.price, p2.price LIMIT 10;

// PROFILE
// MATCH (p1:Product)-[:MANUFACTURED_BY]->(b:Brand)<-[:MANUFACTURED_BY]-(p2:Product)
// WHERE p1.asin < p2.asin
// RETURN p1.asin, p2.asin LIMIT 100;
