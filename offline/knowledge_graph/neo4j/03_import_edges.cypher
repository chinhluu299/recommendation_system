// ============================================================
// 03_import_edges.cypher
// Import tất cả edges (relationships) từ CSV vào Neo4j.
//
// Yêu cầu:
//   - Đã chạy 02_import_nodes.cypher (nodes phải tồn tại trước)
//   - File CSV đã copy vào thư mục import:
//       Docker : /var/lib/neo4j/import/edges/
//       Local  : $NEO4J_HOME/import/edges/
//
// Usage:
//   cypher-shell -u neo4j -p <password> --file 03_import_edges.cypher
// ============================================================

// ── 1. MANUFACTURED_BY  (Product → Brand)  ────────────────────
// 7592 edges
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/manufactured_by.csv' AS row
MATCH (src:Product  { id: row.source })
MATCH (tgt:Brand    { id: row.target })
CREATE (src)-[:MANUFACTURED_BY]->(tgt);
:COMMIT

// ── 2. SOLD_BY  (Product → Store)  ───────────────────────────
// 7592 edges
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/sold_by.csv' AS row
MATCH (src:Product { id: row.source })
MATCH (tgt:Store   { id: row.target })
CREATE (src)-[:SOLD_BY]->(tgt);
:COMMIT

// ── 3. BELONGS_TO  (Product → Category)  ─────────────────────
// 7607 edges
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/belongs_to.csv' AS row
MATCH (src:Product  { id: row.source })
MATCH (tgt:Category { id: row.target })
CREATE (src)-[:BELONGS_TO]->(tgt);
:COMMIT

// ── 4. SUBCATEGORY_OF  (Category → Category)  ────────────────
// 1 edge
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/subcategory_of.csv' AS row
MATCH (src:Category { id: row.source })
MATCH (tgt:Category { id: row.target })
CREATE (src)-[:SUBCATEGORY_OF]->(tgt);
:COMMIT

// ── 5. HAS_FEATURE  (Product → Feature)  ─────────────────────
// 32051 edges
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/has_feature.csv' AS row
MATCH (src:Product { id: row.source })
MATCH (tgt:Feature { id: row.target })
CREATE (src)-[:HAS_FEATURE]->(tgt);
:COMMIT

// ── 6. HAS_SPEC  (Product → Spec)  ───────────────────────────
// 72400 edges
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/has_spec.csv' AS row
MATCH (src:Product { id: row.source })
MATCH (tgt:Spec    { id: row.target })
CREATE (src)-[:HAS_SPEC]->(tgt);
:COMMIT

// ── 7. SUPPORTS_CARRIER  (Product → Carrier)  ────────────────
// 2861 edges
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/supports_carrier.csv' AS row
MATCH (src:Product { id: row.source })
MATCH (tgt:Carrier { id: row.target })
CREATE (src)-[:SUPPORTS_CARRIER]->(tgt);
:COMMIT

// ── 8. USES_TECHNOLOGY  (Product → Technology)  ──────────────
// 25813 edges
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/uses_technology.csv' AS row
MATCH (src:Product    { id: row.source })
MATCH (tgt:Technology { id: row.target })
CREATE (src)-[:USES_TECHNOLOGY]->(tgt);
:COMMIT

// ── 9. INCLUDES_ACCESSORY  (Product → Accessory)  ────────────
// 10540 edges
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/includes_accessory.csv' AS row
MATCH (src:Product   { id: row.source })
MATCH (tgt:Accessory { id: row.target })
CREATE (src)-[:INCLUDES_ACCESSORY]->(tgt);
:COMMIT

// ── 10. BOUGHT_TOGETHER  (Product → Product)  ────────────────
// 0 edges hiện tại (data CSV không có trường này)
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/bought_together.csv' AS row
MATCH (src:Product { id: row.source })
MATCH (tgt:Product { id: row.target })
CREATE (src)-[:BOUGHT_TOGETHER]->(tgt);
:COMMIT

// ── 11. RATE  (User → Product)  ──────────────────────────────
// 203250 edges | rating: float (1.0 – 5.0)
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///edges/rate.csv' AS row
MATCH (src:User    { id: row.source })
MATCH (tgt:Product { id: row.target })
CREATE (src)-[:RATE { rating: toFloat(row.rating) }]->(tgt);
:COMMIT
