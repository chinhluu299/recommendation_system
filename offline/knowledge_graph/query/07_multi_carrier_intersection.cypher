// ============================================================
// Query 07 — Sản phẩm hỗ trợ ĐỒNG THỜI nhiều nhà mạng
//
// Mục đích : Intersection pattern (AND logic qua nhiều relationships)
//            Kiểm tra hiệu năng khi join nhiều traversal path
// Kỳ vọng  : Hai lần Expand từ cùng Product node (hash join / apply)
// ============================================================

// Sản phẩm hỗ trợ cả AT&T VÀ T-Mobile
MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c1:Carrier {label: 'AT&T'})
MATCH (p)-[:SUPPORTS_CARRIER]->(c2:Carrier {label: 'T-Mobile'})
OPTIONAL MATCH (p)-[:MANUFACTURED_BY]->(b:Brand)
RETURN
  p.asin           AS asin,
  p.title          AS title,
  p.price          AS price,
  p.average_rating AS rating,
  b.label          AS brand
ORDER BY p.average_rating DESC, p.rating_number DESC
LIMIT 20;

// ── Hỗ trợ AT&T + T-Mobile + Verizon (3 nhà mạng) ───────────
// MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c1:Carrier {label: 'AT&T'})
// MATCH (p)-[:SUPPORTS_CARRIER]->(c2:Carrier {label: 'T-Mobile'})
// MATCH (p)-[:SUPPORTS_CARRIER]->(c3:Carrier {label: 'Verizon'})
// RETURN p.asin, p.title, p.price ORDER BY p.price ASC;

// ── Dùng collect để đếm carriers mỗi sản phẩm hỗ trợ ────────
// MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c:Carrier)
// WITH p, COLLECT(c.label) AS carriers, COUNT(c) AS carrier_count
// WHERE carrier_count >= 3
// RETURN p.asin, p.title, carrier_count, carriers
// ORDER BY carrier_count DESC LIMIT 10;

// PROFILE
// MATCH (p:Product)-[:SUPPORTS_CARRIER]->(c1:Carrier {label: 'AT&T'})
// MATCH (p)-[:SUPPORTS_CARRIER]->(c2:Carrier {label: 'T-Mobile'})
// RETURN p.asin;
