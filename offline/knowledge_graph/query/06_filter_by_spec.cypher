// ============================================================
// Query 06 — Lọc sản phẩm theo thông số kỹ thuật (Spec)
//
// Mục đích : 2-hop: Product→Spec (filter key + value)
//            Kiểm tra index trên Spec.key
// Kỳ vọng  : Index Seek (Spec.key) + Expand ngược về Product
// ============================================================

// Tìm sản phẩm có RAM 6 GB
MATCH (p:Product)-[:HAS_SPEC]->(s:Spec {key: 'ram', value: '6 GB'})
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
RETURN
  p.asin           AS asin,
  p.title          AS title,
  s.value          AS ram,
  p.price          AS price,
  p.average_rating AS rating,
  b.label          AS brand
ORDER BY p.price ASC;

// ── Tất cả giá trị RAM có trong graph ────────────────────────
// MATCH (s:Spec {key: 'ram'})
// RETURN s.value AS ram_value, COUNT { ()-[:HAS_SPEC]->(s) } AS products
// ORDER BY products DESC;

// ── Sản phẩm có storage 128 GB ───────────────────────────────
// MATCH (p:Product)-[:HAS_SPEC]->(s:Spec {key: 'storage', value: '128 GB'})
// OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
// RETURN p.asin, p.title, b.label AS brand, p.price
// ORDER BY p.price ASC LIMIT 15;

// PROFILE
// MATCH (p:Product)-[:HAS_SPEC]->(s:Spec {key: 'ram', value: '6 GB'})
// RETURN p.asin;
