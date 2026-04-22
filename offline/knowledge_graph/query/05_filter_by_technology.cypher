// ============================================================
// Query 05 — Sản phẩm hỗ trợ công nghệ cụ thể (vd: 5G)
//
// Mục đích : 1-hop traversal Product→Technology
//            Kiểm tra index trên Technology.label
// Kỳ vọng  : NodeByLabelScan (Technology) + Expand
// ============================================================

MATCH (p:Product)-[:USES_TECHNOLOGY]->(t:Technology {label: '5G'})
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
OPTIONAL MATCH (p)-[:HAS_SPEC]->(s:Spec {key: 'storage'})
RETURN
  p.asin           AS asin,
  p.title          AS title,
  p.price          AS price,
  p.average_rating AS rating,
  b.label          AS brand,
  s.value          AS storage
ORDER BY p.price DESC
LIMIT 20;

// ── Sản phẩm hỗ trợ cả Wi-Fi VÀ Bluetooth ───────────────────
// MATCH (p:Product)-[:USES_TECHNOLOGY]->(t1:Technology {label: 'Wi-Fi'})
// MATCH (p)-[:USES_TECHNOLOGY]->(t2:Technology {label: 'Bluetooth'})
// RETURN p.asin, p.title, p.price LIMIT 10;

// ── Đếm công nghệ phổ biến ───────────────────────────────────
// MATCH (p:Product)-[:USES_TECHNOLOGY]->(t:Technology)
// RETURN t.label AS technology, COUNT(p) AS usage_count
// ORDER BY usage_count DESC LIMIT 15;

// PROFILE
// MATCH (p:Product)-[:USES_TECHNOLOGY]->(t:Technology {label: '5G'})
// RETURN p.asin;
