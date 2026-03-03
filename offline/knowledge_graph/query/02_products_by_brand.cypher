// ============================================================
// Query 02 — Tất cả sản phẩm của một thương hiệu
//
// Mục đích : 1-hop traversal Product→Brand
//            Kiểm tra index trên Brand.label
// Kỳ vọng  : NodeByLabelScan (Brand) + Expand → Products
// ============================================================

MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand {label: 'Samsung'})
OPTIONAL MATCH (p)-[:BELONGS_TO]->(c:Category)
RETURN
  p.asin           AS asin,
  p.title          AS title,
  p.price          AS price,
  p.average_rating AS rating,
  p.rating_number  AS reviews,
  p.color          AS color,
  c.label          AS category
ORDER BY p.average_rating DESC, p.rating_number DESC;

// ── Thử với brand khác ────────────────────────────────────────
// MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand {label: 'Apple'})  ...
// MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand {label: 'Motorola'}) ...

// PROFILE
// MATCH (p:Product)-[:MANUFACTURED_BY]->(b:Brand {label: 'Samsung'})
// RETURN p.asin, p.title;
