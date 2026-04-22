// ============================================================
// 02_import_nodes.cypher
// Import tất cả node types từ CSV vào Neo4j.
//
// Yêu cầu:
//   - Đã chạy 01_constraints.cypher
//   - File CSV đã copy vào thư mục import của Neo4j:
//       Docker : /var/lib/neo4j/import/nodes/
//       Local  : $NEO4J_HOME/import/nodes/
//
// Usage:
//   cypher-shell -u neo4j -p <password> --file 02_import_nodes.cypher
// ============================================================

// ── 1. Product ────────────────────────────────────────────────
// 7607 nodes | properties: asin, title, rating, price, specs...
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/products.csv' AS row
CREATE (:Product {
  id:                 row.id,
  asin:               row.asin,
  label:              row.label,
  title:              row.title,
  average_rating:     CASE WHEN row.average_rating <> '' THEN toFloat(row.average_rating)     ELSE null END,
  rating_number:      CASE WHEN row.rating_number  <> '' THEN toInteger(row.rating_number)    ELSE null END,
  price:              CASE WHEN row.price           <> '' THEN toFloat(row.price)              ELSE null END,
  color:              CASE WHEN row.color           <> '' THEN row.color                       ELSE null END,
  dimensions:         CASE WHEN row.dimensions      <> '' THEN row.dimensions                  ELSE null END,
  weight:             CASE WHEN row.weight          <> '' THEN row.weight                      ELSE null END,
  model_number:       CASE WHEN row.model_number    <> '' THEN row.model_number                ELSE null END,
  date_first_available: CASE WHEN row.date_first_available <> '' THEN row.date_first_available ELSE null END,
  screen_size:        CASE WHEN row.screen_size     <> '' THEN row.screen_size                 ELSE null END,
  display_resolution: CASE WHEN row.display_resolution <> '' THEN row.display_resolution       ELSE null END,
  form_factor:        CASE WHEN row.form_factor     <> '' THEN row.form_factor                 ELSE null END,
  operating_system:   CASE WHEN row.operating_system <> '' THEN row.operating_system           ELSE null END,
  display_technology: CASE WHEN row.display_technology <> '' THEN row.display_technology       ELSE null END,
  model_name:         CASE WHEN row.model_name      <> '' THEN row.model_name                  ELSE null END,
  ram_gb:             CASE WHEN row.ram_gb          <> '' THEN toFloat(row.ram_gb)             ELSE null END,
  storage_gb:         CASE WHEN row.storage_gb      <> '' THEN toFloat(row.storage_gb)         ELSE null END
});
:COMMIT

// ── 2. Brand ──────────────────────────────────────────────────
// 682 nodes
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/brands.csv' AS row
CREATE (:Brand { id: row.id, label: row.label });
:COMMIT

// ── 3. Store ──────────────────────────────────────────────────
// 565 nodes
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/stores.csv' AS row
CREATE (:Store { id: row.id, label: row.label });
:COMMIT

// ── 4. Category ───────────────────────────────────────────────
// 2 nodes
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/categories.csv' AS row
CREATE (:Category { id: row.id, label: row.label });
:COMMIT

// ── 5. Feature ────────────────────────────────────────────────
// 19225 nodes
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/features.csv' AS row
CREATE (:Feature { id: row.id, label: row.label });
:COMMIT

// ── 6. Spec ───────────────────────────────────────────────────
// 7509 nodes | numeric_value + unit cho phép so sánh >=/<= không cần parse chuỗi
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/specs.csv' AS row
CREATE (:Spec {
  id:            row.id,
  label:         row.label,
  key:           row.key,
  value:         row.value,
  spec_label:    CASE WHEN row.label         <> '' THEN row.label                          ELSE null END,
  numeric_value: CASE WHEN row.numeric_value <> '' THEN toFloat(row.numeric_value)         ELSE null END,
  unit:          CASE WHEN row.unit          <> '' THEN row.unit                           ELSE null END
});
:COMMIT

// ── 7. Carrier ────────────────────────────────────────────────
// 16 nodes
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/carriers.csv' AS row
CREATE (:Carrier { id: row.id, label: row.label });
:COMMIT

// ── 8. Technology ─────────────────────────────────────────────
// 128 nodes
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/technologies.csv' AS row
CREATE (:Technology { id: row.id, label: row.label });
:COMMIT

// ── 9. Accessory ──────────────────────────────────────────────
// 1016 nodes
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/accessories.csv' AS row
CREATE (:Accessory { id: row.id, label: row.label });
:COMMIT

// ── 10. User ──────────────────────────────────────────────────
// 186534 nodes
:BEGIN
LOAD CSV WITH HEADERS FROM 'file:///nodes/users.csv' AS row
CREATE (:User {
  id:      row.id,
  label:   row.label,
  user_id: row.user_id
});
:COMMIT
