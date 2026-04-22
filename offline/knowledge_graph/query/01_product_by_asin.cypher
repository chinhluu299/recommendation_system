// ============================================================
// Query 01 — Tra cứu toàn bộ thông tin một sản phẩm theo ASIN
//
// Mục đích : Point-lookup — kiểm tra index trên Product.asin
// Kỳ vọng  : 1 hàng, Index Seek (không Full Scan)
// ============================================================

// ── Kết quả đơn giản ─────────────────────────────────────────
MATCH (p:Product {asin: 'B07SDQ483V'})
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
OPTIONAL MATCH (p)-[:SOLD_BY]->(s:Store)
OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
RETURN
  p.asin              AS asin,
  p.title             AS title,
  p.price             AS price,
  p.average_rating    AS rating,
  p.rating_number     AS review_count,
  p.color             AS color,
  p.screen_size       AS screen_size,
  p.form_factor       AS form_factor,
  p.operating_system  AS os,
  b.label             AS brand,
  s.label             AS store,
  c.label             AS category;

// ── Phân tích execution plan ──────────────────────────────────
// Bỏ comment dòng dưới để xem query plan (chạy trong Neo4j Browser)
// PROFILE
// MATCH (p:Product {asin: 'B07SDQ483V'}) RETURN p;
