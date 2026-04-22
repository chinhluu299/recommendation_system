// ============================================================
// Query 03 — Lọc sản phẩm theo khoảng giá + sắp xếp
//
// Mục đích : Range filter trên property có index (price)
//            Kiểm tra khả năng index range scan
// Kỳ vọng  : Index Range Seek trên Product.price
// ============================================================

MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand)
WHERE p.price IS NOT NULL
  AND p.price >= 100
  AND p.price <= 300
RETURN
  p.asin           AS asin,
  p.title          AS title,
  p.price          AS price,
  p.average_rating AS rating,
  p.rating_number  AS reviews,
  b.label          AS brand
ORDER BY p.price ASC
LIMIT 20;

// ── Biến thể: tìm sản phẩm rẻ nhất có review > 100 ──────────
// MATCH (p:Product)
// WHERE p.price IS NOT NULL AND p.rating_number > 100
// RETURN p.asin, p.title, p.price, p.average_rating
// ORDER BY p.price ASC
// LIMIT 10;

// PROFILE
// MATCH (p:Product) WHERE p.price >= 100 AND p.price <= 300 RETURN p.asin;
